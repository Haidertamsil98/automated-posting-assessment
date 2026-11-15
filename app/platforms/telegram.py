"""Telegram Bot API adapter for channels, groups, and direct chats."""

import re
from datetime import datetime, timezone

from app.platforms.base import Platform, PlatformError, PublishedPost, secret


class TelegramPlatform(Platform):
    name = "Telegram"

    async def publish(self, message: str, cta_url: str) -> PublishedPost:
        self.require(
            TELEGRAM_BOT_TOKEN=self.settings.telegram_bot_token,
            TELEGRAM_CHAT_ID=self.settings.telegram_chat_id,
        )
        token = secret(self.settings.telegram_bot_token)
        data = await self.request_json(
            "POST",
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": self.settings.telegram_chat_id,
                "text": message,
                "link_preview_options": {"is_disabled": True},
            },
        )
        if data.get("ok") is not True:
            raise PlatformError("Telegram rejected the message; check bot permissions and chat ID.")
        result = data.get("result")
        if not isinstance(result, dict):
            raise PlatformError(
                "Telegram returned an invalid message response; check the chat before retrying."
            )
        chat = result.get("chat")
        message_id = result.get("message_id")
        timestamp = result.get("date")
        if (
            not isinstance(chat, dict)
            or type(message_id) is not int
            or message_id <= 0
            or type(timestamp) is not int
        ):
            raise PlatformError(
                "Telegram returned incomplete message metadata; check the chat before retrying."
            )
        try:
            posted_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (ValueError, OverflowError, OSError) as exc:
            raise PlatformError(
                "Telegram returned an invalid posting time; check the chat before retrying."
            ) from exc

        username = chat.get("username")
        posted_url = None
        public_access = False
        if (
            chat.get("type") in {"channel", "supergroup"}
            and isinstance(username, str)
            and re.fullmatch(r"[A-Za-z0-9_]+", username)
        ):
            posted_url = f"https://t.me/{username}/{message_id}"
            public_access = chat.get("type") == "channel"
        else:
            # Telegram exposes member-only permalinks for private channels/supergroups.
            chat_id = str(chat.get("id", ""))
            if chat.get("type") in {"channel", "supergroup"} and re.fullmatch(r"-100\d+", chat_id):
                posted_url = f"https://t.me/c/{chat_id[4:]}/{message_id}"

        return PublishedPost(
            posted_url=posted_url,
            public_access=public_access,
            posted_at=posted_at,
            warning=None
            if posted_url
            else "Posted successfully; Telegram provides no permalink for this chat type.",
        )
