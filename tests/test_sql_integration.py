"""End-to-end integration: ingest real SQL → assign → engine input → shadow write."""

import pytest
import numpy as np
from pathlib import Path

from mpd_overwatch.data.sql_parser import SQLDumpParser, ingest
from mpd_overwatch.data.sql_models import WellDatabase
from mpd_overwatch.data.engine_manifest import (
    auto_suggest_assignments, prepare_engine_input, EngineManifest,
)
from mpd_overwatch.data.channel_profiles import save_profile, load_all_profiles, validate_profile
from mpd_overwatch.data.shadow_tables import build_computed_channel, write_shadow_sql

DEPTH_FILE = str(Path(__file__).parent.parent /
    "DATA_TYPES_for_System_Use_EXAMPLES" /
    "Oilfield_EDR_SQL_Depth_and_Time" / "SQL_Depth" /
    "172.26.69.100_1760755485076.sql")

TIME_FILE = str(Path(__file__).parent.parent /
    "DATA_TYPES_for_System_Use_EXAMPLES" /
    "Oilfield_EDR_SQL_Depth_and_Time" / "SQL_Time" /
    "172.26.69.100_timedata_1760755485077.sql")


class TestEndToEnd:
    @pytest.fixture(scope="class")
    def db(self):
        """Ingest real depth file."""
        return ingest(DEPTH_FILE)

    def test_ingest_produces_welldb(self, db):
        assert isinstance(db, WellDatabase)
        assert db.source_ip == "172.26.69.100"
        assert len(db.channels) > 50

    def test_auto_suggest_finds_channels(self, db):
        suggestions = auto_suggest_assignments(db)
        assert len(suggestions) > 5
        # Common channels should be suggested
        assert "standpipe_pressure" in suggestions or "hole_depth" in suggestions

    def test_assign_and_prepare_engine(self, db):
        suggestions = auto_suggest_assignments(db)
        db.assignments = dict(suggestions)

        manifest = EngineManifest(
            engine_id="hydraulics",
            required_channels=["hole_depth"],
            optional_channels=["standpipe_pressure", "wob"],
            min_points=1,
        )
        # Only test if hole_depth was suggested
        if "hole_depth" in db.assignments:
            result = prepare_engine_input(db, manifest)
            assert "hole_depth" in result
            assert result["hole_depth"].n_points > 0

    def test_save_load_profile(self, db, tmp_path):
        db.assignments = auto_suggest_assignments(db)
        path = tmp_path / "test_profiles.json"
        save_profile("Integration Test", db, path)
        profiles = load_all_profiles(path)
        assert "Integration Test" in profiles
        # Validate against same DB — should be all green
        results = validate_profile(profiles["Integration Test"], db)
        for vr in results.values():
            assert vr.status == "green"

    def test_shadow_table_write(self, db, tmp_path):
        db.assignments = auto_suggest_assignments(db)
        if "hole_depth" not in db.assignments:
            pytest.skip("No hole_depth assignment")
        hd = db.assigned("hole_depth")
        # Build fake ECD from hole depth (just for testing the write path)
        ecd_values = hd.value * 0.052 * 10.0  # rough ECD approximation
        cf = build_computed_channel("ecd_computed", hd.time, hd.depth, ecd_values)

        outpath = tmp_path / "computed.sql"
        write_shadow_sql({"ecd_computed": cf}, outpath)
        content = outpath.read_text()
        assert "T9001" in content
        assert "COMPUTED" in content

    def test_dual_index_from_depth_file(self, db):
        """Every channel from depth file should have both time and depth."""
        for wid, cf in db.channels.items():
            if cf.n_points > 0:
                assert len(cf.time) == len(cf.depth) == cf.n_points, \
                    f"Channel {wid} ({cf.mnemonic}): time/depth/value length mismatch"

    def test_computed_channels_separated(self, db):
        """Computed channels (witsid >= 9001) in db.computed, not db.channels."""
        for wid in db.channels:
            if wid.isdigit() and int(wid) >= 9001:
                pytest.fail(f"Computed channel {wid} in db.channels, should be in db.computed")
