"""Tests never load local credentials or make real platform requests."""

import pytest

from app.config import Settings

ENV_NAMES = (
    "MASTODON_BASE_URL",
    "MASTODON_ACCESS_TOKEN",
    "BLUESKY_PDS_URL",
    "BLUESKY_IDENTIFIER",
    "BLUESKY_APP_PASSWORD",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "DISCORD_WEBHOOK_URL",
    "DISCORD_GUILD_ID",
    "SLACK_BOT_TOKEN",
    "SLACK_CHANNEL_ID",
    "HTTP_TIMEOUT_SECONDS",
)


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.lower(), raising=False)


@pytest.fixture
def configured_settings():
    return Settings(
        _env_file=None,
        mastodon_base_url="https://mastodon.social",
        mastodon_access_token="fake-mastodon-secret",
        bluesky_pds_url="https://bsky.social",
        bluesky_identifier="assessment.bsky.social",
        bluesky_app_password="fake-bluesky-secret",
        telegram_bot_token="123456:fake-telegram-secret",
        telegram_chat_id="@assessment_channel",
        discord_webhook_url=("https://discord.com/api/webhooks/123456789/fake-discord-secret"),
        discord_guild_id="987654321",
        slack_bot_token="xoxb-fake-slack-secret",
        slack_channel_id="C123456",
    )
