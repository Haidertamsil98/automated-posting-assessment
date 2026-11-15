"""Environment-backed settings. Credentials never have source-code defaults."""

import re

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    http_timeout_seconds: float = Field(default=10, gt=0, le=60)
    mastodon_base_url: str = "https://mastodon.social"
    mastodon_access_token: SecretStr | None = None
    bluesky_pds_url: str = "https://bsky.social"
    bluesky_identifier: str | None = None
    bluesky_app_password: SecretStr | None = None
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None
    discord_webhook_url: SecretStr | None = None
    discord_guild_id: str | None = None
    slack_bot_token: SecretStr | None = None
    slack_channel_id: str | None = None

    @field_validator("mastodon_base_url", "bluesky_pds_url")
    @classmethod
    def validate_origin(cls, value: str) -> str:
        from urllib.parse import urlsplit

        origin = urlsplit(value)
        if (
            origin.scheme != "https"
            or not origin.hostname
            or origin.username is not None
            or origin.password is not None
            or origin.path not in ("", "/")
            or origin.query
            or origin.fragment
        ):
            raise ValueError("Platform base URL must be an HTTPS origin")
        return value.rstrip("/")

    @field_validator("discord_webhook_url")
    @classmethod
    def validate_webhook(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None or not value.get_secret_value().strip():
            return None
        if not re.fullmatch(
            r"https://discord\.com/api(?:/v\d+)?/webhooks/\d+/[A-Za-z0-9_.-]+",
            value.get_secret_value(),
        ):
            raise ValueError("Discord webhook must be an official HTTPS webhook URL")
        return value
