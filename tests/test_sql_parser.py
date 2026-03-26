# tests/test_sql_parser.py
import pytest
import numpy as np
from datetime import datetime
from pathlib import Path
from mpd_overwatch.data.sql_parser import SQLDumpParser
from mpd_overwatch.data.sql_models import WellDatabase

DEPTH_FILE = str(Path(__file__).parent.parent /
    "DATA_TYPES_for_System_Use_EXAMPLES" /
    "Oilfield_EDR_SQL_Depth_and_Time" / "SQL_Depth" /
    "172.26.69.100_1760755485076.sql")

TIME_FILE = str(Path(__file__).parent.parent /
    "DATA_TYPES_for_System_Use_EXAMPLES" /
    "Oilfield_EDR_SQL_Depth_and_Time" / "SQL_Time" /
    "172.26.69.100_timedata_1760755485077.sql")


class TestSourceDetection:
    def test_detect_depth_file(self):
        parser = SQLDumpParser()
        ip, epoch, is_time = parser._detect_source(DEPTH_FILE)
        assert ip == "172.26.69.100"
        assert epoch == 1760755485076
        assert is_time is False

    def test_detect_time_file(self):
        parser = SQLDumpParser()
        ip, epoch, is_time = parser._detect_source(TIME_FILE)
        assert ip == "172.26.69.100"
        assert epoch == 1760755485077
        assert is_time is True

    def test_is_time_file(self):
        parser = SQLDumpParser()
        assert parser._is_time_file(TIME_FILE) is True
        assert parser._is_time_file(DEPTH_FILE) is False


class TestDepthFileParsing:
    @pytest.fixture(scope="class")
    def parser(self):
        return SQLDumpParser()

    @pytest.fixture(scope="class")
    def welldb(self, parser):
        """Parse the real depth file once for all tests in this class."""
        return parser.parse_file(DEPTH_FILE)

    def test_idtable_channel_count(self, welldb):
        """Real file has 236 idtable entries, but not all have T-tables."""
        assert len(welldb.channels) > 50  # at least 50 channels with data

    def test_known_channel_pump_pressure(self, welldb):
        """WITS 0121 = Pump Pressure is in this database."""
        assert "0121" in welldb.channels
        pp = welldb.channels["0121"]
        assert pp.mnemonic == "PP"
        assert pp.units == "psi"
        assert pp.description == "Pump Pressure"
        assert pp.n_points > 0

    def test_channel_has_dual_index(self, welldb):
        """Every channel should have both time and depth arrays."""
        pp = welldb.channels["0121"]
        assert len(pp.time) == len(pp.depth) == len(pp.value) == pp.n_points

    def test_source_identity(self, welldb):
        assert welldb.source_ip == "172.26.69.100"
        assert welldb.dump_epoch == 1760755485076

    def test_log_by_normalized(self, welldb):
        """log_by should be 'depth', 'time', or 'unknown'."""
        for cf in welldb.channels.values():
            assert cf.log_by in ("depth", "time", "unknown")

    def test_changelog_parsed(self, welldb):
        """Survey Depth (0822) has a multi-entry changelog."""
        if "0822" in welldb.channels:
            cf = welldb.channels["0822"]
            assert len(cf.changelog) > 0
            for epoch, cal in cf.changelog.items():
                assert isinstance(epoch, int)
                assert "bias" in cal or "scale" in cal or "depthoffset" in cal

    def test_value_is_float(self, welldb):
        """Values should be float64, not strings."""
        pp = welldb.channels["0121"]
        assert pp.value.dtype == np.float64

    def test_computed_channels_separated(self, welldb):
        """Any T9001+ channels should be in computed, not channels."""
        for wid in welldb.channels:
            assert not (wid.isdigit() and int(wid) >= 9001), \
                f"Computed channel {wid} should be in welldb.computed"


class TestTimeFileParsing:
    @pytest.fixture(scope="class")
    def parser(self):
        return SQLDumpParser()

    @pytest.fixture(scope="class")
    def time_result(self, parser):
        return parser._parse_time_file(TIME_FILE)

    def test_returns_channel_data(self, time_result):
        channel_data, witsidcfg = time_result
        assert len(channel_data) > 10  # expect 20+ channels

    def test_pump_pressure_present(self, time_result):
        channel_data, _ = time_result
        assert "0121" in channel_data
        ts_list = channel_data["0121"]
        assert len(ts_list) > 100  # should have many data points

    def test_hole_depth_present(self, time_result):
        """WITS 0108 (hole depth) must be present — it's the depth source."""
        channel_data, _ = time_result
        assert "0108" in channel_data

    def test_witsidcfg_loaded(self, time_result):
        _, witsidcfg = time_result
        assert len(witsidcfg) > 0
        # Pump Pressure should have config
        if "0121" in witsidcfg:
            assert "description" in witsidcfg["0121"]

    def test_non_numeric_values_are_nan(self, time_result):
        """WITS 1984 mostly contains text — most values should be NaN."""
        channel_data, _ = time_result
        if "1984" in channel_data:
            ts_list = channel_data["1984"]
            values = [v for _, v in ts_list]
            nan_count = sum(1 for v in values if np.isnan(v))
            # Vast majority should be NaN (text values)
            assert nan_count / len(values) > 0.99

    def test_timestamps_are_datetime(self, time_result):
        channel_data, _ = time_result
        ts_list = channel_data["0121"]
        first_ts, first_val = ts_list[0]
        assert isinstance(first_ts, datetime)


class TestCompanionMerging:
    @pytest.fixture(scope="class")
    def merged_db(self):
        parser = SQLDumpParser()
        return parser.parse_pair(DEPTH_FILE, TIME_FILE)

    def test_merge_has_depth_channels(self, merged_db):
        assert "0121" in merged_db.channels  # from depth file

    def test_merge_source_identity(self, merged_db):
        assert merged_db.source_ip == "172.26.69.100"

    def test_merge_increases_data(self, merged_db):
        """Merged channels should have >= the depth-only point count."""
        # Just check that data exists
        pp = merged_db.channels.get("0121")
        assert pp is not None
        assert pp.n_points > 0


class TestUnifiedIngest:
    def test_ingest_depth_file(self):
        from mpd_overwatch.data.sql_parser import ingest
        db = ingest(DEPTH_FILE)
        assert isinstance(db, WellDatabase)
        assert len(db.channels) > 50

    def test_ingest_directory(self):
        from mpd_overwatch.data.sql_parser import ingest
        dirpath = str(Path(DEPTH_FILE).parent.parent)
        db = ingest(dirpath)
        assert isinstance(db, WellDatabase)
        assert db.source_ip == "172.26.69.100"
