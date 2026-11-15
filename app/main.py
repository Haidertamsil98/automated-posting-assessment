"""Run with uvicorn app.main:app --host 0.0.0.0 --port 4000."""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request

from app.config import Settings
from app.platforms.bluesky import BlueskyPlatform
from app.platforms.discord import DiscordPlatform
from app.platforms.mastodon import MastodonPlatform
from app.platforms.slack import SlackPlatform
from app.platforms.telegram import TelegramPlatform
from app.schemas import PostingRequest, PostingResponse, extract_cta
from app.services.posting_service import PostingService


def create_app(
    settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        config = settings if settings is not None else Settings()
        # HTTPX info logs include request URLs; Telegram and Discord URLs carry secrets.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        async with httpx.AsyncClient(
            timeout=config.http_timeout_seconds,
            follow_redirects=False,
            transport=transport,
            headers={"User-Agent": "automated-posting-assessment/1.0"},
        ) as client:
            application.state.posting_service = PostingService(
                [
                    adapter(config, client)
                    for adapter in (
                        MastodonPlatform,
                        BlueskyPlatform,
                        TelegramPlatform,
                        DiscordPlatform,
                        SlackPlatform,
                    )
                ]
            )
            yield

    application = FastAPI(
        title="Automated Multi-Platform Posting",
        version="1.0.0",
        description="Publish one validated message to five internally selected platforms.",
        lifespan=lifespan,
    )

    @application.post("/posting", response_model=PostingResponse, tags=["posting"])
    async def posting(payload: PostingRequest, request: Request) -> PostingResponse:
        """Return all five outcomes, even when some or all platforms fail.

        HTTP 422 indicates invalid input. HTTP 200 means the request was processed;
        inspect each result and the aggregate success flag for delivery outcomes.
        All response dates/times are UTC. No retry is performed automatically.
        """
        return await request.app.state.posting_service.post(
            payload.message, extract_cta(payload.message)
        )

    return application


app = create_app()
