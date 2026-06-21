import httpx
import respx

from app.core.cache import TTLCache
from app.services.github import GitHubClient

BASE = "https://api.github.com"


async def test_paginates_across_pages():
    cache = TTLCache(ttl_seconds=3600)
    client = GitHubClient("tok", cache)
    with respx.mock(base_url=BASE) as mock:
        mock.get("/repos/owner/repo/stargazers").side_effect = [
            httpx.Response(
                200,
                json=[{"login": "alice"}],
                headers={"Link": '<https://api.github.com/x?page=2>; rel="next"'},
            ),
            httpx.Response(200, json=[{"login": "bob"}]),
        ]
        try:
            users = await client.get_stargazers("owner", "repo")
        finally:
            await client.aclose()

    assert users == ["alice", "bob"]


async def test_fresh_cache_avoids_second_network_call():
    cache = TTLCache(ttl_seconds=3600)
    client = GitHubClient("tok", cache)
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/users/alice/starred").mock(
            return_value=httpx.Response(
                200, json=[{"full_name": "owner/A"}], headers={"ETag": "v1"}
            )
        )
        try:
            first = await client.get_starred_repos("alice")
            second = await client.get_starred_repos("alice")
        finally:
            await client.aclose()

    assert first == second == ["owner/A"]
    # The 2nd call is served from the fresh cache: no network round-trip.
    assert route.call_count == 1


async def test_stale_cache_revalidates_with_etag_and_reuses_body_on_304():
    cache = TTLCache(ttl_seconds=-1)  # every entry is immediately stale
    client = GitHubClient("tok", cache)
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/users/alice/starred")
        route.side_effect = [
            httpx.Response(200, json=[{"full_name": "owner/A"}], headers={"ETag": "v1"}),
            httpx.Response(304),
        ]
        try:
            first = await client.get_starred_repos("alice")
            second = await client.get_starred_repos("alice")
        finally:
            await client.aclose()

    assert first == ["owner/A"]
    # The 304 returns no body: we serve the cached one.
    assert second == ["owner/A"]
    assert route.call_count == 2
    # The 2nd request must carry the conditional header.
    assert route.calls[1].request.headers.get("If-None-Match") == "v1"


async def test_waits_then_retries_on_exhausted_rate_limit(monkeypatch):
    slept: list[float] = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr("app.services.github.asyncio.sleep", fake_sleep)

    cache = TTLCache(ttl_seconds=3600)
    client = GitHubClient("tok", cache)
    with respx.mock(base_url=BASE) as mock:
        mock.get("/users/alice/starred").side_effect = [
            httpx.Response(
                403,
                headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "0"},
            ),
            httpx.Response(200, json=[{"full_name": "owner/A"}]),
        ]
        try:
            result = await client.get_starred_repos("alice")
        finally:
            await client.aclose()

    assert result == ["owner/A"]
    assert slept  # we did wait for the reset window before retrying
