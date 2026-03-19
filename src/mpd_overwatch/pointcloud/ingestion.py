"""Ingestion adapters -- convert any drilling data source into PointCloud4D.

Supported formats:
    * pandas DataFrame (wide format)
    * LAS files (via ``lasio``)
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

try:
    import lasio
    _HAS_LASIO = True
except ImportError:
    _HAS_LASIO = False

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
# LAS file ingestion
# ---------------------------------------------------------------------------

def _guess_depth_column(curve_names: List[str]) -> str:
    """Heuristic to find the depth index column in a LAS file."""
    depth_candidates = [
        "DEPT", "DEPTH", "MD", "MEASURED_DEPTH", "TVD", "TVDSS",
        "dept", "depth", "md", "measured_depth", "tvd",
    ]
    for name in curve_names:
        if name.upper() in [c.upper() for c in depth_candidates]:
            return name
    # Fall back to first column
    return curve_names[0]


def ingest_las(
    filepath: str,
    registry: Optional[ChannelRegistry] = None,
    well_name: Optional[str] = None,
    channel_map: Optional[Dict[str, str]] = None,
) -> PointCloud4D:
    """Load a LAS file and convert to PointCloud4D.

    Parameters
    ----------
    filepath : str
        Path to the .LAS file.
    registry : ChannelRegistry, optional
        Channel metadata.  Defaults to a fresh registry.
    well_name : str, optional
        If not provided the well name is extracted from the LAS header.
    channel_map : dict, optional
        Additional column-to-channel overrides.

    Returns
    -------
    PointCloud4D

    Raises
    ------
    ImportError
        If ``lasio`` is not installed.
    FileNotFoundError
        If *filepath* does not exist.
    """
    if not _HAS_LASIO:
        raise ImportError(
            "lasio is required for LAS ingestion.  Install with: pip install lasio"
        )
    if not _HAS_PANDAS:
        raise ImportError(
            "pandas is required for LAS ingestion.  Install with: pip install pandas"
        )

    filepath = str(filepath)
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"LAS file not found: {filepath}")

    las = lasio.read(filepath, ignore_header_errors=True)

    # Extract well name from header if not provided
    if well_name is None:
        try:
            well_name = las.well.WELL.value or ""
        except Exception:
            well_name = Path(filepath).stem

    # Build DataFrame from curves
    import pandas as pd
    df = las.df().reset_index()

    # Identify the depth column (lasio puts the index curve first)
    curve_names = [c.mnemonic for c in las.curves]
    depth_col = _guess_depth_column(list(df.columns))

    # Build metadata from LAS header
    meta: dict = {"source_file": filepath, "format": "LAS"}
    try:
        meta["field"] = las.well.FLD.value
        meta["company"] = las.well.COMP.value
        meta["location"] = las.well.LOC.value
    except Exception:
        pass

    if registry is None:
        registry = ChannelRegistry()

    return PointCloud4D.from_dataframe(
        df,
        depth_col=depth_col,
        time_col=None,  # LAS files rarely have explicit time
        channel_map=channel_map,
        registry=registry,
        well_name=well_name,
        metadata=meta,
    )


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
# Directory batch ingestion
# ---------------------------------------------------------------------------

def ingest_directory(
    dirpath: str,
    pattern: str = "*.las",
    registry: Optional[ChannelRegistry] = None,
    channel_map: Optional[Dict[str, str]] = None,
) -> List[PointCloud4D]:
    """Load all matching files from a directory.

    Parameters
    ----------
    dirpath : str
        Root directory to scan.
    pattern : str
        Glob pattern to match (e.g. ``"*.las"``, ``"*.csv"``).
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
            if ext_lower in ("las",):
                pc = ingest_las(
                    str(fpath),
                    registry=registry,
                    channel_map=channel_map,
                )
            elif ext_lower in ("csv",):
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
        - File path (``.las``, ``.csv``): auto-detects format.
        - Directory path: batch-ingests all ``.las`` files (returns first).
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
    if ext == ".las":
        return ingest_las(
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
