"""Health Scoring — roll up per-channel alerts into domain and system health.

Computes health scores at three levels:
  1. Channel health — single channel's alert status
  2. Domain health — aggregate of all channels in an operational domain
  3. System health — aggregate of all domain healths

Scores are 0-100 where 100 = no issues, 0 = critical.
Status colors: green (80-100), yellow (50-79), red (0-49).
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Health status
# ---------------------------------------------------------------------------

class HealthStatus(enum.Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


def _score_to_status(score: float) -> HealthStatus:
    if score >= 80:
        return HealthStatus.GREEN
    elif score >= 50:
        return HealthStatus.YELLOW
    return HealthStatus.RED


STATUS_COLORS = {
    HealthStatus.GREEN: "#2ecc71",
    HealthStatus.YELLOW: "#f1c40f",
    HealthStatus.RED: "#e74c3c",
}


# ---------------------------------------------------------------------------
# Health dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ChannelHealth:
    """Health status for a single channel."""
    canonical: str
    score: float            # 0-100
    status: HealthStatus
    alert_count: int
    worst_severity: str     # "ok", "info", "warning", "critical"


@dataclass
class DomainHealth:
    """Aggregate health for one operational domain."""
    domain_name: str
    score: float            # 0-100, average of channel scores
    status: HealthStatus
    channel_count: int
    alert_count: int
    worst_channel: Optional[str]  # channel with lowest score
    channels: List[ChannelHealth] = field(default_factory=list)


@dataclass
class SystemHealth:
    """Overall system health — aggregate of all domains."""
    score: float            # 0-100, weighted average of domain scores
    status: HealthStatus
    domain_count: int
    total_alerts: int
    domains: Dict[str, DomainHealth] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Severity weights
# ---------------------------------------------------------------------------

_SEVERITY_PENALTY = {
    "critical": 40,
    "warning": 20,
    "info": 5,
    "ok": 0,
}


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def score_channel(canonical: str, alerts: list) -> ChannelHealth:
    """Score a single channel based on its alerts.

    Parameters
    ----------
    canonical : str
        Canonical channel name.
    alerts : list
        Alert objects with .severity attribute (or dicts with "severity" key).
    """
    if not alerts:
        return ChannelHealth(
            canonical=canonical,
            score=100.0,
            status=HealthStatus.GREEN,
            alert_count=0,
            worst_severity="ok",
        )

    total_penalty = 0
    worst = "ok"
    for alert in alerts:
        sev = getattr(alert, "severity", None) or alert.get("severity", "info")
        penalty = _SEVERITY_PENALTY.get(sev, 5)
        total_penalty += penalty
        if _SEVERITY_PENALTY.get(sev, 0) > _SEVERITY_PENALTY.get(worst, 0):
            worst = sev

    score = max(0.0, 100.0 - total_penalty)
    return ChannelHealth(
        canonical=canonical,
        score=score,
        status=_score_to_status(score),
        alert_count=len(alerts),
        worst_severity=worst,
    )


def score_domain(
    domain_name: str,
    channel_names: List[str],
    alerts_by_channel: Dict[str, list],
) -> DomainHealth:
    """Score a domain by aggregating its channel health scores.

    Parameters
    ----------
    domain_name : str
        Human-readable domain name.
    channel_names : list of str
        Canonical channel names in this domain.
    alerts_by_channel : dict
        {canonical_name: [alerts]} for channels with alerts.
    """
    if not channel_names:
        return DomainHealth(
            domain_name=domain_name,
            score=100.0,
            status=HealthStatus.GREEN,
            channel_count=0,
            alert_count=0,
            worst_channel=None,
        )

    channel_healths = []
    for ch in channel_names:
        ch_alerts = alerts_by_channel.get(ch, [])
        channel_healths.append(score_channel(ch, ch_alerts))

    total_alerts = sum(ch.alert_count for ch in channel_healths)
    avg_score = sum(ch.score for ch in channel_healths) / len(channel_healths)
    worst = min(channel_healths, key=lambda c: c.score)

    return DomainHealth(
        domain_name=domain_name,
        score=round(avg_score, 1),
        status=_score_to_status(avg_score),
        channel_count=len(channel_names),
        alert_count=total_alerts,
        worst_channel=worst.canonical if worst.score < 100 else None,
        channels=channel_healths,
    )


def score_system(domain_healths: Dict[str, DomainHealth]) -> SystemHealth:
    """Compute overall system health from domain healths.

    Parameters
    ----------
    domain_healths : dict
        {domain_name: DomainHealth} for all active domains.
    """
    if not domain_healths:
        return SystemHealth(
            score=100.0,
            status=HealthStatus.GREEN,
            domain_count=0,
            total_alerts=0,
        )

    scores = [dh.score for dh in domain_healths.values()]
    total_alerts = sum(dh.alert_count for dh in domain_healths.values())
    avg = sum(scores) / len(scores)

    return SystemHealth(
        score=round(avg, 1),
        status=_score_to_status(avg),
        domain_count=len(domain_healths),
        total_alerts=total_alerts,
        domains=dict(domain_healths),
    )


# ---------------------------------------------------------------------------
# Convenience: compute full health from data_store state
# ---------------------------------------------------------------------------

def compute_full_health(
    alerts: list,
    assigned_channels: Dict[str, str],
) -> SystemHealth:
    """Compute system health from alerts and channel assignments.

    Uses operational_domains to group channels, then scores each domain.

    Parameters
    ----------
    alerts : list
        All alerts from data_store.get_alerts().
    assigned_channels : dict
        {canonical_name: wits_id} from db.assignments.

    Returns
    -------
    SystemHealth
    """
    try:
        from mpd_overwatch.knowledge.operational_domains import (
            get_domain,
            OperationalDomain,
        )
    except ImportError:
        # operational_domains not built yet — return default
        return SystemHealth(
            score=100.0, status=HealthStatus.GREEN,
            domain_count=0, total_alerts=len(alerts),
        )

    # Group alerts by channel
    alerts_by_channel: Dict[str, list] = {}
    for alert in alerts:
        ch = getattr(alert, "channel", None) or alert.get("channel", "unknown")
        alerts_by_channel.setdefault(ch, []).append(alert)

    # Group assigned channels by operational domain
    domain_channels: Dict[str, List[str]] = {}
    for canonical in assigned_channels:
        try:
            domain = get_domain(canonical)
            domain_name = domain.value
        except Exception:
            domain_name = "Derived Calculations"
        domain_channels.setdefault(domain_name, []).append(canonical)

    # Score each domain
    domain_healths = {}
    for domain_name, channels in domain_channels.items():
        domain_healths[domain_name] = score_domain(
            domain_name, channels, alerts_by_channel,
        )

    return score_system(domain_healths)
