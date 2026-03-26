# tests/test_sql_parser.py
import pytest
import numpy as np
from pathlib import Path
from mpd_overwatch.data.sql_parser import SQLDumpParser

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
