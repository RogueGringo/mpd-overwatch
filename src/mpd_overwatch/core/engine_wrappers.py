"""Hydraulics Engine Wrappers
============================

Each function in this module calls an existing core hydraulics function
unchanged, then wraps the return value in an EngineeringResult that carries
method metadata, input provenance, validity envelope, and operational guidance.

The wrappers add no new computation — the core functions remain the single
source of truth for numeric results.
"""

from __future__ import annotations

from mpd_overwatch.core.hydraulics import (
    equivalent_circulating_density,
    hydrostatic_pressure,
    bottom_hole_pressure_static,
    bottom_hole_pressure_dynamic,
    annular_velocity,
)
from mpd_overwatch.core.engineering_result import (
    EngineeringResult,
    EngineeringInput,
    Method,
    Provenance,
)


def compute_ecd(
    mw: float,
    afp: float,
    tvd: float,
    mw_prov: Provenance = Provenance.MEASURED,
    afp_prov: Provenance = Provenance.MODELED,
    tvd_prov: Provenance = Provenance.SURVEY,
) -> EngineeringResult:
    """Equivalent Circulating Density wrapped as an EngineeringResult.

    Parameters
    ----------
    mw : float
        Mud weight (ppg).
    afp : float
        Annular friction pressure (psi).
    tvd : float
        True vertical depth (ft).
    mw_prov : Provenance
        Provenance tag for the mud weight input. Default MEASURED.
    afp_prov : Provenance
        Provenance tag for the AFP input. Default MODELED.
    tvd_prov : Provenance
        Provenance tag for the TVD input. Default SURVEY.

    Returns
    -------
    EngineeringResult
        ECD in ppg with full method and provenance metadata.
    """
    value = equivalent_circulating_density(mw, afp, tvd)
    return EngineeringResult(
        label="ECD",
        value=value,
        unit="ppg",
        provenance=Provenance.DERIVED,
        method=Method(
            name="Bourgoyne et al. Eq 4.72",
            reference="Applied Drilling Engineering, SPE Textbook Series Vol. 2",
            equation="MW + AFP / (0.052 × TVD)",
            novel=False,
        ),
        inputs=[
            EngineeringInput("MW", mw, "ppg", mw_prov),
            EngineeringInput("AFP", afp, "psi", afp_prov, source="Fanning friction"),
            EngineeringInput("TVD", tvd, "ft", tvd_prov, source="survey interpolation"),
        ],
        validity="Incompressible fluid, steady-state flow, concentric annulus.",
        cross_check="Compare to APWD if available; verify SPP trend.",
        sensitivity="±0.3 ppg per 100 psi AFP uncertainty. Dominant input: TVD accuracy.",
        implication=(
            "If approaching frac gradient, reduce flow rate or adjust choke backpressure."
        ),
    )


def compute_hydrostatic(
    mw: float,
    tvd: float,
    mw_prov: Provenance = Provenance.MEASURED,
    tvd_prov: Provenance = Provenance.SURVEY,
) -> EngineeringResult:
    """Hydrostatic pressure wrapped as an EngineeringResult.

    Parameters
    ----------
    mw : float
        Mud weight (ppg).
    tvd : float
        True vertical depth (ft).
    mw_prov : Provenance
        Provenance tag for the mud weight input. Default MEASURED.
    tvd_prov : Provenance
        Provenance tag for the TVD input. Default SURVEY.

    Returns
    -------
    EngineeringResult
        Hydrostatic pressure in psi with full method and provenance metadata.
    """
    value = hydrostatic_pressure(mw, tvd)
    return EngineeringResult(
        label="Hydrostatic",
        value=value,
        unit="psi",
        provenance=Provenance.DERIVED,
        method=Method(
            name="Hydrostatic gradient (oilfield)",
            reference="Applied Drilling Engineering, SPE Textbook Series Vol. 2",
            equation="P_h = 0.052 × MW × TVD",
            novel=False,
        ),
        inputs=[
            EngineeringInput("MW", mw, "ppg", mw_prov),
            EngineeringInput("TVD", tvd, "ft", tvd_prov, source="survey interpolation"),
        ],
        validity="Static fluid column; assumes uniform mud weight with depth.",
        cross_check="Verify MW density against retort or Coriolis meter readings.",
        sensitivity="±5.46 psi per 0.1 ppg MW change at 10,000 ft TVD.",
        implication=(
            "Baseline pressure component; all BHP calculations depend on this value."
        ),
    )


def compute_bhp_static(
    mw: float,
    tvd: float,
    sbp: float = 0.0,
    mw_prov: Provenance = Provenance.MEASURED,
    tvd_prov: Provenance = Provenance.SURVEY,
    sbp_prov: Provenance = Provenance.MEASURED,
) -> EngineeringResult:
    """Static bottom-hole pressure wrapped as an EngineeringResult.

    Parameters
    ----------
    mw : float
        Mud weight (ppg).
    tvd : float
        True vertical depth (ft).
    sbp : float
        Surface back-pressure applied via MPD choke (psi). Default 0.
    mw_prov : Provenance
        Provenance tag for the mud weight input. Default MEASURED.
    tvd_prov : Provenance
        Provenance tag for the TVD input. Default SURVEY.
    sbp_prov : Provenance
        Provenance tag for the SBP input. Default MEASURED.

    Returns
    -------
    EngineeringResult
        Static BHP in psi with full method and provenance metadata.
    """
    value = bottom_hole_pressure_static(mw, tvd, sbp)
    return EngineeringResult(
        label="BHP Static",
        value=value,
        unit="psi",
        provenance=Provenance.DERIVED,
        method=Method(
            name="Static BHP — hydrostatic plus surface backpressure",
            reference="Applied Drilling Engineering, SPE Textbook Series Vol. 2",
            equation="BHP_static = 0.052 × MW × TVD + SBP",
            novel=False,
        ),
        inputs=[
            EngineeringInput("MW", mw, "ppg", mw_prov),
            EngineeringInput("TVD", tvd, "ft", tvd_prov, source="survey interpolation"),
            EngineeringInput("SBP", sbp, "psi", sbp_prov, source="choke manifold gauge"),
        ],
        validity="Pumps off; assumes uniform mud weight with depth; no fluid movement.",
        cross_check=(
            "Compare against drillpipe pressure gauge when pumps are off; "
            "cross-reference SIDPP after well shut-in."
        ),
        sensitivity="Direct 1:1 sensitivity to SBP changes; ±5.46 psi per 0.1 ppg MW at 10,000 ft.",
        implication=(
            "Must remain above pore pressure at all times to prevent influx; "
            "SBP is the MPD tool for fine-tuning this margin during connections."
        ),
    )


def compute_bhp_dynamic(
    mw: float,
    tvd: float,
    afp: float,
    sbp: float = 0.0,
    mw_prov: Provenance = Provenance.MEASURED,
    tvd_prov: Provenance = Provenance.SURVEY,
    afp_prov: Provenance = Provenance.MODELED,
    sbp_prov: Provenance = Provenance.MEASURED,
) -> EngineeringResult:
    """Dynamic bottom-hole pressure wrapped as an EngineeringResult.

    Parameters
    ----------
    mw : float
        Mud weight (ppg).
    tvd : float
        True vertical depth (ft).
    afp : float
        Total annular friction pressure (psi).
    sbp : float
        Surface back-pressure (psi). Default 0.
    mw_prov : Provenance
        Provenance tag for the mud weight input. Default MEASURED.
    tvd_prov : Provenance
        Provenance tag for the TVD input. Default SURVEY.
    afp_prov : Provenance
        Provenance tag for the AFP input. Default MODELED.
    sbp_prov : Provenance
        Provenance tag for the SBP input. Default MEASURED.

    Returns
    -------
    EngineeringResult
        Dynamic BHP in psi with full method and provenance metadata.
    """
    value = bottom_hole_pressure_dynamic(mw, tvd, afp, sbp)
    return EngineeringResult(
        label="BHP Dynamic",
        value=value,
        unit="psi",
        provenance=Provenance.DERIVED,
        method=Method(
            name="Dynamic BHP — hydrostatic plus AFP plus surface backpressure",
            reference="Applied Drilling Engineering, SPE Textbook Series Vol. 2",
            equation="BHP_dynamic = 0.052 × MW × TVD + AFP + SBP",
            novel=False,
        ),
        inputs=[
            EngineeringInput("MW", mw, "ppg", mw_prov),
            EngineeringInput("TVD", tvd, "ft", tvd_prov, source="survey interpolation"),
            EngineeringInput("AFP", afp, "psi", afp_prov, source="Bingham Plastic model"),
            EngineeringInput("SBP", sbp, "psi", sbp_prov, source="choke manifold gauge"),
        ],
        validity=(
            "Pumps on; Bingham Plastic fluid model; steady-state annular flow; "
            "concentric annulus assumed."
        ),
        cross_check=(
            "Compare ECD trend against APWD sensor; "
            "monitor SPP for changes indicating hole-condition anomalies."
        ),
        sensitivity=(
            "AFP is the primary dynamic variable; "
            "±100 psi AFP shifts BHP by 100 psi and ECD by ~0.18 ppg at 10,000 ft."
        ),
        implication=(
            "Must remain below fracture pressure while circulating; "
            "reduce flow rate or increase MW density offset with lower SBP if ECD is high."
        ),
    )


def compute_annular_velocity(
    q: float,
    d_hole: float,
    d_pipe: float,
    q_prov: Provenance = Provenance.MEASURED,
    d_hole_prov: Provenance = Provenance.MEASURED,
    d_pipe_prov: Provenance = Provenance.MEASURED,
) -> EngineeringResult:
    """Annular velocity wrapped as an EngineeringResult.

    Parameters
    ----------
    q : float
        Flow rate (gpm).
    d_hole : float
        Hole / casing inside diameter (in).
    d_pipe : float
        Pipe outside diameter (in).
    q_prov : Provenance
        Provenance tag for the flow rate input. Default MEASURED.
    d_hole_prov : Provenance
        Provenance tag for the hole diameter input. Default MEASURED.
    d_pipe_prov : Provenance
        Provenance tag for the pipe OD input. Default MEASURED.

    Returns
    -------
    EngineeringResult
        Annular velocity in ft/min with full method and provenance metadata.
    """
    value = annular_velocity(q, d_hole, d_pipe)
    return EngineeringResult(
        label="Annular Velocity",
        value=value,
        unit="ft/min",
        provenance=Provenance.DERIVED,
        method=Method(
            name="Annular velocity from flow rate and annular area",
            reference="Applied Drilling Engineering, SPE Textbook Series Vol. 2",
            equation="V = 24.5 × Q / (D_hole² − D_pipe²)",
            novel=False,
        ),
        inputs=[
            EngineeringInput("Q", q, "gpm", q_prov, source="flow meter"),
            EngineeringInput("D_hole", d_hole, "in", d_hole_prov, source="bit/casing record"),
            EngineeringInput("D_pipe", d_pipe, "in", d_pipe_prov, source="drill-string tally"),
        ],
        validity="Incompressible fluid; uniform diameter annular section.",
        cross_check=(
            "Verify against pump stroke count and liner efficiency; "
            "compare to cuttings transport minimum velocity (~100 ft/min for vertical wells)."
        ),
        sensitivity=(
            "Linear with Q; changes inversely with annular cross-section area. "
            "Small OD errors amplify quickly in tight annuli."
        ),
        implication=(
            "Must exceed minimum transport velocity to prevent cuttings bed buildup; "
            "high AV increases AFP and ECD — balance hole-cleaning against fracture risk."
        ),
    )
