# tests/test_sql_models.py
import pytest
import numpy as np
from mpd_overwatch.data.sql_models import ChannelFrame, WellDatabase, ChannelSummary


class TestChannelFrame:
    def _make_frame(self, n=100):
        return ChannelFrame(
            wits_id="0121", db_id=107, mnemonic="PP",
            description="Pump Pressure", units="psi", source="WITS",
            bias=0.0, scale=1.0, depth_offset=0.0, log_by="depth",
            changelog={},
            time=np.arange(np.datetime64("2025-07-03T00:00:00"), np.datetime64("2025-07-03T00:00:00") + np.timedelta64(n, "s"), dtype="datetime64[s]"),
            depth=np.linspace(0, 10000, n),
            value=np.random.uniform(0, 5000, n),
            hide=np.zeros(n, dtype=np.int8),
        )

    def test_n_points(self):
        cf = self._make_frame(50)
        assert cf.n_points == 50

    def test_visible_mask_all_visible(self):
        cf = self._make_frame(10)
        assert cf.visible_mask.all()

    def test_visible_mask_some_hidden(self):
        cf = self._make_frame(10)
        cf.hide[3] = 1
        cf.hide[7] = 1
        assert cf.visible_mask.sum() == 8

    def test_calibrated_value(self):
        cf = self._make_frame(5)
        cf.value[:] = [10, 20, 30, 40, 50]
        cf.bias = 5.0
        cf.scale = 2.0
        expected = np.array([25, 45, 65, 85, 105], dtype=float)
        np.testing.assert_array_almost_equal(cf.calibrated_value, expected)

    def test_depth_corrected(self):
        cf = self._make_frame(3)
        cf.depth[:] = [100, 200, 300]
        cf.depth_offset = 37.0
        np.testing.assert_array_almost_equal(
            cf.depth_corrected, [137, 237, 337]
        )

    def test_log_by_normalization(self):
        """log_by stores the raw value; normalization is parser's job."""
        cf = self._make_frame(1)
        cf.log_by = "depth"
        assert cf.log_by == "depth"


class TestWellDatabase:
    def _make_db(self):
        cf1 = ChannelFrame(
            wits_id="0121", db_id=107, mnemonic="PP",
            description="Pump Pressure", units="psi", source="WITS",
            bias=0, scale=1, depth_offset=0, log_by="depth",
            time=np.array(["2025-07-03T21:34:48", "2025-07-03T21:35:00"], dtype="datetime64[s]"),
            depth=np.array([850.4, 851.0]),
            value=np.array([131.0, 129.0]),
            hide=np.zeros(2, dtype=np.int8),
        )
        cf2 = ChannelFrame(
            wits_id="0117", db_id=104, mnemonic="WOB",
            description="Weight on Bit", units="klbs", source="WITS",
            bias=0, scale=1, depth_offset=0, log_by="depth",
            time=np.array(["2025-07-03T21:34:48", "2025-07-03T21:35:00"], dtype="datetime64[s]"),
            depth=np.array([850.4, 851.0]),
            value=np.array([77.0, 76.8]),
            hide=np.zeros(2, dtype=np.int8),
        )
        db = WellDatabase(
            source_ip="172.26.69.100",
            dump_epoch=1760755485076,
            dump_timestamp="2025-10-17T12:04:45Z",
            channels={"0121": cf1, "0117": cf2},
        )
        return db

    def test_assigned_returns_channel(self):
        db = self._make_db()
        db.assignments = {"standpipe_pressure": "0121"}
        cf = db.assigned("standpipe_pressure")
        assert cf.mnemonic == "PP"

    def test_assigned_raises_on_missing(self):
        db = self._make_db()
        with pytest.raises(KeyError):
            db.assigned("nonexistent")

    def test_has_required_true(self):
        db = self._make_db()
        db.assignments = {"standpipe_pressure": "0121", "wob": "0117"}
        assert db.has_required(["standpipe_pressure", "wob"])

    def test_has_required_false(self):
        db = self._make_db()
        db.assignments = {"standpipe_pressure": "0121"}
        assert not db.has_required(["standpipe_pressure", "wob"])

    def test_available_channels(self):
        db = self._make_db()
        summaries = db.available_channels()
        assert len(summaries) == 2
        wits_ids = {s.wits_id for s in summaries}
        assert wits_ids == {"0121", "0117"}

    def test_depth_range(self):
        db = self._make_db()
        lo, hi = db.depth_range()
        assert lo == pytest.approx(850.4)
        assert hi == pytest.approx(851.0)
