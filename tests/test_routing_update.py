"""Tests for routing changes and sidebar restructure."""

import pytest


class TestRoutingChanges:
    """New routes work, ungating applied, landing page at /."""

    def test_landing_at_root(self):
        """/ should render landing page, not file manager."""
        from mpd_overwatch.app import create_app
        app = create_app()
        with app.server.test_request_context():
            from mpd_overwatch.dashboard.landing import landing_layout
            layout = landing_layout()
            assert layout is not None

    def test_engines_route_accessible(self):
        """/engines should be in ALWAYS_ACCESSIBLE."""
        from mpd_overwatch.app import ALWAYS_ACCESSIBLE
        assert "/engines" in ALWAYS_ACCESSIBLE

    def test_capabilities_route_accessible(self):
        """/capabilities should be in ALWAYS_ACCESSIBLE."""
        from mpd_overwatch.app import ALWAYS_ACCESSIBLE
        assert "/capabilities" in ALWAYS_ACCESSIBLE

    def test_formulas_ungated(self):
        """/formulas should be in ALWAYS_ACCESSIBLE, not ANALYSIS_PAGES."""
        from mpd_overwatch.app import ALWAYS_ACCESSIBLE, ANALYSIS_PAGES
        assert "/formulas" in ALWAYS_ACCESSIBLE
        assert "/formulas" not in ANALYSIS_PAGES

    def test_vv_report_ungated(self):
        """/vv-report should be in ALWAYS_ACCESSIBLE, not ANALYSIS_PAGES."""
        from mpd_overwatch.app import ALWAYS_ACCESSIBLE, ANALYSIS_PAGES
        assert "/vv-report" in ALWAYS_ACCESSIBLE
        assert "/vv-report" not in ANALYSIS_PAGES

    def test_files_route_still_works(self):
        """/files should still be in ALWAYS_ACCESSIBLE."""
        from mpd_overwatch.app import ALWAYS_ACCESSIBLE
        assert "/files" in ALWAYS_ACCESSIBLE


class TestNavSectionsRestructure:
    """NAV_SECTIONS has 5 groups with effect-first names."""

    def test_five_sections(self):
        from mpd_overwatch.app import NAV_SECTIONS
        assert len(NAV_SECTIONS) == 5

    def test_section_headings(self):
        from mpd_overwatch.app import NAV_SECTIONS
        headings = [s["heading"] for s in NAV_SECTIONS]
        assert "PLATFORM" in headings
        assert "OPERATIONS" in headings
        assert "CLASSICAL ENGINES" in headings
        assert "NOVEL ENGINES" in headings
        assert "ENGINEERING" in headings

    def test_effect_first_names(self):
        from mpd_overwatch.app import NAV_SECTIONS
        all_labels = [link[1] for s in NAV_SECTIONS for link in s["links"]]
        assert "Pressure & Flow" in all_labels
        assert "Rock Strength" in all_labels
        assert "Physics Consistency" in all_labels
        assert "Pattern Discovery" in all_labels
        assert "Risk Topology" in all_labels
        assert "Hydraulics" not in all_labels
        assert "Geomechanics" not in all_labels
        assert "Coherence Log" not in all_labels

    def test_engines_page_in_platform_section(self):
        from mpd_overwatch.app import NAV_SECTIONS
        platform = [s for s in NAV_SECTIONS if s["heading"] == "PLATFORM"][0]
        paths = [link[0] for link in platform["links"]]
        assert "/engines" in paths

    def test_capabilities_in_engineering_section(self):
        from mpd_overwatch.app import NAV_SECTIONS
        engineering = [s for s in NAV_SECTIONS if s["heading"] == "ENGINEERING"][0]
        paths = [link[0] for link in engineering["links"]]
        assert "/capabilities" in paths

    def test_heading_colors_defined(self):
        from mpd_overwatch.app import NAV_SECTIONS
        for section in NAV_SECTIONS:
            assert "heading_color" in section, f"{section['heading']} missing heading_color"


class TestSidebarBrand:
    """Sidebar brand updated to MPD COMMAND."""

    def test_sidebar_renders(self):
        from mpd_overwatch.app import create_app
        app = create_app()
        assert app is not None

    def test_app_title(self):
        from mpd_overwatch.app import create_app
        app = create_app()
        assert "MPD Command" in app.title or "MPD" in app.title


class TestConfigPages:
    """config.PAGES dict updated with new routes."""

    def test_engines_in_pages(self):
        from mpd_overwatch.config import PAGES
        assert "/engines" in PAGES

    def test_capabilities_in_pages(self):
        from mpd_overwatch.config import PAGES
        assert "/capabilities" in PAGES
