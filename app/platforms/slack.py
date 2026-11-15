"""Slack Web API adapter; a permalink failure never hides a successful post."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import httpx

from app.platforms.base import Platform, PlatformError, PublishedPost, secret

_SLACK_ERRORS = {
    "invalid_auth": "Slack authentication failed.",
    "not_authed": "Slack authentication is missing.",
    "token_revoked": "Slack token has been revoked.",
    "account_inactive": "Slack account is inactive.",
    "missing_scope": "Slack token needs the chat:write scope.",
    "channel_not_found": "Slack channel was not found or the bot lacks access.",
    "not_in_channel": "Invite the Slack bot to the configured channel.",
    "is_archived": "Slack channel is archived.",
    "restricted_action": "Slack workspace policy prevents this action.",
    "ratelimited": "Slack rate limit reached; check the channel before retrying.",
}


class SlackPlatform(Platform):
    name = "Slack"

    async def publish(self, message: str, cta_url: str) -> PublishedPost:
        self.require(
            SLACK_BOT_TOKEN=self.settings.slack_bot_token,
            SLACK_CHANNEL_ID=self.settings.slack_channel_id,
        )
        headers = {"Authorization": f"Bearer {secret(self.settings.slack_bot_token)}"}
        # Escape Slack's control delimiters so submitted text cannot inject mentions.
        # Leave ordinary URL recognition enabled so the CTA stays clickable.
        plain_text = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        data = await self.request_json(
            "POST",
            "https://slack.com/api/chat.postMessage",
            headers=headers,
            json={
                "channel": self.settings.slack_channel_id,
                "text": plain_text,
                "mrkdwn": False,
                "link_names": False,
                "unfurl_links": False,
                "unfurl_media": False,
            },
        )
        if data.get("ok") is not True:
            error = data.get("error")
            description = "Slack rejected the message; check token and channel permissions."
            if isinstance(error, str):
                description = _SLACK_ERRORS.get(error, description)
            raise PlatformError(description)
        channel = data.get("channel")
        timestamp = data.get("ts")
        if not isinstance(channel, str) or not channel or not isinstance(timestamp, str):
            raise PlatformError(
                "Slack returned incomplete message metadata; check the channel before retrying."
            )
        try:
            seconds = Decimal(timestamp)
            if not seconds.is_finite():
                raise ValueError("Invalid timestamp")
            posted_at = datetime.fromtimestamp(float(seconds), tz=timezone.utc)
        except (ValueError, InvalidOperation, OverflowError, OSError) as exc:
            raise PlatformError(
                "Slack returned an invalid posting time; check the channel before retrying."
            ) from exc

        posted_url = None
        try:
            permalink = await self.request_json(
                "GET",
                "https://slack.com/api/chat.getPermalink",
                headers=headers,
                params={"channel": channel, "message_ts": timestamp},
            )
            candidate = permalink.get("permalink")
            if (
                permalink.get("ok") is True
                and isinstance(candidate, str)
                and candidate.startswith("https://")
            ):
                posted_url = candidate
        except (PlatformError, httpx.HTTPError):
            # Delivery already succeeded; retrying the post would create a duplicate.
            pass

        return PublishedPost(
            posted_url=posted_url,
            public_access=False,
            posted_at=posted_at,
            warning=None
            if posted_url
            else "Posted successfully; Slack permalink lookup failed. Check the channel; do not repost automatically.",
        )
