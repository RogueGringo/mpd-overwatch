"""V&V Section 6: UI Integration (End-to-End).

Principle: File load -> channel assign -> every analysis page renders
without errors. Workflow state transitions correctly.
"""

import pytest
from dash import html

from mpd_overwatch.dashboard.app_state import AppState, WorkflowStage


class TestFileLoadPath:
    """data_store.load_file() with real SQL dump."""

    def test_load_returns_header(self, depth_file_path):
        from mpd_overwatch.dashboard.data_store import load_file, clear
        try:
            header = load_file(str(depth_file_path))
            assert isinstance(header, dict)
            assert "channel_count" in header
            assert header["channel_count"] >= 50
            assert "filepath" in header
        finally:
            clear()

    def test_is_loaded_after_load(self, depth_file_path):
        from mpd_overwatch.dashboard.data_store import load_file, is_loaded, clear
        try:
            load_file(str(depth_file_path))
            assert is_loaded()
        finally:
            clear()

    def test_get_well_database_after_load(self, depth_file_path):
        from mpd_overwatch.dashboard.data_store import load_file, get_well_database, clear
        try:
            load_file(str(depth_file_path))
            db = get_well_database()
            assert db is not None
            assert len(db.channels) > 0
        finally:
            clear()


class TestChannelAssignmentPath:
    """After load, auto-suggest and apply assignments."""

    def test_auto_suggest_produces_mappings(self, depth_file_path):
        from mpd_overwatch.dashboard.data_store import load_file, get_well_database, clear
        from mpd_overwatch.data.engine_manifest import auto_suggest_assignments
        try:
            load_file(str(depth_file_path))
            db = get_well_database()
            suggestions = auto_suggest_assignments(db)
            assert len(suggestions) >= 5
        finally:
            clear()

    def test_all_pages_render_after_full_workflow(self, depth_file_path):
        from mpd_overwatch.dashboard.data_store import load_file, get_well_database, clear
        from mpd_overwatch.data.engine_manifest import auto_suggest_assignments
        try:
            load_file(str(depth_file_path))
            db = get_well_database()
            suggestions = auto_suggest_assignments(db)
            db.assignments = dict(suggestions)
            assignments_data = dict(suggestions)

            # Standard-signature pages
            page_modules = [
                ("mpd_overwatch.dashboard.hydraulics", "page_hydraulics"),
                ("mpd_overwatch.dashboard.pore_pressure", "page_pore_pressure"),
                ("mpd_overwatch.dashboard.geomechanics", "page_geomechanics"),
                ("mpd_overwatch.dashboard.formation_damage", "page_formation_damage"),
                ("mpd_overwatch.dashboard.supervisory_panel", "page_supervisory"),
                ("mpd_overwatch.dashboard.hmu_panel", "page_hmu"),
                ("mpd_overwatch.dashboard.topology", "page_topology"),
                ("mpd_overwatch.dashboard.persistent_homology_page", "page_persistent_homology"),
                ("mpd_overwatch.dashboard.atft_analysis", "page_atft_analysis"),
            ]

            import importlib
            for mod_path, func_name in page_modules:
                mod = importlib.import_module(mod_path)
                page_func = getattr(mod, func_name)
                result = page_func(assignments_data)
                assert isinstance(result, html.Div), f"{func_name} returned {type(result).__name__}"

            # well_overview has different signature
            from mpd_overwatch.dashboard.well_overview import page_well_overview
            well_header = {"source_ip": "172.26.69.100", "channel_count": len(db.channels)}
            result = page_well_overview(well_header=well_header, assignments_data=assignments_data)
            assert isinstance(result, html.Div)
        finally:
            clear()


class TestWorkflowStageTransitions:
    """AppState round-trip and workflow stage transitions."""

    def test_app_state_roundtrip(self):
        state = AppState()
        state.stage = WorkflowStage.ANALYSIS
        state.filepath = "test.sql"
        state.well_header = {"source_ip": "172.26.69.100"}
        d = state.to_dict()
        restored = AppState.from_dict(d)
        assert restored.stage == WorkflowStage.ANALYSIS
        assert restored.filepath == "test.sql"
        assert restored.well_header["source_ip"] == "172.26.69.100"

    def test_workflow_stages_valid(self):
        for stage in WorkflowStage:
            assert isinstance(stage.value, str)
            assert len(stage.value) > 0

    def test_stage_transitions_via_roundtrip(self):
        state = AppState()
        assert state.stage == WorkflowStage.FILE_SELECT
        state.stage = WorkflowStage.CHANNEL_SELECT
        state.filepath = "172.26.69.100_1760755485076.sql"
        d1 = state.to_dict()
        assert d1["stage"] == "channel_select"
        state.stage = WorkflowStage.ANALYSIS
        d2 = state.to_dict()
        r2 = AppState.from_dict(d2)
        assert r2.stage == WorkflowStage.ANALYSIS
        assert r2.filepath == "172.26.69.100_1760755485076.sql"

    def test_backward_compat_las_filepath(self):
        d = {"stage": "analysis", "las_filepath": "old.las"}
        state = AppState.from_dict(d)
        assert state.filepath == "old.las"


class TestErrorResilience:
    """Pages handle missing data gracefully."""

    def test_pages_return_div_with_no_db(self):
        from mpd_overwatch.dashboard.data_store import clear
        clear()
        from mpd_overwatch.dashboard.hydraulics import page_hydraulics
        result = page_hydraulics(None)
        assert isinstance(result, html.Div)

    def test_pages_return_div_with_empty_assignments(self, depth_file_path):
        from mpd_overwatch.dashboard.data_store import load_file, clear
        try:
            load_file(str(depth_file_path))
            from mpd_overwatch.dashboard.hydraulics import page_hydraulics
            result = page_hydraulics({})
            assert isinstance(result, html.Div)
        finally:
            clear()
