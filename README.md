# Stargazer

A small web service that finds the **neighbours** of a GitHub repository.

> A neighbour of repository **A** is a repository **B** that shares at least one
> stargazer with **A**. The more stargazers two repositories have in common, the
> closer they are.

```
GET /repos/{owner}/{repo}/starneighbours
```

returns the list of neighbouring repositories, ordered by the number of common
stargazers (descending):

```json
[
  { "repo": "owner/projectA", "stargazers": ["alice", "bob"] },
  { "repo": "owner/projectB", "stargazers": ["alice"] }
]
```

## How it works

1. Fetch the stargazers of the target repository — `GET /repos/{owner}/{repo}/stargazers`
2. For each stargazer, fetch the repositories they have starred — `GET /users/{user}/starred`
3. Aggregate: for every other repository, collect the users it has in common with the target
4. Sort by number of common stargazers and return

The aggregation logic lives in `app/services/neighbours.py` as a single function with
no I/O of its own — it depends only on a small `GitHubClient` interface, which makes it
trivial to unit-test without hitting the network.

## Tech stack

- **Python 3.12**
- **FastAPI** — web framework, automatic OpenAPI docs, dependency-injection for auth
- **httpx** — async HTTP client for the GitHub API
- **Docker** — reproducible runtime

## Project layout

```
app/
  main.py                  # FastAPI app factory
  api/routes.py            # /starneighbours endpoint
  core/config.py           # settings (env-overridable)
  core/security.py         # authentication dependency
  core/cache.py            # TTL cache (GitHub responses + ETag)
  services/github.py       # GitHub API client (pagination, rate-limit handling)
  services/neighbours.py   # neighbour-computation logic (pure, testable)
  models/schemas.py        # Pydantic response models
tests/                     # unit + API tests
```

## Running locally

```bash
# install dependencies (uv)
uv sync

# run the API
uv run uvicorn app.main:app --reload
```

The interactive docs are then available at http://localhost:8000/docs.

### With Docker

```bash
docker build -t stargazer .
docker run -p 8000:8000 stargazer
```

## Authentication

The endpoint is protected by a **Bearer token**, supplied via the `Authorization`
header. The token is a GitHub personal access token (PAT): it authenticates the
caller *and* is reused for the downstream GitHub API calls, so each user consumes
their own GitHub rate-limit quota.

```bash
curl -H "Authorization: Bearer <YOUR_GITHUB_TOKEN>" \
  "http://localhost:8000/repos/python/cpython/starneighbours?max_stargazers=200"
```

## Query parameters

| Parameter        | Default | Description                                            |
|------------------|---------|--------------------------------------------------------|
| `max_stargazers` | `500`   | Maximum number of stargazers analysed (bounds the cost)|
| `limit`          | `50`    | Number of neighbours returned                          |
| `offset`         | `0`     | Offset into the neighbour list (pagination)            |

## Scalability & design notes

The naive algorithm is `O(N_stargazers)` GitHub API calls. A popular repository has
hundreds of thousands of stars, while the authenticated GitHub API allows only
**5000 requests/hour** — so a naive implementation would exhaust the quota instantly.
The service mitigates this with:

- **Capping** — `max_stargazers` bounds how many stargazers are analysed, making the
  request complete in finite time and budget.
- **Concurrency** — downstream calls run concurrently (`asyncio.gather`) behind a
  semaphore that respects a configurable concurrency limit.
- **Caching + conditional requests** — GitHub responses are cached in-memory with a TTL.
  A repeated request that hits a *fresh* entry is served straight from the cache, with no
  network call at all — so an identical query returns near-instantly. Once an entry's TTL
  expires it is revalidated with `ETag` / `If-None-Match`: a `304 Not Modified` reuses the
  cached body without re-downloading it and does not count against the quota. The cache is
  shared across requests and keyed by URL, so overlapping work between users is reused too.
- **Rate-limit handling** — on `403/429` with an exhausted quota, the client waits for
  the `X-RateLimit-Reset` window.
- **Response pagination** — `limit` / `offset` avoid returning thousands of neighbours
  at once.

### Possible further improvements

- **GitHub GraphQL API** to fetch stargazers and their starred repos in far fewer calls.
- **Shared cache (Redis)** for horizontal scaling across instances.
- **Background processing** — for very large repositories, return a `job_id` and compute
  asynchronously (e.g. ARQ / Celery), then poll for the result.
- **Streaming** the response to avoid holding the full neighbour set in memory.

## Tests

```bash
uv run pytest
```

Unit tests cover the neighbour-computation logic with a fake GitHub client (no network).
The GitHub client and the endpoint are tested with mocked HTTP responses (`respx`) and
FastAPI's `TestClient`.
