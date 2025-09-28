from typing import Dict, Optional


class InMemoryCache:
    """Simple in-memory cache implementation."""
    
    def __init__(self):
        self._cache: Dict[str, bytes] = {}
        self._etags: Dict[str, str] = {}
    
    def get(self, key: str) -> bytes | None:
        """Get cached data by key."""
        return self._cache.get(key)
    
    def set(self, key: str, data: bytes, etag: str | None = None) -> None:
        """Set cached data with optional etag."""
        self._cache[key] = data
        if etag:
            self._etags[key] = etag
    
    def get_etag(self, key: str) -> str | None:
        """Get etag for cached data."""
        return self._etags.get(key)