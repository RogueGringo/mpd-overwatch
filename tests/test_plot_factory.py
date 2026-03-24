"""Tests for plot factory -- figure generation and PNG export."""

import numpy as np
import pytest

from mpd_overwatch.core.plot_factory import (
    plot_raw_channels,
    plot_channel_characterization,
    plot_coherence_log,
    export_figure_png,
    list_available_plots,
)


class TestPlotFunctions:
    """Test that plot functions return valid Plotly figures."""

    def _make_channel_data(self):
        n = 100
        depths = np.linspace(5000, 15000, n)
        return {
            "depth_md": depths,
            "spp": np.random.rand(n) * 3000 + 1000,
            "rop": np.random.rand(n) * 200,
            "gamma_ray": np.random.rand(n) * 150,
        }

    def test_raw_channels_returns_figure(self):
        import plotly.graph_objects as go
        data = self._make_channel_data()
        fig = plot_raw_channels(data)
        assert isinstance(fig, go.Figure)

    def test_raw_channels_has_traces(self):
        data = self._make_channel_data()
        fig = plot_raw_channels(data)
        # One trace per channel (excluding depth_md which is the x-axis)
        assert len(fig.data) >= 3

    def test_channel_characterization_returns_figure(self):
        import plotly.graph_objects as go
        chars = [
            {"name": "SPP", "physics_domain": "hydraulic", "mpd_relevance": "primary"},
            {"name": "ROP", "physics_domain": "mechanical", "mpd_relevance": "secondary"},
            {"name": "GR", "physics_domain": "formation", "mpd_relevance": "contextual"},
        ]
        fig = plot_channel_characterization(chars)
        assert isinstance(fig, go.Figure)

    def test_coherence_log_returns_figure(self):
        import plotly.graph_objects as go
        n = 50
        depths = np.linspace(5000, 15000, n)
        scores = np.random.rand(n) * 0.3 + 0.7  # 0.7-1.0
        fig = plot_coherence_log(depths, scores)
        assert isinstance(fig, go.Figure)

    def test_list_available_plots(self):
        plots = list_available_plots()
        assert isinstance(plots, list)
        assert len(plots) >= 3
        assert "raw_channels" in plots


class TestPngExport:
    """Test PNG export via kaleido."""

    def test_export_creates_file(self, tmp_path):
        import plotly.graph_objects as go
        fig = go.Figure(data=[go.Scatter(x=[1, 2, 3], y=[1, 2, 3])])
        out_path = tmp_path / "test.png"
        export_figure_png(fig, out_path)
        assert out_path.exists()
        assert out_path.stat().st_size > 0

    def test_export_with_dimensions(self, tmp_path):
        import plotly.graph_objects as go
        fig = go.Figure(data=[go.Scatter(x=[1, 2], y=[1, 2])])
        out_path = tmp_path / "sized.png"
        export_figure_png(fig, out_path, width=1200, height=800)
        assert out_path.exists()
