"""Shared transport helpers and the publishing adapter contract."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from pydantic import SecretStr

from app.config import Settings


class PlatformError(Exception):
    """A controlled, credential-free message safe to return to the caller."""


def secret(value: SecretStr | None) -> str:
    return value.get_secret_value() if value else ""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Platform timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class PublishedPost:
    posted_url: str | None
    public_access: bool
    posted_at: datetime
    warning: str | None = None


class Platform(ABC):
    name: str

    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client

    def require(self, **values: object) -> None:
        missing = [
            name
            for name, value in values.items()
            if value is None
            or not (secret(value) if isinstance(value, SecretStr) else str(value)).strip()
        ]
        if missing:
            raise PlatformError("Not configured: " + ", ".join(missing))

    async def request_json(self, method: str, url: str, **kwargs) -> dict:
        response = await self.client.request(method, url, **kwargs)
        # Do not forward bodies or exception strings: they can echo API credentials.
        if response.status_code in (401, 403):
            raise PlatformError("Authentication failed or posting permission denied")
        if response.status_code == 429:
            raise PlatformError("Rate limit reached (HTTP 429); retry later")
        if not response.is_success:
            raise PlatformError(f"Platform returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError:
            raise PlatformError(
                "Platform returned invalid JSON; posting outcome may be unknown"
            ) from None
        if not isinstance(payload, dict):
            raise PlatformError("Platform returned an unexpected response object")
        return payload

    @abstractmethod
    async def publish(self, message: str, cta_url: str) -> PublishedPost:
        """Publish once; return confirmed metadata or raise a controlled failure."""
