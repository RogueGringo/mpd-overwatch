"""
Profile Manager — persistence layer for client/rig channel-mapping profiles.

Each profile is stored as a JSON file in a configurable directory. The filename
is derived by slugifying the profile_name field so that filenames stay
filesystem-safe while preserving human-readable names inside the JSON.

Public API
----------
save_profile(profile, profiles_dir="profiles/")
    Persist a profile dict to disk. Adds/updates ``created`` (first save only)
    and ``last_used`` (every save) ISO-8601 UTC timestamps.

load_profile(name, profiles_dir="profiles/")
    Load a profile by its ``profile_name``. Updates ``last_used`` on disk.

find_matching_profile(service_company, data_provider, rig_id, profiles_dir="profiles/")
    Return the first profile whose ``key`` triple matches the arguments, or
    ``None`` if no match is found.

list_profiles(profiles_dir="profiles/")
    Return a list of all saved profile dicts in the directory.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with a 'Z' suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slugify(name: str) -> str:
    """
    Convert a human-readable profile name to a safe filename stem.

    Rules:
    - Lowercase everything.
    - Replace any run of non-alphanumeric characters with a single hyphen.
    - Strip leading/trailing hyphens.

    Examples
    --------
    >>> _slugify("H&P Rig 566 Pason")
    'h-p-rig-566-pason'
    >>> _slugify("Test Profile")
    'test-profile'
    """
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def _profile_path(name: str, profiles_dir: str) -> Path:
    """Return the Path for a profile file given its name and directory."""
    return Path(profiles_dir) / f"{_slugify(name)}.json"


def _ensure_dir(profiles_dir: str) -> None:
    """Create the profiles directory if it does not already exist."""
    Path(profiles_dir).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_profile(profile: dict, profiles_dir: str = "profiles/") -> None:
    """
    Save *profile* as a JSON file inside *profiles_dir*.

    The ``profile_name`` key is required and must be non-empty. ``created`` is
    set only on the first save; ``last_used`` is updated on every call.

    Parameters
    ----------
    profile:
        Mapping conforming to the profile schema.  Must contain at minimum
        ``"profile_name"``.
    profiles_dir:
        Directory where profile JSON files are stored.  Created automatically
        if it does not exist.

    Raises
    ------
    ValueError
        If ``profile_name`` is missing or empty.
    """
    if not profile.get("profile_name"):
        raise ValueError("profile must contain a non-empty 'profile_name'")

    _ensure_dir(profiles_dir)

    path = _profile_path(profile["profile_name"], profiles_dir)

    # Preserve the original ``created`` timestamp if the file already exists.
    now = _utc_now_iso()
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            existing = json.load(fh)
        created = existing.get("created", now)
    else:
        created = now

    data = dict(profile)
    data["created"] = created
    data["last_used"] = now

    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def load_profile(name: str, profiles_dir: str = "profiles/") -> dict:
    """
    Load and return the profile identified by *name*.

    ``last_used`` is updated on disk each time a profile is loaded.

    Parameters
    ----------
    name:
        The ``profile_name`` value (not the slug / filename).
    profiles_dir:
        Directory where profile JSON files are stored.

    Returns
    -------
    dict
        The deserialized profile.

    Raises
    ------
    FileNotFoundError
        If no profile with the given name exists in *profiles_dir*.
    """
    path = _profile_path(name, profiles_dir)
    if not path.exists():
        raise FileNotFoundError(
            f"No profile named '{name}' found in '{profiles_dir}' "
            f"(expected file: {path})"
        )

    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    # Refresh last_used and persist.
    data["last_used"] = _utc_now_iso()
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)

    return data


def find_matching_profile(
    service_company: str,
    data_provider: str,
    rig_id: str,
    profiles_dir: str = "profiles/",
) -> Optional[dict]:
    """
    Search *profiles_dir* for a profile whose ``key`` triple matches the
    supplied arguments.

    Comparison is case-sensitive and exact (no partial matching).

    Parameters
    ----------
    service_company:
        Value to match against ``profile["key"]["service_company"]``.
    data_provider:
        Value to match against ``profile["key"]["data_provider"]``.
    rig_id:
        Value to match against ``profile["key"]["rig_id"]``.
    profiles_dir:
        Directory to search.

    Returns
    -------
    dict or None
        The first matching profile dict, or ``None`` if no match is found.
    """
    profiles_path = Path(profiles_dir)
    if not profiles_path.exists():
        return None

    for json_file in sorted(profiles_path.glob("*.json")):
        try:
            with json_file.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            # Skip malformed or unreadable files.
            continue

        key = data.get("key", {})
        if (
            key.get("service_company") == service_company
            and key.get("data_provider") == data_provider
            and key.get("rig_id") == rig_id
        ):
            return data

    return None


def list_profiles(profiles_dir: str = "profiles/") -> list[dict]:
    """
    Return a list of all profile dicts found in *profiles_dir*.

    Files that cannot be parsed as valid JSON are silently skipped.

    Parameters
    ----------
    profiles_dir:
        Directory to scan.

    Returns
    -------
    list[dict]
        All successfully loaded profiles (order is filesystem-dependent but
        deterministic within a single run).
    """
    profiles_path = Path(profiles_dir)
    if not profiles_path.exists():
        return []

    result: list[dict] = []
    for json_file in sorted(profiles_path.glob("*.json")):
        try:
            with json_file.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            result.append(data)
        except (json.JSONDecodeError, OSError):
            continue

    return result
