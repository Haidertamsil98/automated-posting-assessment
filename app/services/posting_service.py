"""Fan out concurrently; one platform's failure never cancels the others."""

import asyncio
from datetime import timezone

import httpx

from app.platforms.base import Platform, PlatformError
from app.schemas import PlatformResult, PostingResponse


class PostingService:
    def __init__(self, platforms: list[Platform]):
        self.platforms = platforms

    async def _post_one(self, platform: Platform, message: str, cta_url: str) -> PlatformResult:
        try:
            published = await platform.publish(message, cta_url)
            if published.posted_at.tzinfo is None:
                raise ValueError("Timezone missing from posting result")
            posted_at = published.posted_at.astimezone(timezone.utc)
            return PlatformResult(
                platform=platform.name,
                status="success",
                posted_url=published.posted_url,
                public_access=published.public_access,
                date=posted_at.date(),
                time=posted_at.time().replace(microsecond=0),
                error=published.warning,
            )
        except PlatformError as exc:
            error = str(exc)
        except httpx.TimeoutException:
            error = "Request timed out; outcome unknown. Check platform before retrying"
        except httpx.RequestError:
            error = "Network request failed; outcome unknown. Check platform before retrying"
        except Exception:
            # Never expose exception values: HTTP URLs can contain webhook/bot tokens.
            error = "Unexpected platform response or adapter error; check platform before retrying"
        return PlatformResult(platform=platform.name, status="failed", error=error)

    async def post(self, message: str, cta_url: str) -> PostingResponse:
        results = await asyncio.gather(
            *(self._post_one(platform, message, cta_url) for platform in self.platforms)
        )
        return PostingResponse(
            success=any(result.status == "success" for result in results), results=results
        )
