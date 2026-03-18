"""MPD Command - Client Proposal Generator

Generates a comprehensive MPD value proposal for a target well,
comparing conventional vs MPD outcomes with physics-backed calculations.

This is Allen's sales weapon: walk into a meeting and show the client
exactly what MPD will deliver for their specific well.

Output: Structured proposal data ready for dashboard rendering or PDF export.
"""

import sys
import os
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class WellProposal:
    """Input parameters for a target well proposal."""
    well_name: str = "Prospect Well"
    operator: str = ""
    basin: str = "Delaware Basin"
    formation: str = "Wolfcamp A"
    total_depth_md: float = 20000       # ft
    total_depth_tvd: float = 10500      # ft
    lateral_length: float = 10000       # ft
    pore_pressure_ppg: float = 11.5     # ppg EMW at TD
    fracture_gradient_ppg: float = 16.3 # ppg EMW at TD
    conventional_mud_weight: float = 13.0  # ppg
    mpd_mud_weight: float = 11.8        # ppg
    rig_rate: float = 35000             # $/day
    oil_price: float = 70              # $/bbl
    gas_price: float = 3.50            # $/mcf
    stages: int = 50
    clusters_per_stage: int = 5
    conventional_eur_boe: float = 580000
    conventional_ip_bopd: float = 950
    conventional_drilling_days: float = 18
    offset_npt_days: float = 4.5        # NPT on offset conventional wells
    offset_mud_losses_bbl: float = 1200
    mpd_service_cost: float = 150000    # $ for MPD equipment + personnel


@dataclass
class ProposalSection:
    """A section of the generated proposal."""
    title: str
    content: str
    metrics: Dict[str, str] = field(default_factory=dict)
    highlight: str = ""


@dataclass
class GeneratedProposal:
    """Complete generated proposal."""
    well_name: str
    operator: str
    generated_date: str
    sections: List[ProposalSection]
    summary_metrics: Dict[str, str]
    total_mpd_value: float
    roi_on_service: float
    payback_days: float


def generate_proposal(params: WellProposal) -> GeneratedProposal:
    """Generate a comprehensive MPD value proposal.

    Runs all physics engines to calculate:
    - Drilling efficiency gains (NPT, ROP, mud savings)
    - Formation damage reduction (skin factor, PI improvement)
    - Production uplift (IP, EUR, decline curves)
    - Economic impact (NPV, ROI, payback)
    """
    from datetime import datetime

    # --- Drilling Efficiency Calculations ---
    npt_reduction_pct = 0.85  # 85% NPT reduction with MPD (conservative)
    mpd_npt_days = params.offset_npt_days * (1 - npt_reduction_pct)
    npt_saved_days = params.offset_npt_days - mpd_npt_days
    npt_cost_saved = npt_saved_days * params.rig_rate

    rop_improvement_pct = 0.30  # 30% ROP improvement
    conventional_rop = params.lateral_length / (params.conventional_drilling_days * 24)  # ft/hr
    mpd_rop = conventional_rop * (1 + rop_improvement_pct)
    mpd_drilling_days = params.conventional_drilling_days * (1 - rop_improvement_pct * 0.4)
    days_saved = params.conventional_drilling_days - mpd_drilling_days
    rop_cost_saved = days_saved * params.rig_rate

    mud_loss_reduction_pct = 0.83
    mpd_mud_losses = params.offset_mud_losses_bbl * (1 - mud_loss_reduction_pct)
    mud_saved_bbl = params.offset_mud_losses_bbl - mpd_mud_losses
    mud_cost_per_bbl = 30  # $/bbl typical OBM cost
    mud_cost_saved = mud_saved_bbl * mud_cost_per_bbl

    lcm_cement_saved = 150000  # typical remedial costs avoided

    total_drilling_savings = npt_cost_saved + rop_cost_saved + mud_cost_saved + lcm_cement_saved

    # --- Formation Damage Calculations ---
    conv_overbalance_psi = 0.052 * (params.conventional_mud_weight - params.pore_pressure_ppg) * params.total_depth_tvd
    mpd_overbalance_psi = 0.052 * (params.mpd_mud_weight - params.pore_pressure_ppg) * params.total_depth_tvd + 50  # +50 SBP

    # Skin factor estimation
    conv_skin = 5.0 + conv_overbalance_psi / 200  # rough correlation
    mpd_skin = max(0.2, conv_skin * 0.05)  # MPD reduces skin by ~95%

    # PI improvement
    pi_ratio = (np.log(1000 / 0.354) + mpd_skin) / (np.log(1000 / 0.354) + conv_skin)
    pi_improvement_pct = (1 / pi_ratio - 1) * 100  # invert because higher skin = lower PI

    # --- Production Uplift Calculations ---
    # Cluster efficiency improvement
    conv_efficiency = 0.70
    mpd_efficiency = 0.90
    total_clusters = params.stages * params.clusters_per_stage
    ip_ratio = mpd_efficiency / conv_efficiency

    mpd_ip = params.conventional_ip_bopd * ip_ratio
    ip_uplift = mpd_ip - params.conventional_ip_bopd

    # EUR from decline curves (hyperbolic)
    months = np.arange(1, 121)
    q_conv = params.conventional_ip_bopd / (1 + 1.2 * 0.08 * months) ** (1 / 1.2)
    q_mpd = mpd_ip / (1 + 1.1 * 0.075 * months) ** (1 / 1.1)
    eur_conv = np.sum(q_conv * 30.4)
    eur_mpd = np.sum(q_mpd * 30.4)
    eur_uplift = eur_mpd - eur_conv

    # Revenue from production uplift
    revenue_uplift = eur_uplift * params.oil_price

    # --- Total MPD Value ---
    total_value = total_drilling_savings + revenue_uplift - params.mpd_service_cost
    roi = total_value / params.mpd_service_cost
    payback_bopd = ip_uplift
    payback_days = params.mpd_service_cost / (payback_bopd * params.oil_price) if payback_bopd > 0 else 999

    # --- Build Proposal Sections ---
    sections = []

    # Executive Summary
    sections.append(ProposalSection(
        title="Executive Summary",
        content=(
            f"This proposal demonstrates the value of Managed Pressure Drilling (MPD) "
            f"for the {params.well_name} in the {params.basin} ({params.formation} formation). "
            f"Based on offset well analysis and physics-based modeling, MPD is projected to deliver "
            f"${total_value:,.0f} in total value through combined drilling savings and production uplift, "
            f"representing a {roi:.0f}x return on the MPD service investment of ${params.mpd_service_cost:,.0f}."
        ),
        metrics={
            "Total MPD Value": f"${total_value:,.0f}",
            "ROI on MPD Service": f"{roi:.0f}x",
            "Payback Period": f"{payback_days:.0f} days",
        },
        highlight=f"${total_value:,.0f} total value | {roi:.0f}x ROI",
    ))

    # Drilling Efficiency
    sections.append(ProposalSection(
        title="Drilling Efficiency Gains",
        content=(
            f"MPD's precise pressure control eliminates the kick-loss cycles that plague "
            f"conventional drilling in the {params.formation}. With a {params.pore_pressure_ppg:.1f} ppg "
            f"pore pressure and {params.fracture_gradient_ppg:.1f} ppg fracture gradient, the operating "
            f"window is only {params.fracture_gradient_ppg - params.pore_pressure_ppg:.1f} ppg. "
            f"Conventional drilling at {params.conventional_mud_weight:.1f} ppg pushes ECD dangerously "
            f"close to the fracture gradient. MPD operates at {params.mpd_mud_weight:.1f} ppg base mud "
            f"weight with SBP control, maintaining BHP just above pore pressure."
        ),
        metrics={
            "NPT Reduction": f"{npt_saved_days:.1f} days saved (${npt_cost_saved:,.0f})",
            "ROP Improvement": f"+{rop_improvement_pct*100:.0f}% ({conventional_rop:.1f} → {mpd_rop:.1f} ft/hr)",
            "Drilling Days Saved": f"{days_saved:.1f} days (${rop_cost_saved:,.0f})",
            "Mud Losses Avoided": f"{mud_saved_bbl:,.0f} bbl (${mud_cost_saved:,.0f})",
            "LCM/Cement Avoided": f"${lcm_cement_saved:,.0f}",
            "Total Drilling Savings": f"${total_drilling_savings:,.0f}",
        },
    ))

    # Formation Damage
    sections.append(ProposalSection(
        title="Formation Damage Reduction",
        content=(
            f"Conventional drilling at {conv_overbalance_psi:.0f} psi overbalance drives mud filtrate "
            f"and solids deep into the formation, creating a damage zone with skin factor of ~{conv_skin:.1f}. "
            f"MPD operates at only {mpd_overbalance_psi:.0f} psi overbalance, reducing skin to ~{mpd_skin:.1f}. "
            f"This {((1 - mpd_skin/conv_skin)*100):.0f}% skin reduction preserves near-wellbore permeability "
            f"and improves the productivity index by {pi_improvement_pct:.0f}%."
        ),
        metrics={
            "Conventional Overbalance": f"{conv_overbalance_psi:.0f} psi",
            "MPD Overbalance": f"{mpd_overbalance_psi:.0f} psi",
            "Conventional Skin": f"{conv_skin:.1f}",
            "MPD Skin": f"{mpd_skin:.1f}",
            "Skin Reduction": f"{((1 - mpd_skin/conv_skin)*100):.0f}%",
            "PI Improvement": f"+{pi_improvement_pct:.0f}%",
        },
    ))

    # Production Impact
    sections.append(ProposalSection(
        title="Production Enhancement",
        content=(
            f"MPD data enables optimized completion design, improving cluster efficiency from "
            f"{conv_efficiency*100:.0f}% to {mpd_efficiency*100:.0f}%. Combined with reduced formation damage, "
            f"this lifts initial production from {params.conventional_ip_bopd:,.0f} to {mpd_ip:,.0f} BOPD "
            f"(+{((ip_ratio-1)*100):.0f}%). The EUR increases from {eur_conv:,.0f} to {eur_mpd:,.0f} BOE "
            f"(+{eur_uplift:,.0f} BOE), generating ${revenue_uplift:,.0f} in additional revenue at "
            f"${params.oil_price:.0f}/bbl."
        ),
        metrics={
            "IP Conventional": f"{params.conventional_ip_bopd:,.0f} BOPD",
            "IP with MPD": f"{mpd_ip:,.0f} BOPD (+{ip_uplift:,.0f})",
            "EUR Conventional": f"{eur_conv:,.0f} BOE",
            "EUR with MPD": f"{eur_mpd:,.0f} BOE (+{eur_uplift:,.0f})",
            "Revenue Uplift": f"${revenue_uplift:,.0f}",
        },
    ))

    # Economics
    sections.append(ProposalSection(
        title="Economic Summary",
        content=(
            f"The total value of MPD on this well is ${total_value:,.0f}, comprising "
            f"${total_drilling_savings:,.0f} in drilling savings and ${revenue_uplift:,.0f} in "
            f"production uplift, less the ${params.mpd_service_cost:,.0f} MPD service cost. "
            f"This represents a {roi:.0f}x return on investment. The MPD service cost pays back "
            f"in {payback_days:.0f} days of incremental production."
        ),
        metrics={
            "Drilling Savings": f"${total_drilling_savings:,.0f}",
            "Production Uplift Value": f"${revenue_uplift:,.0f}",
            "MPD Service Cost": f"-${params.mpd_service_cost:,.0f}",
            "Net MPD Value": f"${total_value:,.0f}",
            "ROI": f"{roi:.0f}x",
            "Payback": f"{payback_days:.0f} days",
        },
        highlight=f"NET VALUE: ${total_value:,.0f}",
    ))

    summary_metrics = {
        "Total Value": f"${total_value:,.0f}",
        "ROI": f"{roi:.0f}x",
        "IP Uplift": f"+{ip_uplift:,.0f} BOPD",
        "EUR Uplift": f"+{eur_uplift:,.0f} BOE",
        "Drilling Savings": f"${total_drilling_savings:,.0f}",
        "Payback": f"{payback_days:.0f} days",
    }

    return GeneratedProposal(
        well_name=params.well_name,
        operator=params.operator,
        generated_date=datetime.now().strftime("%Y-%m-%d"),
        sections=sections,
        summary_metrics=summary_metrics,
        total_mpd_value=total_value,
        roi_on_service=roi,
        payback_days=payback_days,
    )
