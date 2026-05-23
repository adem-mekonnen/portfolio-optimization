"""
Cache manager for the GMF Investments data layer.

Tracks when each (tickers, start, end) combination was last fetched from
yfinance and decides whether the cached result is still fresh.

The manifest is a simple JSON file stored alongside the joblib cache so it
survives container restarts when the cache directory is mounted as a volume.

TTL policy
----------
- Short-range queries  (start within the last 90 days)  → 4-hour TTL
  These are used for asset_info and LSTM seed windows; prices change daily.
- Long-range queries   (start older than 90 days)        → 24-hour TTL
  These are used for portfolio optimisation and backtesting; less time-sensitive.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
CACHE_DIR      = os.path.join(os.path.dirname(__file__), "..", ".cache")
MANIFEST_PATH  = os.path.join(CACHE_DIR, "fetch_manifest.json")

SHORT_TTL_HOURS = 4    # for recent-data queries (last 90 days)
LONG_TTL_HOURS  = 24   # for historical queries (older than 90 days)
SHORT_RANGE_DAYS = 90  # threshold that separates the two TTL buckets


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _load_manifest() -> dict:
    """Load the manifest from disk, returning an empty dict on any error."""
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_manifest(manifest: dict) -> None:
    """Persist the manifest to disk atomically."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = MANIFEST_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        os.replace(tmp, MANIFEST_PATH)
    except OSError as exc:
        logger.warning("Could not save cache manifest: %s", exc)


def _cache_key(tickers: list, start: str, end: Any) -> str:
    """Deterministic string key for a fetch_data call."""
    tickers_str = ",".join(sorted(str(t) for t in tickers))
    return f"{tickers_str}|{start}|{end}"


def _ttl_hours(start: str) -> int:
    """Return the appropriate TTL in hours based on how old the start date is."""
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        age_days = (_now_utc() - start_dt).days
        return SHORT_TTL_HOURS if age_days <= SHORT_RANGE_DAYS else LONG_TTL_HOURS
    except (ValueError, TypeError):
        return LONG_TTL_HOURS


# ── Public API ────────────────────────────────────────────────────────────────

def record_fetch(tickers: list, start: str, end: Any) -> None:
    """
    Record that we just fetched fresh data for this (tickers, start, end)
    combination.  Call this immediately after a successful yfinance download.
    """
    manifest = _load_manifest()
    key = _cache_key(tickers, start, end)
    manifest[key] = _now_utc().isoformat()
    _save_manifest(manifest)


def is_stale(tickers: list, start: str, end: Any) -> bool:
    """
    Return True if the cached result for this query is older than its TTL
    (or has never been recorded), meaning a fresh download is needed.
    """
    manifest = _load_manifest()
    key = _cache_key(tickers, start, end)
    recorded = manifest.get(key)
    if recorded is None:
        return True  # never fetched → always stale
    try:
        fetched_at = datetime.fromisoformat(recorded)
        ttl = timedelta(hours=_ttl_hours(start))
        return (_now_utc() - fetched_at) > ttl
    except (ValueError, TypeError):
        return True


def invalidate(tickers: list | None = None) -> None:
    """
    Invalidate cache entries.

    - If *tickers* is None, wipe the entire manifest (full refresh).
    - If *tickers* is provided, remove only entries that include all of those
      tickers (partial invalidation).
    """
    if tickers is None:
        _save_manifest({})
        logger.info("Cache manifest wiped (full invalidation).")
        return

    manifest = _load_manifest()
    tickers_set = {str(t).upper() for t in tickers}
    keys_to_remove = [
        k for k in manifest
        if tickers_set.issubset({t.upper() for t in k.split("|")[0].split(",")})
    ]
    for k in keys_to_remove:
        del manifest[k]
    _save_manifest(manifest)
    logger.info("Invalidated %d cache entries for tickers %s.", len(keys_to_remove), tickers)


def get_status() -> dict:
    """
    Return a summary of all tracked cache entries with their age and staleness.
    Useful for the /data/status API endpoint.
    """
    manifest = _load_manifest()
    now = _now_utc()
    entries = []
    for key, recorded in manifest.items():
        parts = key.split("|")
        tickers_str, start = parts[0], parts[1] if len(parts) > 1 else "?"
        try:
            fetched_at = datetime.fromisoformat(recorded)
            age_seconds = int((now - fetched_at).total_seconds())
            ttl_hours = _ttl_hours(start)
            stale = age_seconds > ttl_hours * 3600
        except (ValueError, TypeError):
            age_seconds = -1
            stale = True
        entries.append({
            "tickers": tickers_str,
            "start":   start,
            "fetched_at": recorded,
            "age_seconds": age_seconds,
            "stale": stale,
        })
    return {"entries": entries, "total": len(entries)}
