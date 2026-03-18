"""
Formation Damage Calculation Module — MPD Command
===================================================
Compares formation damage between conventional overbalanced drilling (OBD)
and Managed Pressure Drilling (MPD).

Physics basis:
  - Hawkins (1956) skin factor model
  - Radial filtrate invasion (simplified)
  - Permeability impairment from solids plugging, clay swelling, phase trapping
  - Productivity index (Darcy radial‑flow, semi‑steady‑state)

Default values calibrated for Delaware Basin Wolfcamp wells.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np


# ============================================================================
# Data classes — inputs
# ============================================================================

@dataclass
class ReservoirProperties:
    """Static reservoir properties."""
    k: float = 0.1                # Virgin permeability, mD (Wolfcamp matrix)
    phi: float = 0.07             # Porosity, fraction
    h: float = 200.0              # Net pay thickness, ft
    r_w: float = 0.354            # Wellbore radius, ft  (8‑1/2″ hole → 4.25″ radius)
    r_e: float = 660.0            # Drainage radius, ft  (~40‑acre spacing)
    Bo: float = 1.35              # Oil formation volume factor, RB/STB
    mu_o: float = 0.8             # Oil viscosity, cP
    Sw: float = 0.30              # Water saturation, fraction
    So: float = 0.55              # Oil saturation, fraction
    temperature: float = 200.0    # Reservoir temperature, degF


@dataclass
class DrillingConditions:
    """Drilling parameters that drive formation damage."""
    overbalance_psi: float = 500.0       # Overbalance pressure, psi
    exposure_time_hr: float = 48.0       # Open‑hole exposure time, hours
    mud_filtrate_rate: float = 0.02      # Static filtrate rate, bbl/hr/ft²
    mud_solids_fraction: float = 0.06    # Volume fraction of drilled solids in mud
    mud_type: str = "WBM"                # "WBM" or "OBM"
    spurt_loss_bbl: float = 0.05         # Spurt loss per sq ft, bbl


@dataclass
class MPDConditions:
    """MPD‑specific drilling parameters (tighter pressure window)."""
    overbalance_psi: float = 75.0        # Overbalance pressure, psi (typical CBHP MPD)
    exposure_time_hr: float = 24.0       # Reduced open‑hole exposure time, hours
    mud_filtrate_rate: float = 0.005     # Reduced filtrate rate, bbl/hr/ft²
    mud_solids_fraction: float = 0.03    # Cleaner mud / less invasion
    mud_type: str = "OBM"                # OBM more common in MPD ops
    spurt_loss_bbl: float = 0.01


# ============================================================================
# Data classes — outputs
# ============================================================================

@dataclass
class DamageResult:
    """Calculated formation damage for one scenario."""
    scenario: str                    # "Conventional OBD" or "MPD"
    overbalance_psi: float
    filtrate_volume_bbl: float       # Total filtrate lost into formation
    invasion_radius_ft: float        # r_d
    kd_over_k: float                 # Permeability reduction ratio
    k_damaged_mD: float              # Damaged permeability
    skin_factor: float               # S (Hawkins)
    PI: float                        # Productivity index, STB/d/psi
    damage_mechanisms: Dict[str, float] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    """Side‑by‑side comparison of conventional vs MPD formation damage."""
    conventional: DamageResult
    mpd: DamageResult
    skin_reduction_pct: float        # (S_conv - S_mpd) / S_conv × 100
    PI_uplift_pct: float             # (PI_mpd - PI_conv) / PI_conv × 100
    comparison_table: Dict[str, Dict[str, float]] = field(default_factory=dict)


# ============================================================================
# Core calculation functions
# ============================================================================

def filtrate_volume(
    overbalance_psi: float,
    exposure_hr: float,
    filtrate_rate: float,
    spurt_loss: float,
    r_w: float,
    h: float,
) -> float:
    """
    Estimate cumulative filtrate invasion volume (bbl).

    Combines spurt loss with time‑dependent Carter‑type leak‑off.
    Filtrate volume ~ ΔP^0.5 × sqrt(t) for filter‑cake controlled loss.

    Parameters
    ----------
    overbalance_psi : float  Overbalance pressure, psi.
    exposure_hr     : float  Open‑hole exposure time, hours.
    filtrate_rate   : float  Static filtrate rate at reference ΔP=100 psi, bbl/hr/ft².
    spurt_loss      : float  Instantaneous spurt loss, bbl/ft².
    r_w             : float  Wellbore radius, ft.
    h               : float  Net pay, ft.

    Returns
    -------
    float : Cumulative filtrate volume, bbl.
    """
    # Wellbore surface area open to formation (lateral area of cylinder)
    A_ft2 = 2.0 * math.pi * r_w * h

    # Pressure scaling — filtrate leak‑off proportional to sqrt(ΔP)
    dp_factor = math.sqrt(max(overbalance_psi, 0.0) / 100.0)

    # Time‑dependent filtrate (Carter model: V ~ sqrt(t))
    V_time = filtrate_rate * dp_factor * math.sqrt(exposure_hr) * A_ft2

    # Spurt loss (instantaneous)
    V_spurt = spurt_loss * dp_factor * A_ft2

    return V_spurt + V_time


def invasion_radius(
    r_w: float,
    V_filtrate_bbl: float,
    h: float,
    phi: float,
) -> float:
    """
    Simplified radial invasion depth.

    r_d = sqrt(r_w² + (V_filtrate × 5.615) / (π × h × φ))

    Parameters
    ----------
    r_w            : float  Wellbore radius, ft.
    V_filtrate_bbl : float  Cumulative filtrate volume, bbl.
    h              : float  Net pay thickness, ft.
    phi            : float  Porosity, fraction.

    Returns
    -------
    float : Invasion radius r_d, ft.
    """
    V_ft3 = V_filtrate_bbl * 5.615  # bbl → ft³
    inner = r_w ** 2 + V_ft3 / (math.pi * h * phi)
    return math.sqrt(max(inner, r_w ** 2))


def permeability_reduction(
    overbalance_psi: float,
    mud_solids_frac: float,
    mud_type: str = "WBM",
    reservoir: Optional[ReservoirProperties] = None,
) -> tuple[float, Dict[str, float]]:
    """
    Estimate k_d/k ratio and breakdown by damage mechanism.

    Returns a tuple of (kd_over_k, mechanisms_dict).

    Mechanism contributions (multiplicative model):
        k_d/k = f_solids × f_clay × f_phase

    Parameters
    ----------
    overbalance_psi : float   Overbalance pressure, psi.
    mud_solids_frac : float   Volume fraction of drilled solids in mud.
    mud_type        : str     "WBM" or "OBM".
    reservoir       : ReservoirProperties (optional, used for clay/phase logic).

    Returns
    -------
    (float, dict) : (k_d/k ratio, {mechanism: impairment factor}).
    """
    # --- 1. Solids plugging ---------------------------------------------------
    # Higher ΔP drives more solids into pore throats.
    # Empirical sigmoid‑ish model: factor drops from ~0.95 (low ΔP) to ~0.3 (high ΔP)
    dp_norm = overbalance_psi / 1000.0  # normalise to 1000 psi reference
    f_solids = 1.0 - 0.65 * (1.0 - math.exp(-2.0 * dp_norm)) * (mud_solids_frac / 0.06)
    f_solids = max(0.10, min(f_solids, 1.0))

    # --- 2. Clay swelling / fines migration -----------------------------------
    # WBM causes far more clay damage than OBM
    if mud_type.upper() == "WBM":
        f_clay = 1.0 - 0.35 * (1.0 - math.exp(-1.5 * dp_norm))
    else:
        f_clay = 1.0 - 0.08 * (1.0 - math.exp(-1.0 * dp_norm))
    f_clay = max(0.25, min(f_clay, 1.0))

    # --- 3. Phase trapping (relative‑perm damage) -----------------------------
    # Filtrate invasion creates a mixed‑phase zone → reduced kro
    f_phase = 1.0 - 0.20 * (1.0 - math.exp(-1.8 * dp_norm))
    f_phase = max(0.40, min(f_phase, 1.0))

    kd_over_k = f_solids * f_clay * f_phase
    kd_over_k = max(0.05, min(kd_over_k, 1.0))

    mechanisms = {
        "solids_plugging": f_solids,
        "clay_swelling": f_clay,
        "phase_trapping": f_phase,
        "combined_kd_over_k": kd_over_k,
    }
    return kd_over_k, mechanisms


def skin_factor(
    k: float,
    k_d: float,
    r_d: float,
    r_w: float,
) -> float:
    """
    Hawkins skin factor.

    S = (k / k_d - 1) × ln(r_d / r_w)

    Parameters
    ----------
    k   : float  Virgin permeability, mD.
    k_d : float  Damaged permeability, mD.
    r_d : float  Damage (invasion) radius, ft.
    r_w : float  Wellbore radius, ft.

    Returns
    -------
    float : Dimensionless skin factor S.
    """
    if k_d <= 0 or r_w <= 0:
        raise ValueError("k_d and r_w must be positive.")
    if r_d <= r_w:
        return 0.0  # No damage zone beyond wellbore wall
    return (k / k_d - 1.0) * math.log(r_d / r_w)


def productivity_index(
    k: float,
    h: float,
    Bo: float,
    mu: float,
    r_e: float,
    r_w: float,
    S: float,
) -> float:
    """
    Productivity index for radial semi‑steady‑state flow (Darcy units).

    PI = (k × h) / (141.2 × B_o × μ × (ln(r_e / r_w) + S))

    Parameters
    ----------
    k   : float  Permeability, mD.
    h   : float  Net pay, ft.
    Bo  : float  Oil FVF, RB/STB.
    mu  : float  Viscosity, cP.
    r_e : float  Drainage radius, ft.
    r_w : float  Wellbore radius, ft.
    S   : float  Skin factor (dimensionless).

    Returns
    -------
    float : PI in STB/d/psi.
    """
    denom = 141.2 * Bo * mu * (math.log(r_e / r_w) + S)
    if denom <= 0:
        raise ValueError("Denominator in PI equation is non‑positive; check inputs.")
    return (k * h) / denom


# ============================================================================
# Scenario runners
# ============================================================================

def calculate_damage(
    reservoir: ReservoirProperties,
    drilling: DrillingConditions | MPDConditions,
    scenario_name: str = "Scenario",
) -> DamageResult:
    """
    Run full formation damage calculation for one drilling scenario.

    Parameters
    ----------
    reservoir     : ReservoirProperties
    drilling      : DrillingConditions or MPDConditions
    scenario_name : str  Label for the result.

    Returns
    -------
    DamageResult
    """
    # Step 1 — filtrate volume
    V_f = filtrate_volume(
        overbalance_psi=drilling.overbalance_psi,
        exposure_hr=drilling.exposure_time_hr,
        filtrate_rate=drilling.mud_filtrate_rate,
        spurt_loss=drilling.spurt_loss_bbl,
        r_w=reservoir.r_w,
        h=reservoir.h,
    )

    # Step 2 — invasion radius
    r_d = invasion_radius(
        r_w=reservoir.r_w,
        V_filtrate_bbl=V_f,
        h=reservoir.h,
        phi=reservoir.phi,
    )

    # Step 3 — permeability impairment
    kd_ratio, mechs = permeability_reduction(
        overbalance_psi=drilling.overbalance_psi,
        mud_solids_frac=drilling.mud_solids_fraction,
        mud_type=drilling.mud_type,
        reservoir=reservoir,
    )
    k_d = reservoir.k * kd_ratio

    # Step 4 — skin
    S = skin_factor(reservoir.k, k_d, r_d, reservoir.r_w)

    # Step 5 — productivity index
    PI = productivity_index(
        k=reservoir.k,
        h=reservoir.h,
        Bo=reservoir.Bo,
        mu=reservoir.mu_o,
        r_e=reservoir.r_e,
        r_w=reservoir.r_w,
        S=S,
    )

    return DamageResult(
        scenario=scenario_name,
        overbalance_psi=drilling.overbalance_psi,
        filtrate_volume_bbl=V_f,
        invasion_radius_ft=r_d,
        kd_over_k=kd_ratio,
        k_damaged_mD=k_d,
        skin_factor=S,
        PI=PI,
        damage_mechanisms=mechs,
    )


def compare_conventional_vs_mpd(
    reservoir: Optional[ReservoirProperties] = None,
    conventional: Optional[DrillingConditions] = None,
    mpd: Optional[MPDConditions] = None,
) -> ComparisonResult:
    """
    Run both scenarios and produce a side‑by‑side comparison.

    All arguments are optional — defaults represent a typical
    Delaware Basin Wolfcamp lateral.

    Returns
    -------
    ComparisonResult
    """
    if reservoir is None:
        reservoir = ReservoirProperties()
    if conventional is None:
        conventional = DrillingConditions()
    if mpd is None:
        mpd = MPDConditions()

    conv_result = calculate_damage(reservoir, conventional, "Conventional OBD")
    mpd_result = calculate_damage(reservoir, mpd, "MPD (CBHP)")

    # Percent changes
    if conv_result.skin_factor > 0:
        skin_reduction = (
            (conv_result.skin_factor - mpd_result.skin_factor)
            / conv_result.skin_factor * 100.0
        )
    else:
        skin_reduction = 0.0

    if conv_result.PI > 0:
        PI_uplift = (mpd_result.PI - conv_result.PI) / conv_result.PI * 100.0
    else:
        PI_uplift = 0.0

    # Comparison table — every damage mechanism side‑by‑side
    table = _build_comparison_table(conv_result, mpd_result, reservoir)

    return ComparisonResult(
        conventional=conv_result,
        mpd=mpd_result,
        skin_reduction_pct=skin_reduction,
        PI_uplift_pct=PI_uplift,
        comparison_table=table,
    )


# ============================================================================
# Comparison table generator
# ============================================================================

def _build_comparison_table(
    conv: DamageResult,
    mpd: DamageResult,
    reservoir: ReservoirProperties,
) -> Dict[str, Dict[str, float]]:
    """
    Build a structured comparison dict covering all damage mechanisms and
    key deliverables.

    Structure:
        {
          "parameter_name": {
              "conventional": value,
              "mpd": value,
              "unit": str,
              "improvement_pct": value,   # positive = MPD better
          },
          ...
        }
    """
    def pct_improvement(conv_val: float, mpd_val: float, lower_is_better: bool = True) -> float:
        """Return % improvement (positive = MPD better)."""
        if conv_val == 0:
            return 0.0
        delta = conv_val - mpd_val if lower_is_better else mpd_val - conv_val
        return delta / abs(conv_val) * 100.0

    table: Dict[str, Dict[str, float | str]] = {}

    # Overbalance pressure
    table["overbalance_pressure"] = {
        "conventional": conv.overbalance_psi,
        "mpd": mpd.overbalance_psi,
        "unit": "psi",
        "improvement_pct": pct_improvement(conv.overbalance_psi, mpd.overbalance_psi),
    }

    # Filtrate invasion volume
    table["filtrate_volume"] = {
        "conventional": round(conv.filtrate_volume_bbl, 2),
        "mpd": round(mpd.filtrate_volume_bbl, 2),
        "unit": "bbl",
        "improvement_pct": round(pct_improvement(conv.filtrate_volume_bbl, mpd.filtrate_volume_bbl), 1),
    }

    # Invasion radius
    table["invasion_radius"] = {
        "conventional": round(conv.invasion_radius_ft, 3),
        "mpd": round(mpd.invasion_radius_ft, 3),
        "unit": "ft",
        "improvement_pct": round(pct_improvement(conv.invasion_radius_ft, mpd.invasion_radius_ft), 1),
    }

    # Permeability ratio (k_d / k) — higher is better
    table["kd_over_k"] = {
        "conventional": round(conv.kd_over_k, 4),
        "mpd": round(mpd.kd_over_k, 4),
        "unit": "fraction",
        "improvement_pct": round(pct_improvement(conv.kd_over_k, mpd.kd_over_k, lower_is_better=False), 1),
    }

    # Individual mechanisms
    for mech_key in ("solids_plugging", "clay_swelling", "phase_trapping"):
        conv_val = conv.damage_mechanisms.get(mech_key, 1.0)
        mpd_val = mpd.damage_mechanisms.get(mech_key, 1.0)
        table[mech_key] = {
            "conventional": round(conv_val, 4),
            "mpd": round(mpd_val, 4),
            "unit": "fraction (1.0 = no damage)",
            "improvement_pct": round(pct_improvement(conv_val, mpd_val, lower_is_better=False), 1),
        }

    # Skin factor (lower is better)
    table["skin_factor"] = {
        "conventional": round(conv.skin_factor, 2),
        "mpd": round(mpd.skin_factor, 2),
        "unit": "dimensionless",
        "improvement_pct": round(pct_improvement(conv.skin_factor, mpd.skin_factor), 1),
    }

    # Productivity index (higher is better)
    table["productivity_index"] = {
        "conventional": round(conv.PI, 4),
        "mpd": round(mpd.PI, 4),
        "unit": "STB/d/psi",
        "improvement_pct": round(pct_improvement(conv.PI, mpd.PI, lower_is_better=False), 1),
    }

    return table


# ============================================================================
# Sensitivity / sweep helpers
# ============================================================================

def skin_vs_overbalance_sweep(
    reservoir: Optional[ReservoirProperties] = None,
    dp_range: Optional[np.ndarray] = None,
    mud_type: str = "WBM",
    exposure_hr: float = 48.0,
    filtrate_rate: float = 0.02,
    solids_frac: float = 0.06,
    spurt_loss: float = 0.05,
) -> Dict[str, np.ndarray]:
    """
    Sweep overbalance pressure and return arrays of skin, kd/k, invasion radius.

    Useful for plotting skin factor vs overbalance.

    Returns
    -------
    dict with keys: "dp", "skin", "kd_over_k", "invasion_radius_ft", "PI"
    """
    if reservoir is None:
        reservoir = ReservoirProperties()
    if dp_range is None:
        dp_range = np.linspace(25.0, 1500.0, 60)

    skins = np.zeros_like(dp_range)
    kd_ratios = np.zeros_like(dp_range)
    r_ds = np.zeros_like(dp_range)
    PIs = np.zeros_like(dp_range)

    for i, dp in enumerate(dp_range):
        V_f = filtrate_volume(dp, exposure_hr, filtrate_rate, spurt_loss,
                              reservoir.r_w, reservoir.h)
        r_d = invasion_radius(reservoir.r_w, V_f, reservoir.h, reservoir.phi)
        kd_ratio, _ = permeability_reduction(dp, solids_frac, mud_type, reservoir)
        k_d = reservoir.k * kd_ratio
        S = skin_factor(reservoir.k, k_d, r_d, reservoir.r_w)
        PI = productivity_index(reservoir.k, reservoir.h, reservoir.Bo,
                                reservoir.mu_o, reservoir.r_e, reservoir.r_w, S)
        skins[i] = S
        kd_ratios[i] = kd_ratio
        r_ds[i] = r_d
        PIs[i] = PI

    return {
        "dp": dp_range,
        "skin": skins,
        "kd_over_k": kd_ratios,
        "invasion_radius_ft": r_ds,
        "PI": PIs,
    }


# ============================================================================
# Pretty‑print utility
# ============================================================================

def print_comparison(result: ComparisonResult) -> str:
    """Return a formatted string summarising the comparison."""
    lines: List[str] = []
    lines.append("=" * 78)
    lines.append("  FORMATION DAMAGE COMPARISON -- Conventional OBD  vs  MPD (CBHP)")
    lines.append("=" * 78)

    header = f"{'Parameter':<30} {'Conventional':>14} {'MPD':>14} {'Improvement':>14}"
    lines.append(header)
    lines.append("-" * 78)

    for key, row in result.comparison_table.items():
        label = key.replace("_", " ").title()
        conv_val = row["conventional"]
        mpd_val = row["mpd"]
        imp = row["improvement_pct"]
        unit = row.get("unit", "")
        lines.append(
            f"{label:<30} {conv_val:>14} {mpd_val:>14} {imp:>+13.1f}%"
        )

    lines.append("-" * 78)
    lines.append(
        f"  Skin Reduction:  {result.skin_reduction_pct:+.1f}%   |   "
        f"PI Uplift:  {result.PI_uplift_pct:+.1f}%"
    )
    lines.append("=" * 78)
    return "\n".join(lines)


# ============================================================================
# Quick demo / self‑test
# ============================================================================

if __name__ == "__main__":
    result = compare_conventional_vs_mpd()
    print(print_comparison(result))
