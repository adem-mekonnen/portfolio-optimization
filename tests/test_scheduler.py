"""
Unit tests for src/scheduler.py.

APScheduler is mocked so no real background threads are started.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestStartScheduler:
    def test_returns_scheduler_instance(self):
        mock_sched = MagicMock()
        mock_sched.running = False

        with patch("src.scheduler._scheduler", None), \
             patch("src.scheduler.BackgroundScheduler", return_value=mock_sched):
            from src.scheduler import start_scheduler
            result = start_scheduler()

        mock_sched.start.assert_called_once()
        assert result is mock_sched

    def test_idempotent_when_already_running(self):
        """Calling start_scheduler() twice should not start a second scheduler."""
        mock_sched = MagicMock()
        mock_sched.running = True

        with patch("src.scheduler._scheduler", mock_sched):
            from src.scheduler import start_scheduler
            result = start_scheduler()

        mock_sched.start.assert_not_called()
        assert result is mock_sched

    def test_two_jobs_registered(self):
        mock_sched = MagicMock()
        mock_sched.running = False

        with patch("src.scheduler._scheduler", None), \
             patch("src.scheduler.BackgroundScheduler", return_value=mock_sched):
            from src.scheduler import start_scheduler
            start_scheduler()

        assert mock_sched.add_job.call_count == 2


class TestStopScheduler:
    def test_shuts_down_running_scheduler(self):
        mock_sched = MagicMock()
        mock_sched.running = True

        with patch("src.scheduler._scheduler", mock_sched):
            from src.scheduler import stop_scheduler
            stop_scheduler()

        mock_sched.shutdown.assert_called_once_with(wait=False)

    def test_noop_when_not_running(self):
        mock_sched = MagicMock()
        mock_sched.running = False

        with patch("src.scheduler._scheduler", mock_sched):
            from src.scheduler import stop_scheduler
            stop_scheduler()

        mock_sched.shutdown.assert_not_called()

    def test_noop_when_none(self):
        with patch("src.scheduler._scheduler", None):
            from src.scheduler import stop_scheduler
            stop_scheduler()  # should not raise


class TestGetNextRuns:
    def test_returns_empty_when_no_scheduler(self):
        with patch("src.scheduler._scheduler", None):
            from src.scheduler import get_next_runs
            assert get_next_runs() == []

    def test_returns_job_list(self):
        from datetime import datetime, timezone
        mock_job = MagicMock()
        mock_job.id = "cache_refresh"
        mock_job.name = "Daily price cache refresh"
        mock_job.next_run_time = datetime(2026, 5, 1, 23, 5, tzinfo=timezone.utc)

        mock_sched = MagicMock()
        mock_sched.running = True
        mock_sched.get_jobs.return_value = [mock_job]

        with patch("src.scheduler._scheduler", mock_sched):
            from src.scheduler import get_next_runs
            result = get_next_runs()

        assert len(result) == 1
        assert result[0]["id"] == "cache_refresh"
        assert "2026-05-01" in result[0]["next_run"]

    def test_none_next_run_handled(self):
        mock_job = MagicMock()
        mock_job.id = "model_retrain"
        mock_job.name = "Weekly LSTM model retrain"
        mock_job.next_run_time = None

        mock_sched = MagicMock()
        mock_sched.running = True
        mock_sched.get_jobs.return_value = [mock_job]

        with patch("src.scheduler._scheduler", mock_sched):
            from src.scheduler import get_next_runs
            result = get_next_runs()

        assert result[0]["next_run"] is None
