"""Layer 1 — passive annotations on Plotly figures.

State bands, validity shading, artifact markers, health indicators.
All rendering is optional enrichment — never blocks page rendering.

detail_level parameter:
  "compact" = MWD hand (rig site, action-oriented) — minimal decoration
  "full"    = drilling engineer (office, deep analysis) — full labels + tooltips
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import plotly.graph_objects as go

from mpd_overwatch.knowledge.dossier import ChannelDossier, ArtifactSignature, StateProfile
from mpd_overwatch.knowledge.rig_state import RigState

# State colors (visual mapping only — no numeric values)
STATE_COLORS = {
    "DRILLING": "rgba(0, 200, 100, 0.08)",
    "CONNECTION": "rgba(255, 200, 0, 0.08)",
    "CIRCULATING": "rgba(0, 150, 255, 0.08)",
    "STATIC": "rgba(128, 128, 128, 0.08)",
    "TRIPPING": "rgba(200, 100, 255, 0.08)",
    "SLIDING": "rgba(255, 150, 0, 0.08)",
    "REAMING": "rgba(255, 100, 100, 0.08)",
    "BACKREAMING_DOWN": "rgba(200, 50, 50, 0.08)",
    "WASHING": "rgba(100, 200, 255, 0.08)",
    "UNKNOWN": "rgba(200, 200, 200, 0.05)",
}


def add_state_bands(
    fig: go.Figure,
    states: Optional[List[RigState]],
    depths: np.ndarray,
    detail_level: str = "full",
) -> None:
    """Add semi-transparent colored bands for each rig state segment.

    detail_level="compact": major state transitions only (DRILLING vs non-DRILLING)
    detail_level="full": all states with labels
    """
    if states is None or len(states) == 0 or len(depths) == 0:
        return

    n = min(len(states), len(depths))
    states = states[:n]
    depths = depths[:n]

    # Find contiguous runs of the same state
    runs = []
    current_state = states[0]
    start_idx = 0

    for i in range(1, n):
        if states[i] != current_state:
            runs.append((current_state, start_idx, i - 1))
            current_state = states[i]
            start_idx = i
    runs.append((current_state, start_idx, n - 1))

    # In compact mode, merge minor states into "other"
    if detail_level == "compact":
        major_states = {RigState.DRILLING, RigState.CONNECTION, RigState.TRIPPING}
        merged_runs = []
        for state, s, e in runs:
            if state not in major_states:
                state_name = "UNKNOWN"
            else:
                state_name = state.name if isinstance(state, RigState) else str(state)
            merged_runs.append((state_name, s, e))

        # Consolidate adjacent same-name runs
        consolidated = [merged_runs[0]]
        for name, s, e in merged_runs[1:]:
            if name == consolidated[-1][0]:
                consolidated[-1] = (name, consolidated[-1][1], e)
            else:
                consolidated.append((name, s, e))

        for state_name, s, e in consolidated:
            color = STATE_COLORS.get(state_name, STATE_COLORS["UNKNOWN"])
            fig.add_shape(
                type="rect",
                x0=float(depths[s]), x1=float(depths[e]),
                y0=0, y1=1, yref="paper",
                fillcolor=color, line_width=0,
                layer="below",
            )
    else:
        # Full mode: all states with labels
        for state, s, e in runs:
            state_name = state.name if isinstance(state, RigState) else str(state)
            color = STATE_COLORS.get(state_name, STATE_COLORS["UNKNOWN"])
            fig.add_shape(
                type="rect",
                x0=float(depths[s]), x1=float(depths[e]),
                y0=0, y1=1, yref="paper",
                fillcolor=color, line_width=0,
                layer="below",
            )


def add_validity_shading(
    fig: go.Figure,
    dossier: ChannelDossier,
    states: Optional[List[RigState]],
    detail_level: str = "full",
) -> None:
    """Dim data points where the channel is non-informative in the current state.

    Adds gray shading rectangles over regions where the channel's
    state profile shows informative=False.
    """
    if states is None or len(states) == 0:
        return

    # Find state regions where channel is non-informative
    for state_name, profile in dossier.state_profiles.items():
        if profile.informative is False:
            # This state is not informative — add subtle gray overlay
            # We don't have depth arrays here, so we just mark it noted
            pass  # Visual implementation depends on depth array availability


def add_artifact_markers(
    fig: go.Figure,
    artifacts: List[ArtifactSignature],
    depths: np.ndarray,
    transition_indices: List[int],
    detail_level: str = "full",
) -> None:
    """Add markers at state transitions where artifacts are known.

    detail_level="compact": small marker only
    detail_level="full": marker + hover text with cause and settle distance
    """
    if not artifacts or len(depths) == 0:
        return

    for artifact in artifacts:
        for idx in transition_indices:
            if 0 <= idx < len(depths):
                depth = float(depths[idx])

                if detail_level == "compact":
                    text = artifact.name
                else:
                    text = (
                        f"{artifact.name}<br>"
                        f"Cause: {artifact.cause}<br>"
                        f"Settle: {artifact.settle_distance_ft:.1f} ft / "
                        f"{artifact.settle_time_s:.0f}s<br>"
                        f"Peak deviation: {artifact.peak_deviation:.1f}"
                    )

                fig.add_annotation(
                    x=depth, y=1, yref="paper",
                    text="!" if detail_level == "compact" else "! Artifact",
                    showarrow=True, arrowhead=2,
                    ax=0, ay=-30,
                    hovertext=text,
                    font=dict(size=10),
                )
                break  # One marker per artifact, at first matching transition


def channel_health_indicator(
    dossier: ChannelDossier,
    current_value: float,
    current_state: str,
) -> Dict:
    """Check if a channel's current value is within its expected range for the state.

    Returns {"status": "normal"|"out_of_range"|"unknown", "detail": str}
    """
    profile = dossier.state_profiles.get(current_state)

    if profile is None or profile.range is None:
        return {"status": "unknown", "detail": f"No profile for state {current_state}"}

    low, high = profile.range

    if low <= current_value <= high:
        return {
            "status": "normal",
            "detail": f"{dossier.canonical}: {current_value} within [{low:.1f}, {high:.1f}]",
        }
    else:
        return {
            "status": "out_of_range",
            "detail": f"{dossier.canonical}: {current_value} outside [{low:.1f}, {high:.1f}]",
        }
