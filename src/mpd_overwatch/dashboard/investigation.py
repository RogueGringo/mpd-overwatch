"""Layer 3 — interactive investigation query handlers.

Three query types:
  point_query   — what's happening at this depth?
  channel_query — tell me everything about this channel
  interval_query — summarize this depth interval

Optional LLM narrative synthesis via LM Studio at localhost:1234.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import numpy as np

from mpd_overwatch.data.sql_models import WellDatabase
from mpd_overwatch.knowledge.dossier import ChannelDossier
from mpd_overwatch.knowledge.rig_state import RigState

logger = logging.getLogger(__name__)


def point_query(
    db: WellDatabase,
    dossier_set,
    depth: float,
) -> Dict[str, Any]:
    """What's happening at this depth?

    Returns rig state, all channel values at nearest sample,
    each value checked against dossier state profile.
    """
    result: Dict[str, Any] = {
        "depth": depth,
        "state": "unknown",
        "channels": [],
        "transitions_nearby": [],
    }

    if dossier_set is None:
        return result

    # Find nearest sample index across all channels
    # Use a reference channel (first one with data) to find index
    ref_idx = None
    for wid, cf in db.channels.items():
        if cf.n_points > 0:
            depths = cf.depth
            if len(depths) > 0:
                idx = int(np.argmin(np.abs(depths - depth)))
                ref_idx = idx
                break

    if ref_idx is None:
        return result

    # Get rig state at this index
    if dossier_set.states is not None and ref_idx < len(dossier_set.states):
        state = dossier_set.states[ref_idx]
        result["state"] = state.value if isinstance(state, RigState) else str(state)

    # Get all channel values at this index
    state_name = result["state"]
    for wid, dossier in dossier_set.dossiers.items():
        cf = db.channels.get(wid)
        if cf is None or cf.n_points == 0:
            continue

        # Find index in this specific channel closest to target depth
        chan_depths = cf.depth
        if len(chan_depths) == 0:
            continue
        chan_idx = int(np.argmin(np.abs(chan_depths - depth)))

        if chan_idx >= cf.n_points:
            continue

        value = float(cf.calibrated_value[chan_idx])
        if not np.isfinite(value):
            continue

        chan_info: Dict[str, Any] = {
            "canonical": dossier.canonical,
            "wits_id": wid,
            "value": value,
            "units": dossier.units,
            "depth": float(chan_depths[chan_idx]),
        }

        # Check health against state profile
        # State profiles are keyed by state.value (lowercase)
        profile = dossier.state_profiles.get(state_name)
        if profile is not None and profile.range is not None:
            low, high = profile.range
            if low <= value <= high:
                chan_info["health"] = "normal"
            else:
                chan_info["health"] = "out_of_range"
                chan_info["expected_range"] = [low, high]
        else:
            chan_info["health"] = "unknown"

        result["channels"].append(chan_info)

    # Find nearby transitions
    for t in dossier_set.transitions:
        # Check if transition index maps to a depth near our target
        for wid, cf in db.channels.items():
            if cf.n_points > 0 and t.index < len(cf.depth):
                t_depth = float(cf.depth[t.index])
                if abs(t_depth - depth) < 100:  # within 100 ft
                    result["transitions_nearby"].append({
                        "from_state": t.from_state.value,
                        "to_state": t.to_state.value,
                        "depth": t_depth,
                    })
                break

    return result


def channel_query(
    dossier_set,
    canonical: str,
) -> Optional[Dict[str, Any]]:
    """Tell me everything about this channel.

    Returns full dossier as structured dict.
    """
    if dossier_set is None:
        return {"found": False}

    dossier = dossier_set.get_by_canonical(canonical)
    if dossier is None:
        return {"found": False}

    result: Dict[str, Any] = {
        "found": True,
        "identity": {
            "wits_id": dossier.wits_id,
            "canonical": dossier.canonical,
            "mnemonic": dossier.mnemonic,
            "units": dossier.units,
            "physics_domain": dossier.physics_domain.value,
            "index_type": dossier.index_type.value,
        },
        "operational_meaning": {},
        "state_profiles": {},
        "relationships": [],
        "artifacts": [],
        "provenance": {
            "encoded_fields": dossier.encoded_fields,
            "discovered_fields": dossier.discovered_fields,
        },
    }

    # Operational meaning
    if dossier.what_it_measures:
        result["operational_meaning"]["what_it_measures"] = dossier.what_it_measures
    if dossier.physical_phenomenon:
        result["operational_meaning"]["physical_phenomenon"] = dossier.physical_phenomenon
    if dossier.trust_conditions:
        result["operational_meaning"]["trust_conditions"] = dossier.trust_conditions
    if dossier.common_misinterpretations:
        result["operational_meaning"]["common_misinterpretations"] = dossier.common_misinterpretations

    # State profiles
    for state_name, profile in dossier.state_profiles.items():
        result["state_profiles"][state_name] = {
            "range": list(profile.range) if profile.range else None,
            "distribution": profile.distribution,
            "variance": profile.variance,
            "trend": profile.trend,
            "informative": profile.informative,
        }

    # Relationships
    for rel in dossier.relationships:
        result["relationships"].append({
            "target": rel.target_channel,
            "type": rel.relationship_type,
            "state": rel.state,
            "strength": rel.strength,
            "lag": rel.lag,
        })

    # Artifacts
    for art in dossier.artifacts:
        result["artifacts"].append({
            "name": art.name,
            "transition": list(art.state_transition),
            "settle_profile": art.settle_profile,
            "peak_deviation": art.peak_deviation,
            "settle_distance_ft": art.settle_distance_ft,
            "settle_time_s": art.settle_time_s,
            "cause": art.cause,
            "correction": art.correction_strategy,
        })

    # Well context
    if dossier.overall_range:
        result["well_context"] = {
            "overall_range": list(dossier.overall_range),
            "depth_trend": dossier.depth_trend,
        }

    return result


def interval_query(
    db: WellDatabase,
    dossier_set,
    start_depth: float,
    end_depth: float,
) -> Dict[str, Any]:
    """Summarize this depth interval.

    Returns state timeline, transitions, per-channel trend summary.
    """
    result: Dict[str, Any] = {
        "start_depth": start_depth,
        "end_depth": end_depth,
        "state_timeline": [],
        "transitions": [],
        "channel_summaries": [],
    }

    if dossier_set is None:
        return result

    # Find sample indices corresponding to depth range
    # Use a reference channel
    ref_depths = None
    for wid, cf in db.channels.items():
        if cf.n_points > 0:
            ref_depths = cf.depth
            break

    if ref_depths is None or len(ref_depths) == 0:
        return result

    # Find index range
    mask = (ref_depths >= start_depth) & (ref_depths <= end_depth)
    indices = np.where(mask)[0]

    if len(indices) == 0:
        return result

    start_idx = int(indices[0])
    end_idx = int(indices[-1])

    # State timeline
    if dossier_set.states is not None:
        states_in_range = dossier_set.states[start_idx:end_idx + 1]
        if len(states_in_range) > 0:
            current_state = states_in_range[0]
            run_start = start_idx
            for i, s in enumerate(states_in_range[1:], start=start_idx + 1):
                if s != current_state:
                    state_name = current_state.value if isinstance(current_state, RigState) else str(current_state)
                    result["state_timeline"].append({
                        "state": state_name,
                        "start_idx": run_start,
                        "end_idx": i - 1,
                        "samples": i - run_start,
                    })
                    current_state = s
                    run_start = i
            # Final run
            state_name = current_state.value if isinstance(current_state, RigState) else str(current_state)
            result["state_timeline"].append({
                "state": state_name,
                "start_idx": run_start,
                "end_idx": end_idx,
                "samples": end_idx - run_start + 1,
            })

    # Transitions in range
    for t in dossier_set.transitions:
        if start_idx <= t.index <= end_idx:
            result["transitions"].append({
                "from_state": t.from_state.value,
                "to_state": t.to_state.value,
                "index": t.index,
            })

    # Channel summaries in this interval
    for wid, dossier in dossier_set.dossiers.items():
        cf = db.channels.get(wid)
        if cf is None or cf.n_points == 0:
            continue

        # Get values in depth range
        chan_mask = (cf.depth >= start_depth) & (cf.depth <= end_depth)
        values = cf.calibrated_value[chan_mask]
        finite = values[np.isfinite(values)]

        if len(finite) < 2:
            continue

        result["channel_summaries"].append({
            "canonical": dossier.canonical,
            "wits_id": wid,
            "n_points": len(finite),
            "min": float(np.min(finite)),
            "max": float(np.max(finite)),
            "mean": float(np.mean(finite)),
            "std": float(np.std(finite)),
        })

    return result


def _try_llm_narrative(structured_data: dict) -> Optional[str]:
    """Try to synthesize natural language from structured dossier data.

    Uses LM Studio at localhost:1234 if available.
    Returns None if LLM is not available — caller falls back to structured data.
    """
    try:
        import requests
        response = requests.post(
            "http://localhost:1234/v1/chat/completions",
            json={
                "model": "local-model",
                "messages": [
                    {"role": "system", "content": "You are a drilling engineer writing a morning report summary. Be concise and technical."},
                    {"role": "user", "content": f"Summarize this drilling data context:\n{json.dumps(structured_data, default=str)}"},
                ],
                "max_tokens": 500,
            },
            timeout=5,
        )
        if response.ok:
            return response.json()["choices"][0]["message"]["content"]
    except Exception:
        pass
    return None
