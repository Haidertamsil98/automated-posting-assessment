"""Discord incoming-webhook adapter with explicit delivery confirmation."""

import re

from app.platforms.base import Platform, PlatformError, PublishedPost, parse_timestamp, secret


class DiscordPlatform(Platform):
    name = "Discord"

    async def publish(self, message: str, cta_url: str) -> PublishedPost:
        self.require(
            DISCORD_WEBHOOK_URL=self.settings.discord_webhook_url,
            DISCORD_GUILD_ID=self.settings.discord_guild_id,
        )
        guild_id = self.settings.discord_guild_id
        if not isinstance(guild_id, str) or not re.fullmatch(r"\d+", guild_id):
            raise PlatformError("DISCORD_GUILD_ID must be the numeric server ID.")
        data = await self.request_json(
            "POST",
            secret(self.settings.discord_webhook_url),
            params={"wait": "true"},
            json={"content": message, "allowed_mentions": {"parse": []}},
        )
        message_id = data.get("id")
        channel_id = data.get("channel_id")
        timestamp = data.get("timestamp")
        if not all(
            isinstance(value, str) and re.fullmatch(r"\d+", value)
            for value in (message_id, channel_id)
        ):
            raise PlatformError(
                "Discord returned incomplete message metadata; check the channel before retrying."
            )
        if not isinstance(timestamp, str):
            raise PlatformError(
                "Discord returned no posting time; check the channel before retrying."
            )
        return PublishedPost(
            posted_url=f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}",
            public_access=False,
            posted_at=parse_timestamp(timestamp),
        )
