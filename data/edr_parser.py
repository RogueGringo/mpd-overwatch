"""
MPD Command - EDR / CSV / Excel Parser
=======================================

Parse drilling data from CSV and Excel files (EDR exports, Pason, Totco,
Corva, etc.).  Handles common column-naming variations, auto-detects time
and depth columns, and can merge time-indexed and depth-indexed datasets.

Typical usage::

    parser = EDRParser()
    result = parser.parse("well_edr_export.csv")
    df     = result.to_dataframe()
    dd     = result.to_drilling_data()
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from .models import DrillingData, WellInfo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Column name aliases -> canonical names
# ---------------------------------------------------------------------------

# Each entry: canonical_name -> list of regex patterns (case-insensitive)
# Patterns are tried in order; first match wins.

COLUMN_PATTERNS: Dict[str, List[str]] = {
    "depth_md": [
        r"^dept?h?\s*[\(\[]?m\.?d\.?",
        r"^hole\s*depth",
        r"^bit\s*depth",
        r"^dmea",
        r"^md[\s_]",
        r"^depth$",
        r"^dept$",
    ],
    "depth_tvd": [
        r"tvd",
        r"true\s*vert",
        r"dtvd",
    ],
    "rop": [
        r"^rop[\s_\(\[]",
        r"^rop$",
        r"rate\s*of\s*pen",
        r"^rop5",
        r"^mrop",
    ],
    "wob": [
        r"^wob[\s_\(\[]",
        r"^wob$",
        r"weight\s*on\s*bit",
        r"^swob",
    ],
    "torque": [
        r"^tor(?:que)?[\s_\(\[]",
        r"^tor(?:que)?$",
        r"^trq",
        r"surf.*torque",
    ],
    "spp": [
        r"^spp[\s_\(\[]",
        r"^spp$",
        r"standpipe",
        r"pump\s*press",
        r"^sppa",
    ],
    "flow_in": [
        r"flow[\s_]?in",
        r"^mfia",
        r"^pump.*rate",
        r"^total\s*pump\s*output",
    ],
    "flow_out": [
        r"flow[\s_]?out",
        r"^mfoa",
        r"mud\s*flow\s*out",
        r"return\s*flow",
    ],
    "gamma_ray": [
        r"^gr[\s_\(\[]",
        r"^gr$",
        r"gamma",
        r"^sgr",
        r"^cgr",
    ],
    "apwd": [
        r"apwd",
        r"annular\s*press",
        r"^aprs",
        r"^ecd_psi",
    ],
    "ecd": [
        r"^ecd[\s_\(\[]",
        r"^ecd$",
        r"equiv.*circ.*dens",
    ],
    "rpm": [
        r"^rpm[\s_\(\[]",
        r"^rpm$",
        r"^rpma",
        r"rotary\s*speed",
        r"^srpm",
    ],
    "hookload": [
        r"hook\s*load",
        r"^hkl[\s_\(\[]",
        r"^hkla",
    ],
    "choke_pressure": [
        r"choke.*press",
        r"^sbp[\s_\(\[]",
        r"^sbp$",
        r"back\s*press",
        r"^abp",
        r"mpd.*choke",
    ],
    "bhp": [
        r"^bhp[\s_\(\[]",
        r"^bhp$",
        r"bottom\s*hole\s*press",
    ],
    "timestamp": [
        r"^time[\s_]?stamp",
        r"^date[\s_]?time",
        r"^time$",
        r"^date$",
        r"^rig[\s_]?time",
    ],
    "block_position": [
        r"block\s*pos",
        r"^bpos",
        r"^blkpos",
    ],
    "mud_weight_in": [
        r"mud\s*w.*in",
        r"^mwin",
        r"^mw[\s_]?in",
    ],
    "mud_weight_out": [
        r"mud\s*w.*out",
        r"^mwout",
        r"^mw[\s_]?out",
    ],
}


# ---------------------------------------------------------------------------
# Parsed result container
# ---------------------------------------------------------------------------

@dataclass
class EDRResult:
    """Container returned by :class:`EDRParser` after reading one or more
    EDR/CSV/Excel files."""

    well_info: WellInfo
    dataframe: pd.DataFrame
    column_mapping: Dict[str, str] = field(default_factory=dict)
    unmapped_columns: List[str] = field(default_factory=list)
    source_files: List[str] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        """Return the canonical DataFrame."""
        return self.dataframe.copy()

    def to_drilling_data(self) -> DrillingData:
        """Convert to a :class:`DrillingData` instance.

        Missing channels are NaN-filled.
        """
        n = len(self.dataframe)
        nan_arr = np.full(n, np.nan)

        def _col(name: str) -> np.ndarray:
            if name in self.dataframe.columns:
                return self.dataframe[name].to_numpy(dtype=np.float64, na_value=np.nan)
            return nan_arr.copy()

        # Handle timestamp
        if "timestamp" in self.dataframe.columns:
            ts = pd.to_datetime(self.dataframe["timestamp"], errors="coerce")
            ts_arr = ts.to_numpy(dtype="datetime64[s]")
        else:
            ts_arr = np.empty(n, dtype="datetime64[s]")
            ts_arr[:] = np.datetime64("NaT")

        return DrillingData(
            depth_md=_col("depth_md"),
            depth_tvd=_col("depth_tvd"),
            rop=_col("rop"),
            wob=_col("wob"),
            torque=_col("torque"),
            spp=_col("spp"),
            flow_in=_col("flow_in"),
            flow_out=_col("flow_out"),
            gamma_ray=_col("gamma_ray"),
            apwd=_col("apwd"),
            rpm=_col("rpm"),
            hookload=_col("hookload"),
            choke_pressure=_col("choke_pressure"),
            timestamp=ts_arr,
        )


# ---------------------------------------------------------------------------
# Main parser class
# ---------------------------------------------------------------------------

class EDRParser:
    """Parse CSV / Excel drilling-data exports.

    Parameters
    ----------
    column_overrides : dict, optional
        Explicit ``{original_column: canonical_name}`` mappings that take
        precedence over auto-detection.
    skip_rows : int
        Number of header/junk rows to skip (common in Pason exports).
    """

    def __init__(
        self,
        column_overrides: Optional[Dict[str, str]] = None,
        skip_rows: int = 0,
    ) -> None:
        self.column_overrides = column_overrides or {}
        self.skip_rows = skip_rows

    # ----- public API ------------------------------------------------------

    def parse(
        self,
        filepath: Union[str, Path],
        sheet_name: Union[str, int] = 0,
        well_info: Optional[WellInfo] = None,
    ) -> EDRResult:
        """Parse a single CSV or Excel file.

        Parameters
        ----------
        filepath : str or Path
        sheet_name : str or int
            Excel sheet to read (ignored for CSV).
        well_info : WellInfo, optional
            Pre-populated well metadata.  If ``None``, a stub is created
            from the filename.

        Returns
        -------
        EDRResult
        """
        filepath = str(filepath)
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        ext = Path(filepath).suffix.lower()
        if ext in (".xlsx", ".xls", ".xlsm"):
            raw_df = self._read_excel(filepath, sheet_name)
        elif ext in (".csv", ".txt", ".tsv"):
            raw_df = self._read_csv(filepath)
        else:
            # Try CSV as default
            logger.warning("Unknown extension %s -- attempting CSV parse", ext)
            raw_df = self._read_csv(filepath)

        # Map columns
        df, mapping, unmapped = self._map_columns(raw_df)

        # Parse timestamps if present
        df = self._coerce_timestamps(df)

        # Sort by depth if available, else by timestamp
        if "depth_md" in df.columns:
            df.sort_values("depth_md", inplace=True)
            df.reset_index(drop=True, inplace=True)
        elif "timestamp" in df.columns:
            df.sort_values("timestamp", inplace=True)
            df.reset_index(drop=True, inplace=True)

        if well_info is None:
            well_info = WellInfo(
                well_name=Path(filepath).stem,
                operator="",
                field="",
                basin="",
                county="",
                state="",
                api_number="",
            )

        return EDRResult(
            well_info=well_info,
            dataframe=df,
            column_mapping=mapping,
            unmapped_columns=unmapped,
            source_files=[filepath],
        )

    def parse_and_merge(
        self,
        filepaths: Sequence[Union[str, Path]],
        merge_on: str = "depth_md",
        well_info: Optional[WellInfo] = None,
    ) -> EDRResult:
        """Parse multiple files for the same well and merge.

        Parameters
        ----------
        filepaths : sequence of str/Path
        merge_on : str
            Column to join on (``"depth_md"`` or ``"timestamp"``).
        well_info : WellInfo, optional

        Returns
        -------
        EDRResult
        """
        if not filepaths:
            raise ValueError("No files provided")

        results = [self.parse(fp, well_info=well_info) for fp in filepaths]

        merged_df = results[0].dataframe
        all_mappings: Dict[str, str] = dict(results[0].column_mapping)
        all_unmapped: List[str] = list(results[0].unmapped_columns)
        all_sources: List[str] = list(results[0].source_files)

        for res in results[1:]:
            all_sources.extend(res.source_files)
            all_unmapped.extend(res.unmapped_columns)
            all_mappings.update(res.column_mapping)

            if merge_on in merged_df.columns and merge_on in res.dataframe.columns:
                merged_df = pd.merge(
                    merged_df,
                    res.dataframe,
                    on=merge_on,
                    how="outer",
                    suffixes=("", "_dup"),
                )
                dup_cols = [c for c in merged_df.columns if c.endswith("_dup")]
                for dc in dup_cols:
                    base = dc.replace("_dup", "")
                    if base in merged_df.columns:
                        merged_df[base] = merged_df[base].fillna(merged_df[dc])
                    merged_df.drop(columns=[dc], inplace=True)
                merged_df.sort_values(merge_on, inplace=True)
                merged_df.reset_index(drop=True, inplace=True)
            else:
                merged_df = pd.concat([merged_df, res.dataframe], axis=1)

        info = well_info or results[0].well_info
        return EDRResult(
            well_info=info,
            dataframe=merged_df,
            column_mapping=all_mappings,
            unmapped_columns=sorted(set(all_unmapped)),
            source_files=all_sources,
        )

    def time_depth_merge(
        self,
        time_df: pd.DataFrame,
        depth_df: pd.DataFrame,
        time_col: str = "timestamp",
        depth_col: str = "depth_md",
        tolerance_sec: float = 5.0,
    ) -> pd.DataFrame:
        """Merge a time-indexed DataFrame with a depth-indexed DataFrame.

        Uses ``pd.merge_asof`` to join the two on timestamp after ensuring
        both have a time column.  The *depth_df* must also contain a
        timestamp column for this to work.

        Parameters
        ----------
        time_df : DataFrame
            DataFrame indexed/sorted by time.
        depth_df : DataFrame
            DataFrame with both time and depth columns.
        time_col, depth_col : str
        tolerance_sec : float
            Maximum seconds between matched rows.

        Returns
        -------
        DataFrame
        """
        # Ensure datetime types
        for df in (time_df, depth_df):
            if time_col in df.columns:
                df[time_col] = pd.to_datetime(df[time_col], errors="coerce")

        time_df = time_df.sort_values(time_col).reset_index(drop=True)
        depth_df = depth_df.sort_values(time_col).reset_index(drop=True)

        merged = pd.merge_asof(
            time_df,
            depth_df[[time_col, depth_col]],
            on=time_col,
            tolerance=pd.Timedelta(seconds=tolerance_sec),
            direction="nearest",
        )
        return merged

    # ----- internal --------------------------------------------------------

    def _read_csv(self, filepath: str) -> pd.DataFrame:
        """Read a CSV/TSV file, auto-detecting delimiter."""
        # Sniff delimiter from first few lines
        with open(filepath, "r", errors="replace") as fh:
            sample = fh.read(4096)

        if "\t" in sample and "," not in sample:
            sep = "\t"
        elif ";" in sample and "," not in sample:
            sep = ";"
        else:
            sep = ","

        try:
            df = pd.read_csv(
                filepath,
                sep=sep,
                skiprows=self.skip_rows,
                engine="python",
                on_bad_lines="skip",
            )
        except Exception:
            # Last resort: let pandas figure it out
            df = pd.read_csv(filepath, skiprows=self.skip_rows, on_bad_lines="skip")

        return df

    def _read_excel(self, filepath: str, sheet_name: Union[str, int] = 0) -> pd.DataFrame:
        """Read an Excel file."""
        try:
            import openpyxl  # noqa: F401 -- ensure engine available
        except ImportError:
            logger.warning("openpyxl not installed -- Excel parsing may fail")

        df = pd.read_excel(
            filepath,
            sheet_name=sheet_name,
            skiprows=self.skip_rows,
            engine="openpyxl" if filepath.endswith(".xlsx") else None,
        )
        return df

    def _map_columns(
        self, raw_df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, Dict[str, str], List[str]]:
        """Auto-detect and rename columns to canonical names.

        Returns (renamed_df, mapping_used, unmapped_column_list).
        """
        mapping: Dict[str, str] = {}  # original -> canonical
        used_canonical: set = set()
        unmapped: List[str] = []

        # First apply explicit overrides
        for orig, canon in self.column_overrides.items():
            if orig in raw_df.columns:
                mapping[orig] = canon
                used_canonical.add(canon)

        # Then auto-detect remaining
        for orig_col in raw_df.columns:
            if orig_col in mapping:
                continue

            col_lower = str(orig_col).strip()
            matched = False
            for canonical, patterns in COLUMN_PATTERNS.items():
                if canonical in used_canonical:
                    continue
                for pat in patterns:
                    if re.search(pat, col_lower, re.IGNORECASE):
                        mapping[orig_col] = canonical
                        used_canonical.add(canonical)
                        matched = True
                        break
                if matched:
                    break

            if not matched:
                unmapped.append(str(orig_col))

        # Rename
        rename_dict = {k: v for k, v in mapping.items() if k in raw_df.columns}
        df = raw_df.rename(columns=rename_dict)

        # Keep unmapped columns under their original names (lowered, cleaned)
        clean_map = {}
        for col in df.columns:
            if col not in mapping.values() and col not in rename_dict.values():
                clean = re.sub(r"[^a-z0-9_]", "_", str(col).lower()).strip("_")
                if clean and clean != col:
                    clean_map[col] = clean
        df.rename(columns=clean_map, inplace=True)

        return df, mapping, unmapped

    @staticmethod
    def _coerce_timestamps(df: pd.DataFrame) -> pd.DataFrame:
        """Attempt to parse the timestamp column to datetime."""
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        return df
