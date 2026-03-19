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


class TestSemanticPrime:
    """Well scenario descriptions use semantic prime: measurements only."""

    BANNED_ADJECTIVES = [
        "standard", "narrow", "significant", "critical", "extreme",
        "excessive", "catastrophic", "optimal", "advanced", "superior",
        "comprehensive", "innovative", "cutting-edge", "state-of-the-art",
        "robust", "powerful", "intelligent", "smart", "good", "bad",
        "best", "worst", "excellent", "poor", "great", "terrible",
        "amazing", "incredible", "outstanding",
    ]

    def test_no_adjectives_in_scenarios(self):
        """No banned adjectives in well scenario descriptions."""
        import sys
        import importlib

        # Import app module to access WELL_SCENARIOS
        from mpd_overwatch import app as app_module
        importlib.reload(app_module)
        scenarios = app_module.WELL_SCENARIOS

        violations = []
        for key, scenario in scenarios.items():
            desc = scenario.get("description", "").lower()
            for adj in self.BANNED_ADJECTIVES:
                if adj in desc:
                    violations.append(
                        f"Scenario '{key}': contains '{adj}' in description"
                    )

        assert not violations, (
            f"Semantic prime violations found:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


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
