"""V&V Section 4: Shadow Table Round-Trip.

Principle: Computed results written as shadow SQL can be re-ingested
and produce identical values.
"""

from pathlib import Path

import numpy as np
import pytest

from mpd_overwatch.data.shadow_tables import (
    COMPUTED_CHANNELS,
    build_computed_channel,
    write_shadow_sql,
)


class TestBuildComputedChannel:
    """build_computed_channel() produces valid ChannelFrames."""

    @pytest.mark.parametrize("name", list(COMPUTED_CHANNELS.keys()))
    def test_channel_has_correct_witsid(self, name):
        meta = COMPUTED_CHANNELS[name]
        times = np.array(
            ["2025-07-01T12:00:00", "2025-07-01T12:01:00"],
            dtype="datetime64[s]",
        )
        depths = np.array([10000.0, 10001.0])
        values = np.array([12.5, 12.6])
        cf = build_computed_channel(name, times, depths, values)
        expected_witsid = str(meta["witsid_base"])
        assert cf.wits_id == expected_witsid

    @pytest.mark.parametrize("name", list(COMPUTED_CHANNELS.keys()))
    def test_channel_has_correct_units(self, name):
        meta = COMPUTED_CHANNELS[name]
        times = np.array(["2025-07-01T12:00:00"], dtype="datetime64[s]")
        depths = np.array([10000.0])
        values = np.array([12.5])
        cf = build_computed_channel(name, times, depths, values)
        assert cf.units == meta["units"]

    @pytest.mark.parametrize("name", list(COMPUTED_CHANNELS.keys()))
    def test_channel_identity_calibration(self, name):
        times = np.array(["2025-07-01T12:00:00"], dtype="datetime64[s]")
        depths = np.array([10000.0])
        values = np.array([42.0])
        cf = build_computed_channel(name, times, depths, values)
        assert cf.scale == 1.0
        assert cf.bias == 0.0
        np.testing.assert_array_equal(cf.calibrated_value, values)


class TestWriteShadowSQL:
    """write_shadow_sql() produces valid pg_dump-compatible SQL."""

    def test_write_creates_file(self, tmp_path):
        times = np.array(
            ["2025-07-01T12:00:00", "2025-07-01T12:01:00"],
            dtype="datetime64[s]",
        )
        depths = np.array([10000.0, 10001.0])
        values = np.array([12.5, 12.6])
        cf = build_computed_channel("ecd_computed", times, depths, values)
        output = tmp_path / "shadow.sql"
        write_shadow_sql({"ecd_computed": cf}, output)
        assert output.exists()
        content = output.read_text()
        assert len(content) > 100
        assert "CREATE TABLE" in content or "COPY" in content

    def test_write_contains_idtable_insert(self, tmp_path):
        times = np.array(["2025-07-01T12:00:00"], dtype="datetime64[s]")
        depths = np.array([10000.0])
        values = np.array([12.5])
        cf = build_computed_channel("mse", times, depths, values)
        output = tmp_path / "shadow_meta.sql"
        write_shadow_sql({"mse": cf}, output)
        content = output.read_text()
        assert "idtable" in content.lower() or "INSERT" in content

    def test_write_contains_copy_block(self, tmp_path):
        """T-table data is emitted as COPY blocks the parser can read."""
        times = np.array(
            ["2025-07-01T12:00:00", "2025-07-01T12:01:00"],
            dtype="datetime64[s]",
        )
        depths = np.array([10000.0, 10001.0])
        values = np.array([12.5, 12.6])
        cf = build_computed_channel("ecd_computed", times, depths, values)
        output = tmp_path / "copy_test.sql"
        write_shadow_sql({"ecd_computed": cf}, output)
        content = output.read_text()
        assert 'COPY public."T9001"' in content
        assert "\\." in content

    def test_write_contains_all_data_rows(self, tmp_path):
        """Every value appears in the written SQL."""
        n = 10
        times = np.array(
            [f"2025-07-01T12:{i:02d}:00" for i in range(n)],
            dtype="datetime64[s]",
        )
        depths = np.linspace(10000, 10009, n)
        values = np.linspace(12.5, 13.4, n)
        cf = build_computed_channel("ecd_computed", times, depths, values)
        output = tmp_path / "rows_test.sql"
        write_shadow_sql({"ecd_computed": cf}, output)
        content = output.read_text()
        # Each value should appear as text in the COPY block
        for v in values:
            assert str(v) in content


class TestRoundTrip:
    """Write computed channels -> re-parse -> verify identical values.

    The SQL parser (_detect_source) requires filenames matching the UMS EDR
    pattern: <ip>_<epoch>.sql.  Shadow files are written with a compatible
    name so ingest() can handle them.

    Note: write_shadow_sql() emits idtable metadata via INSERT statements,
    but the parser reads idtable from COPY blocks.  As a result, metadata
    (mnemonic, units, etc.) does not survive the round-trip — only T-table
    data values do.  Channels with witsid >= 9001 land in WellDatabase.computed.
    """

    @staticmethod
    def _shadow_filename(tmp_path: Path) -> Path:
        """Return a filename that matches the parser's expected pattern."""
        return tmp_path / "10.0.0.1_1000000000000.sql"

    def test_values_roundtrip_single_channel(self, tmp_path):
        """Write one computed channel, re-ingest, verify values match."""
        from mpd_overwatch.data.sql_parser import ingest

        times = np.array(
            ["2025-07-01T12:00:00", "2025-07-01T12:01:00", "2025-07-01T12:02:00"],
            dtype="datetime64[s]",
        )
        depths = np.array([10000.0, 10001.0, 10002.0])
        values = np.array([12.5, 12.6, 12.7])
        cf = build_computed_channel("ecd_computed", times, depths, values)

        output = self._shadow_filename(tmp_path)
        write_shadow_sql({"ecd_computed": cf}, output)

        reparsed = ingest(str(output))
        wid = cf.wits_id  # "9001"

        # Computed channels (witsid >= 9001) go into reparsed.computed
        assert wid in reparsed.computed, (
            f"WITS ID {wid} not in computed channels: "
            f"{list(reparsed.computed.keys())}"
        )
        reparsed_cf = reparsed.computed[wid]

        np.testing.assert_array_almost_equal(
            reparsed_cf.value, values, decimal=10,
            err_msg="ECD round-trip: values don't match",
        )
        np.testing.assert_array_almost_equal(
            reparsed_cf.depth, depths, decimal=5,
            err_msg="ECD round-trip: depths don't match",
        )

    def test_values_roundtrip_multiple_channels(self, tmp_path):
        """Write multiple computed channels, re-ingest, all survive."""
        from mpd_overwatch.data.sql_parser import ingest

        times = np.array(
            ["2025-07-01T12:00:00", "2025-07-01T12:01:00"],
            dtype="datetime64[s]",
        )
        depths = np.array([10000.0, 10001.0])
        channels_dict = {}
        expected = {}
        for name in ["ecd_computed", "mse", "fd_index"]:
            seed = abs(hash(name)) % (2**31)
            vals = np.array([np.random.default_rng(seed).random() * 100,
                             np.random.default_rng(seed).random() * 50])
            cf = build_computed_channel(name, times, depths, vals)
            channels_dict[name] = cf
            expected[cf.wits_id] = vals

        output = self._shadow_filename(tmp_path)
        write_shadow_sql(channels_dict, output)

        reparsed = ingest(str(output))

        for wid, exp_vals in expected.items():
            assert wid in reparsed.computed, (
                f"WITS ID {wid} missing from round-trip. "
                f"Available: {list(reparsed.computed.keys())}"
            )
            np.testing.assert_array_almost_equal(
                reparsed.computed[wid].value, exp_vals, decimal=10,
                err_msg=f"Round-trip mismatch for WITS ID {wid}",
            )

    def test_ecd_roundtrip_from_real_data(self, assigned_db, tmp_path):
        """Compute ECD from real data, write, re-parse, verify values."""
        from mpd_overwatch.core.engine_wrappers import compute_ecd
        from mpd_overwatch.data.sql_parser import ingest

        try:
            mw_cf = assigned_db.assigned("mud_weight_in")
            spp_cf = assigned_db.assigned("standpipe_pressure")
        except KeyError:
            pytest.skip("Required channels not assigned")

        n = min(50, len(mw_cf.calibrated_value), len(spp_cf.calibrated_value))
        if n < 2:
            pytest.skip("Not enough data points")

        ecd_values = np.zeros(n)
        for i in range(n):
            mw = float(mw_cf.calibrated_value[i])
            afp = float(spp_cf.calibrated_value[i]) * 0.6
            tvd = float(mw_cf.depth[i]) if mw_cf.depth[i] > 0 else 10000.0
            if tvd <= 0:
                tvd = 10000.0
            result = compute_ecd(mw=mw, afp=afp, tvd=tvd)
            ecd_values[i] = result.value

        times = mw_cf.time[:n]
        depths = mw_cf.depth[:n]
        cf = build_computed_channel("ecd_computed", times, depths, ecd_values)

        output = self._shadow_filename(tmp_path)
        write_shadow_sql({"ecd_computed": cf}, output)

        reparsed = ingest(str(output))

        # Computed channels (witsid >= 9001) go into reparsed.computed
        assert cf.wits_id in reparsed.computed, (
            f"WITS ID {cf.wits_id} not found in re-parsed computed channels: "
            f"{list(reparsed.computed.keys())}"
        )
        reparsed_cf = reparsed.computed[cf.wits_id]

        np.testing.assert_array_almost_equal(
            reparsed_cf.value, ecd_values, decimal=10,
            err_msg="ECD round-trip: values don't match",
        )
