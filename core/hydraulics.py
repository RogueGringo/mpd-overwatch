"""
MPD Command -- Core Hydraulics Calculation Engine
==================================================

Implements petroleum-engineering-standard drilling hydraulics in oilfield units.

Unit conventions throughout this module
---------------------------------------
  Pressure        : psi
  Depth (MD/TVD)  : ft
  Mud weight (MW) : ppg  (pounds per gallon)
  Flow rate (Q)   : gpm  (gallons per minute)
  Diameter        : in   (inches)
  Viscosity (PV)  : cP   (centipoise)
  Yield point(YP) : lb/100 ft²
  Velocity        : ft/min
  Length          : ft

Reference equations are drawn from:
  - Bourgoyne et al., *Applied Drilling Engineering* (SPE Textbook Series Vol. 2)
  - Mitchell & Miska, *Fundamentals of Drilling Engineering* (SPE Textbook Series Vol. 12)
  - API RP 13D -- Rheology and Hydraulics of Oil-Well Drilling Fluids
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HYDROSTATIC_CONSTANT: float = 0.052
"""psi / (ppg * ft) -- converts MW × TVD to hydrostatic pressure."""

ANNULAR_VELOCITY_CONSTANT: float = 24.5
"""Conversion factor for Q (gpm) and diameters (in) to annular velocity (ft/min).
    V = 24.5 * Q / (D_hole² - D_pipe²)
"""


# ===================================================================
# Data Structures
# ===================================================================

@dataclass
class WellSection:
    """Geometry of a single wellbore section (casing, liner, or open-hole).

    Attributes
    ----------
    md_top : float
        Measured depth to top of section (ft).
    md_bottom : float
        Measured depth to bottom of section (ft).
    tvd_top : float
        True vertical depth to top of section (ft).
    tvd_bottom : float
        True vertical depth to bottom of section (ft).
    hole_id : float
        Inside diameter of the hole or casing (in).
    pipe_od : float
        Outside diameter of the drill-pipe / BHA in this section (in).
    pipe_id : float
        Inside diameter of the drill-pipe / BHA in this section (in).
    name : str
        Human-readable label, e.g. "13-3/8 csg", "8-1/2 OH".
    """
    md_top: float
    md_bottom: float
    tvd_top: float
    tvd_bottom: float
    hole_id: float
    pipe_od: float
    pipe_id: float
    name: str = ""

    @property
    def length(self) -> float:
        """Section length along the wellbore (ft, measured depth)."""
        return self.md_bottom - self.md_top

    @property
    def tvd_length(self) -> float:
        """Vertical height of this section (ft)."""
        return self.tvd_bottom - self.tvd_top

    def __post_init__(self) -> None:
        if self.md_bottom <= self.md_top:
            raise ValueError(
                f"md_bottom ({self.md_bottom}) must exceed md_top ({self.md_top})"
            )
        if self.hole_id <= self.pipe_od:
            raise ValueError(
                f"hole_id ({self.hole_id}) must exceed pipe_od ({self.pipe_od})"
            )


@dataclass
class WellGeometry:
    """Complete wellbore geometry composed of ordered sections from surface to TD.

    Attributes
    ----------
    sections : list[WellSection]
        Ordered top-to-bottom list of wellbore sections.
    """
    sections: List[WellSection] = field(default_factory=list)

    @property
    def total_depth_md(self) -> float:
        """Total measured depth (ft)."""
        if not self.sections:
            return 0.0
        return max(s.md_bottom for s in self.sections)

    @property
    def total_depth_tvd(self) -> float:
        """Total true vertical depth (ft)."""
        if not self.sections:
            return 0.0
        return max(s.tvd_bottom for s in self.sections)

    def tvd_at_md(self, md: float) -> float:
        """Linearly interpolate TVD at a given MD within the well sections.

        Parameters
        ----------
        md : float
            Measured depth (ft).

        Returns
        -------
        float
            Interpolated true vertical depth (ft).
        """
        for sec in self.sections:
            if sec.md_top <= md <= sec.md_bottom:
                fraction = (
                    (md - sec.md_top) / sec.length if sec.length > 0 else 0.0
                )
                return sec.tvd_top + fraction * sec.tvd_length
        raise ValueError(f"MD {md} ft is outside the defined well sections.")

    def section_at_md(self, md: float) -> WellSection:
        """Return the WellSection that contains the given MD."""
        for sec in self.sections:
            if sec.md_top <= md <= sec.md_bottom:
                return sec
        raise ValueError(f"MD {md} ft is outside the defined well sections.")


@dataclass
class MudProperties:
    """Drilling fluid properties (Bingham Plastic model).

    Attributes
    ----------
    mw : float
        Mud weight (ppg).
    pv : float
        Plastic viscosity (cP).
    yp : float
        Yield point (lb/100 ft²).
    """
    mw: float
    pv: float = 0.0
    yp: float = 0.0

    def __post_init__(self) -> None:
        if self.mw <= 0:
            raise ValueError(f"Mud weight must be positive, got {self.mw} ppg")


@dataclass
class FormationPressure:
    """Pore-pressure and fracture-gradient at a given depth.

    Attributes
    ----------
    tvd : float
        True vertical depth (ft).
    pore_pressure : float
        Pore pressure (psi).
    fracture_pressure : float
        Fracture pressure (psi).
    """
    tvd: float
    pore_pressure: float
    fracture_pressure: float

    @property
    def pore_gradient(self) -> float:
        """Pore-pressure gradient (ppg equivalent)."""
        if self.tvd <= 0:
            return 0.0
        return self.pore_pressure / (HYDROSTATIC_CONSTANT * self.tvd)

    @property
    def fracture_gradient(self) -> float:
        """Fracture gradient (ppg equivalent)."""
        if self.tvd <= 0:
            return 0.0
        return self.fracture_pressure / (HYDROSTATIC_CONSTANT * self.tvd)

    @property
    def operating_window_psi(self) -> float:
        """Available pressure window between pore and fracture (psi)."""
        return self.fracture_pressure - self.pore_pressure


@dataclass
class PressureAtDepth:
    """Calculated pressure state at a single depth station.

    Attributes
    ----------
    md : float
        Measured depth (ft).
    tvd : float
        True vertical depth (ft).
    hydrostatic : float
        Hydrostatic pressure of mud column (psi).
    afp : float
        Annular friction pressure contribution above this depth (psi).
    bhp_static : float
        Bottom-hole pressure, static (psi).  Includes SBP.
    bhp_dynamic : float
        Bottom-hole pressure, circulating (psi).  Includes SBP + AFP.
    ecd : float
        Equivalent circulating density at this depth (ppg).
    esd : float
        Equivalent static density at this depth (ppg).
    pore_pressure : float | None
        Pore pressure at this depth, if known (psi).
    fracture_pressure : float | None
        Fracture pressure at this depth, if known (psi).
    """
    md: float
    tvd: float
    hydrostatic: float
    afp: float
    bhp_static: float
    bhp_dynamic: float
    ecd: float
    esd: float
    pore_pressure: Optional[float] = None
    fracture_pressure: Optional[float] = None

    @property
    def within_window(self) -> Optional[bool]:
        """True if dynamic BHP is between pore and fracture pressure."""
        if self.pore_pressure is None or self.fracture_pressure is None:
            return None
        return self.pore_pressure <= self.bhp_dynamic <= self.fracture_pressure


@dataclass
class MPDWindow:
    """MPD operating envelope at a single depth.

    Attributes
    ----------
    tvd : float
        True vertical depth (ft).
    pore_pressure : float
        Pore pressure (psi).
    fracture_pressure : float
        Fracture pressure (psi).
    hydrostatic : float
        Hydrostatic pressure at this depth (psi).
    afp : float
        Annular friction pressure contribution at this depth (psi).
    min_sbp_static : float
        Minimum surface back-pressure to stay above pore pressure (static, psi).
    max_sbp_static : float
        Maximum surface back-pressure to stay below fracture gradient (static, psi).
    min_sbp_dynamic : float
        Minimum SBP while circulating (psi).
    max_sbp_dynamic : float
        Maximum SBP while circulating (psi).
    """
    tvd: float
    pore_pressure: float
    fracture_pressure: float
    hydrostatic: float
    afp: float
    min_sbp_static: float
    max_sbp_static: float
    min_sbp_dynamic: float
    max_sbp_dynamic: float

    @property
    def static_window(self) -> float:
        """Available SBP range when static (psi)."""
        return max(0.0, self.max_sbp_static - self.min_sbp_static)

    @property
    def dynamic_window(self) -> float:
        """Available SBP range while circulating (psi)."""
        return max(0.0, self.max_sbp_dynamic - self.min_sbp_dynamic)


@dataclass
class KillSheet:
    """Well-kill calculation results.

    Attributes
    ----------
    original_mw : float
        Original mud weight in hole (ppg).
    tvd : float
        True vertical depth to influx / kick zone (ft).
    sidpp : float
        Shut-in drill-pipe pressure (psi).
    sicp : float
        Shut-in casing pressure (psi).
    slow_circ_rate_pressure : float
        Slow circulating rate pressure (psi) -- measured at kill rate.
    kill_mw : float
        Required kill mud weight (ppg).
    icp : float
        Initial circulating pressure (psi).
    fcp : float
        Final circulating pressure (psi).
    """
    original_mw: float
    tvd: float
    sidpp: float
    sicp: float
    slow_circ_rate_pressure: float
    kill_mw: float
    icp: float
    fcp: float


@dataclass
class SurgeSwabResult:
    """Surge and swab pressure estimates.

    Attributes
    ----------
    surge_pressure : float
        Pressure increase due to pipe running in hole (psi).
    swab_pressure : float
        Pressure decrease due to pipe pulling out of hole (psi).
    bhp_surge : float
        BHP with surge effect (psi).
    bhp_swab : float
        BHP with swab effect (psi).
    ecd_surge : float
        Equivalent density including surge (ppg).
    ecd_swab : float
        Equivalent density including swab (ppg).
    """
    surge_pressure: float
    swab_pressure: float
    bhp_surge: float
    bhp_swab: float
    ecd_surge: float
    ecd_swab: float


# ===================================================================
# Core Hydraulics Functions
# ===================================================================

def hydrostatic_pressure(mw: float, tvd: float) -> float:
    """Hydrostatic pressure of a static fluid column.

    P_h = 0.052 x MW x TVD

    Parameters
    ----------
    mw : float
        Mud weight (ppg).
    tvd : float
        True vertical depth (ft).

    Returns
    -------
    float
        Hydrostatic pressure (psi).
    """
    return HYDROSTATIC_CONSTANT * mw * tvd


def annular_velocity(q: float, d_hole: float, d_pipe: float) -> float:
    """Annular velocity from flow rate and annular dimensions.

    V = 24.5 x Q / (D_hole² - D_pipe²)

    Parameters
    ----------
    q : float
        Flow rate (gpm).
    d_hole : float
        Hole / casing inside diameter (in).
    d_pipe : float
        Pipe outside diameter (in).

    Returns
    -------
    float
        Annular velocity (ft/min).

    Raises
    ------
    ValueError
        If the annular area is zero or negative.
    """
    annular_area = d_hole ** 2 - d_pipe ** 2
    if annular_area <= 0:
        raise ValueError(
            f"Annular area must be positive: D_hole={d_hole}, D_pipe={d_pipe}"
        )
    return ANNULAR_VELOCITY_CONSTANT * q / annular_area


def annular_friction_pressure(
    pv: float,
    yp: float,
    length: float,
    q: float,
    d_hole: float,
    d_pipe: float,
) -> float:
    """Annular friction pressure loss using the Bingham Plastic model.

    AFP = (PV x L x V) / (60000 x (D_h - D_p)²)
        + (YP x L) / (200 x (D_h - D_p))

    Parameters
    ----------
    pv : float
        Plastic viscosity (cP).
    yp : float
        Yield point (lb/100 ft²).
    length : float
        Annular section length (ft, measured depth).
    q : float
        Flow rate (gpm).
    d_hole : float
        Hole / casing ID (in).
    d_pipe : float
        Pipe OD (in).

    Returns
    -------
    float
        Annular friction pressure loss for this section (psi).
    """
    if length <= 0 or q <= 0:
        return 0.0

    d_annular = d_hole - d_pipe
    if d_annular <= 0:
        raise ValueError("Hole ID must be greater than pipe OD.")

    v = annular_velocity(q, d_hole, d_pipe)

    viscous_term = (pv * length * v) / (60_000.0 * d_annular ** 2)
    yield_term = (yp * length) / (200.0 * d_annular)

    return viscous_term + yield_term


def total_annular_friction(
    well: WellGeometry,
    mud: MudProperties,
    q: float,
) -> float:
    """Sum AFP across all wellbore sections from TD to surface.

    Parameters
    ----------
    well : WellGeometry
        Complete well geometry.
    mud : MudProperties
        Drilling fluid properties (Bingham Plastic).
    q : float
        Flow rate (gpm).

    Returns
    -------
    float
        Total annular friction pressure loss (psi).
    """
    total = 0.0
    for sec in well.sections:
        total += annular_friction_pressure(
            pv=mud.pv,
            yp=mud.yp,
            length=sec.length,
            q=q,
            d_hole=sec.hole_id,
            d_pipe=sec.pipe_od,
        )
    return total


def cumulative_afp_at_depth(
    well: WellGeometry,
    mud: MudProperties,
    q: float,
    target_md: float,
) -> float:
    """AFP accumulated from TD up to a target MD (annular flow direction).

    In conventional circulation the fluid travels down the drill-string and
    up the annulus.  AFP accumulates from the bit (TD) toward surface.
    This function returns the AFP that has built up by the time the fluid
    reaches ``target_md`` on its way to surface.

    Parameters
    ----------
    well : WellGeometry
        Well geometry.
    mud : MudProperties
        Fluid properties.
    q : float
        Flow rate (gpm).
    target_md : float
        Measured depth at which to evaluate cumulative AFP (ft).

    Returns
    -------
    float
        Cumulative annular friction pressure at target_md (psi).
    """
    afp = 0.0
    # Walk sections from deepest to shallowest.
    for sec in sorted(well.sections, key=lambda s: s.md_bottom, reverse=True):
        if sec.md_top >= target_md:
            # Entire section is below our target -- full contribution.
            afp += annular_friction_pressure(
                mud.pv, mud.yp, sec.length, q, sec.hole_id, sec.pipe_od
            )
        elif sec.md_bottom > target_md:
            # Section straddles target -- partial contribution from the
            # portion below the target depth.
            partial_length = sec.md_bottom - target_md
            afp += annular_friction_pressure(
                mud.pv, mud.yp, partial_length, q, sec.hole_id, sec.pipe_od
            )
        # Sections entirely above target contribute nothing on the
        # TD-to-target path.
    return afp


def bottom_hole_pressure_static(mw: float, tvd: float, sbp: float = 0.0) -> float:
    """Static bottom-hole pressure (pumps off).

    BHP_static = 0.052 x MW x TVD + SBP

    Parameters
    ----------
    mw : float
        Mud weight (ppg).
    tvd : float
        True vertical depth (ft).
    sbp : float
        Surface back-pressure applied via MPD choke (psi).  Default 0.

    Returns
    -------
    float
        Static bottom-hole pressure (psi).
    """
    return hydrostatic_pressure(mw, tvd) + sbp


def bottom_hole_pressure_dynamic(
    mw: float, tvd: float, afp: float, sbp: float = 0.0
) -> float:
    """Dynamic bottom-hole pressure (pumps on).

    BHP_dynamic = 0.052 x MW x TVD + AFP + SBP

    Parameters
    ----------
    mw : float
        Mud weight (ppg).
    tvd : float
        True vertical depth (ft).
    afp : float
        Total annular friction pressure (psi).
    sbp : float
        Surface back-pressure (psi).

    Returns
    -------
    float
        Dynamic bottom-hole pressure (psi).
    """
    return hydrostatic_pressure(mw, tvd) + afp + sbp


def equivalent_circulating_density(
    mw: float, afp: float, tvd: float
) -> float:
    """Equivalent circulating density.

    ECD = MW + AFP / (0.052 x TVD)

    Parameters
    ----------
    mw : float
        Mud weight (ppg).
    afp : float
        Annular friction pressure (psi).
    tvd : float
        True vertical depth (ft).

    Returns
    -------
    float
        ECD (ppg).
    """
    if tvd <= 0:
        return mw
    return mw + afp / (HYDROSTATIC_CONSTANT * tvd)


def equivalent_static_density(bhp_static: float, tvd: float) -> float:
    """Equivalent static density.

    ESD = BHP_static / (0.052 x TVD)

    Parameters
    ----------
    bhp_static : float
        Static bottom-hole pressure (psi).  May include SBP.
    tvd : float
        True vertical depth (ft).

    Returns
    -------
    float
        ESD (ppg).
    """
    if tvd <= 0:
        return 0.0
    return bhp_static / (HYDROSTATIC_CONSTANT * tvd)


# ===================================================================
# Pressure Window Analysis
# ===================================================================

def pressure_window(
    formation: FormationPressure,
    mw: float,
    afp: float = 0.0,
    sbp: float = 0.0,
) -> dict:
    """Evaluate whether current BHP falls within the pore/fracture window.

    Parameters
    ----------
    formation : FormationPressure
        Pore and fracture pressures at the depth of interest.
    mw : float
        Mud weight (ppg).
    afp : float
        Annular friction pressure (psi).
    sbp : float
        Surface back-pressure (psi).

    Returns
    -------
    dict
        Keys: tvd, pore_pressure, fracture_pressure, bhp_static,
              bhp_dynamic, ecd, esd, margin_to_pore, margin_to_frac,
              within_window.
    """
    tvd = formation.tvd
    bhp_s = bottom_hole_pressure_static(mw, tvd, sbp)
    bhp_d = bottom_hole_pressure_dynamic(mw, tvd, afp, sbp)
    ecd = equivalent_circulating_density(mw, afp, tvd)
    esd = equivalent_static_density(bhp_s, tvd)

    margin_pore = bhp_d - formation.pore_pressure
    margin_frac = formation.fracture_pressure - bhp_d
    within = (margin_pore >= 0) and (margin_frac >= 0)

    return {
        "tvd": tvd,
        "pore_pressure": formation.pore_pressure,
        "fracture_pressure": formation.fracture_pressure,
        "pore_gradient_ppg": formation.pore_gradient,
        "fracture_gradient_ppg": formation.fracture_gradient,
        "bhp_static": bhp_s,
        "bhp_dynamic": bhp_d,
        "ecd": ecd,
        "esd": esd,
        "margin_to_pore_psi": margin_pore,
        "margin_to_fracture_psi": margin_frac,
        "within_window": within,
    }


# ===================================================================
# Surge & Swab  (Simplified Burkhardt Model)
# ===================================================================

def surge_swab_pressure(
    mw: float,
    tvd: float,
    pipe_velocity: float,
    d_hole: float,
    d_pipe: float,
    pv: float,
    mud_clinging_factor: float = 0.45,
) -> SurgeSwabResult:
    """Estimate surge and swab pressures using a simplified Burkhardt method.

    The Burkhardt model approximates the pressure change induced by pipe
    movement as an equivalent circulating effect:

        delta_P = K_c x (PV x V_pipe x L_eff) / (60000 x (D_h - D_p)^2)

    where K_c is a clinging factor that accounts for the mud displaced by
    the moving pipe.  A typical value is 0.40-0.50 for open-ended pipe.

    Parameters
    ----------
    mw : float
        Mud weight (ppg).
    tvd : float
        True vertical depth (ft).
    pipe_velocity : float
        Tripping speed of the pipe (ft/min).  Positive value.
    d_hole : float
        Hole / casing ID (in).
    d_pipe : float
        Pipe OD (in).
    pv : float
        Plastic viscosity (cP).
    mud_clinging_factor : float
        Burkhardt clinging constant K_c (dimensionless).  Default 0.45.

    Returns
    -------
    SurgeSwabResult
        Surge and swab pressures and resulting BHP / ECD values.
    """
    d_ann = d_hole - d_pipe
    if d_ann <= 0:
        raise ValueError("Hole ID must be greater than pipe OD.")

    # Equivalent annular velocity produced by pipe movement.
    # Using the area ratio:  V_ann_eq = V_pipe x (D_pipe² / (D_hole² - D_pipe²))
    area_ratio = d_pipe ** 2 / (d_hole ** 2 - d_pipe ** 2)
    v_equivalent = pipe_velocity * area_ratio

    # Simplified Burkhardt pressure change.
    # delta_P  ~= K_c x PV x V_eq x TVD / (60000 x d_ann^2)
    # (using TVD as effective length for a vertical well simplification)
    delta_p = (
        mud_clinging_factor * pv * v_equivalent * tvd
    ) / (60_000.0 * d_ann ** 2)

    bhp_static = hydrostatic_pressure(mw, tvd)
    bhp_surge = bhp_static + delta_p
    bhp_swab = bhp_static - delta_p

    ecd_surge = equivalent_static_density(bhp_surge, tvd) if tvd > 0 else mw
    ecd_swab = equivalent_static_density(bhp_swab, tvd) if tvd > 0 else mw

    return SurgeSwabResult(
        surge_pressure=delta_p,
        swab_pressure=delta_p,
        bhp_surge=bhp_surge,
        bhp_swab=bhp_swab,
        ecd_surge=ecd_surge,
        ecd_swab=ecd_swab,
    )


# ===================================================================
# Kill Sheet Calculations
# ===================================================================

def calculate_kill_sheet(
    original_mw: float,
    tvd: float,
    sidpp: float,
    sicp: float,
    slow_circ_rate_pressure: float,
) -> KillSheet:
    """Driller's / Wait-and-Weight kill-sheet calculations.

    Kill MW   = Original MW + SIDPP / (0.052 x TVD)
    ICP       = SIDPP + Slow Circulating Rate Pressure
    FCP       = Slow Circulating Rate Pressure x (Kill MW / Original MW)

    Parameters
    ----------
    original_mw : float
        Mud weight currently in the hole (ppg).
    tvd : float
        True vertical depth to the kick zone (ft).
    sidpp : float
        Shut-in drill-pipe pressure (psi).
    sicp : float
        Shut-in casing pressure (psi).
    slow_circ_rate_pressure : float
        Pressure recorded at the selected kill-rate (psi).

    Returns
    -------
    KillSheet
        Populated kill-sheet data.
    """
    if tvd <= 0:
        raise ValueError("TVD must be positive for kill calculations.")
    if original_mw <= 0:
        raise ValueError("Original MW must be positive.")

    kill_mw = original_mw + sidpp / (HYDROSTATIC_CONSTANT * tvd)
    icp = sidpp + slow_circ_rate_pressure
    fcp = slow_circ_rate_pressure * (kill_mw / original_mw)

    return KillSheet(
        original_mw=original_mw,
        tvd=tvd,
        sidpp=sidpp,
        sicp=sicp,
        slow_circ_rate_pressure=slow_circ_rate_pressure,
        kill_mw=kill_mw,
        icp=icp,
        fcp=fcp,
    )


# ===================================================================
# Pressure Profile Along Wellbore
# ===================================================================

def pressure_profile(
    well: WellGeometry,
    mud: MudProperties,
    q: float = 0.0,
    sbp: float = 0.0,
    formation_pressures: Optional[List[FormationPressure]] = None,
    num_stations: int = 50,
) -> List[PressureAtDepth]:
    """Build a pressure-vs-depth profile from surface to TD.

    Computes hydrostatic, AFP, BHP (static & dynamic), ECD, and ESD at
    evenly-spaced depth stations.  If formation pressure data is supplied,
    pore/fracture values are linearly interpolated and attached to each
    station.

    Parameters
    ----------
    well : WellGeometry
        Well geometry definition.
    mud : MudProperties
        Drilling fluid properties.
    q : float
        Flow rate (gpm).  Pass 0 for a static profile.
    sbp : float
        Surface back-pressure (psi).
    formation_pressures : list[FormationPressure] | None
        Optional sorted-by-TVD formation pressure points for interpolation.
    num_stations : int
        Number of depth stations (default 50).

    Returns
    -------
    list[PressureAtDepth]
        Pressure data at each depth station.
    """
    if num_stations < 2:
        num_stations = 2

    td_md = well.total_depth_md
    md_step = td_md / (num_stations - 1)
    stations: List[PressureAtDepth] = []

    for i in range(num_stations):
        md = i * md_step
        # Clamp to TD
        md = min(md, td_md)

        try:
            tvd = well.tvd_at_md(md)
        except ValueError:
            continue

        hp = hydrostatic_pressure(mud.mw, tvd)
        afp_here = cumulative_afp_at_depth(well, mud, q, md) if q > 0 else 0.0
        bhp_s = hp + sbp
        bhp_d = hp + afp_here + sbp
        ecd = equivalent_circulating_density(mud.mw, afp_here, tvd)
        esd = equivalent_static_density(bhp_s, tvd)

        pp = _interpolate_formation(tvd, formation_pressures, "pore")
        fp = _interpolate_formation(tvd, formation_pressures, "frac")

        stations.append(PressureAtDepth(
            md=md,
            tvd=tvd,
            hydrostatic=hp,
            afp=afp_here,
            bhp_static=bhp_s,
            bhp_dynamic=bhp_d,
            ecd=ecd,
            esd=esd,
            pore_pressure=pp,
            fracture_pressure=fp,
        ))

    return stations


def _interpolate_formation(
    tvd: float,
    fp_list: Optional[List[FormationPressure]],
    kind: str,
) -> Optional[float]:
    """Linear interpolation of pore or fracture pressure at a given TVD.

    Parameters
    ----------
    tvd : float
        Target TVD (ft).
    fp_list : list[FormationPressure] | None
        Formation pressure data sorted by TVD ascending.
    kind : str
        "pore" or "frac".

    Returns
    -------
    float | None
    """
    if not fp_list:
        return None

    # Sort defensively
    pts = sorted(fp_list, key=lambda f: f.tvd)

    if tvd <= pts[0].tvd:
        return pts[0].pore_pressure if kind == "pore" else pts[0].fracture_pressure
    if tvd >= pts[-1].tvd:
        return pts[-1].pore_pressure if kind == "pore" else pts[-1].fracture_pressure

    for j in range(len(pts) - 1):
        if pts[j].tvd <= tvd <= pts[j + 1].tvd:
            frac_d = (tvd - pts[j].tvd) / (pts[j + 1].tvd - pts[j].tvd)
            if kind == "pore":
                return pts[j].pore_pressure + frac_d * (
                    pts[j + 1].pore_pressure - pts[j].pore_pressure
                )
            else:
                return pts[j].fracture_pressure + frac_d * (
                    pts[j + 1].fracture_pressure - pts[j].fracture_pressure
                )
    return None


# ===================================================================
# MPD Operating Envelope
# ===================================================================

def mpd_operating_envelope(
    well: WellGeometry,
    mud: MudProperties,
    q: float,
    formation_pressures: List[FormationPressure],
    num_stations: int = 50,
) -> List[MPDWindow]:
    """Calculate the MPD operating envelope along the wellbore.

    For each depth station the function determines:
      - The minimum SBP required so that BHP >= pore pressure (static & dynamic)
      - The maximum SBP allowed so that BHP <= fracture pressure (static & dynamic)

    This tells the MPD operator exactly what choke-pressure range is
    permissible at every depth, and highlights where the window narrows
    or where SBP adjustments are critical.

    Parameters
    ----------
    well : WellGeometry
        Well geometry.
    mud : MudProperties
        Fluid properties.
    q : float
        Flow rate (gpm).
    formation_pressures : list[FormationPressure]
        Pore-pressure and fracture-gradient data sorted by TVD.
    num_stations : int
        Number of depth evaluation points.

    Returns
    -------
    list[MPDWindow]
        Operating envelope at each depth station.
    """
    if num_stations < 2:
        num_stations = 2

    td_md = well.total_depth_md
    md_step = td_md / (num_stations - 1)
    envelope: List[MPDWindow] = []

    for i in range(num_stations):
        md = min(i * md_step, td_md)

        try:
            tvd = well.tvd_at_md(md)
        except ValueError:
            continue

        if tvd <= 0:
            continue

        hp = hydrostatic_pressure(mud.mw, tvd)
        afp_here = cumulative_afp_at_depth(well, mud, q, md) if q > 0 else 0.0

        pp = _interpolate_formation(tvd, formation_pressures, "pore")
        fp = _interpolate_formation(tvd, formation_pressures, "frac")
        if pp is None or fp is None:
            continue

        # Static: BHP_static = HP + SBP  -->  PP <= HP + SBP <= FP
        #   min SBP (static) = PP - HP   (but not less than 0)
        #   max SBP (static) = FP - HP
        min_sbp_static = max(0.0, pp - hp)
        max_sbp_static = max(0.0, fp - hp)

        # Dynamic: BHP_dyn = HP + AFP + SBP  -->  PP <= HP + AFP + SBP <= FP
        #   min SBP (dynamic) = PP - HP - AFP
        #   max SBP (dynamic) = FP - HP - AFP
        min_sbp_dynamic = max(0.0, pp - hp - afp_here)
        max_sbp_dynamic = max(0.0, fp - hp - afp_here)

        envelope.append(MPDWindow(
            tvd=tvd,
            pore_pressure=pp,
            fracture_pressure=fp,
            hydrostatic=hp,
            afp=afp_here,
            min_sbp_static=min_sbp_static,
            max_sbp_static=max_sbp_static,
            min_sbp_dynamic=min_sbp_dynamic,
            max_sbp_dynamic=max_sbp_dynamic,
        ))

    return envelope


def find_critical_sbp_range(
    envelope: List[MPDWindow],
    circulating: bool = True,
) -> Tuple[float, float]:
    """From an MPD envelope, find the tightest (governing) SBP range.

    The governing SBP range is the intersection of all per-depth
    windows.  If no single SBP satisfies every depth simultaneously,
    the returned min > max, indicating the well cannot be managed
    with a single constant SBP -- the operator must vary SBP with depth
    (e.g., by adjusting choke during connections or while tripping).

    Parameters
    ----------
    envelope : list[MPDWindow]
        Output of :func:`mpd_operating_envelope`.
    circulating : bool
        If True, use dynamic windows; if False, use static windows.

    Returns
    -------
    tuple[float, float]
        (governing_min_sbp, governing_max_sbp) in psi.
        If governing_min > governing_max the window is collapsed.
    """
    if not envelope:
        return (0.0, 0.0)

    if circulating:
        gov_min = max(w.min_sbp_dynamic for w in envelope)
        gov_max = min(w.max_sbp_dynamic for w in envelope)
    else:
        gov_min = max(w.min_sbp_static for w in envelope)
        gov_max = min(w.max_sbp_static for w in envelope)

    return (gov_min, gov_max)


# ===================================================================
# Convenience / Summary
# ===================================================================

def quick_bhp_summary(
    mw: float,
    tvd: float,
    afp: float = 0.0,
    sbp: float = 0.0,
) -> dict:
    """One-call summary of BHP, ECD, and ESD.

    Parameters
    ----------
    mw : float
        Mud weight (ppg).
    tvd : float
        True vertical depth (ft).
    afp : float
        Annular friction pressure (psi).
    sbp : float
        Surface back-pressure (psi).

    Returns
    -------
    dict
        hydrostatic, bhp_static, bhp_dynamic, ecd, esd.
    """
    hp = hydrostatic_pressure(mw, tvd)
    bhp_s = bottom_hole_pressure_static(mw, tvd, sbp)
    bhp_d = bottom_hole_pressure_dynamic(mw, tvd, afp, sbp)
    ecd = equivalent_circulating_density(mw, afp, tvd)
    esd = equivalent_static_density(bhp_s, tvd)

    return {
        "hydrostatic_psi": round(hp, 2),
        "bhp_static_psi": round(bhp_s, 2),
        "bhp_dynamic_psi": round(bhp_d, 2),
        "ecd_ppg": round(ecd, 4),
        "esd_ppg": round(esd, 4),
    }


# ===================================================================
# Self-Test / Demo
# ===================================================================

def _demo() -> None:
    """Run a quick validation with realistic values."""

    print("=" * 70)
    print("  MPD Command -- Hydraulics Engine Self-Test")
    print("=" * 70)

    # -- Well geometry: vertical well to 15,000 ft -----------------------
    sections = [
        WellSection(
            md_top=0, md_bottom=5_000, tvd_top=0, tvd_bottom=5_000,
            hole_id=12.25, pipe_od=5.0, pipe_id=4.276,
            name="13-3/8 csg",
        ),
        WellSection(
            md_top=5_000, md_bottom=10_000, tvd_top=5_000, tvd_bottom=10_000,
            hole_id=9.875, pipe_od=5.0, pipe_id=4.276,
            name="9-5/8 csg",
        ),
        WellSection(
            md_top=10_000, md_bottom=15_000, tvd_top=10_000, tvd_bottom=15_000,
            hole_id=8.5, pipe_od=5.0, pipe_id=4.276,
            name="8-1/2 OH",
        ),
    ]
    well = WellGeometry(sections=sections)

    mud = MudProperties(mw=12.5, pv=25, yp=15)
    q = 350.0   # gpm
    sbp = 200.0  # psi

    # Formation pressures at three depths
    fp_data = [
        FormationPressure(tvd=5_000,  pore_pressure=2_700,  fracture_pressure=4_550),
        FormationPressure(tvd=10_000, pore_pressure=5_800,  fracture_pressure=8_600),
        FormationPressure(tvd=15_000, pore_pressure=9_100,  fracture_pressure=12_500),
    ]

    # 1. Basic calculations
    print("\n--- Basic Calculations at TD ---")
    tvd_td = 15_000
    hp = hydrostatic_pressure(mud.mw, tvd_td)
    afp_total = total_annular_friction(well, mud, q)
    bhp_s = bottom_hole_pressure_static(mud.mw, tvd_td, sbp)
    bhp_d = bottom_hole_pressure_dynamic(mud.mw, tvd_td, afp_total, sbp)
    ecd_val = equivalent_circulating_density(mud.mw, afp_total, tvd_td)
    esd_val = equivalent_static_density(bhp_s, tvd_td)

    print(f"  Hydrostatic pressure  : {hp:,.1f} psi")
    print(f"  Total AFP             : {afp_total:,.1f} psi")
    print(f"  BHP (static, SBP={sbp}): {bhp_s:,.1f} psi")
    print(f"  BHP (dynamic)         : {bhp_d:,.1f} psi")
    print(f"  ECD                   : {ecd_val:.3f} ppg")
    print(f"  ESD                   : {esd_val:.3f} ppg")

    # 2. Pressure window
    print("\n--- Pressure Window at TD ---")
    pw = pressure_window(fp_data[-1], mud.mw, afp_total, sbp)
    print(f"  Pore pressure         : {pw['pore_pressure']:,.1f} psi")
    print(f"  Fracture pressure     : {pw['fracture_pressure']:,.1f} psi")
    print(f"  BHP dynamic           : {pw['bhp_dynamic']:,.1f} psi")
    print(f"  Margin to pore        : {pw['margin_to_pore_psi']:,.1f} psi")
    print(f"  Margin to fracture    : {pw['margin_to_fracture_psi']:,.1f} psi")
    print(f"  Within window?        : {pw['within_window']}")

    # 3. Surge / Swab
    print("\n--- Surge & Swab (tripping at 90 ft/min) ---")
    ss = surge_swab_pressure(
        mw=mud.mw, tvd=tvd_td, pipe_velocity=90.0,
        d_hole=8.5, d_pipe=5.0, pv=mud.pv,
    )
    print(f"  Surge pressure        : {ss.surge_pressure:,.1f} psi")
    print(f"  Swab pressure         : {ss.swab_pressure:,.1f} psi")
    print(f"  BHP with surge        : {ss.bhp_surge:,.1f} psi")
    print(f"  BHP with swab         : {ss.bhp_swab:,.1f} psi")

    # 4. Kill sheet
    print("\n--- Kill Sheet (SIDPP=350 psi) ---")
    ks = calculate_kill_sheet(
        original_mw=mud.mw, tvd=tvd_td,
        sidpp=350, sicp=450, slow_circ_rate_pressure=600,
    )
    print(f"  Kill MW               : {ks.kill_mw:.2f} ppg")
    print(f"  ICP                   : {ks.icp:,.1f} psi")
    print(f"  FCP                   : {ks.fcp:,.1f} psi")

    # 5. MPD envelope -- governing SBP
    print("\n--- MPD Operating Envelope (governing SBP) ---")
    envelope = mpd_operating_envelope(well, mud, q, fp_data, num_stations=20)
    gov_min_dyn, gov_max_dyn = find_critical_sbp_range(envelope, circulating=True)
    gov_min_sta, gov_max_sta = find_critical_sbp_range(envelope, circulating=False)
    print(f"  Static  SBP window    : {gov_min_sta:,.1f} -- {gov_max_sta:,.1f} psi")
    print(f"  Dynamic SBP window    : {gov_min_dyn:,.1f} -- {gov_max_dyn:,.1f} psi")
    if gov_min_dyn <= gov_max_dyn:
        print(f"  Recommended SBP (dyn) : {(gov_min_dyn + gov_max_dyn) / 2:,.1f} psi (midpoint)")
    else:
        print("  WARNING: Dynamic window is collapsed -- single SBP cannot satisfy all depths.")

    # 6. Pressure profile snippet
    print("\n--- Pressure Profile (first 5 stations) ---")
    profile = pressure_profile(well, mud, q, sbp, fp_data, num_stations=20)
    print(f"  {'MD':>8}  {'TVD':>8}  {'Hydro':>9}  {'AFP':>8}  "
          f"{'BHP_s':>9}  {'BHP_d':>9}  {'ECD':>7}  {'PP':>9}  {'FP':>9}")
    for st in profile[:5]:
        pp_str = f"{st.pore_pressure:9,.1f}" if st.pore_pressure else "     N/A"
        fp_str = f"{st.fracture_pressure:9,.1f}" if st.fracture_pressure else "     N/A"
        print(f"  {st.md:8,.0f}  {st.tvd:8,.0f}  {st.hydrostatic:9,.1f}  "
              f"{st.afp:8,.1f}  {st.bhp_static:9,.1f}  {st.bhp_dynamic:9,.1f}  "
              f"{st.ecd:7.3f}  {pp_str}  {fp_str}")

    print("\n" + "=" * 70)
    print("  Self-test complete.")
    print("=" * 70)


if __name__ == "__main__":
    _demo()
