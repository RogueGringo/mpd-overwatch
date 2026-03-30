"""Tests for health_scoring — channel, domain, and system health rollup."""

import pytest

from mpd_overwatch.knowledge.health_scoring import (
    ChannelHealth,
    DomainHealth,
    HealthStatus,
    SystemHealth,
    score_channel,
    score_domain,
    score_system,
)


class TestChannelHealth:

    def test_no_alerts_green(self):
        h = score_channel("flow_in", [])
        assert h.score == 100.0
        assert h.status == HealthStatus.GREEN
        assert h.alert_count == 0

    def test_info_alerts_minor_penalty(self):
        alerts = [{"severity": "info"}, {"severity": "info"}]
        h = score_channel("spp", alerts)
        assert h.score == 90.0  # 100 - 5 - 5
        assert h.status == HealthStatus.GREEN

    def test_warning_alert_yellow(self):
        alerts = [{"severity": "warning"}, {"severity": "info"}]
        h = score_channel("torque", alerts)
        assert h.score == 75.0  # 100 - 20 - 5
        assert h.status == HealthStatus.YELLOW
        assert h.worst_severity == "warning"

    def test_critical_alert_red(self):
        alerts = [{"severity": "critical"}, {"severity": "warning"}]
        h = score_channel("flow_out", alerts)
        assert h.score == 40.0  # 100 - 40 - 20
        assert h.status == HealthStatus.RED

    def test_score_floors_at_zero(self):
        alerts = [{"severity": "critical"}] * 5
        h = score_channel("test", alerts)
        assert h.score == 0.0


class TestDomainHealth:

    def test_no_channels(self):
        h = score_domain("Empty", [], {})
        assert h.score == 100.0
        assert h.channel_count == 0

    def test_all_healthy(self):
        h = score_domain("MPD Ops", ["flow_in", "flow_out", "spp"], {})
        assert h.score == 100.0
        assert h.status == HealthStatus.GREEN
        assert h.channel_count == 3

    def test_mixed_health(self):
        alerts = {
            "flow_in": [{"severity": "warning"}],  # 80
            "spp": [],                               # 100
        }
        h = score_domain("MPD Ops", ["flow_in", "spp"], alerts)
        assert h.score == 90.0  # (80 + 100) / 2
        assert h.worst_channel == "flow_in"

    def test_worst_channel_identified(self):
        alerts = {
            "torque": [{"severity": "critical"}],  # 60
            "rpm": [{"severity": "info"}],           # 95
        }
        h = score_domain("Rig Health", ["torque", "rpm"], alerts)
        assert h.worst_channel == "torque"


class TestSystemHealth:

    def test_no_domains(self):
        h = score_system({})
        assert h.score == 100.0
        assert h.domain_count == 0

    def test_all_green(self):
        domains = {
            "MPD": DomainHealth("MPD", 95.0, HealthStatus.GREEN, 3, 0, None),
            "Rig": DomainHealth("Rig", 100.0, HealthStatus.GREEN, 4, 0, None),
        }
        h = score_system(domains)
        assert h.score == 97.5
        assert h.status == HealthStatus.GREEN
        assert h.domain_count == 2

    def test_mixed_status(self):
        domains = {
            "MPD": DomainHealth("MPD", 40.0, HealthStatus.RED, 3, 5, "flow_in"),
            "Rig": DomainHealth("Rig", 100.0, HealthStatus.GREEN, 4, 0, None),
        }
        h = score_system(domains)
        assert h.score == 70.0  # (40 + 100) / 2
        assert h.status == HealthStatus.YELLOW
        assert h.total_alerts == 5
