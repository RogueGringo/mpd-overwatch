"""MPD Command - Drilling Parameter Optimizer

Recommends optimal drilling parameters (WOB, RPM, flow rate, SBP) to maximize
ROP while maintaining BHP within the MPD operating window.

This is the "craft" differentiator - turning MPD from equipment rental into
intelligent operations optimization.

Physics basis:
  - ROP increases with WOB and RPM (Bourgoyne-Young model simplified)
  - ROP increases with reduced overbalance (chip hold-down effect)
  - BHP must stay between pore pressure and fracture gradient
  - ECD is a function of flow rate, mud properties, and well geometry
  - SBP compensates for ECD changes during connections
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class DrillingWindow:
    """Safe operating envelope at a given depth."""
    tvd: float              # ft
    pore_pressure_ppg: float
    fracture_gradient_ppg: float
    current_mud_weight: float  # ppg
    current_ecd: float       # ppg
    current_sbp: float       # psi
    current_bhp: float       # psi


@dataclass
class OptimizedParameters:
    """Recommended drilling parameters."""
    wob_klbs: float
    rpm: float
    flow_rate_gpm: float
    sbp_psi: float
    predicted_rop_fthr: float
    predicted_ecd_ppg: float
    predicted_bhp_psi: float
    overbalance_psi: float
    margin_to_frac_psi: float
    margin_to_pp_psi: float
    confidence: float        # 0-1
    notes: str


@dataclass
class ConnectionPlan:
    """SBP management plan for a pipe connection."""
    pre_connection_sbp: float    # psi (while circulating)
    static_sbp: float            # psi (pumps off, compensate for AFP loss)
    post_connection_sbp: float   # psi (pumps back on)
    afp_loss: float              # psi (friction pressure lost when pumps stop)
    bhp_during_connection: float # psi
    swab_margin: float           # psi (safety margin for pipe movement)
    time_to_adjust: float        # seconds (recommended ramp time)


def calculate_rop_model(
    wob_klbs: float,
    rpm: float,
    differential_pressure_psi: float,
    bit_diameter_in: float = 8.75,
    formation_drillability: float = 1.0,
    bit_wear_factor: float = 1.0,
) -> float:
    """Simplified Bourgoyne-Young ROP model.

    ROP = K * (WOB/D)^a1 * RPM^a2 * exp(-a3 * DP)

    Where:
        K = drillability constant (formation dependent)
        WOB/D = weight per inch of bit diameter
        DP = differential pressure (chip hold-down effect)
        a1 ≈ 1.0, a2 ≈ 0.6, a3 ≈ 0.0001 (typical shale values)

    Returns ROP in ft/hr.
    """
    if wob_klbs <= 0 or rpm <= 0 or bit_diameter_in <= 0:
        return 0.0

    K = 50.0 * formation_drillability * bit_wear_factor
    wob_per_inch = (wob_klbs * 1000) / bit_diameter_in  # lbs/inch
    a1 = 1.0
    a2 = 0.6
    a3 = 0.0001  # chip hold-down coefficient

    # Normalize WOB/D to typical range
    wob_factor = (wob_per_inch / 3000) ** a1
    rpm_factor = (rpm / 120) ** a2
    pressure_factor = np.exp(-a3 * max(differential_pressure_psi, 0))

    rop = K * wob_factor * rpm_factor * pressure_factor
    return max(rop, 0.0)


def calculate_ecd(
    mud_weight_ppg: float,
    flow_rate_gpm: float,
    tvd_ft: float,
    hole_diameter_in: float = 8.75,
    pipe_od_in: float = 5.0,
    pv_cp: float = 15.0,
    yp_lbf_100ft2: float = 10.0,
    lateral_length_ft: float = 10000.0,
) -> float:
    """Calculate ECD for given flow conditions.

    Uses Bingham Plastic model for annular friction pressure.
    """
    if tvd_ft <= 0:
        return mud_weight_ppg

    # Annular velocity
    d_ann = hole_diameter_in**2 - pipe_od_in**2
    if d_ann <= 0:
        return mud_weight_ppg
    v_ann = 24.5 * flow_rate_gpm / d_ann  # ft/min

    # AFP (simplified Bingham for full wellbore length)
    total_length = tvd_ft + lateral_length_ft
    afp_viscous = (pv_cp * total_length * v_ann) / (60000 * (hole_diameter_in - pipe_od_in)**2)
    afp_yield = (yp_lbf_100ft2 * total_length) / (200 * (hole_diameter_in - pipe_od_in))
    afp = afp_viscous + afp_yield

    ecd = mud_weight_ppg + afp / (0.052 * tvd_ft)
    return ecd


def optimize_parameters(
    window: DrillingWindow,
    bit_diameter_in: float = 8.75,
    pipe_od_in: float = 5.0,
    pv_cp: float = 15.0,
    yp_lbf_100ft2: float = 10.0,
    lateral_length_ft: float = 10000.0,
    formation_drillability: float = 1.0,
    wob_range: Tuple[float, float] = (15, 40),     # klbs
    rpm_range: Tuple[float, float] = (80, 180),     # rev/min
    flow_range: Tuple[float, float] = (400, 800),   # gpm
    sbp_range: Tuple[float, float] = (0, 500),      # psi
    safety_margin_ppg: float = 0.3,
) -> OptimizedParameters:
    """Find optimal drilling parameters that maximize ROP within the pressure window.

    Uses grid search over parameter space (fast enough for real-time use).
    Constraints:
      - BHP must stay > PP + safety_margin
      - ECD must stay < FG - safety_margin
      - Minimize overbalance (reduces formation damage and chip hold-down)
    """
    best_rop = 0.0
    best_params = None

    pp_psi = 0.052 * window.pore_pressure_ppg * window.tvd
    fg_psi = 0.052 * window.fracture_gradient_ppg * window.tvd
    safety_psi = 0.052 * safety_margin_ppg * window.tvd

    # Grid search
    for wob in np.linspace(wob_range[0], wob_range[1], 6):
        for rpm_val in np.linspace(rpm_range[0], rpm_range[1], 6):
            for flow in np.linspace(flow_range[0], flow_range[1], 5):
                ecd = calculate_ecd(
                    window.current_mud_weight, flow, window.tvd,
                    bit_diameter_in, pipe_od_in, pv_cp, yp_lbf_100ft2,
                    lateral_length_ft,
                )

                # Try SBP values
                for sbp in np.linspace(sbp_range[0], sbp_range[1], 5):
                    bhp = 0.052 * ecd * window.tvd + sbp
                    overbalance = bhp - pp_psi
                    margin_to_frac = fg_psi - bhp

                    # Constraints
                    if bhp < pp_psi + safety_psi:
                        continue  # too low - risk of kick
                    if bhp > fg_psi - safety_psi:
                        continue  # too high - risk of losses

                    rop = calculate_rop_model(
                        wob, rpm_val, overbalance,
                        bit_diameter_in, formation_drillability,
                    )

                    if rop > best_rop:
                        best_rop = rop
                        best_params = OptimizedParameters(
                            wob_klbs=wob,
                            rpm=rpm_val,
                            flow_rate_gpm=flow,
                            sbp_psi=sbp,
                            predicted_rop_fthr=rop,
                            predicted_ecd_ppg=ecd,
                            predicted_bhp_psi=bhp,
                            overbalance_psi=overbalance,
                            margin_to_frac_psi=margin_to_frac,
                            margin_to_pp_psi=bhp - pp_psi,
                            confidence=0.8,
                            notes="",
                        )

    if best_params is None:
        # No feasible solution found - return current parameters
        return OptimizedParameters(
            wob_klbs=25, rpm=120, flow_rate_gpm=650, sbp_psi=150,
            predicted_rop_fthr=0, predicted_ecd_ppg=window.current_ecd,
            predicted_bhp_psi=window.current_bhp,
            overbalance_psi=window.current_bhp - pp_psi,
            margin_to_frac_psi=fg_psi - window.current_bhp,
            margin_to_pp_psi=window.current_bhp - pp_psi,
            confidence=0.0,
            notes="No feasible solution within constraints. Widen parameters or adjust mud weight.",
        )

    # Assess confidence based on margins
    margin_ratio = min(
        best_params.margin_to_pp_psi / max(safety_psi, 1),
        best_params.margin_to_frac_psi / max(safety_psi, 1),
    )
    best_params.confidence = min(1.0, 0.5 + 0.5 * min(margin_ratio, 1.0))

    # Generate notes
    notes = []
    if best_params.overbalance_psi < 100:
        notes.append("Near-balance operation - maximum ROP benefit from reduced chip hold-down.")
    if best_params.margin_to_frac_psi < safety_psi * 2:
        notes.append("Tight margin to fracture gradient - monitor ECD closely during connections.")
    if best_params.wob_klbs > 35:
        notes.append("High WOB recommended - verify BHA and directional stability.")
    if best_params.rpm > 160:
        notes.append("High RPM - monitor vibrations and stick-slip.")
    best_params.notes = " ".join(notes)

    return best_params


def plan_connection(
    window: DrillingWindow,
    afp_loss_psi: float = 250.0,
    swab_margin_psi: float = 50.0,
    ramp_time_sec: float = 30.0,
) -> ConnectionPlan:
    """Generate SBP management plan for a pipe connection.

    During connections:
    1. Pumps stop → AFP drops → BHP drops by AFP amount
    2. Must increase SBP to compensate for AFP loss
    3. Pipe movement during connection causes swab (pulling) or surge (running)
    4. Must maintain BHP > PP throughout

    This is the core of CBHP (Constant Bottom Hole Pressure) MPD.
    """
    pp_psi = 0.052 * window.pore_pressure_ppg * window.tvd
    fg_psi = 0.052 * window.fracture_gradient_ppg * window.tvd

    # Current circulating BHP
    circulating_bhp = window.current_bhp

    # When pumps stop, BHP drops by AFP
    static_bhp_without_sbp = circulating_bhp - afp_loss_psi - window.current_sbp

    # Need SBP to compensate: target same BHP as when circulating
    target_bhp = circulating_bhp
    required_static_sbp = target_bhp - static_bhp_without_sbp

    # Clamp SBP to safe limits
    max_sbp = (fg_psi - static_bhp_without_sbp) * 0.95  # 5% safety
    min_sbp = (pp_psi + swab_margin_psi) - static_bhp_without_sbp

    static_sbp = np.clip(required_static_sbp, max(min_sbp, 0), max_sbp)

    bhp_during = static_bhp_without_sbp + static_sbp

    return ConnectionPlan(
        pre_connection_sbp=window.current_sbp,
        static_sbp=static_sbp,
        post_connection_sbp=window.current_sbp,  # return to circulating SBP
        afp_loss=afp_loss_psi,
        bhp_during_connection=bhp_during,
        swab_margin=swab_margin_psi,
        time_to_adjust=ramp_time_sec,
    )


def sensitivity_analysis(
    window: DrillingWindow,
    parameter: str = "wob",
    n_points: int = 20,
    bit_diameter_in: float = 8.75,
) -> dict:
    """Run sensitivity analysis on a single parameter.

    Returns dict with arrays of parameter values and corresponding ROP/BHP.
    """
    pp_psi = 0.052 * window.pore_pressure_ppg * window.tvd

    if parameter == "wob":
        values = np.linspace(10, 45, n_points)
        rops = [calculate_rop_model(w, 120, window.current_bhp - pp_psi, bit_diameter_in)
                for w in values]
        return {"parameter": "WOB (klbs)", "values": values, "rop": np.array(rops)}

    elif parameter == "rpm":
        values = np.linspace(60, 200, n_points)
        rops = [calculate_rop_model(25, r, window.current_bhp - pp_psi, bit_diameter_in)
                for r in values]
        return {"parameter": "RPM", "values": values, "rop": np.array(rops)}

    elif parameter == "overbalance":
        values = np.linspace(0, 1000, n_points)
        rops = [calculate_rop_model(25, 120, ob, bit_diameter_in) for ob in values]
        return {"parameter": "Overbalance (psi)", "values": values, "rop": np.array(rops)}

    elif parameter == "mud_weight":
        values = np.linspace(9, 15, n_points)
        rops = []
        for mw in values:
            bhp = 0.052 * mw * window.tvd + window.current_sbp
            ob = bhp - pp_psi
            rops.append(calculate_rop_model(25, 120, ob, bit_diameter_in))
        return {"parameter": "Mud Weight (ppg)", "values": values, "rop": np.array(rops)}

    return {"parameter": parameter, "values": np.array([]), "rop": np.array([])}
