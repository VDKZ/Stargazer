import pytest
from fastapi.testclient import TestClient

import app.api.routes as routes
from app.main import app

AUTH = {"Authorization": "Bearer dummy-token"}


@pytest.fixture
def client(monkeypatch):
    async def fake_compute(client, owner, repo, max_stargazers):
        return [
            {"repo": "owner/A", "stargazers": ["alice", "bob"]},
            {"repo": "owner/B", "stargazers": ["alice"]},
            {"repo": "owner/C", "stargazers": ["bob"]},
        ]

    # Neutralise all network I/O in the endpoint.
    class DummyClient:
        def __init__(self, token, cache):
            ...

        async def aclose(self):
            ...

    monkeypatch.setattr(routes, "compute_neighbours", fake_compute)
    monkeypatch.setattr(routes, "GitHubClient", DummyClient)
    return TestClient(app)


def test_requires_authentication(client):
    resp = client.get("/repos/owner/repo/starneighbours")
    assert resp.status_code in (401, 403)


def test_returns_neighbours(client):
    resp = client.get("/repos/owner/repo/starneighbours", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body[0] == {"repo": "owner/A", "stargazers": ["alice", "bob"]}
    assert len(body) == 3


def test_limit_and_offset_paginate_the_response(client):
    resp = client.get(
        "/repos/owner/repo/starneighbours",
        params={"limit": 1, "offset": 1},
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert resp.json() == [{"repo": "owner/B", "stargazers": ["alice"]}]


def test_invalid_limit_is_rejected(client):
    resp = client.get(
        "/repos/owner/repo/starneighbours",
        params={"limit": 0},
        headers=AUTH,
    )
    assert resp.status_code == 422
