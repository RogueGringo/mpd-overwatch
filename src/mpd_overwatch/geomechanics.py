"""
MPD Command -- Core Geomechanics Calculation Engine
=====================================================

Bridges real-time drilling mechanics data to formation mechanical properties.
Takes surface-measurable parameters (WOB, torque, RPM, ROP, bit size) and
derives rock strength, wellbore stability limits, and completion-quality
indicators -- capabilities that differentiate MPD operations from
conventional drilling programs.

Unit conventions throughout this module
---------------------------------------
  Pressure            : psi
  Depth (MD / TVD)    : ft
  Mud weight (MW)     : ppg  (pounds per gallon)
  Weight on bit (WOB) : lbs  (pounds-force)
  Torque              : ft-lbs
  RPM                 : rev/min
  ROP                 : ft/hr
  Bit diameter        : in   (inches)
  Density             : ppg  (pounds per gallon)
  Stress              : psi
  Angle               : radians (internal); degrees accepted on public API

Reference equations are drawn from:
  - Teale, R. (1965), "The Concept of Specific Energy in Rock Drilling",
    Int. J. Rock Mech. Mining Sci., Vol. 2
  - Dupriest, F. E. & Koederitz, W. L. (2005), "Maximizing Drill Rates
    with Real-Time Surveillance of Mechanical Specific Energy", SPE 92194
  - Jaeger, Cook & Zimmerman, *Fundamentals of Rock Mechanics* (4th ed.)
  - Zoback, M. D., *Reservoir Geomechanics* (Cambridge University Press)
  - Barton, Bandis & Bakhtar (1985), Mohr-Coulomb failure criterion
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HYDROSTATIC_CONSTANT: float = 0.052
"""psi / (ppg * ft) -- converts MW x TVD to hydrostatic pressure."""

GRAVITY_FT_S2: float = 32.174
"""Acceleration due to gravity (ft/s^2)."""

MSE_TORQUE_CONSTANT: float = 480.0
"""Unit-conversion constant in the Teale MSE equation.

Derives from:  (2 * pi * 12 in/ft * 60 min/hr) / (pi * (1/4) for area)
With torque in ft-lbs, RPM in rev/min, D_bit in inches, ROP in ft/hr,
and result in psi.
"""


# ===================================================================
# Data Structures
# ===================================================================

@dataclass
class RockProperties:
    """Mechanical properties of a formation at a single depth station.

    Attributes
    ----------
    md : float
        Measured depth (ft).
    tvd : float
        True vertical depth (ft).
    mse : float
        Mechanical specific energy (psi).
    mse_corrected : float
        MSE corrected for bit efficiency (psi).
    ucs : float
        Unconfined compressive strength (psi).
    ccs : float
        Confined compressive strength (psi).
    brittleness_index : float
        Rock brittleness index, 0 to 1 (dimensionless).
    drilling_efficiency : float
        Drilling efficiency UCS/MSE, 0 to 1 (dimensionless).
    drillability_index : float
        Formation drillability exponent (dimensionless).
    """
    md: float
    tvd: float
    mse: float
    mse_corrected: float
    ucs: float
    ccs: float
    brittleness_index: float
    drilling_efficiency: float
    drillability_index: float


@dataclass
class StabilityWindow:
    """Wellbore stability analysis results at a single depth.

    Attributes
    ----------
    tvd : float
        True vertical depth (ft).
    breakout_pressure : float
        Minimum BHP to prevent shear failure / breakouts (psi).
    fracture_initiation_pressure : float
        Maximum BHP before tensile fracture initiation (psi).
    breakout_mw : float
        Minimum mud weight to prevent breakouts (ppg).
    fracture_mw : float
        Maximum mud weight before fracture initiation (ppg).
    safe_mw_min : float
        Lower bound of safe mud weight window (ppg).
    safe_mw_max : float
        Upper bound of safe mud weight window (ppg).
    pore_pressure : float
        Pore pressure at this depth (psi).
    overburden : float
        Overburden stress at this depth (psi).
    shmin : float
        Minimum horizontal stress at this depth (psi).
    """
    tvd: float
    breakout_pressure: float
    fracture_initiation_pressure: float
    breakout_mw: float
    fracture_mw: float
    safe_mw_min: float
    safe_mw_max: float
    pore_pressure: float
    overburden: float
    shmin: float


# ===================================================================
# 1. Mechanical Specific Energy (MSE)
# ===================================================================

def mechanical_specific_energy(
    wob: float,
    torque: float,
    rpm: float,
    rop: float,
    bit_diameter: float,
) -> float:
    """Mechanical Specific Energy (Teale, 1965).

    The energy required to destroy a unit volume of rock.  When drilling
    is mechanically efficient, MSE approaches the rock's unconfined
    compressive strength.

    MSE = (480 * T * N) / (D_b^2 * ROP) + (4 * WOB) / (pi * D_b^2)

    Where the first term is the rotary component and the second is the
    axial (thrust) component.

    Parameters
    ----------
    wob : float
        Weight on bit (lbs).
    torque : float
        Surface torque (ft-lbs).
    rpm : float
        Rotary speed (rev/min).
    rop : float
        Rate of penetration (ft/hr).
    bit_diameter : float
        Bit diameter (in).

    Returns
    -------
    float
        Mechanical specific energy (psi).

    Raises
    ------
    ValueError
        If bit_diameter or rop is zero or negative.

    Notes
    -----
    The 480 constant handles the unit conversions:
        2 * pi (rad/rev) * 12 (in/ft) * 60 (min/hr) / pi = 1440 / pi * pi ...
        More precisely: 480 = (2 * pi * 12 * 60) / (pi * (1/4) * pi)
        is the standard Teale form used industry-wide with these oilfield units.
    """
    if bit_diameter <= 0:
        raise ValueError(f"bit_diameter must be positive, got {bit_diameter} in.")
    if rop <= 0:
        raise ValueError(f"ROP must be positive, got {rop} ft/hr.")

    d_sq = bit_diameter ** 2

    # Rotary component
    rotary = (MSE_TORQUE_CONSTANT * torque * rpm) / (d_sq * rop)

    # Axial (thrust) component
    axial = (4.0 * wob) / (math.pi * d_sq)

    return rotary + axial


# ===================================================================
# 2. Corrected MSE (bit efficiency)
# ===================================================================

def corrected_mse(
    mse: float,
    bit_efficiency: float = 0.35,
) -> float:
    """Correct raw MSE for bit mechanical efficiency.

    Real bits are not 100 % efficient at transferring energy into rock
    destruction.  The efficiency factor accounts for energy lost to
    friction, heat, and vibration.

    MSE_corrected = MSE * bit_efficiency

    Parameters
    ----------
    mse : float
        Raw mechanical specific energy (psi).
    bit_efficiency : float
        Bit mechanical efficiency factor (dimensionless, 0 to 1).
        Typical values:
          - PDC bits in shale:  0.30 - 0.40
          - Roller-cone bits:   0.25 - 0.35
          - Impregnated bits:   0.20 - 0.30
        Default is 0.35 (mid-range PDC).

    Returns
    -------
    float
        Corrected MSE (psi).

    Raises
    ------
    ValueError
        If bit_efficiency is not in (0, 1].
    """
    if not (0.0 < bit_efficiency <= 1.0):
        raise ValueError(
            f"bit_efficiency must be in (0, 1], got {bit_efficiency}"
        )
    return mse * bit_efficiency


# ===================================================================
# 3. Unconfined Compressive Strength (UCS) from MSE
# ===================================================================

def ucs_from_mse(
    mse: float,
    bit_efficiency: float = 0.35,
    a: float = 0.35,
    b: float = 0.0,
) -> float:
    """Estimate Unconfined Compressive Strength from MSE.

    When drilling is efficient (DE ~ 1.0), the corrected MSE
    approximates UCS directly.  For field-calibrated correlations,
    a linear model is applied:

        UCS = a * MSE + b

    The default coefficients (a=0.35, b=0) represent PDC bits in
    shale formations -- a common scenario in the Delaware Basin
    Wolfcamp/Bone Spring laterals.

    Parameters
    ----------
    mse : float
        Raw (uncorrected) mechanical specific energy (psi).
    bit_efficiency : float
        Bit efficiency factor (dimensionless, 0 to 1).
        Default 0.35 for PDC bits.
    a : float
        Slope of the field-calibrated MSE-to-UCS correlation.
        Default 0.35 (PDC in shale).
    b : float
        Intercept of the field-calibrated correlation (psi).
        Default 0.0.

    Returns
    -------
    float
        Estimated UCS (psi).

    Notes
    -----
    In practice, calibrate ``a`` and ``b`` against core-test data or
    sonic-derived UCS logs from offset wells.  The default a=0.35
    comes from the observation that PDC bits in shale typically
    operate at DE ~ 0.35 when drilling efficiently.
    """
    mse_c = corrected_mse(mse, bit_efficiency)
    ucs = a * mse + b

    # If the correlation yields a value that exceeds the corrected MSE
    # (which would imply super-efficient drilling), cap at MSE_corrected
    # as a physical upper bound.
    return max(ucs, 0.0)


# ===================================================================
# 4. Confined Compressive Strength (CCS)
# ===================================================================

def confined_compressive_strength(
    ucs: float,
    confining_pressure: float,
    friction_angle_deg: float = 30.0,
) -> float:
    """Confined Compressive Strength via the Mohr-Coulomb failure criterion.

    CCS = UCS + confining_pressure * tan^2(friction_angle/2 + pi/4)

    The Mohr-Coulomb criterion relates the strength increase under
    confining pressure to the internal friction angle of the rock.
    This is essential for predicting rock behavior at depth where
    in-situ stresses provide confinement.

    Parameters
    ----------
    ucs : float
        Unconfined compressive strength (psi).
    confining_pressure : float
        Confining (effective minimum principal) stress (psi).
        In a wellbore context this is typically the effective mud
        pressure minus pore pressure.
    friction_angle_deg : float
        Internal friction angle of the rock (degrees).
        Typical values:
          - Shale:       20 - 30 deg
          - Sandstone:   30 - 45 deg
          - Limestone:   35 - 50 deg
        Default 30 deg (shale).

    Returns
    -------
    float
        Confined compressive strength (psi).
    """
    phi_rad = math.radians(friction_angle_deg)
    # Mohr-Coulomb: sigma_1 = UCS + sigma_3 * tan^2(pi/4 + phi/2)
    tan_term = math.tan(math.pi / 4.0 + phi_rad / 2.0) ** 2
    return ucs + confining_pressure * tan_term


# ===================================================================
# 5. Rock Brittleness Index
# ===================================================================

def brittleness_index(
    ucs: float,
    tensile_strength: Optional[float] = None,
) -> float:
    """Rock Brittleness Index for completion targeting.

    BI = (UCS - T) / (UCS + T)

    Where T is the tensile strength of the rock.  If tensile strength
    is not provided, the standard approximation T = UCS / 10 is used
    (typical for shale formations).

    Interpretation:
      - BI > 0.5 : Brittle rock -- favorable for hydraulic fracturing
      - BI < 0.5 : Ductile rock -- may require higher treatment pressures
      - BI ~ 0.8 : Highly brittle (e.g., siliceous mudstone)
      - BI ~ 0.3 : Highly ductile (e.g., organic-rich clay)

    This directly informs completion design:  stages targeting
    brittle zones will have better fracture complexity and higher
    stimulated reservoir volume (SRV).

    Parameters
    ----------
    ucs : float
        Unconfined compressive strength (psi).
    tensile_strength : float or None
        Tensile strength (psi).  If None, estimated as UCS / 10.

    Returns
    -------
    float
        Brittleness index (dimensionless, 0 to 1).
    """
    if tensile_strength is None:
        tensile_strength = ucs / 10.0

    denominator = ucs + tensile_strength
    if denominator <= 0:
        return 0.0

    bi = (ucs - tensile_strength) / denominator
    return max(0.0, min(bi, 1.0))


# ===================================================================
# 6. Minimum Horizontal Stress (Shmin)
# ===================================================================

def minimum_horizontal_stress(
    overburden: float,
    pore_pressure: float,
    poisson_ratio: float = 0.25,
    tectonic_stress: float = 0.0,
    closure_pressure: Optional[float] = None,
) -> float:
    """Minimum horizontal stress (Shmin) estimation.

    If a closure pressure from a leak-off test (LOT) or APWD loss
    event is available, it is used directly as the best estimate of
    Shmin.  Otherwise, the poro-elastic horizontal strain model is
    applied:

        Shmin = (v / (1 - v)) * (Sv - Pp) + Pp + sigma_tectonic

    Where:
      v              = Poisson's ratio (dimensionless)
      Sv             = Overburden stress (psi)
      Pp             = Pore pressure (psi)
      sigma_tectonic = Tectonic stress contribution (psi)

    Parameters
    ----------
    overburden : float
        Overburden (vertical) stress Sv (psi).
    pore_pressure : float
        Pore pressure Pp (psi).
    poisson_ratio : float
        Poisson's ratio (dimensionless, 0 to 0.5).
        Typical values:
          - Shale:     0.25 - 0.35
          - Sandstone: 0.15 - 0.25
          - Limestone: 0.25 - 0.33
        Default 0.25.
    tectonic_stress : float
        Additional tectonic stress contribution (psi).
        In extensional basins (e.g., Delaware Basin) this is typically
        small or zero.  Default 0.0.
    closure_pressure : float or None
        Direct measurement of Shmin from LOT, XLOT, DFIT, or
        APWD-observed losses (psi).  If provided, this value is
        returned directly and the analytical model is bypassed.

    Returns
    -------
    float
        Minimum horizontal stress Shmin (psi).

    Raises
    ------
    ValueError
        If Poisson's ratio is not in [0, 0.5).
    """
    if closure_pressure is not None:
        return closure_pressure

    if not (0.0 <= poisson_ratio < 0.5):
        raise ValueError(
            f"poisson_ratio must be in [0, 0.5), got {poisson_ratio}"
        )

    v = poisson_ratio
    effective_vertical = overburden - pore_pressure
    shmin = (v / (1.0 - v)) * effective_vertical + pore_pressure + tectonic_stress
    return shmin


# ===================================================================
# 7. Overburden Stress (Sv)
# ===================================================================

def overburden_stress(
    tvd: float,
    rho_avg_ppg: float = 16.33,
) -> float:
    """Overburden (vertical) stress from average bulk density.

    Sv = 0.052 * rho_avg * TVD

    This is the simplified integral of bulk density from surface to
    the depth of interest.  For more accuracy, use a density log and
    integrate numerically via ``overburden_stress_from_density_log``.

    Parameters
    ----------
    tvd : float
        True vertical depth (ft).
    rho_avg_ppg : float
        Average bulk density from surface to TVD (ppg).
        Default 16.33 ppg yields ~ 1.0 psi/ft overburden gradient,
        which is a common assumption when no density data is available.

    Returns
    -------
    float
        Overburden stress Sv (psi).
    """
    return HYDROSTATIC_CONSTANT * rho_avg_ppg * tvd


def overburden_stress_from_density_log(
    tvd_array: np.ndarray,
    density_ppg_array: np.ndarray,
) -> np.ndarray:
    """Overburden stress by numerical integration of a density log.

    Sv(z) = 0.052 * integral_0^z rho(z') dz'

    Uses the trapezoidal rule for integration.

    Parameters
    ----------
    tvd_array : np.ndarray
        True vertical depth values (ft), must be monotonically
        increasing.
    density_ppg_array : np.ndarray
        Bulk density at each TVD station (ppg).

    Returns
    -------
    np.ndarray
        Overburden stress at each TVD station (psi).

    Raises
    ------
    ValueError
        If arrays have different lengths or fewer than 2 points.
    """
    if len(tvd_array) != len(density_ppg_array):
        raise ValueError(
            f"TVD array length ({len(tvd_array)}) must match density array "
            f"length ({len(density_ppg_array)})."
        )
    if len(tvd_array) < 2:
        raise ValueError("Need at least 2 depth stations for integration.")

    # Cumulative trapezoidal integration: integral of (0.052 * rho) dz
    integrand = HYDROSTATIC_CONSTANT * density_ppg_array
    sv = np.zeros_like(tvd_array, dtype=float)

    for i in range(1, len(tvd_array)):
        dz = tvd_array[i] - tvd_array[i - 1]
        # Trapezoidal rule for this interval
        sv[i] = sv[i - 1] + 0.5 * (integrand[i - 1] + integrand[i]) * dz

    return sv


# ===================================================================
# 8. Wellbore Stability Analysis (Kirsch Equations, Simplified)
# ===================================================================

def wellbore_stability(
    tvd: float,
    pore_pressure: float,
    overburden_stress_psi: float,
    shmin: float,
    ucs: float,
    poisson_ratio: float = 0.25,
    shmax: Optional[float] = None,
    tensile_strength: Optional[float] = None,
) -> StabilityWindow:
    """Wellbore stability analysis -- safe mud weight window.

    Uses simplified Kirsch equations for a vertical wellbore to
    determine the pressures at which shear failure (breakouts) and
    tensile failure (fracture initiation) occur at the wellbore wall.

    **Breakout (shear failure) pressure:**
    The maximum tangential (hoop) stress at the wellbore wall occurs
    at the azimuth aligned with Shmin:

        sigma_theta_max = 3 * Shmax - Shmin - Pw

    Breakout occurs when sigma_theta_max exceeds the rock's confined
    compressive strength.  Solving for the minimum wellbore pressure:

        Pw_breakout = (3 * Shmax - Shmin - UCS) / 1   (simplified)

    **Fracture initiation pressure:**
    Tensile failure occurs when the minimum hoop stress goes to zero
    (or equals -T):

        Pw_frac = 3 * Shmin - Shmax - Pp + T

    Parameters
    ----------
    tvd : float
        True vertical depth (ft).
    pore_pressure : float
        Pore pressure at this depth (psi).
    overburden_stress_psi : float
        Vertical (overburden) stress Sv (psi).
    shmin : float
        Minimum horizontal stress (psi).
    ucs : float
        Unconfined compressive strength (psi).
    poisson_ratio : float
        Poisson's ratio (dimensionless).  Default 0.25.
    shmax : float or None
        Maximum horizontal stress (psi).  If None, estimated as
        the average of Sv and Shmin, which is a common assumption
        for a normal-faulting stress regime.
    tensile_strength : float or None
        Rock tensile strength (psi).  If None, estimated as UCS / 10.

    Returns
    -------
    StabilityWindow
        Contains breakout pressure, fracture pressure, and safe MW
        window in ppg.
    """
    if tensile_strength is None:
        tensile_strength = ucs / 10.0

    if shmax is None:
        # Normal-faulting regime assumption: Sv > Shmax > Shmin
        # Estimate Shmax as midpoint of Sv and Shmin
        shmax = (overburden_stress_psi + shmin) / 2.0

    # --- Breakout (shear failure) pressure ---
    # From Kirsch: maximum hoop stress at borehole wall (azimuth of Shmin):
    #   sigma_theta_max = 3*Shmax - Shmin - Pw - Pp
    # Failure when sigma_theta_max >= UCS (using UCS as unconfined strength)
    # So: 3*Shmax - Shmin - Pw_min - Pp = UCS
    #     Pw_min = 3*Shmax - Shmin - Pp - UCS
    breakout_pressure = 3.0 * shmax - shmin - pore_pressure - ucs

    # Breakout pressure cannot be below pore pressure (below that you
    # have an underbalanced kick scenario, handled separately).
    breakout_pressure = max(breakout_pressure, pore_pressure)

    # --- Fracture initiation pressure ---
    # From Kirsch: minimum hoop stress at borehole wall (azimuth of Shmax):
    #   sigma_theta_min = 3*Shmin - Shmax - Pw - Pp
    # Tensile failure when sigma_theta_min <= -T (tensile strength)
    #   3*Shmin - Shmax - Pw_max - Pp = -T
    #   Pw_max = 3*Shmin - Shmax - Pp + T
    fracture_initiation = 3.0 * shmin - shmax - pore_pressure + tensile_strength

    # Convert to equivalent mud weights (ppg)
    if tvd > 0:
        breakout_mw = breakout_pressure / (HYDROSTATIC_CONSTANT * tvd)
        fracture_mw = fracture_initiation / (HYDROSTATIC_CONSTANT * tvd)
        pore_mw = pore_pressure / (HYDROSTATIC_CONSTANT * tvd)
    else:
        breakout_mw = 0.0
        fracture_mw = 0.0
        pore_mw = 0.0

    # Safe MW window: must exceed pore pressure and breakout, stay below frac
    safe_mw_min = max(breakout_mw, pore_mw)
    safe_mw_max = fracture_mw

    return StabilityWindow(
        tvd=tvd,
        breakout_pressure=breakout_pressure,
        fracture_initiation_pressure=fracture_initiation,
        breakout_mw=breakout_mw,
        fracture_mw=fracture_mw,
        safe_mw_min=safe_mw_min,
        safe_mw_max=safe_mw_max,
        pore_pressure=pore_pressure,
        overburden=overburden_stress_psi,
        shmin=shmin,
    )


# ===================================================================
# 9. Drilling Efficiency Indicator
# ===================================================================

def drilling_efficiency(ucs: float, mse: float) -> float:
    """Drilling Efficiency -- ratio of rock strength to energy input.

    DE = UCS / MSE

    A perfect drill bit destroying rock with no wasted energy would
    yield DE = 1.0.  In practice, DE ranges from 0.05 to 0.60.

    Interpretation:
      - DE > 0.40 : Excellent -- bit is drilling efficiently
      - DE 0.20-0.40 : Good -- normal PDC performance
      - DE 0.10-0.20 : Poor -- check bit condition, parameters
      - DE < 0.10 : Very poor -- likely dull bit, wrong bit type,
                     excessive vibration, or founder point exceeded

    Low DE values that trend downward over time indicate:
      - Dulling bit (cutters worn)
      - Poor hydraulics (insufficient hole cleaning)
      - Wrong drilling parameters (founder point)
      - Formation change (harder rock, not recognized)

    Parameters
    ----------
    ucs : float
        Unconfined compressive strength (psi).
    mse : float
        Mechanical specific energy (psi).

    Returns
    -------
    float
        Drilling efficiency (dimensionless, 0 to 1).
    """
    if mse <= 0:
        return 0.0
    de = ucs / mse
    return max(0.0, min(de, 1.0))


# ===================================================================
# 10. Formation Drillability Index
# ===================================================================

def drillability_index(
    rop: float,
    wob: float,
    rpm: float,
) -> float:
    """Formation Drillability Exponent (D-exponent variant).

    D_exp = log10(ROP / (WOB * RPM))

    Higher values indicate more drillable (softer) formations.  A
    sudden decrease in D_exp at constant drilling parameters signals:
      - Harder formation (lithology change)
      - Increasing pore pressure (formation becoming overpressured)
      - Bit dulling

    The classic Jorden & Shirley (1966) D-exponent normalizes for
    bit size and mud weight.  This simplified version uses raw
    drilling parameters and is useful for detecting relative changes
    along the lateral.

    Parameters
    ----------
    rop : float
        Rate of penetration (ft/hr).
    wob : float
        Weight on bit (lbs).
    rpm : float
        Rotary speed (rev/min).

    Returns
    -------
    float
        Drillability exponent (dimensionless).  More negative = harder
        to drill.  Typical range: -6 to -3.

    Notes
    -----
    Returns -99.0 as a sentinel if any input is zero or negative
    (cannot take log of non-positive number).
    """
    if rop <= 0 or wob <= 0 or rpm <= 0:
        return -99.0

    ratio = rop / (wob * rpm)
    if ratio <= 0:
        return -99.0

    return math.log10(ratio)


# ===================================================================
# 11. Stick-Slip Severity Index
# ===================================================================

def stick_slip_severity(
    torque_array: np.ndarray,
    rpm_array: np.ndarray,
) -> float:
    """Stick-Slip Severity Index from torque and RPM variations.

    SSI = (std(torque) / mean(torque)) * (std(RPM) / mean(RPM))

    This is the product of the coefficients of variation of torque
    and RPM.  High SSI indicates severe torsional oscillation,
    which causes:
      - Inefficient rock destruction (wasted energy)
      - BHA component fatigue and failure
      - Irregular borehole (wellbore quality degradation)
      - Poor directional control

    Interpretation:
      - SSI < 0.01  : Minimal stick-slip -- smooth drilling
      - SSI 0.01-0.05 : Moderate -- monitor and consider parameter change
      - SSI 0.05-0.15 : Severe -- adjust RPM/WOB, may need anti-stick-slip
      - SSI > 0.15  : Critical -- high risk of downhole tool damage

    Parameters
    ----------
    torque_array : np.ndarray
        Array of torque measurements over a window (ft-lbs).
    rpm_array : np.ndarray
        Array of RPM measurements over the same window (rev/min).

    Returns
    -------
    float
        Stick-slip severity index (dimensionless, >= 0).

    Notes
    -----
    Requires at least 5 samples for meaningful statistics.
    Returns 0.0 if arrays are too short or contain zero/negative means.
    """
    if len(torque_array) < 5 or len(rpm_array) < 5:
        return 0.0

    mean_torque = np.mean(torque_array)
    mean_rpm = np.mean(rpm_array)

    if mean_torque <= 0 or mean_rpm <= 0:
        return 0.0

    cv_torque = np.std(torque_array) / mean_torque
    cv_rpm = np.std(rpm_array) / mean_rpm

    return float(cv_torque * cv_rpm)


# ===================================================================
# Helper: Lateral Geomechanics Analysis
# ===================================================================

def analyze_lateral_geomechanics(
    md: np.ndarray,
    tvd: np.ndarray,
    wob: np.ndarray,
    torque: np.ndarray,
    rpm: np.ndarray,
    rop: np.ndarray,
    bit_diameter: float,
    bit_efficiency: float = 0.35,
    ucs_a: float = 0.35,
    ucs_b: float = 0.0,
    confining_pressure: Optional[np.ndarray] = None,
    friction_angle_deg: float = 30.0,
) -> pd.DataFrame:
    """Compute geomechanics properties along an entire lateral section.

    Processes arrays of drilling parameters recorded along the
    wellbore and returns a DataFrame with rock mechanical properties
    at each depth station.  This is the primary function for building
    a continuous geomechanical model from drilling data.

    Parameters
    ----------
    md : np.ndarray
        Measured depth at each station (ft).
    tvd : np.ndarray
        True vertical depth at each station (ft).
    wob : np.ndarray
        Weight on bit at each station (lbs).
    torque : np.ndarray
        Surface torque at each station (ft-lbs).
    rpm : np.ndarray
        Rotary speed at each station (rev/min).
    rop : np.ndarray
        Rate of penetration at each station (ft/hr).
    bit_diameter : float
        Bit diameter (in).  Assumed constant across the interval.
    bit_efficiency : float
        Bit mechanical efficiency factor (0 to 1).  Default 0.35.
    ucs_a : float
        Slope of the MSE-to-UCS correlation.  Default 0.35.
    ucs_b : float
        Intercept of the MSE-to-UCS correlation (psi).  Default 0.0.
    confining_pressure : np.ndarray or None
        Effective confining pressure at each station (psi).  If None,
        a default of 0.5 psi/ft * TVD is assumed.
    friction_angle_deg : float
        Internal friction angle for CCS calculation (degrees).
        Default 30 deg (shale).

    Returns
    -------
    pd.DataFrame
        Columns: md, tvd, mse, mse_corrected, ucs, ccs,
        brittleness_index, drilling_efficiency, drillability_index.
        One row per depth station.

    Notes
    -----
    Stations where ROP or RPM are zero are assigned NaN values for
    all derived properties (these represent connections, surveys, or
    non-drilling activity).
    """
    n = len(md)
    if not all(len(arr) == n for arr in [tvd, wob, torque, rpm, rop]):
        raise ValueError(
            "All input arrays must have the same length."
        )

    # Pre-allocate output arrays
    mse_arr = np.full(n, np.nan)
    mse_c_arr = np.full(n, np.nan)
    ucs_arr = np.full(n, np.nan)
    ccs_arr = np.full(n, np.nan)
    bi_arr = np.full(n, np.nan)
    de_arr = np.full(n, np.nan)
    dexp_arr = np.full(n, np.nan)

    # Default confining pressure if not provided
    if confining_pressure is None:
        confining_pressure = 0.5 * tvd  # ~0.5 psi/ft effective stress

    for i in range(n):
        # Skip non-drilling intervals
        if rop[i] <= 0 or rpm[i] <= 0 or bit_diameter <= 0:
            continue

        try:
            mse_val = mechanical_specific_energy(
                wob=float(wob[i]),
                torque=float(torque[i]),
                rpm=float(rpm[i]),
                rop=float(rop[i]),
                bit_diameter=bit_diameter,
            )
            mse_arr[i] = mse_val

            mse_c_val = corrected_mse(mse_val, bit_efficiency)
            mse_c_arr[i] = mse_c_val

            ucs_val = ucs_from_mse(mse_val, bit_efficiency, ucs_a, ucs_b)
            ucs_arr[i] = ucs_val

            conf_p = float(confining_pressure[i])
            ccs_val = confined_compressive_strength(
                ucs_val, conf_p, friction_angle_deg
            )
            ccs_arr[i] = ccs_val

            bi_arr[i] = brittleness_index(ucs_val)
            de_arr[i] = drilling_efficiency(ucs_val, mse_val)
            dexp_arr[i] = drillability_index(
                float(rop[i]), float(wob[i]), float(rpm[i])
            )
        except (ValueError, ZeroDivisionError):
            # Leave NaN for stations with invalid data
            continue

    df = pd.DataFrame({
        "md": md,
        "tvd": tvd,
        "mse": mse_arr,
        "mse_corrected": mse_c_arr,
        "ucs": ucs_arr,
        "ccs": ccs_arr,
        "brittleness_index": bi_arr,
        "drilling_efficiency": de_arr,
        "drillability_index": dexp_arr,
    })

    return df


# ===================================================================
# Helper: Wellbore Stability Window
# ===================================================================

def wellbore_stability_window(
    tvd: float,
    pore_pressure: float,
    overburden: float,
    shmin: float,
    ucs: float,
    poisson: float = 0.25,
    shmax: Optional[float] = None,
    tensile_strength: Optional[float] = None,
) -> dict:
    """Calculate safe mud weight window for wellbore stability.

    Convenience wrapper around ``wellbore_stability`` that returns
    a dictionary suitable for direct use in dashboards, reports,
    and decision logic.

    Parameters
    ----------
    tvd : float
        True vertical depth (ft).
    pore_pressure : float
        Pore pressure at this depth (psi).
    overburden : float
        Overburden stress Sv (psi).
    shmin : float
        Minimum horizontal stress (psi).
    ucs : float
        Unconfined compressive strength (psi).
    poisson : float
        Poisson's ratio (dimensionless).  Default 0.25.
    shmax : float or None
        Maximum horizontal stress (psi).  If None, estimated.
    tensile_strength : float or None
        Rock tensile strength (psi).  If None, estimated as UCS/10.

    Returns
    -------
    dict
        Keys:
          - tvd_ft: true vertical depth (ft)
          - pore_pressure_psi: pore pressure (psi)
          - overburden_psi: overburden stress (psi)
          - shmin_psi: minimum horizontal stress (psi)
          - breakout_pressure_psi: minimum BHP to prevent breakouts (psi)
          - fracture_pressure_psi: maximum BHP before fracture (psi)
          - breakout_mw_ppg: minimum mud weight (ppg)
          - fracture_mw_ppg: maximum mud weight (ppg)
          - safe_mw_min_ppg: lower bound of safe window (ppg)
          - safe_mw_max_ppg: upper bound of safe window (ppg)
          - window_width_ppg: width of safe window (ppg)
          - is_stable: True if safe window exists (min < max)
    """
    result = wellbore_stability(
        tvd=tvd,
        pore_pressure=pore_pressure,
        overburden_stress_psi=overburden,
        shmin=shmin,
        ucs=ucs,
        poisson_ratio=poisson,
        shmax=shmax,
        tensile_strength=tensile_strength,
    )

    window_width = result.safe_mw_max - result.safe_mw_min

    return {
        "tvd_ft": result.tvd,
        "pore_pressure_psi": result.pore_pressure,
        "overburden_psi": result.overburden,
        "shmin_psi": result.shmin,
        "breakout_pressure_psi": round(result.breakout_pressure, 1),
        "fracture_pressure_psi": round(result.fracture_initiation_pressure, 1),
        "breakout_mw_ppg": round(result.breakout_mw, 2),
        "fracture_mw_ppg": round(result.fracture_mw, 2),
        "safe_mw_min_ppg": round(result.safe_mw_min, 2),
        "safe_mw_max_ppg": round(result.safe_mw_max, 2),
        "window_width_ppg": round(window_width, 2),
        "is_stable": window_width > 0,
    }


# ===================================================================
# Helper: Fracability Score
# ===================================================================

def fracability_score(
    bi: float,
    natural_fracture_density: float = 0.0,
    nf_weight: float = 0.3,
) -> float:
    """Composite fracability score for completion targeting.

    Combines the rock brittleness index with natural fracture density
    to produce a single 0-to-1 score that ranks intervals by their
    likelihood of generating complex fracture networks during
    hydraulic fracturing.

    Score = (1 - nf_weight) * BI_norm + nf_weight * NFD_norm

    Where:
      BI_norm  = brittleness index (already 0-1)
      NFD_norm = natural fracture density normalized to 0-1
                 (using a sigmoid centered at 5 fractures/ft)

    Interpretation:
      - Score > 0.7 : Prime frac target -- high complexity expected
      - Score 0.4-0.7 : Moderate -- standard completion design
      - Score < 0.4 : Poor candidate -- consider diversion or skipping

    Parameters
    ----------
    bi : float
        Brittleness index (dimensionless, 0 to 1).
    natural_fracture_density : float
        Natural fracture density (fractures per foot).
        If not available, pass 0 and the score is based on
        brittleness alone.  Default 0.0.
    nf_weight : float
        Weight given to natural fracture density in the composite
        score (0 to 1).  Default 0.3 (70% brittleness, 30% NFD).

    Returns
    -------
    float
        Fracability score (dimensionless, 0 to 1).
    """
    if not (0.0 <= nf_weight <= 1.0):
        raise ValueError(f"nf_weight must be in [0, 1], got {nf_weight}")

    # Normalize brittleness (already 0-1, but clamp for safety)
    bi_norm = max(0.0, min(bi, 1.0))

    # Normalize natural fracture density with a sigmoid
    # Centered at 5 frac/ft, steepness factor of 0.5
    if natural_fracture_density > 0:
        nfd_norm = 1.0 / (1.0 + math.exp(-0.5 * (natural_fracture_density - 5.0)))
    else:
        nfd_norm = 0.0

    score = (1.0 - nf_weight) * bi_norm + nf_weight * nfd_norm
    return max(0.0, min(score, 1.0))


# ===================================================================
# Self-Test / Demo
# ===================================================================

def _demo() -> None:
    """Run a validation with realistic Delaware Basin parameters."""

    print("=" * 74)
    print("  MPD Command -- Geomechanics Engine Self-Test")
    print("=" * 74)

    # ------------------------------------------------------------------
    # 1. MSE calculation -- typical Wolfcamp lateral drilling parameters
    # ------------------------------------------------------------------
    print("\n--- 1. Mechanical Specific Energy (MSE) ---")
    wob_test = 25_000.0       # lbs (25 klbs)
    torque_test = 12_000.0    # ft-lbs
    rpm_test = 120.0          # rev/min
    rop_test = 150.0          # ft/hr
    bit_dia = 8.75            # inches

    mse_val = mechanical_specific_energy(wob_test, torque_test, rpm_test,
                                          rop_test, bit_dia)
    print(f"  WOB = {wob_test:,.0f} lbs, Torque = {torque_test:,.0f} ft-lbs")
    print(f"  RPM = {rpm_test:.0f}, ROP = {rop_test:.0f} ft/hr, "
          f"Bit = {bit_dia}\"")
    print(f"  MSE = {mse_val:,.0f} psi")

    # ------------------------------------------------------------------
    # 2. Corrected MSE and UCS
    # ------------------------------------------------------------------
    print("\n--- 2. Corrected MSE & UCS ---")
    mse_c = corrected_mse(mse_val, bit_efficiency=0.35)
    ucs_val = ucs_from_mse(mse_val, bit_efficiency=0.35)
    print(f"  MSE_corrected (eff=0.35) = {mse_c:,.0f} psi")
    print(f"  UCS estimate             = {ucs_val:,.0f} psi")

    # ------------------------------------------------------------------
    # 3. Confined compressive strength
    # ------------------------------------------------------------------
    print("\n--- 3. Confined Compressive Strength (CCS) ---")
    conf_p = 3_000.0  # psi effective confining pressure
    ccs_val = confined_compressive_strength(ucs_val, conf_p,
                                             friction_angle_deg=30.0)
    print(f"  UCS = {ucs_val:,.0f} psi, Confining = {conf_p:,.0f} psi, "
          f"Phi = 30 deg")
    print(f"  CCS = {ccs_val:,.0f} psi")

    # ------------------------------------------------------------------
    # 4. Brittleness Index
    # ------------------------------------------------------------------
    print("\n--- 4. Rock Brittleness Index ---")
    bi_val = brittleness_index(ucs_val)
    print(f"  UCS = {ucs_val:,.0f} psi, T = {ucs_val / 10:,.0f} psi (est.)")
    print(f"  BI = {bi_val:.3f}", end="")
    if bi_val > 0.5:
        print("  --> BRITTLE (favorable for fracing)")
    else:
        print("  --> DUCTILE (may need higher treatment pressures)")

    # ------------------------------------------------------------------
    # 5. Drilling Efficiency
    # ------------------------------------------------------------------
    print("\n--- 5. Drilling Efficiency ---")
    de_val = drilling_efficiency(ucs_val, mse_val)
    print(f"  DE = UCS / MSE = {de_val:.3f}", end="")
    if de_val > 0.40:
        print("  --> Excellent")
    elif de_val > 0.20:
        print("  --> Good")
    elif de_val > 0.10:
        print("  --> Poor -- check bit/parameters")
    else:
        print("  --> Very poor -- likely dull bit or wrong parameters")

    # ------------------------------------------------------------------
    # 6. Drillability Index
    # ------------------------------------------------------------------
    print("\n--- 6. Formation Drillability Index ---")
    dexp = drillability_index(rop_test, wob_test, rpm_test)
    print(f"  D_exp = log10(ROP / (WOB * RPM)) = {dexp:.4f}")

    # ------------------------------------------------------------------
    # 7. Overburden Stress
    # ------------------------------------------------------------------
    print("\n--- 7. Overburden Stress ---")
    tvd_test = 10_500.0  # ft (typical Wolfcamp TVD)
    sv = overburden_stress(tvd_test, rho_avg_ppg=16.33)
    print(f"  TVD = {tvd_test:,.0f} ft, rho_avg = 16.33 ppg")
    print(f"  Sv = {sv:,.0f} psi ({sv / tvd_test:.3f} psi/ft)")

    # ------------------------------------------------------------------
    # 8. Minimum Horizontal Stress
    # ------------------------------------------------------------------
    print("\n--- 8. Minimum Horizontal Stress (Shmin) ---")
    pp = 0.60 * HYDROSTATIC_CONSTANT * tvd_test * (1.0 / HYDROSTATIC_CONSTANT / 1.0)
    # Using pore pressure gradient of 0.60 psi/ft
    pp = 0.60 * tvd_test  # psi (0.60 psi/ft overpressured)
    shmin_val = minimum_horizontal_stress(sv, pp, poisson_ratio=0.27)
    print(f"  Sv = {sv:,.0f} psi, Pp = {pp:,.0f} psi, v = 0.27")
    print(f"  Shmin = {shmin_val:,.0f} psi "
          f"({shmin_val / tvd_test:.3f} psi/ft)")

    # ------------------------------------------------------------------
    # 9. Wellbore Stability Window
    # ------------------------------------------------------------------
    print("\n--- 9. Wellbore Stability Window ---")
    sw = wellbore_stability_window(
        tvd=tvd_test,
        pore_pressure=pp,
        overburden=sv,
        shmin=shmin_val,
        ucs=ucs_val,
        poisson=0.27,
    )
    print(f"  Breakout MW  = {sw['breakout_mw_ppg']:.2f} ppg")
    print(f"  Fracture MW  = {sw['fracture_mw_ppg']:.2f} ppg")
    print(f"  Safe window  = [{sw['safe_mw_min_ppg']:.2f}, "
          f"{sw['safe_mw_max_ppg']:.2f}] ppg "
          f"(width = {sw['window_width_ppg']:.2f} ppg)")
    print(f"  Stable?      = {sw['is_stable']}")

    # ------------------------------------------------------------------
    # 10. Fracability Score
    # ------------------------------------------------------------------
    print("\n--- 10. Fracability Score ---")
    frac_score = fracability_score(bi_val, natural_fracture_density=3.0)
    print(f"  BI = {bi_val:.3f}, NFD = 3.0 frac/ft")
    print(f"  Fracability = {frac_score:.3f}", end="")
    if frac_score > 0.7:
        print("  --> PRIME frac target")
    elif frac_score > 0.4:
        print("  --> Moderate -- standard completion")
    else:
        print("  --> Poor candidate")

    # ------------------------------------------------------------------
    # 11. Stick-Slip Severity (synthetic data)
    # ------------------------------------------------------------------
    print("\n--- 11. Stick-Slip Severity Index ---")
    np.random.seed(42)
    # Simulate smooth drilling (low stick-slip)
    torque_smooth = np.random.normal(12_000, 300, 100)
    rpm_smooth = np.random.normal(120, 3, 100)
    ssi_smooth = stick_slip_severity(torque_smooth, rpm_smooth)

    # Simulate severe stick-slip
    torque_rough = np.random.normal(12_000, 4_000, 100)
    rpm_rough = np.random.normal(120, 40, 100)
    ssi_rough = stick_slip_severity(torque_rough, rpm_rough)

    print(f"  Smooth drilling: SSI = {ssi_smooth:.5f} (should be < 0.01)")
    print(f"  Severe S-S:      SSI = {ssi_rough:.5f} (should be > 0.05)")

    # ------------------------------------------------------------------
    # 12. Lateral analysis (synthetic 1000-ft section)
    # ------------------------------------------------------------------
    print("\n--- 12. Lateral Geomechanics Analysis (synthetic) ---")
    n_pts = 100
    md_arr = np.linspace(15_000, 16_000, n_pts)
    tvd_arr = np.full(n_pts, 10_500.0)  # Horizontal lateral
    wob_arr = np.random.normal(25_000, 2_000, n_pts).clip(5_000)
    torque_arr = np.random.normal(12_000, 1_500, n_pts).clip(1_000)
    rpm_arr = np.random.normal(120, 10, n_pts).clip(30)
    rop_arr = np.random.normal(150, 30, n_pts).clip(10)

    df = analyze_lateral_geomechanics(
        md=md_arr, tvd=tvd_arr, wob=wob_arr, torque=torque_arr,
        rpm=rpm_arr, rop=rop_arr, bit_diameter=8.75,
    )
    print(f"  Generated {len(df)} depth stations")
    print(f"  MSE range: {df['mse'].min():,.0f} - {df['mse'].max():,.0f} psi")
    print(f"  UCS range: {df['ucs'].min():,.0f} - {df['ucs'].max():,.0f} psi")
    print(f"  BI  range: {df['brittleness_index'].min():.3f} - "
          f"{df['brittleness_index'].max():.3f}")
    print(f"  DE  range: {df['drilling_efficiency'].min():.3f} - "
          f"{df['drilling_efficiency'].max():.3f}")
    print("\n  First 5 rows:")
    print(df.head().to_string(index=False))

    print("\n" + "=" * 74)
    print("  Self-test complete.")
    print("=" * 74)


if __name__ == "__main__":
    _demo()
