"""Engine Wrappers
=================

Each function in this module calls an existing core function unchanged, then
wraps the return value in an EngineeringResult that carries method metadata,
input provenance, validity envelope, and operational guidance.

The wrappers add no new computation — the core functions remain the single
source of truth for numeric results.

Modules covered:
  - hydraulics      : ECD, hydrostatic, BHP static/dynamic, annular velocity
  - geomechanics    : MSE, UCS, brittleness
  - pore_pressure   : d-exponent, Eaton pore pressure
  - formation_damage: skin factor, productivity index
"""

from __future__ import annotations

from mpd_overwatch.core.hydraulics import (
    equivalent_circulating_density,
    hydrostatic_pressure,
    bottom_hole_pressure_static,
    bottom_hole_pressure_dynamic,
    annular_velocity,
)
from mpd_overwatch.core.geomechanics import (
    mechanical_specific_energy,
    ucs_from_mse,
    brittleness_index,
)
from mpd_overwatch.core.pore_pressure import (
    d_exponent as _d_exponent_core,
    eaton_pore_pressure as _eaton_pp_core,
)
from mpd_overwatch.core.formation_damage import (
    skin_factor as _skin_factor_core,
    productivity_index as _productivity_index_core,
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


# ===========================================================================
# Geomechanics wrappers
# ===========================================================================

def compute_mse(
    wob: float,
    torque: float,
    rpm: float,
    rop: float,
    bit_diameter: float,
    wob_prov: Provenance = Provenance.MEASURED,
    torque_prov: Provenance = Provenance.MEASURED,
    rpm_prov: Provenance = Provenance.MEASURED,
    rop_prov: Provenance = Provenance.MEASURED,
    bit_diameter_prov: Provenance = Provenance.MEASURED,
) -> EngineeringResult:
    """Mechanical Specific Energy wrapped as an EngineeringResult.

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
    EngineeringResult
        MSE in psi with full method and provenance metadata.
    """
    value = mechanical_specific_energy(wob, torque, rpm, rop, bit_diameter)
    return EngineeringResult(
        label="MSE",
        value=value,
        unit="psi",
        provenance=Provenance.DERIVED,
        method=Method(
            name="Teale 1965 Mechanical Specific Energy",
            reference="Teale, R. (1965), 'The Concept of Specific Energy in Rock Drilling', "
                      "Int. J. Rock Mech. Mining Sci., Vol. 2",
            equation="MSE = (480 × T × N) / (D_b² × ROP) + (4 × WOB) / (π × D_b²)",
            novel=False,
        ),
        inputs=[
            EngineeringInput("WOB", wob, "lbs", wob_prov, source="surface weight indicator"),
            EngineeringInput("Torque", torque, "ft-lbs", torque_prov, source="top-drive torque gauge"),
            EngineeringInput("RPM", rpm, "rev/min", rpm_prov, source="top-drive RPM sensor"),
            EngineeringInput("ROP", rop, "ft/hr", rop_prov, source="depth/time calculation"),
            EngineeringInput("D_bit", bit_diameter, "in", bit_diameter_prov, source="bit record"),
        ],
        validity=(
            "Surface-measured parameters; does not account for downhole WOB/torque losses "
            "due to friction. Most accurate in vertical or low-inclination wellbores."
        ),
        cross_check=(
            "Compare MSE trend with ROP trend; when MSE rises without a lithology change, "
            "check for bit dulling, vibration, or founder-point conditions."
        ),
        sensitivity=(
            "Strongly sensitive to ROP in the denominator; small ROP changes cause large MSE swings. "
            "Torque term dominates in rotary-dominant drilling (high RPM, low WOB)."
        ),
        implication=(
            "MSE approaching or exceeding UCS indicates poor drilling efficiency; "
            "optimize WOB/RPM or change bit. Low MSE relative to UCS means efficient energy transfer."
        ),
    )


def compute_ucs(
    mse: float,
    bit_efficiency: float = 0.35,
    mse_prov: Provenance = Provenance.DERIVED,
) -> EngineeringResult:
    """Unconfined Compressive Strength from MSE wrapped as an EngineeringResult.

    Parameters
    ----------
    mse : float
        Raw (uncorrected) mechanical specific energy (psi).
    bit_efficiency : float
        Bit efficiency factor (0 to 1). Default 0.35 for PDC bits.

    Returns
    -------
    EngineeringResult
        UCS estimate in psi with full method and provenance metadata.
    """
    value = ucs_from_mse(mse, bit_efficiency)
    return EngineeringResult(
        label="UCS",
        value=value,
        unit="psi",
        provenance=Provenance.DERIVED,
        method=Method(
            name="UCS from MSE — empirical correlation",
            reference=(
                "Dupriest, F.E. & Koederitz, W.L. (2005), "
                "'Maximizing Drill Rates with Real-Time Surveillance of Mechanical Specific Energy', "
                "SPE 92194; Teale (1965)"
            ),
            equation="UCS = a × MSE  (default a = bit_efficiency = 0.35, b = 0)",
            novel=False,
        ),
        inputs=[
            EngineeringInput("MSE", mse, "psi", mse_prov, source="surface drilling parameters"),
            EngineeringInput(
                "bit_efficiency", bit_efficiency, "fraction", Provenance.MODELED,
                source="bit-type assumption (PDC default=0.35)"
            ),
        ],
        validity=(
            "Empirical correlation calibrated for PDC bits in shale (Delaware Basin Wolfcamp). "
            "Must be recalibrated against core UCS or sonic-derived UCS for other lithologies."
        ),
        cross_check=(
            "Compare against sonic-derived dynamic UCS from offset well logs; "
            "validate against core plug test data when available."
        ),
        sensitivity=(
            "Linear in MSE; UCS scales directly with bit efficiency assumption. "
            "A 0.05 change in efficiency shifts UCS by ~14% at constant MSE."
        ),
        implication=(
            "High UCS zones require higher WOB and optimized bit selection; "
            "low UCS ductile zones may indicate organic-rich intervals favorable for completions."
        ),
    )


def compute_brittleness(
    ucs: float,
    tensile_strength: float | None = None,
    ucs_prov: Provenance = Provenance.DERIVED,
) -> EngineeringResult:
    """Rock Brittleness Index wrapped as an EngineeringResult.

    Parameters
    ----------
    ucs : float
        Unconfined compressive strength (psi).
    tensile_strength : float or None
        Tensile strength (psi). If None, estimated as UCS / 10.

    Returns
    -------
    EngineeringResult
        Brittleness index (dimensionless, 0 to 1) with full metadata.
    """
    value = brittleness_index(ucs, tensile_strength)
    t_used = tensile_strength if tensile_strength is not None else ucs / 10.0
    return EngineeringResult(
        label="Brittleness",
        value=value,
        unit="dimensionless",
        provenance=Provenance.DERIVED,
        method=Method(
            name="Brittleness Index — Jarvie 2007 / UCS-tensile ratio",
            reference=(
                "Jarvie, D.M. et al. (2007), 'Unconventional shale-gas systems: "
                "The Mississippian Barnett Shale of north-central Texas as one model "
                "for thermogenic shale-gas assessment', AAPG Bulletin 91(4); "
                "Rickman et al. (2008), SPE 115258"
            ),
            equation="BI = (UCS − T) / (UCS + T)   [T ≈ UCS/10 if not measured]",
            novel=False,
        ),
        inputs=[
            EngineeringInput("UCS", ucs, "psi", ucs_prov, source="MSE-derived or core test"),
            EngineeringInput(
                "T", t_used, "psi", Provenance.MODELED,
                source="estimated as UCS/10" if tensile_strength is None else "measured"
            ),
        ],
        validity=(
            "Valid for competent rock (UCS > 0). "
            "Tensile strength estimation (T = UCS/10) is an approximation for shale; "
            "direct measurement improves accuracy."
        ),
        cross_check=(
            "Cross-check against mineralogy-based brittleness (quartz+carbonate fraction); "
            "compare to Young's Modulus and Poisson's Ratio from sonic logs."
        ),
        sensitivity=(
            "Insensitive to small changes in T when UCS >> T. "
            "More sensitive when UCS is low (ductile formations)."
        ),
        implication=(
            "BI > 0.5 indicates brittle rock favorable for hydraulic fracturing; "
            "target high-BI intervals for frac stage placement to maximize fracture complexity."
        ),
    )


# ===========================================================================
# Pore pressure wrappers
# ===========================================================================

def compute_d_exponent(
    rop: float,
    rpm: float,
    wob_lbs: float,
    bit_diameter: float,
    rop_prov: Provenance = Provenance.MEASURED,
    rpm_prov: Provenance = Provenance.MEASURED,
    wob_prov: Provenance = Provenance.MEASURED,
    bit_diameter_prov: Provenance = Provenance.MEASURED,
) -> EngineeringResult:
    """Drilling d-exponent wrapped as an EngineeringResult.

    Parameters
    ----------
    rop : float
        Rate of penetration (ft/hr).
    rpm : float
        Rotary speed (rev/min).
    wob_lbs : float
        Weight on bit (lbs).
    bit_diameter : float
        Bit diameter (in).

    Returns
    -------
    EngineeringResult
        d-exponent (dimensionless) with full method and provenance metadata.
    """
    value = _d_exponent_core(
        rop_fthr=rop,
        rpm=rpm,
        wob_lbs=wob_lbs,
        bit_diameter_in=bit_diameter,
    )
    return EngineeringResult(
        label="d-exponent",
        value=value,
        unit="dimensionless",
        provenance=Provenance.DERIVED,
        method=Method(
            name="Jorden & Shirley 1966 d-exponent",
            reference=(
                "Jorden, J.R. & Shirley, O.J. (1966), "
                "'Application of Drilling Performance Data to Overpressure Detection', "
                "JPT 18(11); Rehm, W.A. & McClendon, M.T. (1971), SPE 3543"
            ),
            equation=(
                "d = log10(ROP / (60 × RPM)) / log10(12 × WOB / (1000 × D_bit))"
            ),
            novel=False,
        ),
        inputs=[
            EngineeringInput("ROP", rop, "ft/hr", rop_prov, source="depth/time calculation"),
            EngineeringInput("RPM", rpm, "rev/min", rpm_prov, source="top-drive RPM sensor"),
            EngineeringInput("WOB", wob_lbs, "lbs", wob_prov, source="surface weight indicator"),
            EngineeringInput("D_bit", bit_diameter, "in", bit_diameter_prov, source="bit record"),
        ],
        validity=(
            "Valid in shale sequences drilled with rotary methods. "
            "Requires consistent drilling parameters to isolate pore pressure signal; "
            "lithology changes and bit dulling confound the trend."
        ),
        cross_check=(
            "Plot dc-exponent on a semi-log scale against TVD; departures from the "
            "normal compaction trend indicate overpressure. Cross-reference with mud gas shows."
        ),
        sensitivity=(
            "Sensitive to ROP variations; filter noisy ROP data before computing. "
            "WOB and RPM changes must be accounted for by the dc correction."
        ),
        implication=(
            "A decreasing d-exponent trend at constant drilling parameters signals "
            "approaching overpressure — increase SBP target before the formation is penetrated."
        ),
    )


def compute_eaton_pp(
    tvd: float,
    dc_observed: float,
    dc_normal: float,
    overburden_ppg: float,
    normal_pp_ppg: float = 8.65,
    eaton_exponent: float = 1.2,
    tvd_prov: Provenance = Provenance.SURVEY,
    dc_observed_prov: Provenance = Provenance.DERIVED,
    dc_normal_prov: Provenance = Provenance.MODELED,
    overburden_prov: Provenance = Provenance.MODELED,
) -> EngineeringResult:
    """Eaton pore pressure estimate wrapped as an EngineeringResult.

    Parameters
    ----------
    tvd : float
        True vertical depth (ft).
    dc_observed : float
        Observed corrected d-exponent at this depth.
    dc_normal : float
        Normal compaction trend dc value at this depth.
    overburden_ppg : float
        Overburden gradient (ppg EMW).
    normal_pp_ppg : float
        Normal pore pressure gradient (ppg). Default 8.65.
    eaton_exponent : float
        Eaton exponent. Default 1.2 for d-exponent method.

    Returns
    -------
    EngineeringResult
        Pore pressure in ppg EMW with full method and provenance metadata.
    """
    value = _eaton_pp_core(
        tvd_ft=tvd,
        dc_observed=dc_observed,
        dc_normal=dc_normal,
        overburden_ppg=overburden_ppg,
        normal_pp_ppg=normal_pp_ppg,
        eaton_exponent=eaton_exponent,
    )
    return EngineeringResult(
        label="Pore Pressure",
        value=value,
        unit="ppg",
        provenance=Provenance.DERIVED,
        method=Method(
            name="Eaton 1975 Pore Pressure Prediction",
            reference=(
                "Eaton, B.A. (1975), 'The Equation for Geopressure Prediction from "
                "Well Logs', SPE 5544"
            ),
            equation=(
                "Pp = Sv − (Sv − Pp_normal) × (dc_observed / dc_normal)^1.2"
            ),
            novel=False,
        ),
        inputs=[
            EngineeringInput("TVD", tvd, "ft", tvd_prov, source="survey interpolation"),
            EngineeringInput(
                "dc_observed", dc_observed, "dimensionless", dc_observed_prov,
                source="real-time drilling parameters"
            ),
            EngineeringInput(
                "dc_normal", dc_normal, "dimensionless", dc_normal_prov,
                source="normal compaction trend model"
            ),
            EngineeringInput(
                "overburden", overburden_ppg, "ppg", overburden_prov,
                source="density log integration or regional gradient"
            ),
        ],
        validity=(
            "Valid in shale-dominated intervals with established normal compaction trend. "
            "Accuracy decreases in carbonates, sands, and highly cemented formations. "
            "Requires offset-well calibration of normal trend parameters."
        ),
        cross_check=(
            "Compare against repeat formation tester (RFT/MDT) pressures if available; "
            "validate with mud weight used successfully on offset wells."
        ),
        sensitivity=(
            "±0.1 change in dc_observed / dc_normal ratio shifts Pp by ~0.5-1.5 ppg "
            "depending on overburden gradient. Overburden uncertainty dominates in shallow wells."
        ),
        implication=(
            "Set SBP target above Pp estimate with a 0.3-0.5 ppg safety margin; "
            "rising Pp trend requires proactive SBP increase before the kick window opens."
        ),
    )


# ===========================================================================
# Formation damage wrappers
# ===========================================================================

def compute_skin_factor(
    k: float,
    k_d: float,
    r_d: float,
    r_w: float,
    k_prov: Provenance = Provenance.MODELED,
    k_d_prov: Provenance = Provenance.MODELED,
    r_d_prov: Provenance = Provenance.MODELED,
    r_w_prov: Provenance = Provenance.MEASURED,
) -> EngineeringResult:
    """Hawkins skin factor wrapped as an EngineeringResult.

    Parameters
    ----------
    k : float
        Virgin permeability (mD).
    k_d : float
        Damaged permeability (mD).
    r_d : float
        Damage (invasion) radius (ft).
    r_w : float
        Wellbore radius (ft).

    Returns
    -------
    EngineeringResult
        Dimensionless skin factor with full method and provenance metadata.
    """
    value = _skin_factor_core(k=k, k_d=k_d, r_d=r_d, r_w=r_w)
    return EngineeringResult(
        label="Skin Factor",
        value=value,
        unit="dimensionless",
        provenance=Provenance.DERIVED,
        method=Method(
            name="Hawkins 1956 skin factor formula",
            reference=(
                "Hawkins, M.F. (1956), 'A Note on the Skin Effect', "
                "Transactions of AIME 207; "
                "Bennion, D.B. et al. (1998), 'Underbalanced Drilling and Formation Damage', "
                "SPE 46015"
            ),
            equation="S = (k / k_d − 1) × ln(r_d / r_w)",
            novel=False,
        ),
        inputs=[
            EngineeringInput("k", k, "mD", k_prov, source="core analysis or log-derived"),
            EngineeringInput("k_d", k_d, "mD", k_d_prov, source="permeability reduction model"),
            EngineeringInput("r_d", r_d, "ft", r_d_prov, source="invasion radius model"),
            EngineeringInput("r_w", r_w, "ft", r_w_prov, source="bit size record"),
        ],
        validity=(
            "Assumes radially uniform damage zone from r_w to r_d. "
            "Does not account for non-Darcy flow effects or partial penetration. "
            "Valid for single-phase radial flow in the near-wellbore region."
        ),
        cross_check=(
            "Compare against pressure transient analysis (PTA) skin from well tests; "
            "validate invasion radius with resistivity log interpretation."
        ),
        sensitivity=(
            "Sensitive to k/k_d ratio; a 5× permeability reduction yields S ≈ 4 × ln(r_d/r_w). "
            "Invasion radius has logarithmic influence — deep invasion is less damaging than high k/k_d."
        ),
        implication=(
            "High skin (S > 5) significantly reduces well productivity; "
            "MPD reduces overbalance and thereby limits invasion radius and k/k_d damage ratio."
        ),
    )


def compute_productivity_index(
    k: float,
    h: float,
    Bo: float,
    mu: float,
    r_e: float,
    r_w: float,
    S: float,
    k_prov: Provenance = Provenance.MODELED,
    h_prov: Provenance = Provenance.MEASURED,
    Bo_prov: Provenance = Provenance.MODELED,
    mu_prov: Provenance = Provenance.MODELED,
    r_e_prov: Provenance = Provenance.MODELED,
    r_w_prov: Provenance = Provenance.MEASURED,
    S_prov: Provenance = Provenance.DERIVED,
) -> EngineeringResult:
    """Productivity Index wrapped as an EngineeringResult.

    Parameters
    ----------
    k : float
        Permeability (mD).
    h : float
        Net pay thickness (ft).
    Bo : float
        Oil formation volume factor (RB/STB).
    mu : float
        Oil viscosity (cP).
    r_e : float
        Drainage radius (ft).
    r_w : float
        Wellbore radius (ft).
    S : float
        Skin factor (dimensionless).

    Returns
    -------
    EngineeringResult
        Productivity index in STB/d/psi with full method and provenance metadata.
    """
    value = _productivity_index_core(k=k, h=h, Bo=Bo, mu=mu, r_e=r_e, r_w=r_w, S=S)
    return EngineeringResult(
        label="PI",
        value=value,
        unit="STB/d/psi",
        provenance=Provenance.DERIVED,
        method=Method(
            name="Darcy radial flow — semi-steady-state PI",
            reference=(
                "Darcy, H. (1856), 'Les Fontaines Publiques de la Ville de Dijon'; "
                "Bennion, D.B. et al. (1998), 'Underbalanced Drilling and Formation Damage', "
                "SPE 46015; Craft, Hawkins & Terry, 'Applied Petroleum Reservoir Engineering'"
            ),
            equation="PI = (k × h) / (141.2 × Bo × μ × (ln(r_e / r_w) + S))",
            novel=False,
        ),
        inputs=[
            EngineeringInput("k", k, "mD", k_prov, source="core analysis or log-derived"),
            EngineeringInput("h", h, "ft", h_prov, source="net pay from petrophysics"),
            EngineeringInput("Bo", Bo, "RB/STB", Bo_prov, source="PVT analysis"),
            EngineeringInput("mu", mu, "cP", mu_prov, source="PVT analysis"),
            EngineeringInput("r_e", r_e, "ft", r_e_prov, source="drainage area / well spacing"),
            EngineeringInput("r_w", r_w, "ft", r_w_prov, source="bit size record"),
            EngineeringInput("S", S, "dimensionless", S_prov, source="Hawkins skin model"),
        ],
        validity=(
            "Single-phase radial semi-steady-state flow; assumes homogeneous reservoir. "
            "Does not account for non-Darcy flow at high rates, multiphase effects, "
            "or natural fractures."
        ),
        cross_check=(
            "Compare against actual well test PI from pressure buildup/falloff analysis; "
            "validate against analogous wells in the same reservoir interval."
        ),
        sensitivity=(
            "Linearly proportional to k and h; logarithmically sensitive to r_e/r_w ratio. "
            "Skin factor directly subtracts from or adds to the logarithmic resistance term — "
            "skin reduction of 5 can improve PI by 20-40% depending on reservoir geometry."
        ),
        implication=(
            "MPD reduces formation damage (lower S), directly increasing PI and ultimate recovery; "
            "quantify PI uplift to justify MPD incremental cost versus incremental EUR."
        ),
    )
