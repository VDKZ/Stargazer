import asyncio
import time

import httpx

from app.core.cache import TTLCache
from app.core.config import settings


class GitHubClient:
    def __init__(self, token: str, cache: TTLCache):
        self._client = httpx.AsyncClient(
            base_url=settings.github_api,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=settings.request_timeout,
        )
        self._cache = cache

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, url: str, params: dict) -> httpx.Response:
        """Single GET: serve fresh cache directly, otherwise revalidate via ETag."""
        cache_key = f"{url}?{params.get('page', 1)}"
        cached = self._cache.get(cache_key)

        # Fast path: still-fresh entry → serve it without any network call.
        if cached is not None:
            value, fresh = cached
            if fresh:
                return value["response"]

        headers = {}
        if cached is not None and cached[0].get("etag"):
            headers["If-None-Match"] = cached[0]["etag"]

        while True:
            resp = await self._client.get(url, params=params, headers=headers)

            # Rate limit exhausted → wait for the reset window.
            if resp.status_code in (403, 429) and resp.headers.get("X-RateLimit-Remaining") == "0":
                reset = int(resp.headers.get("X-RateLimit-Reset", 0))
                wait = max(reset - int(time.time()), 1)
                await asyncio.sleep(min(wait, 60))
                continue

            # Still valid on GitHub's side → refresh the TTL and serve from cache.
            if resp.status_code == 304 and cached is not None:
                self._cache.set(cache_key, cached[0])
                return cached[0]["response"]

            resp.raise_for_status()
            if etag := resp.headers.get("ETag"):
                self._cache.set(cache_key, {"etag": etag, "response": resp})
            return resp

    async def _paginate(self, url: str) -> list[dict]:
        results: list[dict] = []
        page = 1
        while True:
            resp = await self._get(url, {"per_page": 100, "page": page})
            batch = resp.json()
            if not batch:
                break
            results.extend(batch)
            if 'rel="next"' not in resp.headers.get("Link", ""):
                break
            page += 1
        return results

    async def get_stargazers(self, owner: str, repo: str) -> list[str]:
        data = await self._paginate(f"/repos/{owner}/{repo}/stargazers")
        return [u["login"] for u in data]

    async def get_starred_repos(self, user: str) -> list[str]:
        data = await self._paginate(f"/users/{user}/starred")
        return [r["full_name"] for r in data]