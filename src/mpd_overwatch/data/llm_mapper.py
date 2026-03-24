"""LLM Channel Mapper — prompt builder, response parser, unit validator.

Uses a local LLM (e.g. LM Studio) to map vendor LAS curve mnemonics to
canonical channel names from the ChannelRegistry.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:1234/v1"
_DEFAULT_MODEL = "local-model"

_CACHE_DIR = Path.home() / ".mpd-overwatch" / "llm_mappings"

_EXTRA_TARGETS = [
    "depth_md", "tvd", "bit_depth", "hole_depth", "bit_tvd",
    "casing_pressure", "mud_volume", "flow_out_pct", "toolface",
    "timestamp", "date", "time", "differential_pressure",
    "block_height", "annular_velocity", "bit_rpm", "vibration",
    "stick_slip",
]

_MAX_CURVE_LINES = 120


# ---------------------------------------------------------------------------
# Canonical target list
# ---------------------------------------------------------------------------

def _get_canonical_targets() -> List[str]:
    """Build the full list of canonical channel names from the registry + extras."""
    from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry

    registry = ChannelRegistry()
    names = [ch.name for ch in registry.all_channels]
    return sorted(set(names + _EXTRA_TARGETS))


# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a drilling-data expert that maps LAS file curve mnemonics to canonical channel names.

Given a list of curve mnemonics from a LAS file ~C (Curve Information) section, map each mnemonic
to one of the following canonical channel names:

{canonical_list}

Rules:
1. Match each mnemonic to the BEST canonical name based on the mnemonic text, unit, and description.
2. If a mnemonic has no reasonable match, set canonical to null.
3. If two mnemonics map to the same canonical name, use the description to disambiguate.
4. Return confidence as a float between 0.0 and 1.0.
5. Return ONLY valid JSON with no additional text.

Return your answer as JSON in exactly this format:
{{
  "mappings": [
    {{"mnemonic": "CURVE_NAME", "canonical": "channel_name", "confidence": 0.95}},
    {{"mnemonic": "UNKNOWN", "canonical": null, "confidence": 0.0}}
  ]
}}
"""


def get_system_prompt() -> str:
    """Return the system prompt with the canonical target list filled in."""
    targets = _get_canonical_targets()
    canonical_list = "\n".join(f"  - {t}" for t in targets)
    return _SYSTEM_PROMPT.format(canonical_list=canonical_list)


# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------

def build_mapping_prompt(
    well_lines: List[str],
    curve_lines: List[str],
) -> str:
    """Build the user-message prompt from LAS ~W and ~C sections.

    Parameters
    ----------
    well_lines : list of str
        Lines from the LAS ~W (Well Information) section.
    curve_lines : list of str
        Lines from the LAS ~C (Curve Information) section.

    Returns
    -------
    str
        The user prompt to send alongside the system prompt.
    """
    parts: List[str] = []

    # Well context
    if well_lines:
        parts.append("~W (Well Information):")
        parts.extend(well_lines)
        parts.append("")

    # Curve section (truncate if needed)
    parts.append("~C (Curve Information):")
    if len(curve_lines) > _MAX_CURVE_LINES:
        parts.extend(curve_lines[:_MAX_CURVE_LINES])
        overflow = len(curve_lines) - _MAX_CURVE_LINES
        parts.append(f"... ({overflow} more curves truncated)")
    else:
        parts.extend(curve_lines)

    parts.append("")
    parts.append("Map each curve mnemonic to a canonical channel name. Return JSON only.")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def parse_llm_response(raw_text: str) -> Dict[str, Dict[str, Any]]:
    """Parse the LLM JSON response into a mnemonic -> mapping dict.

    Parameters
    ----------
    raw_text : str
        Raw text from the LLM, possibly wrapped in markdown code fences.

    Returns
    -------
    dict
        ``{MNEMONIC: {"canonical": str|None, "confidence": float}}``.
        Mnemonics are normalized to UPPER case.
        Invalid canonical names are set to None.
        Returns empty dict on unparseable input.
    """
    valid_targets = set(_get_canonical_targets())

    # Strip markdown code fences (handle preamble text before fences)
    text = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    else:
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse LLM response as JSON")
        return {}

    if not isinstance(data, dict) or "mappings" not in data:
        logger.warning("LLM response missing 'mappings' key")
        return {}

    result: Dict[str, Dict[str, Any]] = {}
    for entry in data["mappings"]:
        if not isinstance(entry, dict):
            continue
        mnemonic = str(entry.get("mnemonic", "")).upper().strip()
        if not mnemonic:
            continue

        canonical = entry.get("canonical")
        try:
            confidence = float(entry.get("confidence", 0.0))
        except (ValueError, TypeError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        # Validate canonical name against known targets
        if canonical is not None and canonical not in valid_targets:
            logger.info(
                "Canonical %r not in target list, setting to None for mnemonic %s",
                canonical, mnemonic,
            )
            canonical = None

        result[mnemonic] = {
            "canonical": canonical,
            "confidence": confidence,
        }

    return result


# ---------------------------------------------------------------------------
# Unit validation
# ---------------------------------------------------------------------------

_UNIT_GROUPS: Dict[str, List[str]] = {
    "pressure":    ["psi", "kpa", "mpa", "bar"],
    "flow":        ["gpm", "lpm", "galus-min", "galus/min", "bbl/min"],
    "density":     ["ppg", "sg", "g/cm3", "kg/m3", "lb/galus"],
    "gamma":       ["api", "gapi"],
    "length":      ["ft", "m", "in"],
    "velocity":    ["ft/hr", "m/hr", "ft/h", "m/h"],
    "force":       ["klbs", "kn", "lbf", "klbf"],
    "torque_unit": ["ft-lbs", "ft-lbf", "nm", "n-m", "kft-lbs"],
    "rotation":    ["rev/min", "rpm"],
    "angle":       ["deg", "degrees", "rad"],
    "temperature": ["degf", "degc", "f", "c"],
    "resistivity": ["ohm-m", "ohmm", "ohm.m"],
    "time_unit":   ["s", "sec", "min", "hr"],
    "percent":     ["%", "pct", "percent"],
    "volume":      ["bbl", "gal", "galus", "m3", "liter"],
}

_CHANNEL_UNIT_GROUP: Dict[str, str] = {
    # Pressure channels
    "spp":              "pressure",
    "apwd":             "pressure",
    "choke_pressure":   "pressure",
    "casing_pressure":  "pressure",
    "mse":              "pressure",
    "differential_pressure": "pressure",
    # Flow channels
    "flow_in":          "flow",
    "flow_out":         "flow",
    # Density channels
    "ecd":              "density",
    "mud_weight":       "density",
    # Gamma
    "gamma_ray":        "gamma",
    # Length / depth
    "depth_md":         "length",
    "tvd":              "length",
    "bit_depth":        "length",
    "hole_depth":       "length",
    "bit_tvd":          "length",
    "block_height":     "length",
    # Velocity
    "rop":              "velocity",
    "annular_velocity": "velocity",
    # Force
    "wob":              "force",
    "hookload":         "force",
    # Torque
    "torque":           "torque_unit",
    # Rotation
    "rpm":              "rotation",
    "bit_rpm":          "rotation",
    # Angle
    "inclination":      "angle",
    "azimuth":          "angle",
    "toolface":         "angle",
    # Temperature
    "temperature":      "temperature",
    # Resistivity
    "resistivity":      "resistivity",
    # Flow percent
    "flow_out_pct":     "percent",
    # Volume
    "mud_volume":       "volume",
}


def validate_mapping(
    mnemonic: str,
    canonical: str,
    unit: str,
    registry: "ChannelRegistry",
) -> bool:
    """Check whether a unit is compatible with the proposed canonical channel.

    Parameters
    ----------
    mnemonic : str
        Raw curve mnemonic (for logging).
    canonical : str
        Proposed canonical channel name.
    unit : str
        Unit string from the LAS file.
    registry : ChannelRegistry
        Channel registry (reserved for future use).

    Returns
    -------
    bool
        True if compatible or inconclusive (missing unit info, unknown channel).
        False if the unit clearly conflicts with the expected unit group.
    """
    # No unit info — inconclusive, accept
    if not unit or not unit.strip():
        return True

    # Unknown canonical — inconclusive, accept
    expected_group = _CHANNEL_UNIT_GROUP.get(canonical)
    if expected_group is None:
        return True

    # Check if the unit belongs to the expected group
    unit_lower = unit.lower().strip()
    expected_units = _UNIT_GROUPS.get(expected_group, [])

    if not expected_units:
        return True

    # Check if unit matches any unit in the expected group (exact match)
    if unit_lower in expected_units:
        return True

    # Unit does not match expected group — check if it matches ANY other group
    # If it matches another group, it's a clear conflict
    for group_name, group_units in _UNIT_GROUPS.items():
        if group_name == expected_group:
            continue
        if unit_lower in group_units:
            logger.info(
                "Unit %r for mnemonic %r matches group %r but canonical %r "
                "expects %r — incompatible",
                unit, mnemonic, group_name, canonical, expected_group,
            )
            return False

    # Unit doesn't match any known group — inconclusive, accept
    return True


# ---------------------------------------------------------------------------
# Per-operator mapping cache
# ---------------------------------------------------------------------------

def cache_key(service_company: str, operator: str, curve_names: List[str]) -> str:
    """Generate a deterministic cache key from operator context + curve set.

    Parameters
    ----------
    service_company : str
        Service company name (e.g. "Schlumberger").
    operator : str
        Operator name (e.g. "Noble Energy").
    curve_names : list of str
        Curve mnemonics from the LAS file.

    Returns
    -------
    str
        Hex digest truncated to 16 characters.
    """
    content = json.dumps({
        "srvc": service_company.strip().lower(),
        "comp": operator.strip().lower(),
        "curves": sorted(c.strip().upper() for c in curve_names),
    }, sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def save_cached_mapping(key: str, mapping: Dict[str, Any]) -> None:
    """Save a validated mapping dict to the cache directory.

    Parameters
    ----------
    key : str
        Cache key (from :func:`cache_key`).
    mapping : dict
        Mapping dict to persist.
    """
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    logger.debug("Saved cached mapping to %s", path)


def load_cached_mapping(key: str) -> Optional[Dict[str, Any]]:
    """Load a cached mapping if it exists.

    Parameters
    ----------
    key : str
        Cache key (from :func:`cache_key`).

    Returns
    -------
    dict or None
        The cached mapping dict, or None if not found or corrupt.
    """
    path = _CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            logger.warning("Cached mapping %s is not a dict, ignoring", path)
            return None
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load cached mapping %s: %s", path, exc)
        return None


# ---------------------------------------------------------------------------
# LLM client helper
# ---------------------------------------------------------------------------

def get_llm_client(base_url: str = _DEFAULT_BASE_URL):
    """Create an OpenAI-compatible client for LM Studio.

    Parameters
    ----------
    base_url : str
        Base URL of the LM Studio API (default ``http://localhost:1234/v1``).

    Returns
    -------
    openai.OpenAI or None
        An OpenAI client instance, or None if the ``openai`` package is not
        installed.
    """
    try:
        from openai import OpenAI  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("openai package not installed — LLM mapping unavailable")
        return None
    return OpenAI(base_url=base_url, api_key="lm-studio")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def llm_map_channels(
    well_lines: List[str],
    curve_lines: List[str],
    curve_units: Dict[str, str],
    service_company: str,
    operator: str,
    client=None,
    model: str = _DEFAULT_MODEL,
    confidence_threshold: float = 0.5,
    skip_cache: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """Map LAS curve mnemonics to canonical channel names via a local LLM.

    Full pipeline: cache check -> prompt build -> LLM call -> parse ->
    validate -> cache save.

    Parameters
    ----------
    well_lines : list of str
        Lines from the LAS ~W (Well Information) section.
    curve_lines : list of str
        Lines from the LAS ~C (Curve Information) section.
    curve_units : dict
        ``{MNEMONIC: unit_string}`` from parsed LAS header.
    service_company : str
        Service company name.
    operator : str
        Operator / company name.
    client : openai.OpenAI or None
        Pre-built OpenAI client.  If None the function attempts to create one
        via :func:`get_llm_client`.
    model : str
        Model identifier passed to the completions endpoint.
    confidence_threshold : float
        Minimum confidence to accept a mapping (below -> canonical set to None).
    skip_cache : bool
        If True, bypass the cache and always call the LLM.

    Returns
    -------
    dict
        ``{MNEMONIC: {"canonical": str|None, "confidence": float}}``.
        Returns ``{}`` on LLM failure or empty parse.
    """
    from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry

    # Determine curve names
    curve_names = list(curve_units.keys()) if curve_units else []
    if not curve_names:
        # Fallback: parse mnemonics from curve_lines (take text before first '.')
        for line in curve_lines:
            stripped = line.strip()
            if stripped:
                mnem = stripped.split(".")[0].strip().upper()
                if mnem:
                    curve_names.append(mnem)

    if not curve_names:
        logger.info("No curve names found — nothing to map")
        return {}

    # Cache check
    key = cache_key(service_company, operator, curve_names)
    if not skip_cache:
        cached = load_cached_mapping(key)
        if cached is not None:
            logger.debug("Using cached mapping for key %s", key)
            return cached

    # Resolve client
    if client is None:
        client = get_llm_client()
    if client is None:
        logger.warning("No LLM client available — returning empty mapping")
        return {}

    # Build prompts
    system_prompt = get_system_prompt()
    user_prompt = build_mapping_prompt(well_lines, curve_lines)

    # Call LLM
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=4096,
        )
        raw_text = completion.choices[0].message.content
    except Exception:
        logger.exception("LLM call failed")
        return {}

    # Parse response
    mapping = parse_llm_response(raw_text)
    if not mapping:
        logger.warning("LLM returned empty or unparseable mapping")
        return {}

    # Validate each mapping
    registry = ChannelRegistry()
    for mnemonic, info in mapping.items():
        canonical = info.get("canonical")
        confidence = info.get("confidence", 0.0)

        # Reject low confidence
        if confidence < confidence_threshold:
            info["canonical"] = None
            continue

        # Reject invalid unit mapping
        if canonical is not None:
            unit = curve_units.get(mnemonic, "")
            if not validate_mapping(mnemonic, canonical, unit, registry):
                info["canonical"] = None

    # Cache the validated result
    save_cached_mapping(key, mapping)

    return mapping
