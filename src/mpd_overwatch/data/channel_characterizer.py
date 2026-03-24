"""Channel Characterizer -- domain-enhanced Alpha 1 physics classification.

Combines the Jones Framework Reality Epistemic Engine system prompt with
drilling physics domain knowledge to classify LAS channels by:
  - Physics domain (formation, mechanical, hydraulic, flow, control, survey)
  - Index relationship (time-native, depth-native, bridges-both)
  - MPD relevance (primary, secondary, contextual)

Uses the local LM Studio API (LFM2.5-1.2B or any loaded model) for inference.
Channels are batched for throughput (~5s per 10 channels at 125 tok/s).
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:1234/v1"
_DEFAULT_MODEL = "liquid/lfm2.5-1.2b"

PHYSICS_DOMAINS = frozenset({
    "formation", "mechanical", "hydraulic", "flow", "control", "survey",
})

INDEX_RELATIONSHIPS = frozenset({
    "time-native", "depth-native", "bridges-both",
})

MPD_RELEVANCE = frozenset({"primary", "secondary", "contextual"})

_ALPHA1_DRILLING_SYSTEM = """\
SYSTEM: DRILLING CHANNEL CLASSIFICATION ENGINE (Alpha-1 + Physics)

You are a discrete classification engine for drilling data channels.
Map each input channel to its physics domain using strict domain knowledge.

AXIOMATIC CONSTRAINTS:
[G1] Each channel belongs to exactly ONE physics domain.
[G2] Output must be the most direct classification. Zero meandering.
[G3] Classification must be justified by the channel's unit and physical meaning.

PHYSICS DOMAINS (choose exactly one per channel):
- formation: Measures ROCK properties at depth (gamma ray, resistivity, temperature). \
Invariant with time at a given depth.
- mechanical: Measures DRILLING SYSTEM inputs (WOB, torque, RPM, hookload). \
Force/energy applied by the rig to the bit.
- hydraulic: Measures FLUID PRESSURE in the wellbore (standpipe pressure, annular \
pressure, differential pressure, ECD, BHP). Pressure in psi or ppg.
- flow: Measures FLUID VOLUME RATE (flow in, flow out, mud volume, pit volume). \
Volume per time (gpm) or percentage.
- control: Measures CONTROL SYSTEM state (choke position, surface back pressure, \
AutoDriller setpoints). Human/system control actions.
- survey: Measures WELLBORE GEOMETRY (inclination, azimuth, TVD, measured depth, \
toolface). Position and direction.

INDEX RELATIONSHIPS (choose exactly one per channel):
- time-native: Value changes primarily with TIME (pumps on/off, drilling vs connection). \
Most surface measurements.
- depth-native: Value changes primarily with DEPTH (formation properties, survey stations). \
Formation and geometry measurements.
- bridges-both: Value is a function of BOTH time and depth. ROP (ft/hr) is the \
canonical example: it is dz/dt, the derivative connecting the two axes.

MPD RELEVANCE (choose exactly one per channel):
- primary: Directly used in MPD pressure management (APWD, SPP, flow balance, \
choke pressure, ECD, BHP, SBP, mud weight).
- secondary: Supports MPD decisions (ROP, WOB, torque, hookload, gamma ray). \
Provides context for pressure management.
- contextual: Not directly MPD-related but useful for completeness (survey, \
temperature, resistivity, gas analysis).

RESPOND ONLY WITH JSON. No explanation. No preamble.
{
  "channels": [
    {"name": "...", "physics_domain": "...", "index_relationship": "...", \
"mpd_relevance": "..."}
  ]
}"""


def build_characterization_prompt(
    channels: List[Dict[str, str]],
    index_type: str = "time",
) -> str:
    """Build the user-message prompt for channel characterization."""
    lines = [f"LAS file index type: {index_type}-indexed\n"]
    lines.append("Classify each channel:\n")
    for i, ch in enumerate(channels, 1):
        name = ch.get("name", "UNKNOWN")
        unit = ch.get("unit", "")
        desc = ch.get("description", "")
        lines.append(f"{i}. {name} (unit: {unit}) -- \"{desc}\"")
    lines.append("\nRespond with JSON only.")
    return "\n".join(lines)


def parse_characterization_response(raw_text: str) -> List[Dict[str, Any]]:
    """Parse LLM response into a list of channel characterizations."""
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)\s*```", raw_text, re.DOTALL)
    text = fenced.group(1).strip() if fenced else raw_text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse characterization JSON")
        return []

    channels_raw = data.get("channels", [])
    if not isinstance(channels_raw, list):
        return []

    result = []
    for ch in channels_raw:
        if not isinstance(ch, dict):
            continue
        entry = {
            "name": ch.get("name", ""),
            "physics_domain": ch.get("physics_domain", "unknown"),
            "index_relationship": ch.get("index_relationship", "unknown"),
            "mpd_relevance": ch.get("mpd_relevance", "contextual"),
        }
        if entry["physics_domain"] not in PHYSICS_DOMAINS:
            entry["physics_domain"] = "unknown"
        if entry["index_relationship"] not in INDEX_RELATIONSHIPS:
            entry["index_relationship"] = "unknown"
        if entry["mpd_relevance"] not in MPD_RELEVANCE:
            entry["mpd_relevance"] = "contextual"
        result.append(entry)

    return result


def batch_channels(
    channels: List[Dict[str, str]],
    batch_size: int = 10,
) -> List[List[Dict[str, str]]]:
    """Split channels into batches for LLM throughput."""
    return [channels[i:i + batch_size] for i in range(0, len(channels), batch_size)]


def _call_llm(
    messages: List[Dict[str, str]],
    base_url: str = _DEFAULT_BASE_URL,
    model: str = _DEFAULT_MODEL,
    max_tokens: int = 1200,
    temperature: float = 0.1,
) -> Optional[str]:
    """Call LM Studio API and return response content."""
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.error("LLM API call failed: %s", e)
        return None

    choices = result.get("choices", [])
    if not choices:
        return None
    return choices[0].get("message", {}).get("content")


def characterize_channels(
    channels: List[Dict[str, str]],
    index_type: str = "time",
    base_url: str = _DEFAULT_BASE_URL,
    model: str = _DEFAULT_MODEL,
    batch_size: int = 10,
) -> List[Dict[str, Any]]:
    """Characterize LAS channels via local LLM with Alpha 1 domain prompt."""
    all_results = []
    batches = batch_channels(channels, batch_size=batch_size)

    for i, batch in enumerate(batches):
        logger.info("Characterizing batch %d/%d (%d channels)", i + 1, len(batches), len(batch))
        prompt = build_characterization_prompt(batch, index_type=index_type)
        messages = [
            {"role": "system", "content": _ALPHA1_DRILLING_SYSTEM},
            {"role": "user", "content": prompt},
        ]

        t0 = time.perf_counter()
        raw = _call_llm(messages, base_url=base_url, model=model)
        elapsed = time.perf_counter() - t0

        if raw is None:
            logger.warning("Batch %d failed, marking channels as unknown", i + 1)
            for ch in batch:
                all_results.append({
                    "name": ch.get("name", ""),
                    "physics_domain": "unknown",
                    "index_relationship": "unknown",
                    "mpd_relevance": "contextual",
                })
            continue

        logger.info("Batch %d: %.1fs", i + 1, elapsed)
        parsed = parse_characterization_response(raw)

        # Match by name first, fall back to positional
        parsed_by_name = {
            p["name"].upper(): p for p in parsed if p.get("name")
        }
        for j, ch in enumerate(batch):
            name = ch.get("name", "")
            matched = parsed_by_name.get(name.upper())
            if matched is not None:
                entry = dict(matched)
                entry["name"] = name
            elif j < len(parsed):
                entry = dict(parsed[j])
                entry["name"] = name
            else:
                entry = {
                    "name": name,
                    "physics_domain": "unknown",
                    "index_relationship": "unknown",
                    "mpd_relevance": "contextual",
                }
            all_results.append(entry)

    return all_results
