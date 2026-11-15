"""Publish Bluesky records with a clickable CTA rich-text facet."""

import re
from urllib.parse import quote

from app.platforms.base import Platform, PlatformError, PublishedPost, secret, utc_now


class BlueskyPlatform(Platform):
    name = "Bluesky"

    async def publish(self, message: str, cta_url: str) -> PublishedPost:
        self.require(
            BLUESKY_IDENTIFIER=self.settings.bluesky_identifier,
            BLUESKY_APP_PASSWORD=self.settings.bluesky_app_password,
        )
        pds_url = self.settings.bluesky_pds_url.rstrip("/")
        session = await self.request_json(
            "POST",
            f"{pds_url}/xrpc/com.atproto.server.createSession",
            json={
                "identifier": self.settings.bluesky_identifier,
                "password": secret(self.settings.bluesky_app_password),
            },
        )
        did = session.get("did")
        access_token = session.get("accessJwt")
        if (
            not isinstance(did, str)
            or not re.fullmatch(r"did:[a-z0-9]+:[A-Za-z0-9._:%-]+", did)
            or not isinstance(access_token, str)
            or not access_token
        ):
            raise PlatformError("Invalid Bluesky authentication response.")

        # Facet offsets are UTF-8 bytes, rather than Python character offsets.
        message_bytes = message.encode("utf-8")
        cta_bytes = cta_url.encode("utf-8")
        byte_start = message_bytes.find(cta_bytes)
        if byte_start < 0:
            raise PlatformError("The CTA link was not found in the message.")
        posted_at = utc_now()
        data = await self.request_json(
            "POST",
            f"{pds_url}/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "repo": did,
                "collection": "app.bsky.feed.post",
                "record": {
                    "$type": "app.bsky.feed.post",
                    "text": message,
                    "createdAt": posted_at.isoformat().replace("+00:00", "Z"),
                    "facets": [
                        {
                            "index": {
                                "byteStart": byte_start,
                                "byteEnd": byte_start + len(cta_bytes),
                            },
                            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": cta_url}],
                        }
                    ],
                },
            },
        )
        uri = data.get("uri")
        prefix = f"at://{did}/app.bsky.feed.post/"
        if not isinstance(uri, str) or not uri.startswith(prefix):
            raise PlatformError(
                "Invalid Bluesky record response; a post may have been created. Check before retrying."
            )
        record_key = uri[len(prefix) :]
        if not re.fullmatch(r"[A-Za-z0-9._~:-]{1,512}", record_key) or record_key in {".", ".."}:
            raise PlatformError(
                "Invalid Bluesky record key; a post may have been created. Check before retrying."
            )
        return PublishedPost(
            posted_url=f"https://bsky.app/profile/{quote(did, safe=':')}/post/{quote(record_key, safe='')}",
            public_access=True,
            posted_at=posted_at,
        )
