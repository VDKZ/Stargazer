from app.core.cache import TTLCache


def test_get_unknown_key_returns_none():
    cache = TTLCache(ttl_seconds=60)
    assert cache.get("missing") is None


def test_set_then_get_returns_value_marked_fresh():
    cache = TTLCache(ttl_seconds=60)
    cache.set("k", {"etag": "abc"})

    result = cache.get("k")
    assert result is not None
    value, fresh = result
    assert value == {"etag": "abc"}
    assert fresh is True


def test_expired_entry_is_kept_but_marked_stale():
    # Negative TTL → the entry is immediately stale.
    cache = TTLCache(ttl_seconds=-1)
    cache.set("k", {"etag": "abc"})

    result = cache.get("k")
    assert result is not None
    value, fresh = result
    # The value stays available (for ETag revalidation) but is no longer fresh.
    assert value == {"etag": "abc"}
    assert fresh is False


def test_set_overwrites_existing_entry():
    cache = TTLCache(ttl_seconds=60)
    cache.set("k", "old")
    cache.set("k", "new")

    value, _ = cache.get("k")
    assert value == "new"
