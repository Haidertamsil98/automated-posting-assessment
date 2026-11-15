"""Exercise real adapters with HTTP fixtures; never publish or read credentials.

Run from the project root: ``python -m scripts.offline_demo``.
The JSON output is simulated integration evidence, not proof of live posting.
"""

import json
from datetime import datetime, timezone

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def fixture_settings() -> Settings:
    """Override every setting so ambient credentials and .env are never used."""
    return Settings(
        _env_file=None,
        http_timeout_seconds=10,
        mastodon_base_url="https://mastodon.example.org",
        mastodon_access_token="offline-mastodon-token",
        bluesky_pds_url="https://bluesky.example.org",
        bluesky_identifier="offline.example.org",
        bluesky_app_password="offline-app-password",
        telegram_bot_token="000000:offline-token",
        telegram_chat_id="@offline_fixture_channel",
        discord_webhook_url="https://discord.com/api/webhooks/111111111111111111/offline-token",
        discord_guild_id="222222222222222222",
        slack_bot_token="offline-slack-token",
        slack_channel_id="C_OFFLINE_FIXTURE",
    )


def fixture_transport(*, fail_mastodon: bool = False) -> httpx.MockTransport:
    """Handle every outbound request locally; unknown requests fail closed."""

    def handler(request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if host == "mastodon.example.org" and path == "/api/v1/statuses":
            if fail_mastodon:
                return httpx.Response(401, json={"error": "offline fixture rejection"})
            return httpx.Response(
                200,
                json={
                    "id": "fixture-post-1",
                    "url": "https://mastodon.example.org/@offline/fixture-post-1",
                    "created_at": "2026-11-15T10:30:00Z",
                    "visibility": "public",
                },
            )
        if host == "bluesky.example.org":
            if path == "/xrpc/com.atproto.server.createSession":
                return httpx.Response(
                    200,
                    json={"did": "did:plc:offlinefixture", "accessJwt": "offline-session-token"},
                )
            if path == "/xrpc/com.atproto.repo.createRecord":
                return httpx.Response(
                    200,
                    json={
                        "uri": "at://did:plc:offlinefixture/app.bsky.feed.post/fixture-post-1",
                        "cid": "offline-fixture-cid",
                    },
                )
        if host == "api.telegram.org" and path == "/bot000000:offline-token/sendMessage":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {
                        "message_id": 101,
                        "date": 1794738600,
                        "chat": {
                            "id": -1001234567890,
                            "type": "channel",
                            "username": "offline_fixture_channel",
                        },
                    },
                },
            )
        if host == "discord.com" and path == "/api/webhooks/111111111111111111/offline-token":
            return httpx.Response(
                200,
                json={
                    "id": "444444444444444444",
                    "channel_id": "333333333333333333",
                    "timestamp": "2026-11-15T10:30:00+00:00",
                },
            )
        if host == "slack.com":
            if path == "/api/chat.postMessage":
                return httpx.Response(
                    200,
                    json={"ok": True, "channel": "C_OFFLINE_FIXTURE", "ts": "1794738600.000001"},
                )
            if path == "/api/chat.getPermalink":
                return httpx.Response(
                    200,
                    json={
                        "ok": True,
                        "permalink": "https://offline-fixture.slack.com/archives/C_OFFLINE_FIXTURE/p1794738600000001",
                    },
                )
        raise AssertionError(f"No offline fixture for {request.method} {host}{path}")

    return httpx.MockTransport(handler)


def run_scenario(name: str, message: str, *, fail_mastodon: bool = False) -> dict:
    payload = {"message": message}
    application = create_app(
        fixture_settings(), transport=fixture_transport(fail_mastodon=fail_mastodon)
    )
    with TestClient(application) as client:
        response = client.post("/posting", json=payload)
    return {
        "name": name,
        "request": payload,
        "http_status": response.status_code,
        "response": response.json(),
    }


def main() -> None:
    message = "Explore our new platform: https://example.com"
    scenarios = [
        run_scenario("all_five_succeed_simulated", message),
        run_scenario("mastodon_fails_four_others_succeed_simulated", message, fail_mastodon=True),
        run_scenario(
            "validation_rejects_two_links", "Visit https://example.com and https://example.org"
        ),
    ]
    assert scenarios[0]["http_status"] == 200
    assert all(result["status"] == "success" for result in scenarios[0]["response"]["results"])
    assert len(scenarios[0]["response"]["results"]) == 5
    partial = scenarios[1]["response"]["results"]
    assert scenarios[1]["http_status"] == 200
    assert partial[0]["platform"] == "Mastodon" and partial[0]["status"] == "failed"
    assert sum(result["status"] == "success" for result in partial) == 4
    assert scenarios[2]["http_status"] == 422
    print(
        json.dumps(
            {
                "evidence_type": "OFFLINE SIMULATION: no live posts; URLs are fixtures",
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "scenarios": scenarios,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
