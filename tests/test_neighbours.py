import pytest

from app.services.neighbours import compute_neighbours


class FakeGitHubClient:
    """Implements the interface used by compute_neighbours, without any network."""

    def __init__(self, stargazers: list[str], starred: dict[str, list[str]]):
        self._stargazers = stargazers
        self._starred = starred

    async def get_stargazers(self, owner: str, repo: str) -> list[str]:
        return self._stargazers

    async def get_starred_repos(self, user: str) -> list[str]:
        result = self._starred[user]
        if isinstance(result, Exception):
            raise result
        return result


async def test_aggregates_and_sorts_by_common_stargazers():
    client = FakeGitHubClient(
        stargazers=["alice", "bob", "carol"],
        starred={
            "alice": ["owner/A", "owner/B"],
            "bob": ["owner/A"],
            "carol": ["owner/A", "owner/B"],
        },
    )

    result = await compute_neighbours(client, "owner", "target")

    # owner/A shared by 3, owner/B by 2 → A before B.
    assert result == [
        {"repo": "owner/A", "stargazers": ["alice", "bob", "carol"]},
        {"repo": "owner/B", "stargazers": ["alice", "carol"]},
    ]


async def test_excludes_the_target_repository_itself():
    client = FakeGitHubClient(
        stargazers=["alice"],
        starred={"alice": ["owner/target", "owner/A"]},
    )

    result = await compute_neighbours(client, "owner", "target")

    repos = [n["repo"] for n in result]
    assert "owner/target" not in repos
    assert repos == ["owner/A"]


async def test_caps_number_of_stargazers_analysed():
    client = FakeGitHubClient(
        stargazers=["alice", "bob", "carol"],
        starred={
            "alice": ["owner/A"],
            "bob": ["owner/A"],
            "carol": ["owner/A"],
        },
    )

    result = await compute_neighbours(client, "owner", "target", max_stargazers=2)

    # Only alice and bob are analysed → carol absent.
    assert result == [{"repo": "owner/A", "stargazers": ["alice", "bob"]}]


async def test_one_failing_user_does_not_break_the_whole_request():
    client = FakeGitHubClient(
        stargazers=["alice", "bob"],
        starred={
            "alice": ["owner/A"],
            "bob": RuntimeError("github down"),
        },
    )

    result = await compute_neighbours(client, "owner", "target")

    # bob's error is ignored, alice is still counted.
    assert result == [{"repo": "owner/A", "stargazers": ["alice"]}]


async def test_no_stargazers_returns_empty_list():
    client = FakeGitHubClient(stargazers=[], starred={})

    result = await compute_neighbours(client, "owner", "target")

    assert result == []
