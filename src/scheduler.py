"""
Background scheduler for automated data refresh and model retraining.

Jobs
----
1. **cache_refresh**  — runs daily at 18:05 ET (after US market close at 16:00 ET).
   Invalidates the price cache for all tracked tickers so the next API call
   fetches fresh end-of-day data from yfinance.

2. **model_retrain**  — runs weekly on Sunday at 02:00 UTC.
   Calls retrain_all() to fine-tune LSTM models on the latest available data.

The scheduler is started once when the FastAPI app starts (lifespan event) and
shut down cleanly when the app stops.  APScheduler's BackgroundScheduler runs
jobs in a daemon thread so it never blocks the API.
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .cache_manager import invalidate as invalidate_cache
from .retrain import TICKERS, retrain_all

logger = logging.getLogger(__name__)

# ── Singleton scheduler instance ─────────────────────────────────────────────
_scheduler: BackgroundScheduler | None = None


# ── Job functions ─────────────────────────────────────────────────────────────

def _job_refresh_cache() -> None:
    """Invalidate price cache for all tracked tickers."""
    logger.info("[scheduler] Running cache refresh job at %s UTC", datetime.now(tz=timezone.utc))
    try:
        invalidate_cache(tickers=TICKERS)
        logger.info("[scheduler] Cache invalidated for %s.", TICKERS)
    except Exception as exc:
        logger.error("[scheduler] Cache refresh failed: %s", exc, exc_info=True)


def _job_retrain_models() -> None:
    """Fine-tune LSTM models on the latest market data."""
    logger.info("[scheduler] Running model retrain job at %s UTC", datetime.now(tz=timezone.utc))
    try:
        results = retrain_all()
        logger.info("[scheduler] Retrain results: %s", results)
    except Exception as exc:
        logger.error("[scheduler] Model retrain failed: %s", exc, exc_info=True)


# ── Lifecycle ─────────────────────────────────────────────────────────────────

def start_scheduler() -> BackgroundScheduler:
    """
    Create, configure, and start the background scheduler.

    Returns the running scheduler instance (stored as a module-level singleton
    so start_scheduler() is idempotent).
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.info("[scheduler] Already running — skipping start.")
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="UTC")

    # ── Job 1: daily cache refresh at 18:05 ET = 23:05 UTC (22:05 UTC in summer)
    # We use 23:05 UTC which covers both EST (UTC-5) and EDT (UTC-4) safely.
    _scheduler.add_job(
        _job_refresh_cache,
        trigger=CronTrigger(hour=23, minute=5, timezone="UTC"),
        id="cache_refresh",
        name="Daily price cache refresh",
        replace_existing=True,
        misfire_grace_time=3600,   # allow up to 1 h late if server was down
    )

    # ── Job 2: weekly model retrain on Sunday at 02:00 UTC
    _scheduler.add_job(
        _job_retrain_models,
        trigger=CronTrigger(day_of_week="sun", hour=2, minute=0, timezone="UTC"),
        id="model_retrain",
        name="Weekly LSTM model retrain",
        replace_existing=True,
        misfire_grace_time=7200,   # allow up to 2 h late
    )

    _scheduler.start()
    logger.info(
        "[scheduler] Started. Jobs: %s",
        [j.name for j in _scheduler.get_jobs()],
    )
    return _scheduler


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler (called on app shutdown)."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] Stopped.")
    _scheduler = None


def get_next_runs() -> list[dict]:
    """Return the next scheduled run time for each job (used by /data/status)."""
    if _scheduler is None or not _scheduler.running:
        return []
    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id":       job.id,
            "name":     job.name,
            "next_run": next_run.isoformat() if next_run else None,
        })
    return jobs
