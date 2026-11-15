"""Publish public statuses using the authenticated Mastodon REST API."""

from urllib.parse import urlsplit

from app.platforms.base import Platform, PlatformError, PublishedPost, parse_timestamp, secret


class MastodonPlatform(Platform):
    name = "Mastodon"

    async def publish(self, message: str, cta_url: str) -> PublishedPost:
        self.require(MASTODON_ACCESS_TOKEN=self.settings.mastodon_access_token)
        data = await self.request_json(
            "POST",
            f"{self.settings.mastodon_base_url.rstrip('/')}/api/v1/statuses",
            headers={"Authorization": f"Bearer {secret(self.settings.mastodon_access_token)}"},
            json={"status": message, "visibility": "public"},
        )
        posted_url = data.get("url")
        created_at = data.get("created_at")
        visibility = data.get("visibility")
        if not isinstance(posted_url, str) or not isinstance(created_at, str):
            raise PlatformError(
                "Invalid Mastodon response; a post may have been created. Check before retrying."
            )
        try:
            parsed_url = urlsplit(posted_url)
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
                raise ValueError
            posted_at = parse_timestamp(created_at)
        except (TypeError, ValueError):
            raise PlatformError(
                "Invalid Mastodon post metadata; a post may have been created. Check before retrying."
            ) from None
        if visibility not in {"public", "unlisted", "private", "direct"}:
            raise PlatformError(
                "Missing Mastodon visibility; a post may have been created. Check before retrying."
            )
        return PublishedPost(
            posted_url=posted_url,
            public_access=visibility in {"public", "unlisted"},
            posted_at=posted_at,
        )
