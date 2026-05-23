"""
Unit tests for src/cache_manager.py.

All file I/O is patched so tests run without touching the real .cache directory.
"""

import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import mock_open, patch, MagicMock


# ── Helpers ───────────────────────────────────────────────────────────────────

def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _manifest_with_entry(key: str, fetched_at: datetime) -> str:
    return json.dumps({key: _iso(fetched_at)})


# ── is_stale ──────────────────────────────────────────────────────────────────

class TestIsStale:
    def test_missing_key_is_stale(self):
        with patch("src.cache_manager._load_manifest", return_value={}):
            from src.cache_manager import is_stale
            assert is_stale(["TSLA"], "2025-01-01", None) is True

    def test_fresh_short_range_not_stale(self):
        """Entry fetched 1 hour ago with a short-range start → not stale (TTL=4h)."""
        from src.cache_manager import is_stale, _cache_key
        tickers, start, end = ["TSLA"], "2025-04-01", None
        key = _cache_key(tickers, start, end)
        fetched_at = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        with patch("src.cache_manager._load_manifest", return_value={key: _iso(fetched_at)}):
            assert is_stale(tickers, start, end) is False

    def test_stale_short_range(self):
        """Entry fetched 5 hours ago with a short-range start → stale (TTL=4h)."""
        from src.cache_manager import is_stale, _cache_key
        from datetime import date, timedelta as td
        # Use a start date within the last 90 days so it gets the 4h TTL
        recent_start = (date.today() - td(days=30)).strftime("%Y-%m-%d")
        tickers, start, end = ["TSLA"], recent_start, None
        key = _cache_key(tickers, start, end)
        fetched_at = datetime.now(tz=timezone.utc) - timedelta(hours=5)
        with patch("src.cache_manager._load_manifest", return_value={key: _iso(fetched_at)}):
            assert is_stale(tickers, start, end) is True

    def test_fresh_long_range_not_stale(self):
        """Entry fetched 12 hours ago with a historical start → not stale (TTL=24h)."""
        from src.cache_manager import is_stale, _cache_key
        tickers, start, end = ["SPY", "BND"], "2015-01-01", None
        key = _cache_key(tickers, start, end)
        fetched_at = datetime.now(tz=timezone.utc) - timedelta(hours=12)
        with patch("src.cache_manager._load_manifest", return_value={key: _iso(fetched_at)}):
            assert is_stale(tickers, start, end) is False

    def test_stale_long_range(self):
        """Entry fetched 25 hours ago with a historical start → stale (TTL=24h)."""
        from src.cache_manager import is_stale, _cache_key
        tickers, start, end = ["SPY", "BND"], "2015-01-01", None
        key = _cache_key(tickers, start, end)
        fetched_at = datetime.now(tz=timezone.utc) - timedelta(hours=25)
        with patch("src.cache_manager._load_manifest", return_value={key: _iso(fetched_at)}):
            assert is_stale(tickers, start, end) is True


# ── record_fetch ──────────────────────────────────────────────────────────────

class TestRecordFetch:
    def test_writes_key_to_manifest(self):
        from src.cache_manager import record_fetch, _cache_key
        tickers, start, end = ["TSLA"], "2025-01-01", None
        key = _cache_key(tickers, start, end)

        saved: dict = {}

        def fake_save(manifest):
            saved.update(manifest)

        with patch("src.cache_manager._load_manifest", return_value={}), \
             patch("src.cache_manager._save_manifest", side_effect=fake_save):
            record_fetch(tickers, start, end)

        assert key in saved
        # Value should be a parseable ISO timestamp
        datetime.fromisoformat(saved[key])


# ── invalidate ────────────────────────────────────────────────────────────────

class TestInvalidate:
    def test_full_invalidation_wipes_manifest(self):
        from src.cache_manager import invalidate
        saved: list = []
        with patch("src.cache_manager._load_manifest", return_value={"k1": "v1", "k2": "v2"}), \
             patch("src.cache_manager._save_manifest", side_effect=lambda m: saved.append(m)):
            invalidate(tickers=None)
        assert saved[-1] == {}

    def test_partial_invalidation_removes_matching_keys(self):
        from src.cache_manager import invalidate
        manifest = {
            "TSLA|2015-01-01|None": "2025-01-01T00:00:00+00:00",
            "SPY,BND|2015-01-01|None": "2025-01-01T00:00:00+00:00",
        }
        saved: list = []
        with patch("src.cache_manager._load_manifest", return_value=dict(manifest)), \
             patch("src.cache_manager._save_manifest", side_effect=lambda m: saved.append(dict(m))):
            invalidate(tickers=["TSLA"])
        result = saved[-1]
        assert "TSLA|2015-01-01|None" not in result
        assert "SPY,BND|2015-01-01|None" in result


# ── get_status ────────────────────────────────────────────────────────────────

class TestGetStatus:
    def test_returns_entries_list(self):
        from src.cache_manager import get_status
        fetched_at = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()
        manifest = {"TSLA|2025-01-01|None": fetched_at}
        with patch("src.cache_manager._load_manifest", return_value=manifest):
            result = get_status()
        assert "entries" in result
        assert len(result["entries"]) == 1
        entry = result["entries"][0]
        assert entry["tickers"] == "TSLA"
        assert entry["stale"] is False

    def test_empty_manifest_returns_empty_list(self):
        from src.cache_manager import get_status
        with patch("src.cache_manager._load_manifest", return_value={}):
            result = get_status()
        assert result["entries"] == []
        assert result["total"] == 0
