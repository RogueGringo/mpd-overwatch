"""Server-side data cache for the dashboard.

Holds a parsed WellDatabase in server memory so it never needs to be
serialized to the browser.  For a single-user desktop tool running
on localhost, a module-level reference is the right storage.

The GUI and CLI share the same read path: sql_parser.ingest() builds a
WellDatabase, which lands here.  Everything downstream pulls from this cache.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from mpd_overwatch.data.sql_models import WellDatabase
from mpd_overwatch.data.sql_parser import SQLDumpParser, ingest as sql_ingest
from mpd_overwatch.data.sql_parser import scan_for_sql_files as _scan_sql
from mpd_overwatch.data.channel_profiles import (
    load_all_profiles,
    save_profile as _save_profile,
    delete_profile as _delete_profile,
)

logger = logging.getLogger(__name__)

# ---- recent files persistence ---------------------------------------------

_RECENT_DIR = Path.home() / ".mpd-overwatch"
_RECENT_FILE = _RECENT_DIR / "recent_files.json"
_MAX_RECENT = 20

# ---- module-level cache (lives for the server process lifetime) -----------

_well_database: Optional[WellDatabase] = None
_file_path: Optional[str] = None
_well_dossier_set = None  # Optional[WellDossierSet] — set after scan
_alerts: list = []


# ---- public API -----------------------------------------------------------


def load_file(filepath: str) -> Dict[str, Any]:
    """Load an EDR file and cache its WellDatabase server-side.

    Accepts .sql files (parsed via sql_parser.ingest) or directories
    containing .sql files.

    Returns a header dict summarizing the loaded data.
    Raises ValueError if the file cannot be parsed.
    """
    global _well_database, _file_path, _well_dossier_set

    filepath = str(Path(filepath).resolve())
    logger.info("Loading file: %s", filepath)

    p = Path(filepath)

    # SQL dump files or directories containing them
    if p.suffix.lower() == ".sql" or p.is_dir():
        db = sql_ingest(filepath)
    else:
        raise ValueError(
            f"Unsupported file type: {p.suffix}. "
            f"Expected .sql dump files."
        )

    # Cache the result
    _well_database = db
    _file_path = filepath

    # Run domain knowledge scan
    try:
        from mpd_overwatch.knowledge.scanner import run_scan
        _well_dossier_set = run_scan(db)
        logger.info("Domain knowledge scan: %d dossiers", len(_well_dossier_set.dossiers))
    except Exception:
        logger.exception("Domain knowledge scan failed — continuing without dossiers")
        _well_dossier_set = None

    # --- Layer 2: Compute alerts ---
    global _alerts
    try:
        from mpd_overwatch.dashboard.alerts import run_alert_scan
        if _well_dossier_set is not None:
            _alerts = run_alert_scan(_well_dossier_set, _well_database,
                                      _well_dossier_set.states)
            logger.info("Alert scan: %d alerts generated", len(_alerts))
        else:
            _alerts = []
    except Exception:
        logger.exception("Alert scan failed — continuing without alerts")
        _alerts = []

    # Build header dict
    time_range = db.time_range()
    depth_range = db.depth_range()
    channel_count = len(db.channels) + len(db.computed)
    total_points = sum(cf.n_points for cf in db.channels.values())

    header = {
        "source_ip": db.source_ip,
        "dump_timestamp": db.dump_timestamp,
        "channel_count": channel_count,
        "raw_channels": len(db.channels),
        "computed_channels": len(db.computed),
        "total_points": total_points,
        "time_start": str(time_range[0]) if time_range[0] != datetime.min else "",
        "time_end": str(time_range[1]) if time_range[1] != datetime.min else "",
        "depth_min": depth_range[0],
        "depth_max": depth_range[1],
        "filepath": filepath,
        "filename": p.name,
    }

    # Track in recent files
    well_label = f"{db.source_ip} @ {db.dump_timestamp}"
    _add_recent(filepath, well_label)

    logger.info(
        "Cached WellDatabase: %d channels, %d points from %s",
        channel_count, total_points, p.name,
    )

    return header


def get_well_database() -> Optional[WellDatabase]:
    """Return the cached WellDatabase, or None if nothing is loaded."""
    return _well_database


def is_loaded() -> bool:
    """True if a file has been loaded and a WellDatabase is available."""
    return _well_database is not None and len(_well_database.channels) > 0


def get_file_path() -> Optional[str]:
    """Return the path of the currently loaded file."""
    return _file_path


def clear():
    """Clear all cached data."""
    global _well_database, _file_path, _well_dossier_set, _alerts
    _well_database = None
    _file_path = None
    _well_dossier_set = None
    _alerts = []


def get_well_dossier_set():
    """Return the domain knowledge dossier set, or None if not scanned."""
    return _well_dossier_set


def get_alerts(channel_filter: list | None = None) -> list:
    """Return cached alerts, optionally filtered by channel names."""
    if channel_filter is None:
        return list(_alerts)
    return [a for a in _alerts if a.channel in channel_filter]


# ---- backward-compat bridge -----------------------------------------------


def get_channel_map_from_assignments() -> Dict[str, np.ndarray]:
    """Bridge: build the old-style {canonical: ndarray} from WellDatabase assignments.

    Used during migration while analysis pages still expect this format.
    """
    if _well_database is None:
        return {}
    result = {}
    for canonical, wits_id in _well_database.assignments.items():
        if wits_id in _well_database.channels:
            cf = _well_database.channels[wits_id]
            result[canonical] = cf.calibrated_value
    return result


# ---- directory scanning ---------------------------------------------------


def scan_for_sql_files(dirpath: str) -> List[Dict[str, Any]]:
    """Scan a directory recursively for .sql dump files.

    Delegates to sql_parser.scan_for_sql_files.
    """
    return _scan_sql(dirpath)


# ---- user channel mappings (delegate to channel_profiles) ------------------


def save_user_mappings(profile_name: str, mappings: Dict[str, str]):
    """Save a named channel mapping profile.

    Delegates to channel_profiles.save_profile using the current WellDatabase.
    If no WellDatabase is loaded, stores the mappings directly as assignments.
    """
    if _well_database is not None:
        # Apply mappings to the WellDatabase first, then save
        _well_database.assignments.update(mappings)
        _save_profile(profile_name, _well_database)
    else:
        logger.warning("No WellDatabase loaded; cannot save profile '%s'", profile_name)


def load_user_mappings() -> Dict[str, Any]:
    """Load all saved channel mapping profiles from disk.

    Delegates to channel_profiles.load_all_profiles.
    """
    return load_all_profiles()


def delete_user_mapping(profile_name: str):
    """Remove a saved mapping profile.

    Delegates to channel_profiles.delete_profile.
    """
    _delete_profile(profile_name)


# ---- recent files ---------------------------------------------------------


def _add_recent(filepath: str, well_name: str):
    """Add a file to the recent files list (persisted to disk)."""
    recent = get_recent_files()
    # Remove duplicates, add to front
    recent = [r for r in recent if r["path"] != filepath]
    recent.insert(0, {
        "path": filepath,
        "name": Path(filepath).name,
        "well_name": well_name,
        "timestamp": datetime.now().isoformat(),
    })
    recent = recent[:_MAX_RECENT]
    try:
        _RECENT_DIR.mkdir(parents=True, exist_ok=True)
        _RECENT_FILE.write_text(json.dumps(recent, indent=2))
    except OSError as exc:
        logger.debug("Could not write recent files: %s", exc)


def get_recent_files() -> List[Dict[str, str]]:
    """Return the recent files list (most recent first)."""
    try:
        if _RECENT_FILE.exists():
            data = json.loads(_RECENT_FILE.read_text())
            # Filter to files that still exist
            return [r for r in data if Path(r["path"]).exists()]
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Could not read recent files: %s", exc)
    return []
