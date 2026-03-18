"""
MPD Command - LAS File Parser
==============================

Parse LAS 2.0 well-log files into DrillingData objects or pandas DataFrames.
Uses the ``lasio`` library when available; falls back to a minimal built-in
parser that handles the most common LAS 2.0 structure.

Typical usage::

    parser = LASParser()
    result = parser.parse("path/to/well.las")
    df     = result.to_dataframe()
    dd     = result.to_drilling_data()
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from mpd_overwatch.data.models import DrillingData, WellInfo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try importing lasio; set a flag so the rest of the module can branch.
# ---------------------------------------------------------------------------
try:
    import lasio
    HAS_LASIO = True
except ImportError:
    HAS_LASIO = False
    logger.info("lasio not installed -- falling back to built-in LAS 2.0 parser")


# ---------------------------------------------------------------------------
# Common mnemonic aliases -> canonical names
# ---------------------------------------------------------------------------

# Maps vendor-specific curve mnemonics to our canonical channel names.
# Keys are UPPER-CASED for case-insensitive matching.
MNEMONIC_MAP: Dict[str, str] = {
    # Depth
    "DEPT": "depth_md",
    "DEPTH": "depth_md",
    "MD": "depth_md",
    "DMEA": "depth_md",
    "TDEP": "depth_md",
    "TVD": "depth_tvd",
    "TVDSS": "depth_tvd",
    "DTVD": "depth_tvd",
    # Gamma ray
    "GR": "gamma_ray",
    "GR_EDRC": "gamma_ray",
    "GR_ARC": "gamma_ray",
    "SGR": "gamma_ray",
    "CGR": "gamma_ray",
    "HCGR": "gamma_ray",
    "ECGR": "gamma_ray",
    # Density / porosity (informational -- not in DrillingData but kept in df)
    "RHOB": "bulk_density",
    "RHOZ": "bulk_density",
    "ZDEN": "bulk_density",
    "NPHI": "neutron_porosity",
    "TNPH": "neutron_porosity",
    "NPOR": "neutron_porosity",
    # Resistivity
    "RT": "resistivity_deep",
    "ILD": "resistivity_deep",
    "LLD": "resistivity_deep",
    "AT90": "resistivity_deep",
    "RD": "resistivity_deep",
    "RS": "resistivity_shallow",
    "ILM": "resistivity_shallow",
    "LLS": "resistivity_shallow",
    "AT10": "resistivity_shallow",
    # Drilling parameters
    "ROP": "rop",
    "ROP5": "rop",
    "ROPA": "rop",
    "MROP": "rop",
    "WOB": "wob",
    "WOBX": "wob",
    "SWOB": "wob",
    "TRQ": "torque",
    "TORQUE": "torque",
    "STOR": "torque",
    "TQA": "torque",
    "SPP": "spp",
    "SPPA": "spp",
    "PUMP_PRESS": "spp",
    "FLOWIN": "flow_in",
    "FLOW_IN": "flow_in",
    "MFIA": "flow_in",
    "FLOWOUT": "flow_out",
    "FLOW_OUT": "flow_out",
    "MFOA": "flow_out",
    "RPM": "rpm",
    "RPMA": "rpm",
    "SRPM": "rpm",
    "HKLA": "hookload",
    "HOOKLOAD": "hookload",
    "HKL": "hookload",
    "BPOS": "block_position",
    # Annular pressure
    "APRS": "apwd",
    "APWD": "apwd",
    "ECD": "ecd",
    "ECDA": "ecd",
    # MPD
    "CHOKE_PRESS": "choke_pressure",
    "SBP": "choke_pressure",
    "ABP": "choke_pressure",
    "BHP": "bhp",
}


# ---------------------------------------------------------------------------
# Parsed result container
# ---------------------------------------------------------------------------

@dataclass
class LASResult:
    """Container returned by :class:`LASParser` after reading one or more LAS
    files for a single well."""

    well_info: WellInfo
    dataframe: pd.DataFrame
    raw_curves: Dict[str, np.ndarray] = field(default_factory=dict)
    unmapped_mnemonics: List[str] = field(default_factory=list)
    source_files: List[str] = field(default_factory=list)

    # -- Conversion helpers -------------------------------------------------

    def to_dataframe(self) -> pd.DataFrame:
        """Return the full merged DataFrame (all curves, canonical names)."""
        return self.dataframe.copy()

    def to_drilling_data(self) -> DrillingData:
        """Map available columns into a :class:`DrillingData` instance.

        Missing channels are filled with NaN arrays of the correct length.
        """
        n = len(self.dataframe)
        nan_arr = np.full(n, np.nan)

        def _col(name: str) -> np.ndarray:
            if name in self.dataframe.columns:
                return self.dataframe[name].to_numpy(dtype=np.float64, na_value=np.nan)
            return nan_arr.copy()

        # Timestamp: LAS files rarely carry time -- fill with NaT
        ts = np.empty(n, dtype="datetime64[s]")
        ts[:] = np.datetime64("NaT")

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
            timestamp=ts,
        )


# ---------------------------------------------------------------------------
# Fallback: minimal LAS 2.0 parser
# ---------------------------------------------------------------------------

def _parse_las2_manual(filepath: str) -> Tuple[Dict[str, str], pd.DataFrame]:
    """Bare-bones LAS 2.0 reader.

    Returns
    -------
    header : dict
        Selected well-header fields (WELL, COMP, FLD, LOC, STAT, API, DATE,
        STRT, STOP, STEP, NULL).
    df : DataFrame
        Curve data with original mnemonic column names.
    """
    header: Dict[str, str] = {}
    curve_names: List[str] = []
    data_lines: List[str] = []
    current_section: Optional[str] = None
    null_value = -999.25

    with open(filepath, "r", errors="replace") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            # Section headers
            if line.startswith("~"):
                tag = line[1].upper()
                current_section = tag
                continue

            if current_section == "W":
                # Well information section
                match = re.match(r"^(\S+)\s*\.([^:]*):(.*)$", line)
                if match:
                    mnem = match.group(1).strip().upper()
                    value = match.group(2).strip()
                    desc = match.group(3).strip()
                    # Some LAS files put the value after the colon
                    header[mnem] = value if value else desc

            elif current_section == "C":
                # Curve information section
                match = re.match(r"^(\S+)\s*\.", line)
                if match:
                    curve_names.append(match.group(1).strip())

            elif current_section == "A":
                # ASCII data section
                data_lines.append(line)

    # Parse NULL value
    if "NULL" in header:
        try:
            null_value = float(header["NULL"])
        except ValueError:
            pass

    # Build DataFrame from ASCII lines
    rows: List[List[float]] = []
    for dline in data_lines:
        parts = dline.split()
        if len(parts) == len(curve_names):
            try:
                rows.append([float(v) for v in parts])
            except ValueError:
                continue

    if not rows:
        df = pd.DataFrame(columns=curve_names)
    else:
        df = pd.DataFrame(rows, columns=curve_names)

    # Replace null sentinel with NaN
    df.replace(null_value, np.nan, inplace=True)

    return header, df


# ---------------------------------------------------------------------------
# Main parser class
# ---------------------------------------------------------------------------

class LASParser:
    """Parse one or more LAS files and produce a unified :class:`LASResult`.

    Parameters
    ----------
    mnemonic_overrides : dict, optional
        Extra mnemonic -> canonical-name mappings to merge with the built-in
        ``MNEMONIC_MAP``.
    """

    def __init__(self, mnemonic_overrides: Optional[Dict[str, str]] = None) -> None:
        self.mnemonic_map = dict(MNEMONIC_MAP)
        if mnemonic_overrides:
            self.mnemonic_map.update(
                {k.upper(): v for k, v in mnemonic_overrides.items()}
            )

    # ----- public API ------------------------------------------------------

    def parse(self, filepath: Union[str, Path]) -> LASResult:
        """Parse a single LAS file.

        Parameters
        ----------
        filepath : str or Path
            Path to a .las file.

        Returns
        -------
        LASResult
        """
        filepath = str(filepath)
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"LAS file not found: {filepath}")

        if HAS_LASIO:
            return self._parse_with_lasio(filepath)
        return self._parse_manual(filepath)

    def parse_multiple(self, filepaths: Sequence[Union[str, Path]]) -> LASResult:
        """Parse multiple LAS files for the **same well** and merge on depth.

        Later files overwrite earlier columns if the same canonical name
        appears.  Merging is an outer join on ``depth_md``.

        Parameters
        ----------
        filepaths : sequence of str/Path

        Returns
        -------
        LASResult
        """
        if not filepaths:
            raise ValueError("No files provided")

        results = [self.parse(fp) for fp in filepaths]

        # Use the first file's well info as the base
        merged_info = results[0].well_info
        merged_df = results[0].dataframe
        all_unmapped: List[str] = list(results[0].unmapped_mnemonics)
        all_sources: List[str] = list(results[0].source_files)

        for res in results[1:]:
            all_sources.extend(res.source_files)
            all_unmapped.extend(res.unmapped_mnemonics)

            if "depth_md" in merged_df.columns and "depth_md" in res.dataframe.columns:
                # Merge on depth
                merged_df = pd.merge(
                    merged_df,
                    res.dataframe,
                    on="depth_md",
                    how="outer",
                    suffixes=("", "_dup"),
                )
                # Drop duplicate columns (keep the later file's version)
                dup_cols = [c for c in merged_df.columns if c.endswith("_dup")]
                for dc in dup_cols:
                    base = dc.replace("_dup", "")
                    if base in merged_df.columns:
                        # Fill NaNs in the base from the dup, then drop dup
                        merged_df[base] = merged_df[base].fillna(merged_df[dc])
                    merged_df.drop(columns=[dc], inplace=True)
                merged_df.sort_values("depth_md", inplace=True)
                merged_df.reset_index(drop=True, inplace=True)
            else:
                # No common depth column -- just concat columns
                merged_df = pd.concat([merged_df, res.dataframe], axis=1)

        return LASResult(
            well_info=merged_info,
            dataframe=merged_df,
            unmapped_mnemonics=sorted(set(all_unmapped)),
            source_files=all_sources,
        )

    # ----- internal --------------------------------------------------------

    def _parse_with_lasio(self, filepath: str) -> LASResult:
        """Parse using the lasio library."""
        las = lasio.read(filepath)

        # Extract well info
        well_info = self._extract_well_info_lasio(las, filepath)

        # Build DataFrame with canonical names
        df, unmapped = self._build_dataframe(
            curve_names=[c.mnemonic for c in las.curves],
            curve_data={c.mnemonic: c.data for c in las.curves},
        )

        return LASResult(
            well_info=well_info,
            dataframe=df,
            raw_curves={c.mnemonic: c.data for c in las.curves},
            unmapped_mnemonics=unmapped,
            source_files=[filepath],
        )

    def _parse_manual(self, filepath: str) -> LASResult:
        """Parse using the built-in minimal reader."""
        header, raw_df = _parse_las2_manual(filepath)

        well_info = self._extract_well_info_header(header, filepath)

        # Build canonical DataFrame
        curve_names = list(raw_df.columns)
        curve_data = {col: raw_df[col].to_numpy() for col in raw_df.columns}
        df, unmapped = self._build_dataframe(curve_names, curve_data)

        return LASResult(
            well_info=well_info,
            dataframe=df,
            raw_curves=curve_data,
            unmapped_mnemonics=unmapped,
            source_files=[filepath],
        )

    def _build_dataframe(
        self,
        curve_names: List[str],
        curve_data: Dict[str, np.ndarray],
    ) -> Tuple[pd.DataFrame, List[str]]:
        """Map raw curve names to canonical names and return a DataFrame."""
        columns: Dict[str, np.ndarray] = {}
        unmapped: List[str] = []

        for mnemonic in curve_names:
            canonical = self.mnemonic_map.get(mnemonic.upper())
            if canonical:
                # If we already have this canonical name, keep the first
                if canonical not in columns:
                    columns[canonical] = curve_data[mnemonic]
                else:
                    logger.debug(
                        "Duplicate canonical mapping %s for mnemonic %s -- skipped",
                        canonical,
                        mnemonic,
                    )
            else:
                unmapped.append(mnemonic)
                # Keep unmapped curves under their original name (lowered)
                columns[mnemonic.lower()] = curve_data[mnemonic]

        df = pd.DataFrame(columns)
        return df, unmapped

    @staticmethod
    def _extract_well_info_lasio(las: Any, filepath: str) -> WellInfo:
        """Pull WellInfo fields from a lasio.LASFile object."""

        def _hdr(key: str, default: str = "") -> str:
            try:
                item = las.well[key]
                return str(item.value).strip() if item.value else default
            except (KeyError, IndexError):
                return default

        return WellInfo(
            well_name=_hdr("WELL") or Path(filepath).stem,
            operator=_hdr("COMP"),
            field=_hdr("FLD"),
            basin="",
            county=_hdr("CNTY"),
            state=_hdr("STAT"),
            api_number=_hdr("API") or _hdr("UWI"),
            spud_date=_hdr("DATE") or None,
            total_depth_md=float(_hdr("STOP", "0") or 0),
        )

    @staticmethod
    def _extract_well_info_header(
        header: Dict[str, str], filepath: str
    ) -> WellInfo:
        """Pull WellInfo fields from the manual parser header dict."""

        def _safe_float(key: str, default: float = 0.0) -> float:
            try:
                return float(header.get(key, default))
            except (ValueError, TypeError):
                return default

        return WellInfo(
            well_name=header.get("WELL", "") or Path(filepath).stem,
            operator=header.get("COMP", ""),
            field=header.get("FLD", ""),
            basin="",
            county=header.get("CNTY", ""),
            state=header.get("STAT", ""),
            api_number=header.get("API", "") or header.get("UWI", ""),
            spud_date=header.get("DATE") or None,
            total_depth_md=_safe_float("STOP"),
        )
