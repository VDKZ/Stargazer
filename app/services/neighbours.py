import asyncio
from collections import defaultdict

from app.core.config import settings
from app.services.github import GitHubClient


async def compute_neighbours(
    client: GitHubClient,
    owner: str,
    repo: str,
    max_stargazers: int | None = None,
) -> list[dict]:
    target = f"{owner}/{repo}"
    limit = max_stargazers or settings.max_stargazers

    # 1. Stargazers of the target repo, capped.
    stargazers = (await client.get_stargazers(owner, repo))[:limit]

    # 2. Concurrently fetch each user's starred repos (bounded by max_concurrency).
    semaphore = asyncio.Semaphore(settings.max_concurrency)

    async def starred_for(user: str) -> tuple[str, list[str]]:
        async with semaphore:
            return user, await client.get_starred_repos(user)

    results = await asyncio.gather(
        *(starred_for(u) for u in stargazers),
        return_exceptions=True,   # one failing user doesn't break everything
    )

    # 3. Aggregation.
    common: dict[str, set[str]] = defaultdict(set)
    for item in results:
        if isinstance(item, Exception):
            continue
        user, starred_repos = item
        for starred in starred_repos:
            if starred != target:
                common[starred].add(user)

    # 4. Sort by number of common stargazers, descending.
    neighbours = [
        {"repo": repo_name, "stargazers": sorted(users)}
        for repo_name, users in common.items()
    ]
    neighbours.sort(key=lambda n: len(n["stargazers"]), reverse=True)
    return neighbours