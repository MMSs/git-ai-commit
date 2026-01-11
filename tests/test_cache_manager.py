"""Tests for CacheManager class."""

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from git_ai_commit import CacheManager


class TestCacheManagerInit:
    """Tests for CacheManager initialization."""

    def test_creates_cache_directory(self, temp_dir: Path):
        """Cache directory is created on initialization."""
        cache_dir = temp_dir / ".cache" / "git-ai-commit"
        with patch.object(Path, "home", return_value=temp_dir):
            cache = CacheManager(ttl_minutes=5)
            assert cache.cache_dir.exists()

    def test_ttl_converted_to_seconds(self):
        """TTL is converted from minutes to seconds."""
        cache = CacheManager(ttl_minutes=10)
        assert cache.ttl_seconds == 600


class TestCacheManagerGetSet:
    """Tests for get/set operations."""

    def test_set_and_get_basic(self, temp_cache_dir: Path):
        """Basic set and get operations work correctly."""
        with patch.object(Path, "home", return_value=temp_cache_dir.parent.parent):
            cache = CacheManager(ttl_minutes=5)
            cache.set("/test/repo", "test_key", {"foo": "bar"})
            result = cache.get("/test/repo", "test_key")
            assert result == {"foo": "bar"}

    def test_get_nonexistent_returns_none(self, temp_cache_dir: Path):
        """Getting a nonexistent key returns None."""
        with patch.object(Path, "home", return_value=temp_cache_dir.parent.parent):
            cache = CacheManager(ttl_minutes=5)
            result = cache.get("/test/repo", "nonexistent_key")
            assert result is None

    def test_ttl_expiration(self, temp_cache_dir: Path):
        """Expired cache entries return None."""
        with patch.object(Path, "home", return_value=temp_cache_dir.parent.parent):
            cache = CacheManager(ttl_minutes=0)  # Immediate expiration
            cache.ttl_seconds = 0  # Force immediate expiration
            cache.set("/test/repo", "test_key", {"foo": "bar"})
            time.sleep(0.1)
            result = cache.get("/test/repo", "test_key")
            assert result is None

    def test_branch_invalidation(self, temp_cache_dir: Path):
        """Cache is invalidated when branch changes."""
        with patch.object(Path, "home", return_value=temp_cache_dir.parent.parent):
            cache = CacheManager(ttl_minutes=5)
            cache.set("/test/repo", "test_key", {"foo": "bar"}, branch="main")

            # Same branch - should return data
            result = cache.get("/test/repo", "test_key", branch="main")
            assert result == {"foo": "bar"}

            # Different branch - should return None
            result = cache.get("/test/repo", "test_key", branch="feature")
            assert result is None

    def test_head_sha_invalidation(self, temp_cache_dir: Path):
        """Cache is invalidated when HEAD SHA changes."""
        with patch.object(Path, "home", return_value=temp_cache_dir.parent.parent):
            cache = CacheManager(ttl_minutes=5)
            cache.set("/test/repo", "test_key", {"foo": "bar"}, head_sha="abc123")

            # Same SHA - should return data
            result = cache.get("/test/repo", "test_key", head_sha="abc123")
            assert result == {"foo": "bar"}

            # Different SHA - should return None
            result = cache.get("/test/repo", "test_key", head_sha="def456")
            assert result is None

    def test_complex_data_serialization(self, temp_cache_dir: Path):
        """Complex nested data structures are serialized correctly."""
        with patch.object(Path, "home", return_value=temp_cache_dir.parent.parent):
            cache = CacheManager(ttl_minutes=5)
            complex_data = {
                "string": "value",
                "number": 42,
                "float": 3.14,
                "boolean": True,
                "null": None,
                "list": [1, 2, 3],
                "nested": {"a": {"b": {"c": "deep"}}},
            }
            cache.set("/test/repo", "complex_key", complex_data)
            result = cache.get("/test/repo", "complex_key")
            assert result == complex_data


class TestCacheManagerInvalidate:
    """Tests for cache invalidation."""

    def test_invalidate_specific_key(self, temp_cache_dir: Path):
        """Specific key can be invalidated."""
        with patch.object(Path, "home", return_value=temp_cache_dir.parent.parent):
            cache = CacheManager(ttl_minutes=5)
            cache.set("/test/repo", "key1", "value1")
            cache.set("/test/repo", "key2", "value2")

            cache.invalidate("/test/repo", "key1")

            assert cache.get("/test/repo", "key1") is None
            assert cache.get("/test/repo", "key2") == "value2"

    def test_invalidate_all_for_repo(self, temp_cache_dir: Path):
        """All keys for a repo can be invalidated."""
        with patch.object(Path, "home", return_value=temp_cache_dir.parent.parent):
            cache = CacheManager(ttl_minutes=5)
            cache.set("/test/repo", "key1", "value1")
            cache.set("/test/repo", "key2", "value2")

            cache.invalidate("/test/repo")  # No key = invalidate all

            assert cache.get("/test/repo", "key1") is None
            assert cache.get("/test/repo", "key2") is None

    def test_clear_all(self, temp_cache_dir: Path):
        """All cache entries can be cleared."""
        with patch.object(Path, "home", return_value=temp_cache_dir.parent.parent):
            cache = CacheManager(ttl_minutes=5)
            cache.set("/repo1", "key1", "value1")
            cache.set("/repo2", "key2", "value2")

            cache.clear_all()

            assert cache.get("/repo1", "key1") is None
            assert cache.get("/repo2", "key2") is None


class TestCacheManagerEdgeCases:
    """Tests for edge cases and error handling."""

    def test_corrupted_cache_file(self, temp_cache_dir: Path):
        """Corrupted cache files are handled gracefully."""
        with patch.object(Path, "home", return_value=temp_cache_dir.parent.parent):
            cache = CacheManager(ttl_minutes=5)

            # Create a corrupted cache file
            cache_file = cache._get_cache_file("/test/repo", "corrupted")
            cache_file.write_text("not valid json {{{")

            result = cache.get("/test/repo", "corrupted")
            assert result is None

    def test_cache_file_permissions_error(self, temp_cache_dir: Path):
        """IOError on write is handled gracefully."""
        with patch.object(Path, "home", return_value=temp_cache_dir.parent.parent):
            cache = CacheManager(ttl_minutes=5)

            # Mock open to raise IOError
            with patch("builtins.open", side_effect=IOError("Permission denied")):
                # Should not raise, just silently fail
                cache.set("/test/repo", "test_key", {"foo": "bar"})

    def test_repo_path_hashing_consistency(self, temp_cache_dir: Path):
        """Same repo path always produces same cache file hash."""
        with patch.object(Path, "home", return_value=temp_cache_dir.parent.parent):
            cache = CacheManager(ttl_minutes=5)
            file1 = cache._get_cache_file("/test/repo", "key")
            file2 = cache._get_cache_file("/test/repo", "key")
            assert file1 == file2

    def test_different_repos_different_files(self, temp_cache_dir: Path):
        """Different repo paths produce different cache files."""
        with patch.object(Path, "home", return_value=temp_cache_dir.parent.parent):
            cache = CacheManager(ttl_minutes=5)
            file1 = cache._get_cache_file("/repo1", "key")
            file2 = cache._get_cache_file("/repo2", "key")
            assert file1 != file2
