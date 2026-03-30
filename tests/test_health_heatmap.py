"""Tests for health_heatmap — domain strips and heatmap rendering."""

import pytest

from mpd_overwatch.knowledge.health_scoring import (
    ChannelHealth,
    DomainHealth,
    HealthStatus,
    SystemHealth,
)
from mpd_overwatch.dashboard.health_heatmap import (
    render_domain_strips,
    render_health_heatmap,
)


def _make_system_health():
    """Build a SystemHealth with two domains for testing."""
    ch1 = ChannelHealth("flow_in", 95.0, HealthStatus.GREEN, 0, "ok")
    ch2 = ChannelHealth("spp", 70.0, HealthStatus.YELLOW, 2, "warning")
    ch3 = ChannelHealth("torque", 100.0, HealthStatus.GREEN, 0, "ok")
    ch4 = ChannelHealth("hookload", 45.0, HealthStatus.RED, 3, "critical")

    d1 = DomainHealth("MPD Ops", 82.5, HealthStatus.GREEN, 2, 2, "spp", [ch1, ch2])
    d2 = DomainHealth("Rig Health", 72.5, HealthStatus.YELLOW, 2, 3, "hookload", [ch3, ch4])

    return SystemHealth(
        score=77.5, status=HealthStatus.YELLOW,
        domain_count=2, total_alerts=5,
        domains={"MPD Ops": d1, "Rig Health": d2},
    )


def test_heatmap_renders():
    sh = _make_system_health()
    result = render_health_heatmap(sh)
    assert result is not None


def test_heatmap_empty_domains():
    sh = SystemHealth(score=100, status=HealthStatus.GREEN,
                      domain_count=0, total_alerts=0)
    result = render_health_heatmap(sh)
    assert result is not None


def test_domain_strips_renders():
    sh = _make_system_health()
    result = render_domain_strips(sh)
    assert result is not None


def test_domain_strips_empty():
    sh = SystemHealth(score=100, status=HealthStatus.GREEN,
                      domain_count=0, total_alerts=0)
    result = render_domain_strips(sh)
    assert result is not None
