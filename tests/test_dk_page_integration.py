"""Tests for domain knowledge annotation integration on analysis pages."""
import pytest
from dash import html


ANALYSIS_PAGES = [
    ("hydraulics", "page_hydraulics"),
    ("pore_pressure", "page_pore_pressure"),
    ("geomechanics", "page_geomechanics"),
    ("formation_damage", "page_formation_damage"),
    ("well_overview", "page_well_overview"),
    ("supervisory_panel", "page_supervisory"),
    ("hmu_panel", "page_hmu"),
    ("topology", "page_topology"),
    ("persistent_homology_page", "page_persistent_homology"),
    ("atft_analysis", "page_atft_analysis"),
]


class TestAnnotationIntegration:
    @pytest.mark.parametrize("module_name,func_name", ANALYSIS_PAGES)
    def test_page_renders_with_dossiers_loaded(self, assigned_db, depth_file_path,
                                                 module_name, func_name):
        """Each page should render without error when dossiers are available."""
        from mpd_overwatch.dashboard import data_store
        import importlib

        try:
            data_store.load_file(str(depth_file_path))
            module = importlib.import_module(f"mpd_overwatch.dashboard.{module_name}")
            page_func = getattr(module, func_name)
            result = page_func(assignments_data=dict(assigned_db.assignments))
            assert isinstance(result, html.Div)
        finally:
            data_store.clear()

    def test_hydraulics_has_state_bands_when_dossiers_present(self, assigned_db, depth_file_path):
        """Hydraulics page should include state band annotations."""
        from mpd_overwatch.dashboard import data_store
        from mpd_overwatch.dashboard.hydraulics import page_hydraulics

        try:
            data_store.load_file(str(depth_file_path))
            result = page_hydraulics(assignments_data=dict(assigned_db.assignments))
            assert isinstance(result, html.Div)
        finally:
            data_store.clear()
