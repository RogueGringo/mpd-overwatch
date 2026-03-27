"""Ingestion adapters -- convert any drilling data source into PointCloud4D.

Supported formats:
    * pandas DataFrame (wide format)
    * SQL EDR dumps (via ``sql_parser.ingest``)
    * CSV files
    * Directory of files (batch ingest)
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Union

import numpy as np

try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False

from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry
from mpd_overwatch.pointcloud.pointcloud4d import PointCloud4D


# ---------------------------------------------------------------------------
# DataFrame ingestion (core path -- all other formats funnel through here)
# ---------------------------------------------------------------------------

def ingest_dataframe(
    df: "pd.DataFrame",
    depth_col: str,
    time_col: Optional[str] = None,
    channel_map: Optional[Dict[str, str]] = None,
    registry: Optional[ChannelRegistry] = None,
    well_name: str = "",
    metadata: Optional[dict] = None,
) -> PointCloud4D:
    """Convert a wide-format DataFrame to PointCloud4D.

    The DataFrame should have one row per depth/time sample and one column
    per measurement channel.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    depth_col : str
        Name of the column containing measured depth (ft MD).
    time_col : str, optional
        Name of the column containing timestamps.  If ``None`` a synthetic
        monotonic time index is generated from the row order.
    channel_map : dict, optional
        ``{column_name: canonical_channel_name}`` for columns whose name
        does not match any known mnemonic.
    registry : ChannelRegistry, optional
        Channel metadata.  Defaults to a fresh registry with the standard
        18-channel catalogue.
    well_name : str
        Well identifier to attach.
    metadata : dict, optional
        Arbitrary metadata stored on the resulting object.

    Returns
    -------
    PointCloud4D
    """
    if not _HAS_PANDAS:
        raise ImportError("pandas is required for ingest_dataframe()")

    if registry is None:
        registry = ChannelRegistry()

    return PointCloud4D.from_dataframe(
        df,
        depth_col=depth_col,
        time_col=time_col,
        channel_map=channel_map,
        registry=registry,
        well_name=well_name,
        metadata=metadata if metadata is not None else {},
    )


# ---------------------------------------------------------------------------
# Depth column heuristic
# ---------------------------------------------------------------------------

def _guess_depth_column(curve_names: List[str]) -> str:
    """Heuristic to find the depth index column."""
    depth_candidates = [
        "DEPT", "DEPTH", "MD", "MEASURED_DEPTH", "TVD", "TVDSS",
        "dept", "depth", "md", "measured_depth", "tvd",
        "hole_depth", "bit_depth",
    ]
    for name in curve_names:
        if name.upper() in [c.upper() for c in depth_candidates]:
            return name
    # Fall back to first column
    return curve_names[0]


# ---------------------------------------------------------------------------
# CSV ingestion
# ---------------------------------------------------------------------------

def ingest_csv(
    filepath: str,
    depth_col: Optional[str] = None,
    time_col: Optional[str] = None,
    registry: Optional[ChannelRegistry] = None,
    well_name: Optional[str] = None,
    channel_map: Optional[Dict[str, str]] = None,
    **csv_kwargs,
) -> PointCloud4D:
    """Load a CSV file and convert to PointCloud4D.

    Parameters
    ----------
    filepath : str
        Path to the CSV file.
    depth_col : str, optional
        Depth column name.  If not provided a heuristic search is used.
    time_col : str, optional
        Time column name.
    registry : ChannelRegistry, optional
        Channel metadata.
    well_name : str, optional
        Defaults to the file stem.
    channel_map : dict, optional
        Column-to-channel overrides.
    **csv_kwargs
        Extra keyword arguments forwarded to ``pd.read_csv``.

    Returns
    -------
    PointCloud4D
    """
    if not _HAS_PANDAS:
        raise ImportError("pandas is required for CSV ingestion.")

    import pandas as pd

    filepath = str(filepath)
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"CSV file not found: {filepath}")

    df = pd.read_csv(filepath, **csv_kwargs)

    if depth_col is None:
        depth_col = _guess_depth_column(list(df.columns))
        warnings.warn(f"No depth_col specified; guessing {depth_col!r}.")

    if well_name is None:
        well_name = Path(filepath).stem

    if registry is None:
        registry = ChannelRegistry()

    meta: dict = {"source_file": filepath, "format": "CSV"}

    return PointCloud4D.from_dataframe(
        df,
        depth_col=depth_col,
        time_col=time_col,
        channel_map=channel_map,
        registry=registry,
        well_name=well_name,
        metadata=meta,
    )


# ---------------------------------------------------------------------------
# SQL EDR ingestion
# ---------------------------------------------------------------------------

def ingest_sql(
    filepath: str,
    registry: Optional[ChannelRegistry] = None,
    well_name: Optional[str] = None,
    channel_map: Optional[Dict[str, str]] = None,
) -> PointCloud4D:
    """Load a SQL EDR dump and convert to PointCloud4D.

    Parameters
    ----------
    filepath : str
        Path to the .sql dump file.
    registry : ChannelRegistry, optional
        Channel metadata.  Defaults to a fresh registry.
    well_name : str, optional
        If not provided the source IP is used.
    channel_map : dict, optional
        Additional column-to-channel overrides.

    Returns
    -------
    PointCloud4D
    """
    if not _HAS_PANDAS:
        raise ImportError("pandas is required for SQL ingestion.")

    from mpd_overwatch.data.sql_parser import ingest as sql_ingest
    from mpd_overwatch.data.engine_manifest import auto_suggest_assignments

    db = sql_ingest(filepath)

    if well_name is None:
        well_name = db.source_ip or Path(filepath).stem

    # Auto-suggest assignments
    suggestions = auto_suggest_assignments(db)
    for canonical, wits_id in suggestions.items():
        db.assignments[canonical] = wits_id

    # Build DataFrame from assigned channels
    if not db.assignments:
        raise ValueError(f"No channels could be auto-mapped from {filepath}")

    canonical_data = {}
    for canonical, wits_id in db.assignments.items():
        cf = db.channels[wits_id]
        canonical_data[canonical] = cf.calibrated_value

    # Align arrays to same length
    min_len = min(len(v) for v in canonical_data.values())
    for k in canonical_data:
        canonical_data[k] = canonical_data[k][:min_len]

    import pandas as pd
    df = pd.DataFrame(canonical_data)
    depth_col = _guess_depth_column(list(df.columns))

    if registry is None:
        registry = ChannelRegistry()

    meta: dict = {"source_file": filepath, "format": "SQL_EDR"}

    return PointCloud4D.from_dataframe(
        df,
        depth_col=depth_col,
        time_col=None,
        channel_map=channel_map,
        registry=registry,
        well_name=well_name,
        metadata=meta,
    )


# ---------------------------------------------------------------------------
# Directory batch ingestion
# ---------------------------------------------------------------------------

def ingest_directory(
    dirpath: str,
    pattern: str = "*.sql",
    registry: Optional[ChannelRegistry] = None,
    channel_map: Optional[Dict[str, str]] = None,
) -> List[PointCloud4D]:
    """Load all matching files from a directory.

    Parameters
    ----------
    dirpath : str
        Root directory to scan.
    pattern : str
        Glob pattern to match (e.g. ``"*.sql"``, ``"*.csv"``).
    registry : ChannelRegistry, optional
        Shared channel registry.  A single instance is reused for all files
        so channel IDs are consistent across the returned list.
    channel_map : dict, optional
        Column-to-channel overrides applied to every file.

    Returns
    -------
    list of PointCloud4D
    """
    dirpath = str(dirpath)
    if not os.path.isdir(dirpath):
        raise FileNotFoundError(f"Directory not found: {dirpath}")

    if registry is None:
        registry = ChannelRegistry()

    results: List[PointCloud4D] = []
    root = Path(dirpath)
    files = sorted(root.glob(pattern))

    if not files:
        warnings.warn(f"No files matching {pattern!r} found in {dirpath}")
        return results

    ext_lower = pattern.rsplit(".", 1)[-1].lower() if "." in pattern else ""

    for fpath in files:
        try:
            if ext_lower == "sql":
                pc = ingest_sql(
                    str(fpath),
                    registry=registry,
                    channel_map=channel_map,
                )
            elif ext_lower == "csv":
                pc = ingest_csv(
                    str(fpath),
                    registry=registry,
                    channel_map=channel_map,
                )
            else:
                # Try CSV as fallback for unknown extensions
                pc = ingest_csv(
                    str(fpath),
                    registry=registry,
                    channel_map=channel_map,
                )
            results.append(pc)
        except Exception as exc:
            warnings.warn(f"Failed to ingest {fpath.name}: {exc}")

    return results


# ---------------------------------------------------------------------------
# Unified ingestion entry point
# ---------------------------------------------------------------------------

def ingest(
    source: "Union[str, Path, pd.DataFrame, DrillingData]",
    well_name: str = "",
    depth_col: Optional[str] = None,
    channel_map: Optional[Dict[str, str]] = None,
    registry: Optional[ChannelRegistry] = None,
) -> PointCloud4D:
    """Universal ingestion entry point.

    Accepts any supported source type and returns a ``PointCloud4D``.

    Parameters
    ----------
    source : str, Path, pd.DataFrame, or DrillingData
        - File path (``.sql``, ``.csv``): auto-detects format.
        - Directory path: batch-ingests all ``.sql`` files (returns first).
        - ``pandas.DataFrame``: direct conversion.
        - ``DrillingData``: converts via ``to_dataframe()`` then ingests.
    well_name : str
        Well identifier.
    depth_col : str, optional
        Name of the depth column.  If ``None``, auto-detected via
        heuristic (looks for 'DEPT', 'depth_md', 'MD', etc.).
    channel_map : dict, optional
        Override mnemonic-to-channel mapping.
    registry : ChannelRegistry, optional
        Channel definitions.  Uses default 18-channel registry if not
        provided.

    Returns
    -------
    PointCloud4D
    """
    if registry is None:
        registry = ChannelRegistry()

    # -- DrillingData --
    # Import here to avoid circular import at module level.
    try:
        from mpd_overwatch.data.models import DrillingData
        is_drilling_data = isinstance(source, DrillingData)
    except ImportError:
        is_drilling_data = False

    if is_drilling_data:
        df = source.to_dataframe()
        return ingest_dataframe(
            df,
            depth_col="depth_md",
            channel_map=channel_map,
            registry=registry,
            well_name=well_name,
        )

    # -- pandas DataFrame --
    if _HAS_PANDAS and isinstance(source, pd.DataFrame):
        if depth_col is None:
            depth_col = _guess_depth_column(list(source.columns))
        return ingest_dataframe(
            source,
            depth_col=depth_col,
            channel_map=channel_map,
            registry=registry,
            well_name=well_name,
        )

    # -- File / directory path --
    path = Path(str(source))

    if path.is_dir():
        results = ingest_directory(
            str(path),
            registry=registry,
            channel_map=channel_map,
        )
        if not results:
            raise ValueError(f"No files could be ingested from {path}")
        return results[0]

    if not path.is_file():
        raise FileNotFoundError(f"Source not found: {source}")

    ext = path.suffix.lower()
    if ext == ".sql":
        return ingest_sql(
            str(path),
            registry=registry,
            well_name=well_name or None,
            channel_map=channel_map,
        )
    elif ext == ".csv":
        return ingest_csv(
            str(path),
            depth_col=depth_col,
            registry=registry,
            well_name=well_name or None,
            channel_map=channel_map,
        )
    else:
        # Try CSV as fallback
        return ingest_csv(
            str(path),
            depth_col=depth_col,
            registry=registry,
            well_name=well_name or None,
            channel_map=channel_map,
        )


# ---------------------------------------------------------------------------
# Channel-map ingestion (bridge from dashboard dcc.Store to PointCloud4D)
# ---------------------------------------------------------------------------

def ingest_channel_map(
    channel_map: Dict[str, np.ndarray],
    well_name: str = "",
    registry: Optional[ChannelRegistry] = None,
) -> PointCloud4D:
    """Convert a deserialized channel map into a PointCloud4D.

    This is the bridge between the Dash dashboard's ``dcc.Store`` channel data
    (canonical name -> numpy array) and the topology/sheaf analysis engine.

    Parameters
    ----------
    channel_map : dict
        ``{canonical_channel_name: np.ndarray}`` -- the deserialized channel
        map from ``data_store.get_channel_map_from_assignments()``.
    well_name : str
        Well identifier.
    registry : ChannelRegistry, optional
        Defaults to a fresh registry with the standard channel catalogue.

    Returns
    -------
    PointCloud4D
    """
    if not _HAS_PANDAS:
        raise ImportError("pandas is required for ingest_channel_map()")

    if registry is None:
        registry = ChannelRegistry()

    # Build a DataFrame from the channel map
    df = pd.DataFrame(channel_map)

    # Determine depth column
    depth_col = None
    for candidate in ("depth_md", "hole_depth", "dept", "md", "depth"):
        if candidate in df.columns:
            depth_col = candidate
            break
    if depth_col is None:
        # Fall back to first column
        depth_col = df.columns[0]

    return PointCloud4D.from_dataframe(
        df,
        depth_col=depth_col,
        channel_map=None,  # columns are already canonical names
        registry=registry,
        well_name=well_name,
        metadata={},
    )
