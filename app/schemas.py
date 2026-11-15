"""Request validation and the public response contract."""

import ipaddress
import re
from datetime import date as Date
from datetime import time as Time
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, field_validator

HTTP_URL = TypeAdapter(HttpUrl)
# A link is an explicitly schemed URL or a www. token. Bare domains are rejected
# separately so a second, schemeless CTA cannot silently pass the one-link rule.
URL_TOKEN = re.compile(r"(?:[a-z][a-z0-9+.-]*://|www\.)[^\s<>\"'`]*", re.I)
URL_SCHEME = re.compile(r"[a-z][a-z0-9+.-]*://", re.I)
BARE_DOMAIN = re.compile(r"(?<![\w@])(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}\b", re.I)


def extract_cta(message: str) -> str:
    matches = list(URL_TOKEN.finditer(message))
    if len(matches) != 1 or len(URL_SCHEME.findall(message)) != 1:
        raise ValueError("Message must contain exactly one HTTP(S) CTA link")
    match = matches[0]
    url = match.group().rstrip(".,;!?")
    # Strip only unmatched closing parentheses, preserving balanced URL paths.
    while url.endswith(")") and url.count(")") > url.count("("):
        url = url[:-1]
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("CTA link must start with http:// or https://")
    if re.search(r"[\x00-\x20\x7f\\]", url) or re.search(r"%(?![0-9a-f]{2})", url, re.I):
        raise ValueError("CTA link contains invalid characters or escapes")
    try:
        parsed = urlsplit(url)
        # HttpUrl normalizes malformed inputs such as https:///example.com.
        # Validate the submitted authority before allowing that normalization.
        if not parsed.netloc or not parsed.hostname:
            raise ValueError("CTA link must include a hostname after ://")
        validated = HTTP_URL.validate_python(url)
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("User information is not allowed in CTA links")
        if not validated.host:
            raise ValueError("CTA link must have a hostname")
        hostname = validated.host.strip("[]")
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            labels = hostname.rstrip(".").split(".")
            if len(hostname) > 253 or not all(
                re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label, re.I)
                for label in labels
            ):
                raise ValueError("CTA link has an invalid hostname") from None
    except ValueError:
        raise ValueError("CTA link must be a valid HTTP(S) URL without credentials") from None
    remainder = message[: match.start()] + message[match.end() :]
    if BARE_DOMAIN.search(remainder) or re.search(r"\b(?:mailto|tel|data):", remainder, re.I):
        raise ValueError("Use exactly one CTA link; additional links are not allowed")
    return url


class PostingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        strict=True,
        min_length=1,
        max_length=200,
        description="At most 200 Unicode characters, including exactly one HTTP(S) CTA link.",
        examples=["Explore our latest platform: https://example.com"],
    )

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message must not be blank")
        if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
            raise ValueError("Message contains unsupported control characters")
        extract_cta(value)
        return value


class PlatformResult(BaseModel):
    platform: str
    status: Literal["success", "failed"]
    posted_url: str | None = None
    public_access: bool = False
    date: Date | None = None
    time: Time | None = Field(default=None, description="Posting time in UTC")
    error: str | None = None


class PostingResponse(BaseModel):
    success: bool = Field(description="True when at least one platform confirmed publication")
    results: list[PlatformResult]
