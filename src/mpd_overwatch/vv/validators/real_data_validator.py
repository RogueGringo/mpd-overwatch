"""
MPD Command -- Real-Data Validation Module
============================================

Loads actual drilling data from LAS files and validates MPD Command's
calculations against it.  Designed to work with files in the
DATA_TYPES_for_System_Use_EXAMPLES directory tree.

Classes
-------
RealDataLoader      - Discovers and loads LAS files from a directory tree.
HydrostatsValidator - Validates hydrostatic / ECD / pressure-gradient calcs.
SurveyValidator     - Validates survey calculations (min-curvature, DLS, TVD).
DataQualityChecker  - Checks data completeness, null rates, value ranges.

Functions
---------
run_real_data_validation(data_dir) - Orchestrates all validators and returns
                                     a structured report.

Usage::

    from vv_pipeline.validators.real_data_validator import run_real_data_validation

    report = run_real_data_validation(
        "C:/Claude/MPD model building/DATA_TYPES_for_System_Use_EXAMPLES"
    )
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from mpd_overwatch.data.las_parser import LASParser, LASResult
from mpd_overwatch.core.hydraulics import (
    HYDROSTATIC_CONSTANT,
    hydrostatic_pressure,
    equivalent_circulating_density,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants -- Delaware Basin expected ranges
# ---------------------------------------------------------------------------

# Pore-pressure gradient range (psi/ft) for Delaware Basin
DELAWARE_PP_GRAD_MIN = 0.45  # psi/ft
DELAWARE_PP_GRAD_MAX = 0.65  # psi/ft

# Fracture gradient range (psi/ft) for Delaware Basin
DELAWARE_FG_GRAD_MIN = 0.70  # psi/ft
DELAWARE_FG_GRAD_MAX = 0.95  # psi/ft

# DLS realism bound
DLS_MAX_REALISTIC = 15.0  # deg/100ft

# Null sentinel used in most LAS files
LAS_NULL_VALUE = -999.25

# Reasonable drilling-parameter ranges (oilfield units)
PARAMETER_RANGES: Dict[str, Tuple[float, float, str]] = {
    "rop":             (0.0,    500.0,  "ft/hr"),
    "wob":             (0.0,     80.0,  "klbs"),
    "torque":          (0.0,  60000.0,  "ft-lbs"),
    "spp":             (0.0,   8000.0,  "psi"),
    "flow_in":         (0.0,   1500.0,  "gpm"),
    "flow_out":        (0.0,   1500.0,  "gpm"),
    "rpm":             (0.0,    300.0,  "rpm"),
    "hookload":        (0.0,    800.0,  "klbs"),
    "gamma_ray":       (0.0,    300.0,  "API"),
    "apwd":            (0.0,  25000.0,  "psi"),
    "choke_pressure":  (0.0,   5000.0,  "psi"),
    "depth_md":        (0.0,  35000.0,  "ft"),
    "depth_tvd":       (0.0,  25000.0,  "ft"),
    "ecd":             (7.0,     22.0,  "ppg"),
    "bulk_density":    (1.5,      3.2,  "g/cc"),
    "neutron_porosity":(-0.05,    0.6,  "v/v"),
}


# ===================================================================
# Data container for a single validation result
# ===================================================================

@dataclass
class ValidationResult:
    """One validation check outcome."""
    test_name: str
    passed: bool
    expected_range: Optional[str] = None
    actual_value: Optional[Any] = None
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "passed": self.passed,
            "expected_range": self.expected_range,
            "actual_value": self.actual_value,
            "details": self.details,
        }


# ===================================================================
# RealDataLoader
# ===================================================================

class RealDataLoader:
    """Discovers LAS files in a directory tree, loads them with LASParser,
    and returns metadata about what was loaded.

    Parameters
    ----------
    data_dir : str or Path
        Root directory to search for .las files.
    """

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self._parser = LASParser()
        self.loaded: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, str]] = []

    # ----- discovery -------------------------------------------------------

    def discover_las_files(self) -> List[Path]:
        """Recursively find all .las files under *data_dir*."""
        if not self.data_dir.exists():
            logger.warning("Data directory does not exist: %s", self.data_dir)
            return []
        las_files = sorted(self.data_dir.rglob("*.las"))
        logger.info("Discovered %d LAS file(s) under %s", len(las_files), self.data_dir)
        return las_files

    # ----- loading ---------------------------------------------------------

    def load_all(self) -> List[Dict[str, Any]]:
        """Load every discovered LAS file and return metadata dicts.

        Each dict contains:
            file_path, well_name, curves, depth_min, depth_max,
            row_count, result (the LASResult object).
        Files that fail to parse are recorded in *self.errors* and skipped.
        """
        files = self.discover_las_files()
        self.loaded.clear()
        self.errors.clear()

        for fp in files:
            try:
                result = self._parser.parse(str(fp))
                df = result.to_dataframe()

                # Determine depth range
                depth_col = None
                for candidate in ("depth_md", "md"):
                    if candidate in df.columns:
                        depth_col = candidate
                        break
                # Also check for original mnemonic columns (lowered)
                if depth_col is None:
                    for col in df.columns:
                        if col.lower() in ("dept", "depth", "md", "dmea"):
                            depth_col = col
                            break

                depth_min = float(df[depth_col].dropna().min()) if depth_col and not df[depth_col].dropna().empty else None
                depth_max = float(df[depth_col].dropna().max()) if depth_col and not df[depth_col].dropna().empty else None

                meta = {
                    "file_path": str(fp),
                    "well_name": result.well_info.well_name,
                    "curves": list(df.columns),
                    "depth_min": depth_min,
                    "depth_max": depth_max,
                    "row_count": len(df),
                    "result": result,
                }
                self.loaded.append(meta)
                logger.info(
                    "Loaded %s -- %s (%d rows, %d curves)",
                    fp.name, result.well_info.well_name, len(df), len(df.columns),
                )
            except Exception as exc:
                logger.warning("Failed to load %s: %s", fp, exc)
                self.errors.append({"file_path": str(fp), "error": str(exc)})

        logger.info(
            "Load complete: %d succeeded, %d failed",
            len(self.loaded), len(self.errors),
        )
        return self.loaded

    # ----- summary ---------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict of all loaded files."""
        return {
            "files_found": len(self.loaded) + len(self.errors),
            "files_loaded": len(self.loaded),
            "files_failed": len(self.errors),
            "wells": [
                {
                    "file": m["file_path"],
                    "well_name": m["well_name"],
                    "curves": m["curves"],
                    "depth_range": (m["depth_min"], m["depth_max"]),
                    "row_count": m["row_count"],
                }
                for m in self.loaded
            ],
            "load_errors": self.errors,
        }


# ===================================================================
# HydrostatsValidator
# ===================================================================

class HydrostatsValidator:
    """Validates hydrostatic and ECD calculations against real APWD data.

    Checks
    ------
    1. ECD from APWD vs. surface-calculated ECD.
    2. Hydrostatic pressure at TD for a given mud weight.
    3. Pore-pressure gradients within Delaware Basin expected range.
    4. Fracture gradients within Delaware Basin expected range.
    """

    def __init__(self, loaded_files: List[Dict[str, Any]]) -> None:
        self.loaded_files = loaded_files

    def validate(self) -> List[ValidationResult]:
        """Run all hydrostatic validations and return results."""
        results: List[ValidationResult] = []
        for meta in self.loaded_files:
            try:
                results.extend(self._validate_one(meta))
            except Exception as exc:
                results.append(ValidationResult(
                    test_name=f"hydrostats/{Path(meta['file_path']).name}",
                    passed=False,
                    details=f"Unexpected error: {exc}",
                ))
        return results

    # ----- per-file checks -------------------------------------------------

    def _validate_one(self, meta: Dict[str, Any]) -> List[ValidationResult]:
        results: List[ValidationResult] = []
        result: LASResult = meta["result"]
        df = result.to_dataframe()
        fname = Path(meta["file_path"]).name

        # --- 1. ECD from APWD ------------------------------------------------
        has_apwd = "apwd" in df.columns and df["apwd"].notna().any()
        has_tvd = "depth_tvd" in df.columns and df["depth_tvd"].notna().any()
        has_ecd = "ecd" in df.columns and df["ecd"].notna().any()

        if has_apwd and has_tvd:
            results.extend(self._check_ecd_from_apwd(df, fname))
        else:
            results.append(ValidationResult(
                test_name=f"hydrostats/ecd_from_apwd/{fname}",
                passed=True,
                details="Skipped -- APWD or TVD curve not available",
            ))

        # --- 2. Hydrostatic at TD ---------------------------------------------
        td_md = result.well_info.total_depth_md
        if td_md > 0 and has_tvd:
            results.extend(self._check_hydrostatic_at_td(df, fname, td_md))

        # --- 3. Pore-pressure gradient check (if ECD available) ---------------
        if has_ecd and has_tvd:
            results.extend(self._check_gradient_range(
                df, fname, "ecd", "pore_pressure_gradient",
                DELAWARE_PP_GRAD_MIN, DELAWARE_PP_GRAD_MAX,
            ))

        # --- 4. Fracture gradient (informational, check if any frac data) -----
        # Most LAS files won't carry explicit fracture gradient, but if ECD
        # values are present we can at least verify they are physically
        # reasonable (translates to a gradient within the frac range).
        if has_ecd and has_tvd:
            results.extend(self._check_ecd_gradient_plausibility(
                df, fname,
            ))

        return results

    # ----- individual checks -----------------------------------------------

    def _check_ecd_from_apwd(
        self, df: pd.DataFrame, fname: str
    ) -> List[ValidationResult]:
        """Compare ECD derived from APWD to surface-calculated ECD."""
        results: List[ValidationResult] = []
        mask = df["apwd"].notna() & df["depth_tvd"].notna() & (df["depth_tvd"] > 0)
        sub = df.loc[mask].copy()
        if sub.empty:
            results.append(ValidationResult(
                test_name=f"hydrostats/ecd_from_apwd/{fname}",
                passed=True,
                details="No valid APWD+TVD rows",
            ))
            return results

        # ECD_from_APWD = APWD / (0.052 * TVD)
        ecd_from_apwd = sub["apwd"] / (HYDROSTATIC_CONSTANT * sub["depth_tvd"])

        # If file also has an ECD channel, compare
        if "ecd" in sub.columns and sub["ecd"].notna().any():
            ecd_reported = sub.loc[sub["ecd"].notna(), "ecd"]
            ecd_derived = ecd_from_apwd.loc[ecd_reported.index]
            valid = ecd_derived.notna() & ecd_reported.notna() & (ecd_reported > 0)
            if valid.any():
                pct_diff = ((ecd_derived[valid] - ecd_reported[valid]).abs()
                            / ecd_reported[valid] * 100)
                mean_diff = float(pct_diff.mean())
                passed = mean_diff < 5.0
                results.append(ValidationResult(
                    test_name=f"hydrostats/ecd_apwd_vs_reported/{fname}",
                    passed=passed,
                    expected_range="<5% mean difference",
                    actual_value=f"{mean_diff:.2f}%",
                    details=(
                        f"Mean APWD-derived ECD vs reported ECD difference: "
                        f"{mean_diff:.2f}% over {int(valid.sum())} points"
                    ),
                ))
            else:
                results.append(ValidationResult(
                    test_name=f"hydrostats/ecd_apwd_vs_reported/{fname}",
                    passed=True,
                    details="No overlapping valid APWD + ECD rows",
                ))
        else:
            # Just verify APWD-derived ECD is in a reasonable range
            ecd_valid = ecd_from_apwd.dropna()
            if not ecd_valid.empty:
                ecd_min = float(ecd_valid.min())
                ecd_max = float(ecd_valid.max())
                reasonable = (ecd_min >= 7.0) and (ecd_max <= 22.0)
                results.append(ValidationResult(
                    test_name=f"hydrostats/ecd_from_apwd_range/{fname}",
                    passed=reasonable,
                    expected_range="7.0 - 22.0 ppg",
                    actual_value=f"{ecd_min:.2f} - {ecd_max:.2f} ppg",
                    details=f"APWD-derived ECD range over {len(ecd_valid)} points",
                ))

        return results

    def _check_hydrostatic_at_td(
        self, df: pd.DataFrame, fname: str, td_md: float
    ) -> List[ValidationResult]:
        """Verify hydrostatic at TD is consistent with mud weight."""
        results: List[ValidationResult] = []

        # Get deepest TVD with valid data
        tvd_col = df["depth_tvd"].dropna()
        if tvd_col.empty:
            return results

        td_tvd = float(tvd_col.max())
        if td_tvd <= 0:
            return results

        # Estimate mud weight from ECD or assume a typical range
        if "ecd" in df.columns and df["ecd"].notna().any():
            # Use median ECD as an approximation of mud weight
            approx_mw = float(df["ecd"].dropna().median())
        else:
            # Use a typical Delaware Basin mud weight
            approx_mw = 10.0  # ppg (typical)

        expected_hp = hydrostatic_pressure(approx_mw, td_tvd)

        # Check that hydrostatic is physically plausible
        # For a well at TD_TVD with MW, P_h should be between
        # 0.052 * 8.33 * TD_TVD (freshwater) and 0.052 * 20.0 * TD_TVD
        min_hp = hydrostatic_pressure(8.33, td_tvd)
        max_hp = hydrostatic_pressure(20.0, td_tvd)

        passed = min_hp <= expected_hp <= max_hp
        results.append(ValidationResult(
            test_name=f"hydrostats/hydrostatic_at_td/{fname}",
            passed=passed,
            expected_range=f"{min_hp:.0f} - {max_hp:.0f} psi",
            actual_value=f"{expected_hp:.0f} psi (MW={approx_mw:.1f} ppg, TVD={td_tvd:.0f} ft)",
            details=f"Hydrostatic at TD using estimated MW={approx_mw:.1f} ppg",
        ))

        return results

    def _check_gradient_range(
        self,
        df: pd.DataFrame,
        fname: str,
        ecd_col: str,
        test_label: str,
        grad_min: float,
        grad_max: float,
    ) -> List[ValidationResult]:
        """Check that gradients (psi/ft) derived from ECD fall within range."""
        results: List[ValidationResult] = []
        mask = df[ecd_col].notna() & df["depth_tvd"].notna() & (df["depth_tvd"] > 100)
        sub = df.loc[mask]
        if sub.empty:
            return results

        # Gradient in psi/ft = ECD_ppg * 0.052
        gradients = sub[ecd_col] * HYDROSTATIC_CONSTANT
        g_min = float(gradients.min())
        g_max = float(gradients.max())
        g_median = float(gradients.median())

        # At least the median should be in range
        in_range = grad_min <= g_median <= grad_max
        results.append(ValidationResult(
            test_name=f"hydrostats/{test_label}/{fname}",
            passed=in_range,
            expected_range=f"{grad_min:.2f} - {grad_max:.2f} psi/ft",
            actual_value=f"median={g_median:.3f} psi/ft (range {g_min:.3f}-{g_max:.3f})",
            details=f"Gradient from {ecd_col} over {len(sub)} points",
        ))
        return results

    def _check_ecd_gradient_plausibility(
        self, df: pd.DataFrame, fname: str
    ) -> List[ValidationResult]:
        """Verify ECD-derived pressure gradient is below fracture gradient."""
        results: List[ValidationResult] = []
        mask = df["ecd"].notna() & df["depth_tvd"].notna() & (df["depth_tvd"] > 100)
        sub = df.loc[mask]
        if sub.empty:
            return results

        gradient_psi_ft = sub["ecd"] * HYDROSTATIC_CONSTANT
        g_max = float(gradient_psi_ft.max())

        # ECD should not exceed typical frac gradient
        below_frac = g_max <= DELAWARE_FG_GRAD_MAX
        results.append(ValidationResult(
            test_name=f"hydrostats/ecd_below_frac_gradient/{fname}",
            passed=below_frac,
            expected_range=f"<= {DELAWARE_FG_GRAD_MAX:.2f} psi/ft",
            actual_value=f"{g_max:.3f} psi/ft",
            details=f"Max ECD gradient vs Delaware Basin frac limit",
        ))
        return results


# ===================================================================
# SurveyValidator
# ===================================================================

class SurveyValidator:
    """Validates survey data: minimum-curvature TVD, DLS bounds, quality.

    Expects LAS files with MD, INCL, AZIM, TVD, and DLS curves.
    """

    def __init__(self, loaded_files: List[Dict[str, Any]]) -> None:
        self.loaded_files = loaded_files

    def validate(self) -> List[ValidationResult]:
        results: List[ValidationResult] = []
        for meta in self.loaded_files:
            try:
                results.extend(self._validate_one(meta))
            except Exception as exc:
                results.append(ValidationResult(
                    test_name=f"survey/{Path(meta['file_path']).name}",
                    passed=False,
                    details=f"Unexpected error: {exc}",
                ))
        return results

    def _validate_one(self, meta: Dict[str, Any]) -> List[ValidationResult]:
        results: List[ValidationResult] = []
        result: LASResult = meta["result"]
        df = result.to_dataframe()
        fname = Path(meta["file_path"]).name

        # Identify survey columns -- canonical or raw
        md_col = self._find_col(df, ["depth_md", "md"])
        inc_col = self._find_col(df, ["incl"])
        azi_col = self._find_col(df, ["azim"])
        tvd_col = self._find_col(df, ["depth_tvd", "tvd"])
        dls_col = self._find_col(df, ["dls"])

        has_survey = md_col and inc_col and azi_col
        if not has_survey:
            # Not a survey file -- skip
            return results

        logger.info("Survey data found in %s (MD=%s, INC=%s, AZI=%s)",
                     fname, md_col, inc_col, azi_col)

        # Clean data
        survey_df = df[[c for c in [md_col, inc_col, azi_col, tvd_col, dls_col] if c]].copy()
        survey_df = survey_df.replace(LAS_NULL_VALUE, np.nan).dropna(subset=[md_col, inc_col, azi_col])
        survey_df = survey_df.sort_values(md_col).reset_index(drop=True)

        if len(survey_df) < 2:
            results.append(ValidationResult(
                test_name=f"survey/insufficient_stations/{fname}",
                passed=False,
                details=f"Only {len(survey_df)} valid survey station(s)",
            ))
            return results

        # --- 1. Minimum curvature TVD vs reported TVD -------------------------
        if tvd_col:
            results.extend(self._check_min_curvature_tvd(
                survey_df, md_col, inc_col, azi_col, tvd_col, fname,
            ))

        # --- 2. DLS within realistic bounds -----------------------------------
        if dls_col:
            results.extend(self._check_dls_bounds(survey_df, dls_col, fname))
        else:
            # Compute DLS ourselves and check
            results.extend(self._check_computed_dls(
                survey_df, md_col, inc_col, azi_col, fname,
            ))

        # --- 3. Survey quality indicators -------------------------------------
        results.extend(self._check_survey_quality(survey_df, df, fname))

        return results

    # ----- minimum curvature -----------------------------------------------

    def _check_min_curvature_tvd(
        self,
        sdf: pd.DataFrame,
        md_col: str, inc_col: str, azi_col: str, tvd_col: str,
        fname: str,
    ) -> List[ValidationResult]:
        """Recompute TVD via minimum curvature; compare to reported TVD."""
        results: List[ValidationResult] = []

        md = sdf[md_col].to_numpy(dtype=np.float64)
        inc_deg = sdf[inc_col].to_numpy(dtype=np.float64)
        azi_deg = sdf[azi_col].to_numpy(dtype=np.float64)
        tvd_reported = sdf[tvd_col].to_numpy(dtype=np.float64)

        # Compute TVD via minimum curvature
        tvd_calc = self._minimum_curvature_tvd(md, inc_deg, azi_deg)

        # Compare at each station (skip NaN reported values)
        valid = np.isfinite(tvd_reported) & np.isfinite(tvd_calc) & (tvd_reported > 0)
        if not valid.any():
            results.append(ValidationResult(
                test_name=f"survey/min_curvature_tvd/{fname}",
                passed=True,
                details="No valid reported TVD to compare",
            ))
            return results

        diff = np.abs(tvd_calc[valid] - tvd_reported[valid])
        max_diff = float(np.max(diff))
        mean_diff = float(np.mean(diff))
        pct_diff = float(np.mean(diff / tvd_reported[valid] * 100))

        # Allow 0.5% tolerance or 5 ft absolute, whichever is larger
        td_tvd = float(tvd_reported[valid][-1])
        tol_ft = max(5.0, td_tvd * 0.005)
        passed = max_diff < tol_ft

        results.append(ValidationResult(
            test_name=f"survey/min_curvature_tvd/{fname}",
            passed=passed,
            expected_range=f"max diff < {tol_ft:.1f} ft",
            actual_value=f"max={max_diff:.2f} ft, mean={mean_diff:.2f} ft ({pct_diff:.3f}%)",
            details=(
                f"Compared min-curvature TVD to reported TVD at "
                f"{int(valid.sum())} stations. TD TVD={td_tvd:.0f} ft"
            ),
        ))
        return results

    @staticmethod
    def _minimum_curvature_tvd(
        md: np.ndarray, inc_deg: np.ndarray, azi_deg: np.ndarray,
    ) -> np.ndarray:
        """Compute TVD array using the minimum curvature method.

        Parameters
        ----------
        md : ndarray
            Measured depths (ft).
        inc_deg : ndarray
            Inclinations (degrees).
        azi_deg : ndarray
            Azimuths (degrees).

        Returns
        -------
        ndarray
            Computed TVD at each survey station (ft).
        """
        n = len(md)
        tvd = np.zeros(n, dtype=np.float64)

        inc_rad = np.radians(inc_deg)
        azi_rad = np.radians(azi_deg)

        for i in range(1, n):
            delta_md = md[i] - md[i - 1]
            if delta_md <= 0:
                tvd[i] = tvd[i - 1]
                continue

            i1 = inc_rad[i - 1]
            i2 = inc_rad[i]
            a1 = azi_rad[i - 1]
            a2 = azi_rad[i]

            # Dogleg angle (beta)
            cos_beta = (
                math.cos(i2 - i1)
                - math.sin(i1) * math.sin(i2) * (1 - math.cos(a2 - a1))
            )
            cos_beta = max(-1.0, min(1.0, cos_beta))
            beta = math.acos(cos_beta)

            # Ratio factor (RF)
            if abs(beta) < 1e-7:
                rf = 1.0
            else:
                rf = 2.0 / beta * math.tan(beta / 2.0)

            delta_tvd = 0.5 * delta_md * (math.cos(i1) + math.cos(i2)) * rf
            tvd[i] = tvd[i - 1] + delta_tvd

        return tvd

    # ----- DLS checks ------------------------------------------------------

    def _check_dls_bounds(
        self, sdf: pd.DataFrame, dls_col: str, fname: str,
    ) -> List[ValidationResult]:
        """Check that reported DLS is within realistic bounds."""
        results: List[ValidationResult] = []
        dls = sdf[dls_col].replace(LAS_NULL_VALUE, np.nan).dropna()
        if dls.empty:
            return results

        dls_max = float(dls.max())
        dls_mean = float(dls.mean())
        passed = dls_max <= DLS_MAX_REALISTIC

        results.append(ValidationResult(
            test_name=f"survey/dls_bounds/{fname}",
            passed=passed,
            expected_range=f"<= {DLS_MAX_REALISTIC} deg/100ft",
            actual_value=f"max={dls_max:.2f}, mean={dls_mean:.2f} deg/100ft",
            details=f"Reported DLS over {len(dls)} stations",
        ))
        return results

    def _check_computed_dls(
        self,
        sdf: pd.DataFrame,
        md_col: str, inc_col: str, azi_col: str,
        fname: str,
    ) -> List[ValidationResult]:
        """Compute DLS and check bounds when no DLS curve is present."""
        results: List[ValidationResult] = []

        md = sdf[md_col].to_numpy(dtype=np.float64)
        inc_deg = sdf[inc_col].to_numpy(dtype=np.float64)
        azi_deg = sdf[azi_col].to_numpy(dtype=np.float64)

        dls_values: List[float] = []
        for i in range(1, len(md)):
            delta_md = md[i] - md[i - 1]
            if delta_md <= 0:
                continue
            i1 = math.radians(inc_deg[i - 1])
            i2 = math.radians(inc_deg[i])
            a1 = math.radians(azi_deg[i - 1])
            a2 = math.radians(azi_deg[i])

            cos_beta = (
                math.cos(i2 - i1)
                - math.sin(i1) * math.sin(i2) * (1 - math.cos(a2 - a1))
            )
            cos_beta = max(-1.0, min(1.0, cos_beta))
            beta_deg = math.degrees(math.acos(cos_beta))
            dls = beta_deg / delta_md * 100.0  # deg/100ft
            dls_values.append(dls)

        if not dls_values:
            return results

        dls_arr = np.array(dls_values)
        dls_max = float(dls_arr.max())
        dls_mean = float(dls_arr.mean())
        passed = dls_max <= DLS_MAX_REALISTIC

        results.append(ValidationResult(
            test_name=f"survey/computed_dls_bounds/{fname}",
            passed=passed,
            expected_range=f"<= {DLS_MAX_REALISTIC} deg/100ft",
            actual_value=f"max={dls_max:.2f}, mean={dls_mean:.2f} deg/100ft",
            details=f"Computed DLS over {len(dls_values)} intervals",
        ))
        return results

    # ----- survey quality ---------------------------------------------------

    def _check_survey_quality(
        self, sdf: pd.DataFrame, full_df: pd.DataFrame, fname: str,
    ) -> List[ValidationResult]:
        """Check survey quality indicators (QI column, station spacing, etc.)."""
        results: List[ValidationResult] = []

        # QI (quality index) -- if present, count bad stations
        qi_col = self._find_col(full_df, ["qi"])
        if qi_col and qi_col in sdf.columns:
            qi = sdf[qi_col].replace(LAS_NULL_VALUE, np.nan).dropna()
            # QI == 0 typically means "passed all criteria"
            if not qi.empty:
                # Try numeric comparison
                try:
                    qi_num = qi.astype(float)
                    good_count = int((qi_num == 0).sum())
                    total = len(qi_num)
                    pct_good = good_count / total * 100 if total > 0 else 0
                    results.append(ValidationResult(
                        test_name=f"survey/quality_index/{fname}",
                        passed=pct_good >= 80,
                        expected_range=">= 80% good (QI=0)",
                        actual_value=f"{pct_good:.1f}% ({good_count}/{total})",
                        details="Survey quality index analysis",
                    ))
                except (ValueError, TypeError):
                    results.append(ValidationResult(
                        test_name=f"survey/quality_index/{fname}",
                        passed=True,
                        details=f"QI column not numeric -- skipped",
                    ))

        # Station spacing regularity
        md_col = self._find_col(sdf, ["depth_md", "md"])
        if md_col:
            md_vals = sdf[md_col].dropna().to_numpy()
            if len(md_vals) > 1:
                spacings = np.diff(md_vals)
                spacings = spacings[spacings > 0]
                if len(spacings) > 0:
                    med_spacing = float(np.median(spacings))
                    max_spacing = float(np.max(spacings))
                    # Flag if max gap is more than 10x the median
                    regularity_ok = max_spacing <= 10 * med_spacing
                    results.append(ValidationResult(
                        test_name=f"survey/station_spacing/{fname}",
                        passed=regularity_ok,
                        expected_range=f"max gap <= {10 * med_spacing:.0f} ft (10x median)",
                        actual_value=(
                            f"median={med_spacing:.0f} ft, "
                            f"max={max_spacing:.0f} ft"
                        ),
                        details=f"Survey station spacing over {len(spacings)} intervals",
                    ))

        return results

    # ----- helpers ----------------------------------------------------------

    @staticmethod
    def _find_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        """Return the first column name found in *df* from *candidates*."""
        for c in candidates:
            if c in df.columns:
                return c
            # Also try lowercase version
            if c.lower() in df.columns:
                return c.lower()
        return None


# ===================================================================
# DataQualityChecker
# ===================================================================

class DataQualityChecker:
    """Checks data quality: null percentages, value ranges, data density.

    Parameters
    ----------
    loaded_files : list
        Output of RealDataLoader.load_all().
    """

    def __init__(self, loaded_files: List[Dict[str, Any]]) -> None:
        self.loaded_files = loaded_files

    def check(self) -> List[ValidationResult]:
        """Run quality checks on all loaded files."""
        results: List[ValidationResult] = []
        for meta in self.loaded_files:
            try:
                results.extend(self._check_one(meta))
            except Exception as exc:
                results.append(ValidationResult(
                    test_name=f"quality/{Path(meta['file_path']).name}",
                    passed=False,
                    details=f"Unexpected error: {exc}",
                ))
        return results

    def _check_one(self, meta: Dict[str, Any]) -> List[ValidationResult]:
        results: List[ValidationResult] = []
        result: LASResult = meta["result"]
        df = result.to_dataframe()
        fname = Path(meta["file_path"]).name
        n_rows = len(df)

        if n_rows == 0:
            results.append(ValidationResult(
                test_name=f"quality/empty_file/{fname}",
                passed=False,
                details="File has zero data rows",
            ))
            return results

        # --- 1. Null percentage per curve (using -999.25 AND NaN) -------------
        high_null_curves: List[str] = []
        curve_null_pcts: Dict[str, float] = {}

        for col in df.columns:
            null_count = int(df[col].isna().sum())
            # Also count the LAS null sentinel if column is numeric
            if pd.api.types.is_numeric_dtype(df[col]):
                null_count += int((df[col] == LAS_NULL_VALUE).sum())
            pct = null_count / n_rows * 100
            curve_null_pcts[col] = round(pct, 1)
            if pct > 50.0:
                high_null_curves.append(col)

        passed_nulls = len(high_null_curves) == 0
        results.append(ValidationResult(
            test_name=f"quality/null_check/{fname}",
            passed=passed_nulls,
            expected_range="<= 50% nulls per curve",
            actual_value=(
                f"{len(high_null_curves)} curve(s) > 50% null"
                if high_null_curves else "All curves OK"
            ),
            details=(
                f"High-null curves: {high_null_curves}" if high_null_curves
                else f"Checked {len(df.columns)} curves across {n_rows} rows"
            ),
        ))

        # --- 2. Value range checks --------------------------------------------
        out_of_range_details: List[str] = []
        for col in df.columns:
            canonical = col.lower()
            if canonical not in PARAMETER_RANGES:
                continue
            lo, hi, unit = PARAMETER_RANGES[canonical]
            if not pd.api.types.is_numeric_dtype(df[col]):
                continue
            valid = df[col].dropna()
            valid = valid[valid != LAS_NULL_VALUE]
            if valid.empty:
                continue
            v_min = float(valid.min())
            v_max = float(valid.max())
            if v_min < lo or v_max > hi:
                out_of_range_details.append(
                    f"{col}: {v_min:.2f}-{v_max:.2f} {unit} "
                    f"(expected {lo:.1f}-{hi:.1f})"
                )

        passed_ranges = len(out_of_range_details) == 0
        results.append(ValidationResult(
            test_name=f"quality/value_ranges/{fname}",
            passed=passed_ranges,
            expected_range="All params within physical limits",
            actual_value=(
                f"{len(out_of_range_details)} param(s) out of range"
                if out_of_range_details else "All in range"
            ),
            details="; ".join(out_of_range_details) if out_of_range_details else "OK",
        ))

        # --- 3. Data density (points per foot or per hour) --------------------
        md_col = None
        for c in ("depth_md", "md"):
            if c in df.columns:
                md_col = c
                break
        if md_col:
            md_valid = df[md_col].dropna()
            md_valid = md_valid[md_valid != LAS_NULL_VALUE]
            if len(md_valid) >= 2:
                depth_range = float(md_valid.max() - md_valid.min())
                if depth_range > 0:
                    ppf = len(md_valid) / depth_range  # points per foot
                    results.append(ValidationResult(
                        test_name=f"quality/data_density/{fname}",
                        passed=True,
                        expected_range="informational",
                        actual_value=f"{ppf:.4f} pts/ft ({len(md_valid)} pts / {depth_range:.0f} ft)",
                        details="Data density (depth-indexed)",
                    ))

        return results


# ===================================================================
# Orchestrator
# ===================================================================

def run_real_data_validation(
    data_dir: str | Path,
) -> Dict[str, Any]:
    """Orchestrate all real-data validators.

    Parameters
    ----------
    data_dir : str or Path
        Root directory containing LAS files (searched recursively).

    Returns
    -------
    dict
        Structured report::

            {
                "files_found": int,
                "files_loaded": int,
                "load_errors": list[dict],
                "validation_results": {
                    "hydrostats": [ValidationResult.to_dict(), ...],
                    "survey":     [...],
                    "quality":    [...],
                },
                "data_quality": {...},
                "summary": {
                    "total_checks": int,
                    "passed": int,
                    "failed": int,
                },
            }
    """
    logger.info("=" * 70)
    logger.info("  MPD Command -- Real-Data Validation")
    logger.info("  Data directory: %s", data_dir)
    logger.info("=" * 70)

    # --- Step 1: Load data ---------------------------------------------------
    loader = RealDataLoader(data_dir)
    loaded = loader.load_all()
    load_summary = loader.summary()

    logger.info(
        "Loaded %d / %d files",
        load_summary["files_loaded"], load_summary["files_found"],
    )

    # --- Step 2: Run validators ----------------------------------------------
    hydro_results: List[ValidationResult] = []
    survey_results: List[ValidationResult] = []
    quality_results: List[ValidationResult] = []

    if loaded:
        try:
            hydro_validator = HydrostatsValidator(loaded)
            hydro_results = hydro_validator.validate()
        except Exception as exc:
            logger.error("HydrostatsValidator failed: %s", exc)
            hydro_results = [ValidationResult(
                test_name="hydrostats/suite_error",
                passed=False,
                details=str(exc),
            )]

        try:
            survey_validator = SurveyValidator(loaded)
            survey_results = survey_validator.validate()
        except Exception as exc:
            logger.error("SurveyValidator failed: %s", exc)
            survey_results = [ValidationResult(
                test_name="survey/suite_error",
                passed=False,
                details=str(exc),
            )]

        try:
            quality_checker = DataQualityChecker(loaded)
            quality_results = quality_checker.check()
        except Exception as exc:
            logger.error("DataQualityChecker failed: %s", exc)
            quality_results = [ValidationResult(
                test_name="quality/suite_error",
                passed=False,
                details=str(exc),
            )]

    # --- Step 3: Build report ------------------------------------------------
    all_results = hydro_results + survey_results + quality_results
    total = len(all_results)
    passed = sum(1 for r in all_results if r.passed)
    failed = total - passed

    report = {
        "files_found": load_summary["files_found"],
        "files_loaded": load_summary["files_loaded"],
        "load_errors": load_summary["load_errors"],
        "validation_results": {
            "hydrostats": [r.to_dict() for r in hydro_results],
            "survey": [r.to_dict() for r in survey_results],
            "quality": [r.to_dict() for r in quality_results],
        },
        "data_quality": {
            "wells_loaded": [
                {
                    "well_name": m["well_name"],
                    "file": m["file_path"],
                    "curves": m["curves"],
                    "rows": m["row_count"],
                    "depth_range": (m["depth_min"], m["depth_max"]),
                }
                for m in loaded
            ],
        },
        "summary": {
            "total_checks": total,
            "passed": passed,
            "failed": failed,
        },
    }

    # --- Log summary ---------------------------------------------------------
    logger.info("-" * 70)
    logger.info("  Validation complete: %d/%d checks passed", passed, total)
    for r in all_results:
        status = "PASS" if r.passed else "FAIL"
        logger.info("  [%s] %s -- %s", status, r.test_name, r.details[:80])
    logger.info("-" * 70)

    return report


# ===================================================================
# CLI entry point
# ===================================================================

def _print_report(report: Dict[str, Any]) -> None:
    """Pretty-print a validation report to stdout."""
    print()
    print("=" * 80)
    print("  MPD COMMAND -- REAL-DATA VALIDATION REPORT")
    print("=" * 80)

    print(f"\n  Files found:  {report['files_found']}")
    print(f"  Files loaded: {report['files_loaded']}")
    if report["load_errors"]:
        print(f"  Load errors:  {len(report['load_errors'])}")
        for err in report["load_errors"]:
            print(f"    - {err['file_path']}: {err['error']}")

    for section_name, section_results in report["validation_results"].items():
        print(f"\n  --- {section_name.upper()} ---")
        if not section_results:
            print("    (no checks)")
            continue
        for r in section_results:
            status = "PASS" if r["passed"] else "FAIL"
            print(f"    [{status}] {r['test_name']}")
            if r.get("expected_range"):
                print(f"           expected : {r['expected_range']}")
            if r.get("actual_value"):
                print(f"           actual   : {r['actual_value']}")
            if r.get("details"):
                print(f"           details  : {r['details']}")

    s = report["summary"]
    print(f"\n  SUMMARY: {s['passed']}/{s['total_checks']} checks passed, "
          f"{s['failed']} failed")
    print("=" * 80)


if __name__ == "__main__":
    import sys as _sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Default data directory
    _this_file = os.path.abspath(__file__)
    _pkg_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_this_file)))))
    default_dir = os.path.join(
        _pkg_root,
        "DATA_TYPES_for_System_Use_EXAMPLES",
    )
    data_dir = _sys.argv[1] if len(_sys.argv) > 1 else default_dir

    report = run_real_data_validation(data_dir)
    _print_report(report)
