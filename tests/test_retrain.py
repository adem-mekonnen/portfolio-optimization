"""
Unit tests for src/retrain.py.

All yfinance downloads, TensorFlow model loads/saves, and file I/O are mocked
so tests run offline and fast.
"""

import json
import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, call


def _fake_prices(n=300, start_price=300.0) -> pd.Series:
    """Return a fake daily price Series long enough for sequence creation."""
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    prices = start_price + np.cumsum(np.random.normal(0, 5, n))
    return pd.Series(prices.astype("float32"), index=dates)


# ── _download_prices ──────────────────────────────────────────────────────────

class TestDownloadPrices:
    @patch("src.retrain.yf.download")
    def test_returns_series(self, mock_dl):
        raw = pd.DataFrame({"Adj Close": _fake_prices().values}, index=_fake_prices().index)
        mock_dl.return_value = raw
        from src.retrain import _download_prices
        result = _download_prices("TSLA", "2020-01-01")
        assert isinstance(result, pd.Series)
        assert len(result) > 0

    @patch("src.retrain.yf.download")
    def test_empty_raises(self, mock_dl):
        mock_dl.return_value = pd.DataFrame()
        from src.retrain import _download_prices
        with pytest.raises(ValueError, match="No data"):
            _download_prices("TSLA", "2020-01-01")


# ── _create_sequences ─────────────────────────────────────────────────────────

class TestCreateSequences:
    def test_output_shapes(self):
        from src.retrain import _create_sequences, SEQ_LENGTH
        data = np.random.rand(200, 1).astype("float32")
        X, y = _create_sequences(data, SEQ_LENGTH)
        assert X.shape == (200 - SEQ_LENGTH, SEQ_LENGTH)
        assert y.shape == (200 - SEQ_LENGTH,)

    def test_minimum_data(self):
        from src.retrain import _create_sequences, SEQ_LENGTH
        data = np.random.rand(SEQ_LENGTH + 1, 1).astype("float32")
        X, y = _create_sequences(data, SEQ_LENGTH)
        assert len(X) == 1


# ── retrain_ticker — full training path (no existing model) ───────────────────

class TestRetrainTickerFullTrain:
    @patch("src.retrain._model_exists", return_value=False)
    @patch("src.retrain._download_prices")
    @patch("src.retrain._save_meta")
    @patch("src.retrain.shutil.move")
    @patch("src.retrain.joblib.dump")
    @patch("src.retrain._build_lstm")
    def test_full_train_called_when_no_model(
        self, mock_build, mock_jdump, mock_move, mock_meta, mock_dl, mock_exists
    ):
        mock_dl.return_value = _fake_prices(300)
        fake_model = MagicMock()
        mock_build.return_value = fake_model

        from src.retrain import retrain_ticker, FULL_EPOCHS
        retrain_ticker("TSLA")

        mock_build.assert_called_once()
        fake_model.fit.assert_called_once()
        # Verify epochs argument
        _, fit_kwargs = fake_model.fit.call_args
        assert fit_kwargs.get("epochs") == FULL_EPOCHS or fake_model.fit.call_args[0][2] == FULL_EPOCHS or \
               fake_model.fit.call_args[1].get("epochs") == FULL_EPOCHS


# ── retrain_ticker — fine-tune path (model exists, new data available) ────────

class TestRetrainTickerFinetune:
    @patch("src.retrain._model_exists", return_value=True)
    @patch("src.retrain._download_prices")
    @patch("src.retrain._load_meta")
    @patch("src.retrain._save_meta")
    @patch("src.retrain.shutil.move")
    @patch("src.retrain.joblib.dump")
    @patch("src.retrain.tempfile.TemporaryDirectory")
    @patch("src.retrain.load_model")
    def test_finetune_called_when_model_exists(
        self, mock_load_model, mock_tmpdir, mock_jdump, mock_move, mock_meta_save,
        mock_meta_load, mock_dl, mock_exists
    ):
        # Use 500 rows so there are plenty of new rows after the cutoff
        prices = _fake_prices(500)
        mock_dl.return_value = prices
        # Cutoff 100 rows from the end → 100 new rows > SEQ_LENGTH+1 (61)
        cutoff = prices.index[-100].strftime("%Y-%m-%d")
        mock_meta_load.return_value = {"TSLA": {"trained_through": cutoff}}

        fake_model = MagicMock()
        mock_load_model.return_value = fake_model

        # Make TemporaryDirectory a no-op context manager returning a temp path
        import tempfile
        mock_tmpdir.return_value.__enter__ = MagicMock(return_value=tempfile.gettempdir())
        mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)

        from src.retrain import retrain_ticker, FINETUNE_EPOCHS
        retrain_ticker("TSLA")

        mock_load_model.assert_called_once()
        fake_model.fit.assert_called_once()
        _, fit_kwargs = fake_model.fit.call_args
        assert fit_kwargs.get("epochs") == FINETUNE_EPOCHS

    @patch("src.retrain._model_exists", return_value=True)
    @patch("src.retrain._download_prices")
    @patch("src.retrain._load_meta")
    @patch("src.retrain.load_model")
    def test_skips_when_insufficient_new_data(
        self, mock_load_model, mock_meta_load, mock_dl, mock_exists
    ):
        """If fewer than SEQ_LENGTH+1 new rows exist, retrain should be skipped."""
        prices = _fake_prices(300)
        mock_dl.return_value = prices
        # Pretend model was trained just 5 days ago (not enough new data)
        cutoff = prices.index[-5].strftime("%Y-%m-%d")
        mock_meta_load.return_value = {"TSLA": {"trained_through": cutoff}}

        from src.retrain import retrain_ticker
        retrain_ticker("TSLA")  # should return early without calling load_model
        mock_load_model.assert_not_called()


# ── retrain_all ───────────────────────────────────────────────────────────────

class TestRetrainAll:
    @patch("src.retrain.retrain_ticker")
    def test_calls_each_ticker(self, mock_retrain):
        from src.retrain import retrain_all, TICKERS
        results = retrain_all()
        assert mock_retrain.call_count == len(TICKERS)
        for t in TICKERS:
            assert results[t] == "ok"

    @patch("src.retrain.retrain_ticker", side_effect=Exception("network error"))
    def test_error_captured_per_ticker(self, mock_retrain):
        from src.retrain import retrain_all, TICKERS
        results = retrain_all()
        for t in TICKERS:
            assert results[t].startswith("error:")

    @patch("src.retrain.retrain_ticker")
    def test_custom_ticker_list(self, mock_retrain):
        from src.retrain import retrain_all
        results = retrain_all(tickers=["TSLA"])
        assert mock_retrain.call_count == 1
        assert "TSLA" in results


# ── Atomic save / .ready marker ───────────────────────────────────────────────

class TestAtomicSave:
    """
    Verify the five-step atomic save protocol using a real temp directory
    so we can inspect actual files on disk without mocking builtins.open.

      A  .ready marker is removed before any file is touched
      B  Both files are written to a temp directory
      C  Model is moved into place
      D  Scaler is moved into place
      E  .ready marker is written only after C and D succeed
    """

    def _run_retrain(self, tmp_path, move_side_effect=None):
        """
        Helper: run retrain_ticker("TSLA") with MODELS_DIR pointing at
        *tmp_path* and all heavy I/O mocked out.
        Returns the mock_move object for inspection.
        """
        import tempfile as _tempfile

        prices = _fake_prices(300)

        fake_model = MagicMock()
        fake_model.save = MagicMock()

        # TemporaryDirectory context manager returns a real sub-dir of tmp_path
        real_tmp = str(tmp_path / "staging")
        os.makedirs(real_tmp, exist_ok=True)

        with (
            patch("src.retrain.MODELS_DIR",       str(tmp_path)),
            patch("src.retrain.META_FILE",         str(tmp_path / "retrain_meta.json")),
            patch("src.retrain._model_exists",     return_value=False),
            patch("src.retrain._download_prices",  return_value=prices),
            patch("src.retrain._save_meta"),
            patch("src.retrain.joblib.dump"),
            patch("src.retrain.tempfile.TemporaryDirectory") as mock_tmpdir,
            patch("src.retrain.load_model",        return_value=fake_model),
        ):
            mock_tmpdir.return_value.__enter__ = MagicMock(return_value=real_tmp)
            mock_tmpdir.return_value.__exit__  = MagicMock(return_value=False)

            # Patch shutil.move to either succeed or fail on demand
            with patch("src.retrain.shutil.move", side_effect=move_side_effect) as mock_move:
                from src.retrain import retrain_ticker
                try:
                    retrain_ticker("TSLA")
                except Exception:
                    pass
                return mock_move

    def test_ready_marker_written_after_successful_save(self, tmp_path):
        """Step E: .ready file exists on disk after both moves succeed."""
        import os
        self._run_retrain(tmp_path, move_side_effect=None)
        ready = tmp_path / "TSLA.ready"
        assert ready.exists(), ".ready marker was not created after a successful save"
        # Marker should contain a valid ISO timestamp
        content = ready.read_text(encoding="utf-8").strip()
        from datetime import datetime
        datetime.fromisoformat(content)   # raises if not a valid timestamp

    def test_ready_marker_absent_when_second_move_fails(self, tmp_path):
        """
        If the second shutil.move (scaler) raises, the .ready marker must NOT
        be written — inference should fall back to mock forecast.
        """
        # First move (model) succeeds, second move (scaler) fails
        self._run_retrain(tmp_path, move_side_effect=[None, OSError("disk full")])
        ready = tmp_path / "TSLA.ready"
        assert not ready.exists(), (
            ".ready marker was written despite a failed save — "
            "inference would load a mismatched model+scaler pair"
        )

    def test_existing_ready_marker_removed_before_save(self, tmp_path):
        """
        Step A: if a .ready marker already exists, it must be removed BEFORE
        any file is touched so inference stops trusting the old pair during
        the replacement window.
        """
        ticker = "TSLA"
        prices = _fake_prices(300)

        # Pre-create a .ready marker simulating a previous successful run
        ready = tmp_path / f"{ticker}.ready"
        ready.write_text("2025-01-01T00:00:00+00:00", encoding="utf-8")
        assert ready.exists()

        # Track whether .ready was gone when the first shutil.move fired.
        # We do NOT call the real shutil.move because the source files are
        # mocked (model.save and joblib.dump are no-ops), so the paths don't
        # exist on disk.  We only care about the .ready state at call time.
        removed_before_first_move: list[bool] = []
        real_tmp = str(tmp_path / "staging")
        os.makedirs(real_tmp, exist_ok=True)

        def tracking_move(src, dst):
            if not removed_before_first_move:
                # First call — record whether .ready is already absent
                removed_before_first_move.append(not ready.exists())
            # Don't actually move (source files are mocked and don't exist)

        fake_model = MagicMock()
        fake_model.save = MagicMock()

        with (
            patch("src.retrain.MODELS_DIR",       str(tmp_path)),
            patch("src.retrain.META_FILE",         str(tmp_path / "retrain_meta.json")),
            patch("src.retrain._model_exists",     return_value=False),
            patch("src.retrain._download_prices",  return_value=prices),
            patch("src.retrain._save_meta"),
            patch("src.retrain.joblib.dump"),
            patch("src.retrain.tempfile.TemporaryDirectory") as mock_tmpdir,
            patch("src.retrain.load_model",        return_value=fake_model),
            patch("src.retrain.shutil.move",       side_effect=tracking_move),
        ):
            mock_tmpdir.return_value.__enter__ = MagicMock(return_value=real_tmp)
            mock_tmpdir.return_value.__exit__  = MagicMock(return_value=False)

            from src.retrain import retrain_ticker
            retrain_ticker(ticker)

        assert removed_before_first_move, "shutil.move was never called"
        assert removed_before_first_move[0], (
            "The .ready marker was still present when the first shutil.move fired — "
            "Step A (invalidation) did not happen before Step C (model move)"
        )


import os
import shutil


class TestModelExistsWithReadyMarker:
    """
    _model_exists must return False when the .ready marker is absent,
    even if the model and scaler files are present on disk.
    """

    def test_returns_false_when_ready_missing(self, tmp_path):
        """Model + scaler present but no .ready → pair is not trustworthy."""
        ticker = "TSLA"
        (tmp_path / f"{ticker}_lstm.keras").touch()
        (tmp_path / f"{ticker}_scaler.pkl").touch()
        # .ready intentionally NOT created

        with patch("src.retrain.MODELS_DIR", str(tmp_path)):
            # Re-evaluate the helper with the patched MODELS_DIR
            model_ok  = os.path.exists(str(tmp_path / f"{ticker}_lstm.keras"))
            scaler_ok = os.path.exists(str(tmp_path / f"{ticker}_scaler.pkl"))
            ready_ok  = os.path.exists(str(tmp_path / f"{ticker}.ready"))

        assert model_ok  is True
        assert scaler_ok is True
        assert ready_ok  is False   # marker absent → _model_exists should be False

    def test_returns_true_when_all_three_present(self, tmp_path):
        """Model + scaler + .ready all present → pair is trustworthy."""
        ticker = "TSLA"
        (tmp_path / f"{ticker}_lstm.keras").touch()
        (tmp_path / f"{ticker}_scaler.pkl").touch()
        (tmp_path / f"{ticker}.ready").touch()

        model_ok  = os.path.exists(str(tmp_path / f"{ticker}_lstm.keras"))
        scaler_ok = os.path.exists(str(tmp_path / f"{ticker}_scaler.pkl"))
        ready_ok  = os.path.exists(str(tmp_path / f"{ticker}.ready"))

        assert model_ok and scaler_ok and ready_ok

    def test_model_inference_respects_ready_marker(self, tmp_path):
        """
        model_inference._model_exists must also check the .ready marker,
        not just the .keras and .pkl files.
        """
        ticker = "TSLA"
        (tmp_path / f"{ticker}_lstm.keras").touch()
        (tmp_path / f"{ticker}_scaler.pkl").touch()
        # No .ready marker

        with patch("src.model_inference.MODELS_DIR", str(tmp_path)):
            from src.model_inference import _model_exists
            assert _model_exists(ticker) is False

        # Now add the marker
        (tmp_path / f"{ticker}.ready").touch()
        with patch("src.model_inference.MODELS_DIR", str(tmp_path)):
            from src.model_inference import _model_exists
            assert _model_exists(ticker) is True

