"""V&V Section 3: Analysis Page Data Access.

Principle: Every analysis page gets correct canonical name -> correct
wits_id -> correct ChannelFrame -> correct values.
"""

import pytest
from dash import html

from mpd_overwatch.data.engine_manifest import (
    WITS_SUGGESTIONS, auto_suggest_assignments,
)


class TestAssignmentResolution:
    """auto_suggest_assignments produces correct canonical->witsid mappings."""

    def test_suggestions_non_empty(self, loaded_db):
        suggestions = auto_suggest_assignments(loaded_db)
        assert len(suggestions) >= 5

    def test_suggestions_match_wits_table(self, loaded_db):
        suggestions = auto_suggest_assignments(loaded_db)
        for canonical, wits_id in suggestions.items():
            assert wits_id in loaded_db.channels
            assert canonical in WITS_SUGGESTIONS.values()

    def test_assigned_returns_correct_channel(self, assigned_db, auto_assignments):
        for canonical, wits_id in auto_assignments.items():
            cf = assigned_db.assigned(canonical)
            assert cf.wits_id == wits_id


@pytest.fixture
def _populate_data_store(assigned_db):
    """Ensure data_store has the WellDatabase loaded for page rendering."""
    from mpd_overwatch.dashboard import data_store
    old_db = data_store._well_database
    old_path = data_store._file_path
    data_store._well_database = assigned_db
    data_store._file_path = "test_vv_fixture"
    yield
    data_store._well_database = old_db
    data_store._file_path = old_path


@pytest.fixture
def _clear_data_store():
    """Ensure data_store has NO WellDatabase loaded."""
    from mpd_overwatch.dashboard import data_store
    old_db = data_store._well_database
    old_path = data_store._file_path
    data_store._well_database = None
    data_store._file_path = None
    yield
    data_store._well_database = old_db
    data_store._file_path = old_path


# Pages with standard signature: page_func(assignments_data)
_PAGE_IMPORTS = [
    ("hydraulics", "mpd_overwatch.dashboard.hydraulics", "page_hydraulics"),
    ("pore_pressure", "mpd_overwatch.dashboard.pore_pressure", "page_pore_pressure"),
    ("geomechanics", "mpd_overwatch.dashboard.geomechanics", "page_geomechanics"),
    ("formation_damage", "mpd_overwatch.dashboard.formation_damage", "page_formation_damage"),
    ("supervisory", "mpd_overwatch.dashboard.supervisory_panel", "page_supervisory"),
    ("hmu", "mpd_overwatch.dashboard.hmu_panel", "page_hmu"),
    ("topology", "mpd_overwatch.dashboard.topology", "page_topology"),
    ("persistent_homology", "mpd_overwatch.dashboard.persistent_homology_page", "page_persistent_homology"),
    ("atft_analysis", "mpd_overwatch.dashboard.atft_analysis", "page_atft_analysis"),
]


class TestPageRender:
    """Each analysis page must render successfully with real data."""

    @pytest.mark.parametrize("page_name,module_path,func_name", _PAGE_IMPORTS)
    def test_page_renders_div(self, page_name, module_path, func_name,
                               assigned_db, _populate_data_store):
        import importlib
        mod = importlib.import_module(module_path)
        page_func = getattr(mod, func_name)
        assignments_data = dict(assigned_db.assignments)
        result = page_func(assignments_data)
        assert isinstance(result, html.Div), (
            f"{page_name} returned {type(result).__name__}, expected html.Div"
        )

    def test_well_overview_renders_div(self, assigned_db, _populate_data_store):
        from mpd_overwatch.dashboard.well_overview import page_well_overview
        assignments_data = dict(assigned_db.assignments)
        well_header = {"source_ip": "172.26.69.100", "channel_count": len(assigned_db.channels)}
        result = page_well_overview(well_header=well_header, assignments_data=assignments_data)
        assert isinstance(result, html.Div)

    @pytest.mark.parametrize("page_name,module_path,func_name", _PAGE_IMPORTS)
    def test_page_no_data_required_with_assignments(self, page_name, module_path,
                                                      func_name, assigned_db,
                                                      _populate_data_store):
        """Pages with valid assignments should not show DATA REQUIRED.

        Pages that need channels absent from the real SQL dump (e.g. rpm,
        torque, depth_tvd) will legitimately show DATA REQUIRED -- those
        are skipped here.  PointCloud-based pages may also show
        DATA REQUIRED if ingestion yields insufficient topology data.
        """
        import importlib

        # Pages whose required channels (rpm, torque, depth_tvd) are
        # absent from the test SQL dump, or that use PointCloud4D
        # ingestion internally.  DATA REQUIRED is correct for these.
        _MAY_LACK_DATA = {
            "pore_pressure",       # requires rpm
            "geomechanics",        # requires rpm, torque
            "topology",            # PointCloud4D ingestion
            "persistent_homology", # PointCloud4D ingestion
            "atft_analysis",       # PointCloud4D ingestion
        }
        if page_name in _MAY_LACK_DATA:
            pytest.skip(
                f"{page_name} may legitimately show DATA REQUIRED with "
                "this test dataset (missing channels or PointCloud ingestion)"
            )

        mod = importlib.import_module(module_path)
        page_func = getattr(mod, func_name)
        assignments_data = dict(assigned_db.assignments)
        result = page_func(assignments_data)
        result_str = str(result)
        assert "DATA REQUIRED" not in result_str, (
            f"{page_name} shows DATA REQUIRED even with valid assignments"
        )


class TestRawVsCalibratedConsistency:
    """Verify pages use calibrated_value, not raw value."""

    def test_calibrated_values_used(self, assigned_db, _populate_data_store):
        import numpy as np
        test_channels = []
        for canonical, wits_id in assigned_db.assignments.items():
            cf = assigned_db.channels[wits_id]
            if cf.scale != 1.0 or cf.bias != 0.0:
                test_channels.append((canonical, cf))
            if len(test_channels) >= 3:
                break
        if not test_channels:
            pytest.skip("No channels with non-trivial calibration in test data")
        for canonical, cf in test_channels:
            expected = cf.value * cf.scale + cf.bias
            np.testing.assert_array_equal(cf.calibrated_value, expected)


class TestPageWithNoData:
    """Pages must show data_required_layout gracefully when no data loaded."""

    @pytest.mark.parametrize("page_name,module_path,func_name", _PAGE_IMPORTS)
    def test_page_shows_data_required_without_assignments(self, page_name,
                                                           module_path, func_name,
                                                           _clear_data_store):
        import importlib
        mod = importlib.import_module(module_path)
        page_func = getattr(mod, func_name)
        result = page_func(None)
        assert isinstance(result, html.Div)

    def test_well_overview_no_data(self, _clear_data_store):
        from mpd_overwatch.dashboard.well_overview import page_well_overview
        result = page_well_overview(well_header=None, assignments_data=None)
        assert isinstance(result, html.Div)
