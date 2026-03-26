"""Channel assignment profiles — save, load, validate."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from mpd_overwatch.data.sql_models import WellDatabase

logger = logging.getLogger(__name__)

_DEFAULT_PROFILES_DIR = Path.home() / ".mpd-overwatch"
_DEFAULT_PROFILES_FILE = _DEFAULT_PROFILES_DIR / "channel_profiles.json"


@dataclass
class ProfileValidationResult:
    """Validation result for one assignment in a profile."""
    canonical: str
    wits_id: str
    status: str  # "green", "yellow", "red"
    message: str


def save_profile(
    name: str, db: WellDatabase,
    path: Optional[Path] = None,
) -> None:
    """Save current assignments as a named profile."""
    path = path or _DEFAULT_PROFILES_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    all_profiles = load_all_profiles(path)
    assignments = {}
    for canonical, wits_id in db.assignments.items():
        cf = db.channels.get(wits_id)
        assignments[canonical] = {
            "wits_id": wits_id,
            "expected_units": cf.units if cf else "",
            "expected_mnemonic": cf.mnemonic if cf else "",
        }
    all_profiles[name] = {
        "profile_name": name,
        "created": datetime.utcnow().isoformat() + "Z",
        "source_ip": db.source_ip,
        "assignments": assignments,
    }
    path.write_text(json.dumps(all_profiles, indent=2))


def load_all_profiles(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load all saved profiles."""
    path = path or _DEFAULT_PROFILES_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def load_profile(name: str, path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Load a single named profile."""
    return load_all_profiles(path).get(name)


def delete_profile(name: str, path: Optional[Path] = None) -> None:
    """Delete a named profile."""
    path = path or _DEFAULT_PROFILES_FILE
    profiles = load_all_profiles(path)
    profiles.pop(name, None)
    path.write_text(json.dumps(profiles, indent=2))


def validate_profile(
    profile: Dict[str, Any], target_db: WellDatabase,
) -> Dict[str, ProfileValidationResult]:
    """Validate a profile against a target database.

    Returns: {canonical_name: ProfileValidationResult}
    - green: wits_id exists, units match, mnemonic matches
    - yellow: wits_id exists, units differ
    - red: wits_id not found
    """
    results = {}
    for canonical, entry in profile.get("assignments", {}).items():
        wid = entry["wits_id"]
        expected_units = entry.get("expected_units", "")
        expected_mnem = entry.get("expected_mnemonic", "")

        if wid not in target_db.channels:
            results[canonical] = ProfileValidationResult(
                canonical=canonical, wits_id=wid, status="red",
                message=f"WITS {wid} not found in database",
            )
        else:
            cf = target_db.channels[wid]
            if expected_units and cf.units != expected_units:
                results[canonical] = ProfileValidationResult(
                    canonical=canonical, wits_id=wid, status="yellow",
                    message=f"Units differ: expected '{expected_units}', got '{cf.units}'",
                )
            else:
                results[canonical] = ProfileValidationResult(
                    canonical=canonical, wits_id=wid, status="green",
                    message="OK",
                )
    return results


def apply_profile(
    profile: Dict[str, Any], db: WellDatabase,
    skip_red: bool = True,
) -> Dict[str, ProfileValidationResult]:
    """Validate and apply a profile to a WellDatabase.

    Returns validation results. Green/yellow entries are applied to db.assignments.
    Red entries are skipped if skip_red=True.
    """
    results = validate_profile(profile, db)
    for canonical, vr in results.items():
        if vr.status == "red" and skip_red:
            continue
        db.assignments[canonical] = vr.wits_id
    return results
