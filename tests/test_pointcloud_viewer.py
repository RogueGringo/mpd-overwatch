"""Tests for pointcloud_viewer — 3D scatter visualization."""

import numpy as np
import pytest

from mpd_overwatch.dashboard.pointcloud_viewer import (
    render_pointcloud_3d,
    render_pointcloud_panel,
)


def _make_channels():
    n = 500
    depth = np.linspace(0, 10000, n)
    return {
        "spp": np.random.uniform(500, 3000, n),
        "rop": np.random.uniform(10, 200, n),
        "hookload": np.random.uniform(100, 400, n),
        "torque": np.random.uniform(5000, 25000, n),
    }, depth


def test_render_3d_basic():
    channels, depth = _make_channels()
    fig = render_pointcloud_3d(channels, depth, "spp", "rop", "hookload")
    assert hasattr(fig, "data")
    assert len(fig.data) >= 1


def test_render_3d_with_color():
    channels, depth = _make_channels()
    fig = render_pointcloud_3d(channels, depth, "spp", "rop", "hookload",
                               color_channel="torque")
    assert len(fig.data) >= 1


def test_render_3d_missing_channel():
    channels, depth = _make_channels()
    fig = render_pointcloud_3d(channels, depth, "spp", "rop", "NONEXISTENT")
    # Should have an annotation about missing channel
    assert len(fig.layout.annotations) > 0


def test_render_3d_downsamples():
    channels, depth = _make_channels()
    fig = render_pointcloud_3d(channels, depth, "spp", "rop", "hookload",
                               max_points=100)
    # Should have fewer than 500 points
    assert len(fig.data[0].x) <= 100


def test_render_panel():
    channels, depth = _make_channels()
    panel = render_pointcloud_panel(channels, depth, ["spp", "rop", "hookload", "torque"])
    assert panel is not None


def test_render_panel_insufficient_channels():
    channels, depth = _make_channels()
    panel = render_pointcloud_panel(channels, depth, ["spp", "rop"])
    assert panel is not None  # Should show error message
