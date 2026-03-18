"""MPD Command - Pore Pressure Prediction Engine

Real-time pore pressure estimation from drilling parameters using
the d-exponent (Rehm & McClendon) and Eaton's method.

This is fundamental to MPD operations: knowing pore pressure while
drilling tells the operator exactly where to set the SBP target.

Physics:
  d-exponent = log10(ROP / (60*RPM)) / log10(12*WOB / (1000*D_bit))
  dc-exponent = d * (MW_normal / MW_actual)  [corrected for mud weight]
  Pp = Sv - (Sv - Pp_normal) * (dc_observed / dc_normal)^1.2  [Eaton]
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class PorePressureResult:
    """Pore pressure estimation at a single depth."""
    depth_tvd: float          # ft
    d_exponent: float         # dimensionless
    dc_exponent: float        # corrected d-exponent
    pore_pressure_ppg: float  # estimated pore pressure (ppg EMW)
    pore_pressure_psi: float  # estimated pore pressure (psi)
    overburden_ppg: float     # overburden gradient (ppg)
    normal_trend_dc: float    # normal compaction trend dc value
    confidence: float         # 0-1 (lower when inputs are marginal)


def d_exponent(rop_fthr: float, rpm: float, wob_lbs: float,
               bit_diameter_in: float) -> float:
    """Calculate Jorden-Rehm d-exponent.

    d = log10(ROP / (60 * RPM)) / log10(12 * WOB / (1000 * D_bit))

    Args:
        rop_fthr: Rate of penetration (ft/hr)
        rpm: Rotary speed (rev/min)
        wob_lbs: Weight on bit (lbs)
        bit_diameter_in: Bit diameter (inches)

    Returns:
        d-exponent (dimensionless, typically 1.0-2.5 in shales)
    """
    if rop_fthr <= 0 or rpm <= 0 or wob_lbs <= 0 or bit_diameter_in <= 0:
        return 0.0

    numerator = np.log10(rop_fthr / (60.0 * rpm))
    denominator = np.log10(12.0 * wob_lbs / (1000.0 * bit_diameter_in))

    if abs(denominator) < 1e-10:
        return 0.0

    return numerator / denominator


def dc_exponent(d_exp: float, mw_normal_ppg: float,
                mw_actual_ppg: float) -> float:
    """Calculate corrected d-exponent (Rehm & McClendon).

    dc = d * (MW_normal / MW_actual)

    This corrects for the effect of mud weight on ROP,
    isolating the formation compaction signal.

    Args:
        d_exp: Raw d-exponent
        mw_normal_ppg: Normal pore pressure mud weight (typically 8.5-9.0 ppg)
        mw_actual_ppg: Actual mud weight being used (ppg)

    Returns:
        Corrected d-exponent
    """
    if mw_actual_ppg <= 0:
        return d_exp
    return d_exp * (mw_normal_ppg / mw_actual_ppg)


def normal_compaction_trend(tvd_ft: float, surface_dc: float = 1.0,
                            compaction_rate: float = 0.00004) -> float:
    """Calculate expected dc on the normal compaction trend line.

    dc_normal = surface_dc + compaction_rate * TVD

    In normally pressured shales, dc increases linearly with depth
    as compaction increases. Departure from this trend indicates
    abnormal pressure.

    Args:
        tvd_ft: True vertical depth (ft)
        surface_dc: dc value extrapolated to surface (typically 0.8-1.2)
        compaction_rate: Rate of dc increase per foot (typically 0.00003-0.00006)

    Returns:
        Expected dc on normal trend
    """
    return surface_dc + compaction_rate * tvd_ft


def overburden_gradient(tvd_ft: float, avg_bulk_density_ppg: float = 19.2) -> float:
    """Calculate overburden stress gradient.

    For Gulf Coast / Permian Basin, average bulk density is ~19.2 ppg
    (2.31 g/cc equivalent).

    Returns overburden in ppg EMW.
    """
    if tvd_ft <= 0:
        return avg_bulk_density_ppg
    # Simplified: overburden increases slightly with depth due to compaction
    # More accurate: integrate density log, but this approximation works
    return avg_bulk_density_ppg + (tvd_ft / 100000) * 2.0


def eaton_pore_pressure(tvd_ft: float, dc_observed: float,
                        dc_normal: float, overburden_ppg: float,
                        normal_pp_ppg: float = 8.65,
                        eaton_exponent: float = 1.2) -> float:
    """Estimate pore pressure using Eaton's method.

    Pp = Sv - (Sv - Pp_normal) * (dc_observed / dc_normal)^exponent

    When dc_observed < dc_normal (undercompacted = overpressured),
    pore pressure exceeds normal.

    Args:
        tvd_ft: True vertical depth (ft)
        dc_observed: Observed corrected d-exponent
        dc_normal: Normal compaction trend dc at this depth
        overburden_ppg: Overburden gradient (ppg EMW)
        normal_pp_ppg: Normal pore pressure gradient (ppg, typically 8.65 for saltwater)
        eaton_exponent: Eaton exponent (typically 1.2 for d-exponent)

    Returns:
        Estimated pore pressure in ppg EMW
    """
    if dc_normal <= 0 or dc_observed <= 0:
        return normal_pp_ppg

    ratio = dc_observed / dc_normal
    pp = overburden_ppg - (overburden_ppg - normal_pp_ppg) * (ratio ** eaton_exponent)

    # Clamp to reasonable range
    return max(normal_pp_ppg * 0.8, min(pp, overburden_ppg * 0.95))


def estimate_pore_pressure(
    tvd_ft: float,
    rop_fthr: float,
    rpm: float,
    wob_lbs: float,
    bit_diameter_in: float,
    mw_actual_ppg: float,
    mw_normal_ppg: float = 8.65,
    surface_dc: float = 1.0,
    compaction_rate: float = 0.00004,
    eaton_exponent: float = 1.2,
) -> PorePressureResult:
    """Full pore pressure estimation pipeline.

    Combines d-exponent, dc correction, normal trend, and Eaton's method.
    """
    # Calculate d and dc exponents
    d_exp = d_exponent(rop_fthr, rpm, wob_lbs, bit_diameter_in)
    dc_exp = dc_exponent(d_exp, mw_normal_ppg, mw_actual_ppg)

    # Normal compaction trend
    dc_norm = normal_compaction_trend(tvd_ft, surface_dc, compaction_rate)

    # Overburden
    sv_ppg = overburden_gradient(tvd_ft)

    # Eaton pore pressure
    pp_ppg = eaton_pore_pressure(tvd_ft, dc_exp, dc_norm, sv_ppg,
                                  mw_normal_ppg, eaton_exponent)
    pp_psi = 0.052 * pp_ppg * tvd_ft

    # Confidence assessment
    confidence = 1.0
    if rop_fthr < 10 or rop_fthr > 300:
        confidence *= 0.5  # Extreme ROP reduces confidence
    if wob_lbs < 5000:
        confidence *= 0.7  # Low WOB reduces reliability
    if abs(dc_exp) < 0.3 or abs(dc_exp) > 3.0:
        confidence *= 0.5  # Extreme dc values

    return PorePressureResult(
        depth_tvd=tvd_ft,
        d_exponent=d_exp,
        dc_exponent=dc_exp,
        pore_pressure_ppg=pp_ppg,
        pore_pressure_psi=pp_psi,
        overburden_ppg=sv_ppg,
        normal_trend_dc=dc_norm,
        confidence=min(confidence, 1.0),
    )


def analyze_pore_pressure_profile(
    tvd: np.ndarray,
    rop: np.ndarray,
    rpm: np.ndarray,
    wob_klbs: np.ndarray,
    bit_diameter_in: float,
    mw_ppg: np.ndarray,
    mw_normal_ppg: float = 8.65,
) -> dict:
    """Estimate pore pressure along the entire wellbore.

    Returns dict with arrays: tvd, d_exp, dc_exp, dc_normal,
    pp_ppg, pp_psi, overburden_ppg, confidence.
    """
    n = len(tvd)
    results = {
        "tvd": tvd,
        "d_exp": np.zeros(n),
        "dc_exp": np.zeros(n),
        "dc_normal": np.zeros(n),
        "pp_ppg": np.zeros(n),
        "pp_psi": np.zeros(n),
        "overburden_ppg": np.zeros(n),
        "confidence": np.zeros(n),
    }

    for i in range(n):
        if tvd[i] <= 0 or rop[i] <= 0 or rpm[i] <= 0 or wob_klbs[i] <= 0:
            results["pp_ppg"][i] = mw_normal_ppg
            results["pp_psi"][i] = 0.052 * mw_normal_ppg * max(tvd[i], 0)
            continue

        r = estimate_pore_pressure(
            tvd_ft=tvd[i],
            rop_fthr=rop[i],
            rpm=rpm[i],
            wob_lbs=wob_klbs[i] * 1000,
            bit_diameter_in=bit_diameter_in,
            mw_actual_ppg=mw_ppg[i] if isinstance(mw_ppg, np.ndarray) else mw_ppg,
            mw_normal_ppg=mw_normal_ppg,
        )

        results["d_exp"][i] = r.d_exponent
        results["dc_exp"][i] = r.dc_exponent
        results["dc_normal"][i] = r.normal_trend_dc
        results["pp_ppg"][i] = r.pore_pressure_ppg
        results["pp_psi"][i] = r.pore_pressure_psi
        results["overburden_ppg"][i] = r.overburden_ppg
        results["confidence"][i] = r.confidence

    return results
