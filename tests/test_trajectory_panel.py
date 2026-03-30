"""Tests for trajectory_panel — minimum curvature and wellpath rendering."""

import numpy as np
import pytest

from mpd_overwatch.dashboard.trajectory_panel import (
    minimum_curvature,
    render_survey_summary,
    render_trajectory_3d,
    render_trajectory_2d,
    render_trajectory_panel,
)


class TestMinimumCurvature:
    """Minimum curvature coordinate conversion."""

    def test_vertical_well(self):
        """Vertical well: inc=0, azm=0 → TVD equals MD, no departure."""
        md = np.array([0, 1000, 2000, 3000])
        inc = np.array([0, 0, 0, 0])
        azm = np.array([0, 0, 0, 0])
        north, east, tvd = minimum_curvature(md, inc, azm)
        np.testing.assert_allclose(tvd, md, atol=0.1)
        np.testing.assert_allclose(north, 0, atol=0.1)
        np.testing.assert_allclose(east, 0, atol=0.1)

    def test_build_section(self):
        """Build section: inclination increases → TVD < MD, departure grows."""
        md = np.array([0, 500, 1000, 1500, 2000])
        inc = np.array([0, 15, 30, 45, 60])
        azm = np.array([90, 90, 90, 90, 90])  # Due east
        north, east, tvd = minimum_curvature(md, inc, azm)
        # TVD should be less than MD due to build
        assert tvd[-1] < md[-1]
        # East departure should be positive (azm=90°)
        assert east[-1] > 0
        # North should be near zero (azm=90°)
        assert abs(north[-1]) < east[-1] * 0.1

    def test_horizontal_well(self):
        """Horizontal section: inc=90° → TVD stays constant, departure grows."""
        md = np.array([0, 1000, 2000, 3000])
        inc = np.array([90, 90, 90, 90])
        azm = np.array([0, 0, 0, 0])  # Due north
        north, east, tvd = minimum_curvature(md, inc, azm)
        # TVD should stay near zero after first point
        assert abs(tvd[-1] - tvd[0]) < 1.0  # Nearly constant
        # North departure should grow
        assert north[-1] > 1000

    def test_empty_arrays(self):
        """Empty input → empty output."""
        n, e, t = minimum_curvature(np.array([]), np.array([]), np.array([]))
        assert len(n) == 0
        assert len(e) == 0
        assert len(t) == 0

    def test_single_station(self):
        """Single station → origin."""
        n, e, t = minimum_curvature(
            np.array([100]), np.array([5]), np.array([45])
        )
        assert len(n) == 1
        assert n[0] == 0
        assert e[0] == 0
        assert t[0] == 0

    def test_s_turn(self):
        """S-turn: build then drop → TVD increases but departure reverses."""
        md = np.array([0, 500, 1000, 1500, 2000])
        inc = np.array([0, 30, 60, 30, 0])  # Build then drop
        azm = np.array([0, 0, 0, 0, 0])
        north, east, tvd = minimum_curvature(md, inc, azm)
        # TVD should increase monotonically
        assert all(tvd[i] >= tvd[i-1] - 0.1 for i in range(1, len(tvd)))


class TestRendering:
    """Plotly figure generation."""

    def _survey_data(self):
        md = np.array([0, 500, 1000, 1500, 2000, 2500])
        inc = np.array([0, 5, 15, 30, 45, 60])
        azm = np.array([45, 45, 45, 45, 45, 45])
        return md, inc, azm

    def test_render_3d_returns_figure(self):
        fig = render_trajectory_3d(*self._survey_data())
        assert hasattr(fig, "data")
        assert len(fig.data) >= 1  # At least wellpath trace

    def test_render_2d_returns_two_figures(self):
        plan, section = render_trajectory_2d(*self._survey_data())
        assert hasattr(plan, "data")
        assert hasattr(section, "data")

    def test_render_summary_returns_div(self):
        summary = render_survey_summary(*self._survey_data())
        # Should be a Dash Div
        assert summary is not None

    def test_render_full_panel(self):
        panel = render_trajectory_panel(*self._survey_data())
        assert panel is not None

    def test_render_panel_insufficient_stations(self):
        md = np.array([100])
        inc = np.array([5])
        azm = np.array([45])
        panel = render_trajectory_panel(md, inc, azm)
        assert panel is not None  # Should show "insufficient" message
