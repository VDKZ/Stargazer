from fastapi import APIRouter, Depends, Query

from app.core.cache import TTLCache
from app.core.config import settings
from app.core.security import get_github_token
from app.models.schemas import Neighbour
from app.services.github import GitHubClient
from app.services.neighbours import compute_neighbours

router = APIRouter()

# Cache shared across requests (instantiated once at startup).
_cache = TTLCache(settings.cache_ttl_seconds)


@router.get("/repos/{owner}/{repo}/starneighbours", response_model=list[Neighbour])
async def star_neighbours(
    owner: str,
    repo: str,
    token: str = Depends(get_github_token),
    max_stargazers: int = Query(default=settings.max_stargazers, ge=1, le=5000),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    client = GitHubClient(token, _cache)
    try:
        neighbours = await compute_neighbours(client, owner, repo, max_stargazers)
    finally:
        await client.aclose()
    return neighbours[offset : offset + limit]