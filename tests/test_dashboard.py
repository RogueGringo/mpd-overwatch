"""Tests for dashboard pages and semantic prime compliance."""

import pytest


class TestATFTPage:
    """ATFT analysis page renders without error."""

    def test_atft_page_renders(self):
        """page_atft_analysis() returns a valid Dash layout."""
        from mpd_overwatch.dashboard.atft_analysis import page_atft_analysis
        from dash import html

        layout = page_atft_analysis()
        assert isinstance(layout, html.Div)
        # Should have children (at minimum: title + well info)
        assert len(layout.children) >= 2


class TestControlsPage:
    """Controls page renders without error."""

    def test_controls_page_renders(self):
        """page_controls() returns a valid Dash layout."""
        from mpd_overwatch.dashboard.controls import page_controls
        from dash import html

        layout = page_controls()
        assert isinstance(layout, html.Div)
        assert len(layout.children) >= 3  # title + params + hardware



class TestRoleFilter:
    """Role-based navigation filtering."""

    def test_hmu_sees_limited_nav(self):
        """HMU operator sees only operational pages."""
        from mpd_overwatch.dashboard.controls import filter_nav_for_role

        nav_sections = [
            {"heading": "OPS", "links": [("/", "Home", "01"), ("/hmu", "HMU", "02")]},
            {"heading": "ANALYSIS", "links": [("/atft", "ATFT", "03"), ("/topology", "Topo", "04")]},
            {"heading": "CONTROL", "links": [("/controls", "Controls", "05")]},
        ]

        filtered = filter_nav_for_role("hmu_operator", nav_sections)

        # HMU should see Home and HMU, not ATFT/topology/controls
        all_paths = [link[0] for section in filtered for link in section["links"]]
        assert "/" in all_paths
        assert "/hmu" in all_paths
        assert "/atft" not in all_paths
        assert "/controls" not in all_paths

    def test_consultant_sees_all(self):
        """Consultant sees all navigation items."""
        from mpd_overwatch.dashboard.controls import filter_nav_for_role

        nav_sections = [
            {"heading": "OPS", "links": [("/", "Home", "01")]},
            {"heading": "ANALYSIS", "links": [("/atft", "ATFT", "02"), ("/topology", "Topo", "03")]},
            {"heading": "CONTROL", "links": [("/controls", "Controls", "04")]},
        ]

        filtered = filter_nav_for_role("consultant", nav_sections)
        all_paths = [link[0] for section in filtered for link in section["links"]]
        assert "/" in all_paths
        assert "/atft" in all_paths
        assert "/controls" in all_paths


class TestHydraulicsPage:
    def test_hydraulics_page_renders(self):
        from mpd_overwatch.dashboard.hydraulics import page_hydraulics
        from dash import html
        layout = page_hydraulics()
        assert isinstance(layout, html.Div)
        assert len(layout.children) >= 2


class TestPorePressurePage:
    def test_pore_pressure_page_renders(self):
        from mpd_overwatch.dashboard.pore_pressure import page_pore_pressure
        from dash import html
        layout = page_pore_pressure()
        assert isinstance(layout, html.Div)
        assert len(layout.children) >= 2


class TestFormationDamagePage:
    def test_formation_damage_page_renders(self):
        from mpd_overwatch.dashboard.formation_damage import page_formation_damage
        from dash import html
        layout = page_formation_damage()
        assert isinstance(layout, html.Div)
        assert len(layout.children) >= 2


class TestPersistentHomologyPage:
    def test_persistent_homology_page_renders(self):
        from mpd_overwatch.dashboard.persistent_homology_page import page_persistent_homology
        from dash import html
        layout = page_persistent_homology()
        assert isinstance(layout, html.Div)
        assert len(layout.children) >= 2
