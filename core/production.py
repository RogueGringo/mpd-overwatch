"""
Production Impact Calculation Module — MPD Command
====================================================
Quantifies the production and economic uplift from MPD‑enhanced drilling
compared to conventional overbalanced drilling.

Models:
  - EUR by segment (OOIP × recovery factor per segment)
  - Initial Production (IP) from cluster efficiency
  - Decline curve analysis (exponential & hyperbolic)
  - EUR uplift from MPD
  - NPV comparison (conventional vs MPD well)
  - Cost savings calculator (NPT, mud loss, casing, ROP)
  - Value summary generator

Default values calibrated for Delaware Basin Wolfcamp horizontal wells.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


# ============================================================================
# Data classes — inputs
# ============================================================================

@dataclass
class WellSegment:
    """One completion segment (stage) of a horizontal well."""
    length_ft: float = 200.0          # Segment (stage) length, ft
    porosity: float = 0.07            # Porosity, fraction
    thickness_ft: float = 200.0       # Net pay, ft
    area_acres: float = 40.0          # Drainage area per segment, acres
    Sw: float = 0.30                  # Water saturation, fraction
    So: float = 0.55                  # Oil saturation, fraction
    Bo: float = 1.35                  # Oil FVF, RB/STB
    recovery_factor_base: float = 0.06   # Base (conventional) RF
    recovery_factor_mpd: float = 0.09    # MPD‑enhanced RF


@dataclass
class WellDesign:
    """Overall well completion design."""
    n_stages: int = 40                    # Number of frac stages
    clusters_per_stage: int = 5           # Perforation clusters per stage
    cluster_spacing_ft: float = 40.0      # Cluster spacing, ft
    lateral_length_ft: float = 10000.0    # Total lateral length, ft
    segments: List[WellSegment] = field(default_factory=list)

    def __post_init__(self):
        if not self.segments:
            # Build uniform segments from stage count
            seg_len = self.lateral_length_ft / self.n_stages
            self.segments = [
                WellSegment(length_ft=seg_len)
                for _ in range(self.n_stages)
            ]


@dataclass
class ClusterEfficiency:
    """Cluster efficiency parameters."""
    base_efficiency: float = 0.55         # Conventional: ~55% clusters contributing
    mpd_efficiency: float = 0.80          # MPD: ~80% clusters contributing
    q_avg_per_cluster_bopd: float = 8.0   # Average rate per contributing cluster, BOPD


@dataclass
class DeclineParameters:
    """Decline curve parameters."""
    qi_bopd: float = 1200.0              # Initial rate, BOPD
    Di_annual: float = 0.80              # Initial nominal decline rate, 1/yr
    b_factor: float = 1.2                # Hyperbolic b‑factor (Wolfcamp ~1.0–1.4)
    economic_limit_bopd: float = 5.0     # Economic limit, BOPD
    forecast_months: int = 360           # 30‑year forecast


@dataclass
class EconomicInputs:
    """Economic parameters for NPV calculation."""
    oil_price_per_bbl: float = 72.0      # $/bbl WTI
    gas_price_per_mcf: float = 3.50      # $/Mcf  (if GOR used)
    gor_scf_per_bbl: float = 2500.0      # Gas‑oil ratio
    nri: float = 0.80                    # Net revenue interest
    opex_per_bbl: float = 12.0           # Lifting cost $/BOE
    fixed_opex_per_month: float = 15000.0  # Fixed monthly operating cost, $
    discount_rate_annual: float = 0.10   # Annual discount rate
    well_cost_conventional: float = 9_500_000.0   # D&C cost, conventional, $
    well_cost_mpd: float = 9_500_000.0            # D&C cost, MPD (before service adder)
    mpd_service_cost: float = 350_000.0           # MPD service adder, $
    tax_rate: float = 0.07               # Severance + ad valorem combined


@dataclass
class CostSavingsInputs:
    """Inputs for drilling cost savings from MPD."""
    rig_rate_per_day: float = 35_000.0       # Daily rig rate, $
    npt_hours_saved: float = 72.0            # Non‑productive time eliminated, hours
    mud_loss_bbl_saved: float = 500.0        # Mud losses avoided, bbl
    mud_cost_per_bbl: float = 120.0          # Weighted mud cost, $/bbl
    lcm_cement_savings: float = 45_000.0     # LCM & remedial cement saved, $
    casing_string_eliminated: bool = False   # Did MPD allow eliminating a string?
    casing_string_cost: float = 250_000.0    # Cost of eliminated casing string, $
    rop_improvement_pct: float = 15.0        # ROP improvement, % (faster drilling)
    base_drill_days: float = 18.0            # Conventional drilling days for lateral
    spread_rate_per_day: float = 55_000.0    # Total daily spread cost, $


# ============================================================================
# Data classes — outputs
# ============================================================================

@dataclass
class EURResult:
    """EUR calculation results."""
    ooip_per_segment_bbl: np.ndarray       # OOIP for each segment
    eur_per_segment_bbl: np.ndarray        # EUR for each segment
    eur_total_bbl: float                   # Sum of segment EURs
    ooip_total_bbl: float                  # Sum of segment OOIPs
    recovery_factor_avg: float             # Weighted average RF


@dataclass
class IPResult:
    """Initial production results."""
    total_clusters: int
    contributing_clusters: float
    ip_bopd: float
    cluster_efficiency: float


@dataclass
class DeclineForecast:
    """Monthly decline curve forecast."""
    months: np.ndarray                     # Month indices (0, 1, 2, …)
    rate_bopd: np.ndarray                  # Oil rate per month, BOPD
    cumulative_bbl: np.ndarray             # Cumulative oil, bbl
    eur_bbl: float                         # EUR (to econ limit or end of forecast)
    economic_life_months: int              # Months until econ limit


@dataclass
class NPVResult:
    """NPV comparison."""
    npv_conventional: float
    npv_mpd: float
    npv_delta: float                       # MPD − Conventional
    irr_conventional: Optional[float] = None
    irr_mpd: Optional[float] = None
    monthly_cashflow_conv: Optional[np.ndarray] = None
    monthly_cashflow_mpd: Optional[np.ndarray] = None


@dataclass
class CostSavingsResult:
    """Drilling cost savings breakdown."""
    npt_savings: float
    mud_loss_savings: float
    lcm_cement_savings: float
    casing_savings: float
    rop_savings: float
    total_drilling_savings: float


@dataclass
class ValueSummary:
    """Total value of MPD = drilling savings + production uplift."""
    drilling_savings: CostSavingsResult
    eur_uplift_bbl: float
    eur_uplift_value: float                # eur_uplift × oil_price × NRI
    ip_uplift_bopd: float
    npv_uplift: float
    total_mpd_value: float                 # drilling savings + NPV uplift
    components: Dict[str, float] = field(default_factory=dict)


# ============================================================================
# 1.  EUR Calculation by Segment
# ============================================================================

def calculate_ooip_segment(seg: WellSegment) -> float:
    """
    Original oil in place for one segment.

    OOIP = (7758 × A × h × φ × So) / Bo

    7758 = acre‑ft → bbl conversion factor.
    """
    return (7758.0 * seg.area_acres * seg.thickness_ft
            * seg.porosity * seg.So) / seg.Bo


def calculate_eur_by_segment(
    well: Optional[WellDesign] = None,
    use_mpd: bool = False,
) -> EURResult:
    """
    EUR_well = Σ(V_i × f_i) for N segments.

    Parameters
    ----------
    well    : WellDesign (defaults to Wolfcamp horizontal)
    use_mpd : bool — if True, use MPD recovery factors

    Returns
    -------
    EURResult
    """
    if well is None:
        well = WellDesign()

    n = len(well.segments)
    ooip = np.zeros(n)
    eur = np.zeros(n)

    for i, seg in enumerate(well.segments):
        ooip[i] = calculate_ooip_segment(seg)
        rf = seg.recovery_factor_mpd if use_mpd else seg.recovery_factor_base
        eur[i] = ooip[i] * rf

    ooip_total = float(np.sum(ooip))
    eur_total = float(np.sum(eur))
    rf_avg = eur_total / ooip_total if ooip_total > 0 else 0.0

    return EURResult(
        ooip_per_segment_bbl=ooip,
        eur_per_segment_bbl=eur,
        eur_total_bbl=eur_total,
        ooip_total_bbl=ooip_total,
        recovery_factor_avg=rf_avg,
    )


# ============================================================================
# 2.  Initial Production (IP) from Cluster Efficiency
# ============================================================================

def calculate_ip(
    well: Optional[WellDesign] = None,
    cluster_eff: Optional[ClusterEfficiency] = None,
    use_mpd: bool = False,
) -> IPResult:
    """
    IP = N_clusters × q_avg × cluster_efficiency

    Parameters
    ----------
    well        : WellDesign
    cluster_eff : ClusterEfficiency
    use_mpd     : bool

    Returns
    -------
    IPResult
    """
    if well is None:
        well = WellDesign()
    if cluster_eff is None:
        cluster_eff = ClusterEfficiency()

    total_clusters = well.n_stages * well.clusters_per_stage
    eff = cluster_eff.mpd_efficiency if use_mpd else cluster_eff.base_efficiency
    contributing = total_clusters * eff
    ip = contributing * cluster_eff.q_avg_per_cluster_bopd

    return IPResult(
        total_clusters=total_clusters,
        contributing_clusters=contributing,
        ip_bopd=ip,
        cluster_efficiency=eff,
    )


# ============================================================================
# 3.  Decline Curve Analysis
# ============================================================================

def decline_exponential(
    qi: float,
    Di_annual: float,
    months: np.ndarray,
) -> np.ndarray:
    """
    Exponential decline:  q(t) = qi × exp(−D × t)

    Parameters
    ----------
    qi        : Initial rate, BOPD.
    Di_annual : Nominal decline rate, 1/yr.
    months    : Array of month indices (0‑based).

    Returns
    -------
    np.ndarray : Rate at each month, BOPD.
    """
    t_years = months / 12.0
    return qi * np.exp(-Di_annual * t_years)


def decline_hyperbolic(
    qi: float,
    Di_annual: float,
    b: float,
    months: np.ndarray,
) -> np.ndarray:
    """
    Hyperbolic decline:  q(t) = qi / (1 + b × D × t)^(1/b)

    Parameters
    ----------
    qi        : Initial rate, BOPD.
    Di_annual : Nominal decline rate, 1/yr.
    b         : Hyperbolic exponent.
    months    : Array of month indices.

    Returns
    -------
    np.ndarray : Rate at each month, BOPD.
    """
    t_years = months / 12.0
    return qi / np.power(1.0 + b * Di_annual * t_years, 1.0 / b)


def forecast_decline(
    params: Optional[DeclineParameters] = None,
    model: str = "hyperbolic",
) -> DeclineForecast:
    """
    Generate a monthly decline forecast and compute EUR.

    Parameters
    ----------
    params : DeclineParameters
    model  : "exponential" or "hyperbolic"

    Returns
    -------
    DeclineForecast
    """
    if params is None:
        params = DeclineParameters()

    months = np.arange(0, params.forecast_months, dtype=float)

    if model == "exponential":
        rates = decline_exponential(params.qi_bopd, params.Di_annual, months)
    else:
        rates = decline_hyperbolic(params.qi_bopd, params.Di_annual,
                                   params.b_factor, months)

    # Find economic life
    above_limit = rates >= params.economic_limit_bopd
    if np.any(above_limit):
        econ_life = int(np.max(np.where(above_limit))) + 1
    else:
        econ_life = 1

    # Zero out rates below economic limit
    rates_clipped = np.where(rates >= params.economic_limit_bopd, rates, 0.0)

    # Cumulative production (trapezoidal, daily rates → monthly volumes)
    monthly_volume = rates_clipped * 30.4375  # avg days per month
    cumulative = np.cumsum(monthly_volume)

    eur = float(cumulative[econ_life - 1]) if econ_life > 0 else 0.0

    return DeclineForecast(
        months=months,
        rate_bopd=rates_clipped,
        cumulative_bbl=cumulative,
        eur_bbl=eur,
        economic_life_months=econ_life,
    )


# ============================================================================
# 4.  EUR Uplift from MPD
# ============================================================================

def calculate_eur_uplift(
    well: Optional[WellDesign] = None,
) -> Dict[str, float]:
    """
    ΔEUR = Σ(V_i × (f_i_MPD − f_i_base))

    Also computes sensitivity of qi/D to changes in qi and D:
        d(qi/D) = (1/D)dqi − (qi/D²)dD

    Returns
    -------
    dict with keys: delta_eur_bbl, eur_base_bbl, eur_mpd_bbl, uplift_pct,
                    sensitivity_dqi, sensitivity_dD
    """
    if well is None:
        well = WellDesign()

    eur_base = calculate_eur_by_segment(well, use_mpd=False)
    eur_mpd = calculate_eur_by_segment(well, use_mpd=True)
    delta = eur_mpd.eur_total_bbl - eur_base.eur_total_bbl
    uplift_pct = delta / eur_base.eur_total_bbl * 100.0 if eur_base.eur_total_bbl > 0 else 0.0

    # Sensitivity of qi/D characteristic
    # Reference decline params
    dp = DeclineParameters()
    qi = dp.qi_bopd
    D = dp.Di_annual
    sens_dqi = 1.0 / D           # d(qi/D)/dqi
    sens_dD = -qi / (D ** 2)     # d(qi/D)/dD

    return {
        "delta_eur_bbl": delta,
        "eur_base_bbl": eur_base.eur_total_bbl,
        "eur_mpd_bbl": eur_mpd.eur_total_bbl,
        "uplift_pct": uplift_pct,
        "sensitivity_dqi_over_dD_wrt_qi": sens_dqi,
        "sensitivity_dqi_over_dD_wrt_D": sens_dD,
    }


# ============================================================================
# 5.  NPV Calculator
# ============================================================================

def _monthly_cashflows(
    forecast: DeclineForecast,
    econ: EconomicInputs,
    capex: float,
) -> np.ndarray:
    """
    Compute monthly net cashflow array.

    Monthly revenue = oil_rate × 30.4375 × oil_price × NRI
                    + gas_revenue (from GOR)
                    − variable opex − fixed opex − taxes
    """
    days_per_month = 30.4375
    n = forecast.economic_life_months
    cf = np.zeros(n + 1)  # index 0 = time‑zero capex

    # Capex at time zero
    cf[0] = -capex

    for m in range(1, n + 1):
        if m - 1 >= len(forecast.rate_bopd):
            break
        q_oil = forecast.rate_bopd[m - 1]  # BOPD
        vol_oil = q_oil * days_per_month     # bbl/month
        vol_gas = vol_oil * econ.gor_scf_per_bbl / 1000.0  # Mcf/month

        gross_rev = (vol_oil * econ.oil_price_per_bbl
                     + vol_gas * econ.gas_price_per_mcf)
        net_rev = gross_rev * econ.nri

        taxes = net_rev * econ.tax_rate
        var_opex = vol_oil * econ.opex_per_bbl
        total_opex = var_opex + econ.fixed_opex_per_month

        cf[m] = net_rev - taxes - total_opex

    return cf


def _npv_from_cashflow(cf: np.ndarray, annual_rate: float) -> float:
    """Discount monthly cashflow array to present value."""
    monthly_rate = annual_rate / 12.0
    months = np.arange(len(cf), dtype=float)
    discount_factors = 1.0 / np.power(1.0 + monthly_rate, months)
    return float(np.sum(cf * discount_factors))


def calculate_npv(
    decline_conv: Optional[DeclineParameters] = None,
    decline_mpd: Optional[DeclineParameters] = None,
    econ: Optional[EconomicInputs] = None,
) -> NPVResult:
    """
    NPV = Σ (monthly_revenue − monthly_opex) / (1 + r/12)^month

    Compare conventional well NPV vs MPD well NPV, including MPD service
    cost as additional capex.

    Parameters
    ----------
    decline_conv : DeclineParameters for conventional well.
    decline_mpd  : DeclineParameters for MPD well (higher qi, lower Di).
    econ         : EconomicInputs.

    Returns
    -------
    NPVResult
    """
    if decline_conv is None:
        decline_conv = DeclineParameters(qi_bopd=1000.0, Di_annual=0.85, b_factor=1.2)
    if decline_mpd is None:
        decline_mpd = DeclineParameters(qi_bopd=1300.0, Di_annual=0.75, b_factor=1.2)
    if econ is None:
        econ = EconomicInputs()

    fc_conv = forecast_decline(decline_conv, model="hyperbolic")
    fc_mpd = forecast_decline(decline_mpd, model="hyperbolic")

    capex_conv = econ.well_cost_conventional
    capex_mpd = econ.well_cost_mpd + econ.mpd_service_cost

    cf_conv = _monthly_cashflows(fc_conv, econ, capex_conv)
    cf_mpd = _monthly_cashflows(fc_mpd, econ, capex_mpd)

    npv_conv = _npv_from_cashflow(cf_conv, econ.discount_rate_annual)
    npv_mpd = _npv_from_cashflow(cf_mpd, econ.discount_rate_annual)

    return NPVResult(
        npv_conventional=npv_conv,
        npv_mpd=npv_mpd,
        npv_delta=npv_mpd - npv_conv,
        monthly_cashflow_conv=cf_conv,
        monthly_cashflow_mpd=cf_mpd,
    )


# ============================================================================
# 6.  Cost Savings Calculator
# ============================================================================

def calculate_cost_savings(
    inputs: Optional[CostSavingsInputs] = None,
) -> CostSavingsResult:
    """
    Drilling cost savings from MPD implementation.

    Components:
      - NPT reduction:   rig_rate × hours_saved / 24
      - Mud loss:         bbl_saved × $/bbl
      - LCM/cement:      lump sum
      - Casing string:    if eliminated
      - ROP improvement:  fewer drill days × spread rate

    Returns
    -------
    CostSavingsResult
    """
    if inputs is None:
        inputs = CostSavingsInputs()

    npt = inputs.rig_rate_per_day * (inputs.npt_hours_saved / 24.0)
    mud = inputs.mud_loss_bbl_saved * inputs.mud_cost_per_bbl
    lcm = inputs.lcm_cement_savings
    casing = inputs.casing_string_cost if inputs.casing_string_eliminated else 0.0

    # ROP improvement → fewer drill days
    days_saved = inputs.base_drill_days * (inputs.rop_improvement_pct / 100.0)
    rop = days_saved * inputs.spread_rate_per_day

    total = npt + mud + lcm + casing + rop

    return CostSavingsResult(
        npt_savings=npt,
        mud_loss_savings=mud,
        lcm_cement_savings=lcm,
        casing_savings=casing,
        rop_savings=rop,
        total_drilling_savings=total,
    )


# ============================================================================
# 7.  Value Summary Generator
# ============================================================================

def generate_value_summary(
    well: Optional[WellDesign] = None,
    cluster_eff: Optional[ClusterEfficiency] = None,
    decline_conv: Optional[DeclineParameters] = None,
    decline_mpd: Optional[DeclineParameters] = None,
    econ: Optional[EconomicInputs] = None,
    cost_inputs: Optional[CostSavingsInputs] = None,
) -> ValueSummary:
    """
    Total value of MPD = drilling savings + production uplift value.

    Aggregates all sub‑calculations into a single structured result.

    Returns
    -------
    ValueSummary
    """
    if econ is None:
        econ = EconomicInputs()

    # Drilling savings
    savings = calculate_cost_savings(cost_inputs)

    # EUR uplift
    eur_info = calculate_eur_uplift(well)
    eur_uplift_bbl = eur_info["delta_eur_bbl"]
    eur_uplift_value = eur_uplift_bbl * econ.oil_price_per_bbl * econ.nri

    # IP uplift
    ip_base = calculate_ip(well, cluster_eff, use_mpd=False)
    ip_mpd = calculate_ip(well, cluster_eff, use_mpd=True)
    ip_uplift = ip_mpd.ip_bopd - ip_base.ip_bopd

    # NPV comparison
    npv_result = calculate_npv(decline_conv, decline_mpd, econ)

    total_value = savings.total_drilling_savings + npv_result.npv_delta

    components = {
        "npt_savings": savings.npt_savings,
        "mud_loss_savings": savings.mud_loss_savings,
        "lcm_cement_savings": savings.lcm_cement_savings,
        "casing_savings": savings.casing_savings,
        "rop_savings": savings.rop_savings,
        "total_drilling_savings": savings.total_drilling_savings,
        "eur_base_bbl": eur_info["eur_base_bbl"],
        "eur_mpd_bbl": eur_info["eur_mpd_bbl"],
        "eur_uplift_bbl": eur_uplift_bbl,
        "eur_uplift_pct": eur_info["uplift_pct"],
        "eur_uplift_value_usd": eur_uplift_value,
        "ip_base_bopd": ip_base.ip_bopd,
        "ip_mpd_bopd": ip_mpd.ip_bopd,
        "ip_uplift_bopd": ip_uplift,
        "npv_conventional": npv_result.npv_conventional,
        "npv_mpd": npv_result.npv_mpd,
        "npv_delta": npv_result.npv_delta,
        "mpd_service_cost": econ.mpd_service_cost,
        "total_mpd_value": total_value,
    }

    return ValueSummary(
        drilling_savings=savings,
        eur_uplift_bbl=eur_uplift_bbl,
        eur_uplift_value=eur_uplift_value,
        ip_uplift_bopd=ip_uplift,
        npv_uplift=npv_result.npv_delta,
        total_mpd_value=total_value,
        components=components,
    )


# ============================================================================
# Pretty‑print utilities
# ============================================================================

def print_value_summary(vs: ValueSummary) -> str:
    """Return a formatted string of the full MPD value summary."""
    lines: List[str] = []
    lines.append("=" * 78)
    lines.append("  MPD VALUE SUMMARY -- Delaware Basin Wolfcamp Horizontal Well")
    lines.append("=" * 78)

    lines.append("")
    lines.append("  DRILLING COST SAVINGS")
    lines.append("  " + "-" * 50)
    ds = vs.drilling_savings
    lines.append(f"    NPT reduction savings:       ${ds.npt_savings:>14,.0f}")
    lines.append(f"    Mud loss reduction:           ${ds.mud_loss_savings:>14,.0f}")
    lines.append(f"    LCM / cement savings:         ${ds.lcm_cement_savings:>14,.0f}")
    lines.append(f"    Casing string elimination:    ${ds.casing_savings:>14,.0f}")
    lines.append(f"    ROP improvement savings:      ${ds.rop_savings:>14,.0f}")
    lines.append(f"    ---------------------------------------------------")
    lines.append(f"    TOTAL DRILLING SAVINGS:       ${ds.total_drilling_savings:>14,.0f}")

    lines.append("")
    lines.append("  PRODUCTION UPLIFT")
    lines.append("  " + "-" * 50)
    c = vs.components
    lines.append(f"    EUR Base (conventional):       {c['eur_base_bbl']:>12,.0f} bbl")
    lines.append(f"    EUR MPD:                       {c['eur_mpd_bbl']:>12,.0f} bbl")
    lines.append(f"    EUR Uplift:                    {c['eur_uplift_bbl']:>12,.0f} bbl  ({c['eur_uplift_pct']:+.1f}%)")
    lines.append(f"    EUR Uplift Value (NRI):       ${c['eur_uplift_value_usd']:>14,.0f}")
    lines.append(f"    IP Base:                       {c['ip_base_bopd']:>12,.0f} BOPD")
    lines.append(f"    IP MPD:                        {c['ip_mpd_bopd']:>12,.0f} BOPD")
    lines.append(f"    IP Uplift:                    +{c['ip_uplift_bopd']:>12,.0f} BOPD")

    lines.append("")
    lines.append("  NPV COMPARISON (10% discount rate)")
    lines.append("  " + "-" * 50)
    lines.append(f"    NPV Conventional:            ${c['npv_conventional']:>14,.0f}")
    lines.append(f"    NPV MPD:                     ${c['npv_mpd']:>14,.0f}")
    lines.append(f"    NPV Uplift (Delta):          ${c['npv_delta']:>14,.0f}")
    lines.append(f"    MPD Service Cost:            ${c['mpd_service_cost']:>14,.0f}")

    lines.append("")
    lines.append("  " + "=" * 54)
    lines.append(f"    TOTAL MPD VALUE:             ${vs.total_mpd_value:>14,.0f}")
    lines.append("  " + "=" * 54)
    lines.append("")

    return "\n".join(lines)


def print_decline_comparison(
    conv_params: Optional[DeclineParameters] = None,
    mpd_params: Optional[DeclineParameters] = None,
) -> str:
    """Print a side-by-side decline curve comparison."""
    if conv_params is None:
        conv_params = DeclineParameters(qi_bopd=1000.0, Di_annual=0.85, b_factor=1.2)
    if mpd_params is None:
        mpd_params = DeclineParameters(qi_bopd=1300.0, Di_annual=0.75, b_factor=1.2)

    fc_conv = forecast_decline(conv_params, model="hyperbolic")
    fc_mpd = forecast_decline(mpd_params, model="hyperbolic")

    lines: List[str] = []
    lines.append("=" * 70)
    lines.append("  DECLINE CURVE COMPARISON -- Hyperbolic Model")
    lines.append("=" * 70)
    lines.append(f"  {'':30s} {'Conventional':>16s} {'MPD':>16s}")
    lines.append(f"  {'-'*64}")
    lines.append(f"  {'Initial Rate (qi)':30s} {conv_params.qi_bopd:>14,.0f}   {mpd_params.qi_bopd:>14,.0f}  BOPD")
    lines.append(f"  {'Decline Rate (Di)':30s} {conv_params.Di_annual:>14.2f}   {mpd_params.Di_annual:>14.2f}  1/yr")
    lines.append(f"  {'b-factor':30s} {conv_params.b_factor:>14.2f}   {mpd_params.b_factor:>14.2f}")
    lines.append(f"  {'EUR':30s} {fc_conv.eur_bbl:>14,.0f}   {fc_mpd.eur_bbl:>14,.0f}  bbl")
    lines.append(f"  {'Economic Life':30s} {fc_conv.economic_life_months:>14,d}   {fc_mpd.economic_life_months:>14,d}  months")

    # Snapshot rates at key times
    for yr in [1, 2, 5, 10]:
        m = yr * 12
        if m < len(fc_conv.rate_bopd) and m < len(fc_mpd.rate_bopd):
            lines.append(
                f"  {'Rate @ Year ' + str(yr):30s} "
                f"{fc_conv.rate_bopd[m]:>14,.0f}   {fc_mpd.rate_bopd[m]:>14,.0f}  BOPD"
            )

    lines.append("=" * 70)
    return "\n".join(lines)


# ============================================================================
# Quick demo / self‑test
# ============================================================================

if __name__ == "__main__":
    print(print_decline_comparison())
    print()
    vs = generate_value_summary()
    print(print_value_summary(vs))
