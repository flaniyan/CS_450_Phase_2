from acmecli.cache import InMemoryCache


def test_cache_set_get():
    """Test basic cache set and get functionality."""
    cache = InMemoryCache()

    # Test set and get
    cache.set("key1", b"value1", "etag1")
    assert cache.get("key1") == b"value1"
    assert cache.get_etag("key1") == "etag1"

    # Test missing key
    assert cache.get("missing") is None
    assert cache.get_etag("missing") is None


def test_cache_overwrite():
    """Test cache overwrite functionality."""
    cache = InMemoryCache()

    cache.set("key1", b"value1", "etag1")
    cache.set("key1", b"value2", "etag2")

    assert cache.get("key1") == b"value2"
    assert cache.get_etag("key1") == "etag2"
