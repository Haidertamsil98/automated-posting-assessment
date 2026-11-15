"""HTTP-level integration tests with simulated third-party API responses."""

import asyncio
import json
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.posting_service import PostingService

MESSAGE = "Grow your business. https://example.com"
POSTED_AT = datetime(2026, 11, 15, 10, 30, tzinfo=timezone.utc)
EPOCH = int(POSTED_AT.timestamp())
NAMES = ["Mastodon", "Bluesky", "Telegram", "Discord", "Slack"]


def success_reply(request):
    """Representative API responses; the identifiers are deliberately fictional."""
    path = request.url.path
    if path == "/api/v1/statuses":
        return httpx.Response(
            200,
            json={
                "id": "111",
                "url": "https://mastodon.social/@assessment/111",
                "created_at": "2026-11-15T10:30:00Z",
                "visibility": "public",
            },
        )
    if path.endswith("com.atproto.server.createSession"):
        return httpx.Response(
            200,
            json={
                "did": "did:plc:assessment",
                "accessJwt": "fake-access-jwt",
                "handle": "assessment.bsky.social",
            },
        )
    if path.endswith("com.atproto.repo.createRecord"):
        return httpx.Response(
            200,
            json={
                "uri": "at://did:plc:assessment/app.bsky.feed.post/fake-record",
                "cid": "fake-cid",
            },
        )
    if path.endswith("/sendMessage"):
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": 42,
                    "date": EPOCH,
                    "chat": {
                        "id": -1001234567890,
                        "type": "channel",
                        "username": "assessment_channel",
                    },
                },
            },
        )
    if "/webhooks/" in path:
        return httpx.Response(
            200,
            json={
                "id": "222",
                "channel_id": "333",
                "guild_id": "987654321",
                "timestamp": "2026-11-15T10:30:00Z",
            },
        )
    if path == "/api/chat.postMessage":
        return httpx.Response(
            200,
            json={
                "ok": True,
                "channel": "C123456",
                "ts": f"{EPOCH}.000001",
                "message": {"ts": f"{EPOCH}.000001"},
            },
        )
    if path == "/api/chat.getPermalink":
        return httpx.Response(
            200,
            json={
                "ok": True,
                "permalink": f"https://assessment.slack.com/archives/C123456/p{EPOCH}000001",
            },
        )
    raise AssertionError(f"Unexpected API endpoint: {request.url.host}{path}")


def client_for(settings, handler):
    return TestClient(create_app(settings, transport=httpx.MockTransport(handler)))


def by_name(response):
    return {item["platform"]: item for item in response.json()["results"]}


def test_all_five_platforms_publish_and_return_actual_identifiers(configured_settings):
    requests = []

    def handler(request):
        requests.append(request)
        return success_reply(request)

    with client_for(configured_settings, handler) as client:
        response = client.post("/posting", json={"message": MESSAGE})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert [result["platform"] for result in body["results"]] == NAMES
    assert all(result["status"] == "success" for result in body["results"])
    assert all(result["posted_url"] for result in body["results"])
    assert all(result["error"] is None for result in body["results"])
    assert all(result["date"] and result["time"] for result in body["results"])
    assert len(requests) == 7  # Each create call is sent once; no implicit retries.

    results = by_name(response)
    assert results["Mastodon"]["posted_url"].endswith("/111")
    assert results["Telegram"]["posted_url"] == "https://t.me/assessment_channel/42"
    assert results["Discord"]["posted_url"] == "https://discord.com/channels/987654321/333/222"
    assert results["Slack"]["posted_url"].endswith(f"p{EPOCH}000001")
    assert results["Mastodon"]["public_access"] is True
    assert results["Bluesky"]["public_access"] is True
    assert results["Telegram"]["public_access"] is True
    assert results["Discord"]["public_access"] is False
    assert results["Slack"]["public_access"] is False
    assert results["Telegram"]["date"] == "2026-11-15"
    assert results["Telegram"]["time"].startswith("10:30:00")

    discord = next(r for r in requests if "/webhooks/" in r.url.path)
    assert discord.url.params["wait"] == "true"
    assert json.loads(discord.content)["allowed_mentions"] == {"parse": []}
    assert json.loads(discord.content)["content"] == MESSAGE
    mastodon = next(r for r in requests if r.url.path == "/api/v1/statuses")
    assert mastodon.headers["authorization"] == "Bearer fake-mastodon-secret"
    assert b"public" in mastodon.content
    telegram = next(r for r in requests if r.url.path.endswith("/sendMessage"))
    assert json.loads(telegram.content)["text"] == MESSAGE
    assert "parse_mode" not in json.loads(telegram.content)


def test_bluesky_uses_utf8_byte_offsets_for_clickable_cta(configured_settings):
    message = "Grüße 🌍 https://example.com/path?q=1"
    posts = []

    def handler(request):
        if request.url.path.endswith("com.atproto.repo.createRecord"):
            posts.append(json.loads(request.content))
        return success_reply(request)

    with client_for(configured_settings, handler) as client:
        response = client.post("/posting", json={"message": message})
    assert response.status_code == 200
    record = posts[0]["record"]
    facet = record["facets"][0]
    assert record["text"] == message
    assert posts[0]["repo"] == "did:plc:assessment"
    assert facet["index"]["byteStart"] == len("Grüße 🌍 ".encode("utf-8"))
    assert facet["index"]["byteEnd"] == len(message.encode("utf-8"))
    assert facet["features"][0]["uri"] == "https://example.com/path?q=1"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": ""},
        {"message": "   "},
        {"message": 123},
        {"message": None},
        {"message": [MESSAGE]},
        {"message": "There is no CTA here"},
        {"message": "https://example.com https://example.org"},
        {"message": "https://example.com https://example.com"},
        {"message": "Visit https://"},
        {"message": "Visit https:///missing-host"},
        {"message": "Visit https:////example.com"},
        {"message": "https://example.com,https://other.org"},
        {"message": "https://example.com)https://other.org"},
        {"message": "Go https://example.com https://"},
        {"message": "Go https://exa_mple.com"},
        {"message": "Go https://exa!mple.com"},
        {"message": "Go https://example..com"},
        {"message": "Go https://-example.com"},
        {"message": "Go https://example.com:bad"},
        {"message": "Visit ftp://example.com"},
        {"message": "Visit https://user:password@example.com"},
        {"message": MESSAGE, "platforms": ["Mastodon"]},
        {"message": "a" * 182 + "https://example.com"},
    ],
)
def test_invalid_input_is_422_before_any_platform_request(payload):
    def no_network(request):
        raise AssertionError("Invalid messages must never reach an upstream API")

    with client_for(Settings(_env_file=None), no_network) as client:
        response = client.post("/posting", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]


@pytest.mark.parametrize(
    "message",
    [
        "Explore https://bücher.de/angebote",
        "Explore https://example.com/search?q=business&lang=en#signup",
        "Explore https://example.com/path_(details).",
        "Explore https://example.com/?next=https%3A%2F%2Fexample.org",
    ],
)
def test_valid_url_forms_are_accepted(configured_settings, message):
    with client_for(configured_settings, success_reply) as client:
        response = client.post("/posting", json={"message": message})
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_exactly_200_unicode_code_points_are_accepted(configured_settings):
    link = "https://example.com"
    message = "🌍" * (200 - len(link) - 1) + " " + link
    assert len(message) == 200
    with client_for(configured_settings, success_reply) as client:
        response = client.post("/posting", json={"message": message})
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_201_unicode_code_points_are_rejected():
    link = "https://example.com"
    message = "🌍" * (201 - len(link) - 1) + " " + link
    with client_for(Settings(_env_file=None), success_reply) as client:
        response = client.post("/posting", json={"message": message})
    assert response.status_code == 422


def test_missing_credentials_return_five_real_failures_without_network():
    def no_network(request):
        raise AssertionError("No platform should be contacted without credentials")

    with client_for(Settings(_env_file=None), no_network) as client:
        response = client.post("/posting", json={"message": MESSAGE})
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert [r["platform"] for r in response.json()["results"]] == NAMES
    for result in response.json()["results"]:
        assert result["status"] == "failed"
        assert result["posted_url"] is None
        assert result["public_access"] is False
        assert result["date"] is None and result["time"] is None
        assert result["error"]


@pytest.mark.parametrize(
    "failure", ["unauthorized", "rate_limit", "timeout", "bad_json", "bad_shape"]
)
def test_one_failure_does_not_stop_remaining_platforms(configured_settings, failure):
    def handler(request):
        if request.url.path == "/api/v1/statuses":
            if failure == "timeout":
                raise httpx.ReadTimeout("fake-mastodon-secret", request=request)
            if failure == "unauthorized":
                return httpx.Response(401, json={"error": "fake-mastodon-secret"})
            if failure == "rate_limit":
                return httpx.Response(
                    429, json={"error": "fake-mastodon-secret"}, headers={"Retry-After": "60"}
                )
            if failure == "bad_json":
                return httpx.Response(200, text="fake-mastodon-secret")
            return httpx.Response(200, json=[])
        return success_reply(request)

    with client_for(configured_settings, handler) as client:
        response = client.post("/posting", json={"message": MESSAGE})
    assert response.status_code == 200
    assert response.json()["success"] is True
    results = by_name(response)
    assert results["Mastodon"]["status"] == "failed"
    assert results["Mastodon"]["posted_url"] is None
    assert results["Mastodon"]["date"] is None
    assert all(results[name]["status"] == "success" for name in NAMES[1:])
    assert "fake-mastodon-secret" not in response.text


def test_slack_semantic_error_in_http_200_is_a_failure(configured_settings):
    def handler(request):
        if request.url.path == "/api/chat.postMessage":
            return httpx.Response(200, json={"ok": False, "error": "invalid_auth"})
        return success_reply(request)

    with client_for(configured_settings, handler) as client:
        response = client.post("/posting", json={"message": MESSAGE})
    results = by_name(response)
    assert results["Slack"]["status"] == "failed"
    assert results["Slack"]["posted_url"] is None
    assert all(results[name]["status"] == "success" for name in NAMES[:-1])


@pytest.mark.parametrize(
    "platform,path",
    [
        ("Mastodon", "/api/v1/statuses"),
        ("Bluesky", "/xrpc/com.atproto.repo.createRecord"),
        ("Telegram", "/bot123456:fake-telegram-secret/sendMessage"),
        ("Discord", "/api/webhooks/123456789/fake-discord-secret"),
        ("Slack", "/api/chat.postMessage"),
    ],
)
def test_missing_success_metadata_is_not_fabricated(configured_settings, platform, path):
    def handler(request):
        if request.url.path == path:
            return httpx.Response(200, json={"ok": True})
        return success_reply(request)

    with client_for(configured_settings, handler) as client:
        response = client.post("/posting", json={"message": MESSAGE})
    result = by_name(response)[platform]
    assert result["status"] == "failed"
    assert result["posted_url"] is None
    assert result["date"] is None
    assert result["error"]


def test_telegram_semantic_error_is_redacted(configured_settings):
    def handler(request):
        if request.url.path.endswith("/sendMessage"):
            return httpx.Response(
                200,
                json={
                    "ok": False,
                    "error_code": 403,
                    "description": "fake-telegram-secret echoed by upstream",
                },
            )
        return success_reply(request)

    with client_for(configured_settings, handler) as client:
        response = client.post("/posting", json={"message": MESSAGE})
    assert by_name(response)["Telegram"]["status"] == "failed"
    assert "fake-telegram-secret" not in response.text


def test_slack_permalink_failure_preserves_confirmed_post(configured_settings):
    def handler(request):
        if request.url.path == "/api/chat.getPermalink":
            return httpx.Response(200, json={"ok": False, "error": "channel_not_found"})
        return success_reply(request)

    with client_for(configured_settings, handler) as client:
        response = client.post("/posting", json={"message": MESSAGE})
    result = by_name(response)["Slack"]
    assert result["status"] == "success"
    assert result["posted_url"] is None
    assert result["date"] == "2026-11-15"
    assert result["error"]


def test_telegram_private_chat_is_not_marked_public(configured_settings):
    def handler(request):
        if request.url.path.endswith("/sendMessage"):
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {
                        "message_id": 42,
                        "date": EPOCH,
                        "chat": {"id": 123, "type": "private", "username": "not_a_public_channel"},
                    },
                },
            )
        return success_reply(request)

    with client_for(configured_settings, handler) as client:
        response = client.post("/posting", json={"message": MESSAGE})
    result = by_name(response)["Telegram"]
    assert result["status"] == "success"
    assert result["public_access"] is False
    assert result["posted_url"] != "https://t.me/not_a_public_channel/42"


def test_unexpected_adapter_exception_is_isolated_and_redacted():
    class BrokenPlatform:
        name = "Broken"

        async def publish(self, message, cta_url):
            raise RuntimeError("private-token-do-not-leak")

    result = asyncio.run(PostingService([BrokenPlatform()]).post(MESSAGE, "https://example.com"))
    body = result.model_dump()
    assert body["success"] is False
    assert body["results"][0]["status"] == "failed"
    assert "private-token-do-not-leak" not in json.dumps(body)


def test_openapi_documents_posting_request_and_response():
    with client_for(Settings(_env_file=None), success_reply) as client:
        response = client.get("/openapi.json")
    operation = response.json()["paths"]["/posting"]["post"]
    assert "requestBody" in operation
    assert "200" in operation["responses"]
    assert "422" in operation["responses"]
