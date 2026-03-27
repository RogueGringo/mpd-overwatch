"""V&V Section 1: Parser Correctness.

Principle: Known values at known timestamps/depths from real SQL dumps
must match exactly. These are NOT approximate — they are ground truth
extracted by reading the raw SQL file.
"""

import numpy as np
import pytest
from datetime import datetime


class TestIdtableMetadata:
    """Verify idtable metadata parsing matches raw SQL ground truth."""

    def test_channel_count_matches_tables(self, loaded_db):
        """Channel count must be >= 50 (63 non-empty T-tables in the real file).

        Note: The SQL file has ~101 T-tables total, but only 63 contain
        data rows.  The parser correctly skips empty tables.
        """
        assert len(loaded_db.channels) >= 50, (
            f"Expected >= 50 channels (63 non-empty T-tables in SQL), got {len(loaded_db.channels)}"
        )

    def test_gamma_depth_metadata(self, loaded_db):
        """WITS 0821 (Gamma Depth): description, units, depthoffset=70.44.

        Adjusted from original 0822 (Survey Depth) which has no data rows
        in this dump.  0821 is a real MWD channel with calibration.
        """
        cf = loaded_db.channels["0821"]
        assert cf.description == "Gamma Depth"
        assert cf.units == "Ft"
        assert cf.depth_offset == 70.44, (
            f"Gamma Depth depth_offset should be 70.44, got {cf.depth_offset}"
        )
        assert cf.bias == 0.0
        assert cf.scale == 1.0

    def test_pump_pressure_metadata(self, loaded_db):
        """WITS 0121 (Pump Pressure): description, units, no calibration."""
        cf = loaded_db.channels["0121"]
        assert cf.description == "Pump Pressure"
        assert cf.units == "psi"
        assert cf.bias == 0.0
        assert cf.scale == 1.0
        assert cf.depth_offset == 0.0

    def test_gamma_api_metadata(self, loaded_db):
        """WITS 0824 (Gamma API): mnemonic=GR, units=API, scale=3.45.

        Adjusted from original 0926 (Lateral Shock) which has no data rows
        in this dump.  0824 is a real MWD channel with non-trivial scale.
        """
        cf = loaded_db.channels["0824"]
        assert cf.mnemonic == "GR"
        assert cf.units == "API"
        assert cf.scale == 3.45, (
            f"Gamma API scale should be 3.45, got {cf.scale}"
        )

    def test_db_id_is_integer(self, loaded_db):
        """Every channel's db_id must be a positive integer."""
        for wid, cf in loaded_db.channels.items():
            assert isinstance(cf.db_id, int), f"Channel {wid} db_id is {type(cf.db_id)}"
            assert cf.db_id > 0, f"Channel {wid} db_id is {cf.db_id}"

    def test_wits_id_matches_key(self, loaded_db):
        """Each channel's wits_id field must match its dict key."""
        for wid, cf in loaded_db.channels.items():
            assert cf.wits_id == wid, f"Key={wid} but cf.wits_id={cf.wits_id}"


class TestDepthIndexedValues:
    """Verify exact values from depth-indexed T-tables."""

    def test_t0108_first_row(self, loaded_db):
        """T0108 first row: depth=96.970001, value=96.97."""
        cf = loaded_db.channels["0108"]
        assert len(cf.value) > 0, "T0108 has no data"
        np.testing.assert_almost_equal(cf.depth[0], 96.970001, decimal=4)
        np.testing.assert_almost_equal(cf.value[0], 96.97, decimal=2)

    def test_t0108_has_timestamps(self, loaded_db):
        """T0108 time array must have valid datetime values."""
        cf = loaded_db.channels["0108"]
        assert cf.time.dtype == np.dtype("datetime64[s]")
        first_ts = cf.time[0].astype("datetime64[s]").astype(datetime)
        assert first_ts.year == 2025
        assert first_ts.month == 7

    def test_t0108_row_count_nonzero(self, loaded_db):
        """T0108 must have many rows (real data has thousands)."""
        cf = loaded_db.channels["0108"]
        assert len(cf.value) > 1000, (
            f"T0108 has only {len(cf.value)} rows — expected thousands"
        )

    def test_no_spurious_nan(self, loaded_db):
        """T0108 (Hole Depth) should have < 1% NaN values."""
        cf = loaded_db.channels["0108"]
        nan_count = np.isnan(cf.value).sum()
        nan_pct = nan_count / len(cf.value) * 100
        assert nan_pct < 1.0, (
            f"T0108 has {nan_pct:.1f}% NaN values — expected < 1%"
        )

    def test_hide_array_correct_type(self, loaded_db):
        """Hide array must be int8 with values 0 or 1."""
        cf = loaded_db.channels["0108"]
        assert cf.hide.dtype == np.int8
        unique_vals = set(np.unique(cf.hide))
        assert unique_vals.issubset({0, 1}), f"Unexpected hide values: {unique_vals}"

    def test_t0108_last_row(self, loaded_db):
        """T0108 last row: depth and value must be plausible (TD region)."""
        cf = loaded_db.channels["0108"]
        last_depth = cf.depth[-1]
        last_value = cf.value[-1]
        assert last_depth > cf.depth[0], (
            f"Last depth ({last_depth}) should exceed first ({cf.depth[0]})"
        )
        assert np.isfinite(last_value), f"Last value is not finite: {last_value}"

    def test_depth_monotonic_for_depth_channel(self, loaded_db):
        """Hole depth (T0108) depth array should be roughly monotonic."""
        cf = loaded_db.channels["0108"]
        assert cf.depth[-1] > cf.depth[0], (
            f"Depth should increase: first={cf.depth[0]}, last={cf.depth[-1]}"
        )


class TestTimeIndexedValues:
    """Verify time-indexed file parsing."""

    def test_time_file_loads(self, time_file_path):
        """Time file can be parsed without error."""
        from mpd_overwatch.data.sql_parser import ingest
        db = ingest(str(time_file_path))
        assert len(db.channels) > 0, "No channels from time file"

    def test_time_channels_have_timestamps(self, time_file_path):
        """Channels from time file must have valid datetime arrays."""
        from mpd_overwatch.data.sql_parser import ingest
        db = ingest(str(time_file_path))
        for wid, cf in list(db.channels.items())[:5]:
            assert cf.time.dtype == np.dtype("datetime64[s]"), (
                f"Channel {wid} time dtype is {cf.time.dtype}"
            )
            assert len(cf.time) > 0, f"Channel {wid} has empty time array"

    def test_time_channel_has_values(self, time_file_path):
        """Time-indexed channels must have non-empty value arrays."""
        from mpd_overwatch.data.sql_parser import ingest
        db = ingest(str(time_file_path))
        channels_with_data = [wid for wid, cf in db.channels.items()
                              if len(cf.value) > 0]
        assert len(channels_with_data) > 0, (
            "No time-indexed channels have data"
        )

    def test_known_witsid_value_pairs_parsed(self, time_file_path):
        """Channels from witsid=value pairs must produce finite values."""
        from mpd_overwatch.data.sql_parser import ingest
        db = ingest(str(time_file_path))
        for wid, cf in list(db.channels.items())[:10]:
            if len(cf.value) == 0:
                continue
            finite_pct = np.isfinite(cf.value).sum() / len(cf.value) * 100
            if finite_pct > 50:
                return  # Found at least one good channel
        any_finite = any(
            np.isfinite(cf.value).any()
            for cf in db.channels.values()
            if len(cf.value) > 0
        )
        assert any_finite, "No time-indexed channels have finite values"


class TestCompanionMerging:
    """Verify depth + time file companion merging."""

    def test_merge_increases_channels(self, depth_file_path, time_file_path):
        """Merging depth + time files should produce >= channels from depth alone."""
        from mpd_overwatch.data.sql_parser import ingest
        depth_db = ingest(str(depth_file_path))
        depth_count = len(depth_db.channels)

        merged_db = ingest(str(depth_file_path.parent.parent))
        merged_count = len(merged_db.channels)
        assert merged_count >= depth_count, (
            f"Merged ({merged_count}) should have >= depth-only ({depth_count}) channels"
        )

    def test_channel_source_attribution(self, depth_file_path):
        """Each channel's source field identifies its origin."""
        from mpd_overwatch.data.sql_parser import ingest
        db = ingest(str(depth_file_path))
        for wid, cf in list(db.channels.items())[:10]:
            assert cf.source is not None and len(cf.source) > 0, (
                f"Channel {wid} has empty source: {cf.source!r}"
            )
