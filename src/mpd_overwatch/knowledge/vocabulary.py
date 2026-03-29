"""Encoded vocabulary — semantic descriptions of drilling channels.

Each entry captures what an experienced MWD hand or drilling engineer knows
about a channel: what it measures, the underlying physics, when to trust it,
and common misinterpretations.

CRITICAL PRINCIPLE: "Expresses Reality True"
This module contains ONLY semantic text.  ZERO numbers.  No ranges, no
thresholds, no preset values.  All numeric parameters are computed from
data by the scan pipeline (Tasks 5-7).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from mpd_overwatch.knowledge.dossier import IndexType, PhysicsDomain


# ── Vocabulary type alias ────────────────────────────────────────────

VocabEntry = Dict


# ── Internal vocabulary table ────────────────────────────────────────

_VOCABULARY: Dict[str, VocabEntry] = {

    # ── Record 01: General drilling parameters ────────────────────

    "0012": {
        "canonical": "slide_indicator",
        "mnemonic": "SLDI",
        "units": "flag",
        "physics_domain": PhysicsDomain.MECHANICAL,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Binary or categorical flag indicating whether the drillstring "
            "is in slide mode (no surface rotation, motor-only drilling) "
            "versus rotary mode."
        ),
        "physical_phenomenon": (
            "Driven by the directional driller's operational decision to "
            "orient the mud motor toolface and push weight without surface "
            "rotation to build or drop angle."
        ),
        "trust_conditions": (
            "Trust when confirmed against surface RPM — slide indicator "
            "should coincide with near-zero surface RPM. Some systems "
            "set this from the directional driller's manual input, which "
            "can lag actual mode changes."
        ),
        "common_misinterpretations": [
            "Assumes motor is always oriented when slide flag is set — "
            "toolface may not be confirmed yet.",
            "Lag between flag activation and actual slide initiation — "
            "weight may not be on bit yet.",
            "Does not capture partial-rotation slide techniques used by "
            "some directional drillers.",
        ],
    },

    "0108": {
        "canonical": "hole_depth",
        "mnemonic": "DEPTHOLE",
        "units": "ft",
        "physics_domain": PhysicsDomain.DEPTH,
        "index_type": IndexType.DEPTH_ONLY,
        "what_it_measures": (
            "Total measured depth of the bottom of the wellbore. "
            "Monotonically increasing during drilling — the deepest "
            "point the bit has reached. This is the primary depth index "
            "for all depth-referenced data."
        ),
        "physical_phenomenon": (
            "Accumulated footage drilled from surface datum. Tracked by "
            "the driller via pipe tally (count and length of joints/stands "
            "run in hole) plus kelly/top-drive position offset."
        ),
        "trust_conditions": (
            "Accurate to driller's depth measurement, which is the "
            "industry standard reference. Subject to stretch/compression "
            "corrections at depth. Pipe tally errors propagate — a "
            "miscounted joint shifts all subsequent depths."
        ),
        "common_misinterpretations": [
            "Hole depth is measured depth (MD), not true vertical depth "
            "(TVD) — in directional wells these diverge significantly.",
            "Hole depth does not decrease during tripping — it represents "
            "maximum depth reached, not current bit position.",
            "Driller's depth differs from logger's depth due to different "
            "stretch corrections and datum references.",
        ],
    },

    "0110": {
        "canonical": "bit_depth",
        "mnemonic": "DEPTBIT",
        "units": "ft",
        "physics_domain": PhysicsDomain.DEPTH,
        "index_type": IndexType.DEPTH_ONLY,
        "what_it_measures": (
            "Current measured depth of the drill bit. Unlike hole depth, "
            "bit depth decreases during trips out and increases during "
            "trips in. Equals hole depth only when on-bottom drilling."
        ),
        "physical_phenomenon": (
            "Computed from pipe tally minus the distance the bit is off "
            "bottom. During drilling, bit depth approaches hole depth. "
            "During connections or trips, bit depth is above hole depth."
        ),
        "trust_conditions": (
            "Trust when pipe tally is current and block position is "
            "accounted for. Off-bottom distance computed from block "
            "position relative to kelly-down position. Most reliable "
            "when actively drilling or at a known depth reference."
        ),
        "common_misinterpretations": [
            "Bit depth equals hole depth only when the bit is on bottom — "
            "during connections the bit is off bottom by a stand length.",
            "Bit depth during trips reflects where the bit is, not where "
            "the hole bottom is.",
            "String stretch means the bit may be deeper than the rigid "
            "pipe-tally calculation suggests, especially in deep wells.",
        ],
    },

    "0112": {
        "canonical": "block_position",
        "mnemonic": "BLKPOS",
        "units": "ft",
        "physics_domain": PhysicsDomain.DEPTH,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Height of the traveling block above the rig floor. Its time "
            "derivative gives block velocity, which is the primary input "
            "for rig state detection — distinguishing drilling, tripping, "
            "connections, and static states."
        ),
        "physical_phenomenon": (
            "Mechanical measurement of the drawworks drum position, "
            "converted to traveling block height. The block moves up to "
            "add pipe, down while drilling, and cycles up-then-down "
            "during connections."
        ),
        "trust_conditions": (
            "Mechanical sensor — generally reliable and high-fidelity. "
            "Calibration drift is rare but can occur over long runs. "
            "Dead-band noise near static positions should be filtered "
            "before derivative computation."
        ),
        "common_misinterpretations": [
            "Block position alone does not indicate drilling — must be "
            "combined with pump and rotation status for state detection.",
            "Block velocity (derivative) is more informative than "
            "absolute position for operational classification.",
            "Heave compensation on floating rigs adds oscillation that "
            "is not real drilling motion.",
        ],
    },

    "0113": {
        "canonical": "rop",
        "mnemonic": "ROP",
        "units": "ft/hr",
        "physics_domain": PhysicsDomain.MECHANICAL,
        "index_type": IndexType.BRIDGES_BOTH,
        "what_it_measures": (
            "Rate of penetration — how fast the bit is destroying rock "
            "and deepening the wellbore. The fundamental measure of "
            "drilling efficiency, linking mechanical energy input "
            "(WOB + RPM) to footage output."
        ),
        "physical_phenomenon": (
            "Rock destruction rate under applied weight on bit and "
            "rotational energy. Governed by rock strength, bit type and "
            "condition, WOB, RPM, hydraulic cleaning efficiency, and "
            "formation properties."
        ),
        "trust_conditions": (
            "Trust only during DRILLING rig state. Invalid during "
            "connections, trips, and reaming. Calculated from block "
            "position derivative (depth change over time), so it inherits "
            "block position sensor quality."
        ),
        "common_misinterpretations": [
            "Connection artifacts — pipe stretch/squat creates irrational "
            "ROP values for the first one to two feet after a connection "
            "as the string elastically unloads.",
            "Bit bounce at hard formation interfaces creates false "
            "high-ROP spikes that do not represent actual penetration.",
            "ROP is a calculated channel (block position derivative), not "
            "a direct measurement — its quality depends entirely on the "
            "block position sensor and the calculation method.",
            "Sliding ROP and rotary ROP are fundamentally different "
            "drilling mechanics and should not be compared directly.",
        ],
    },

    "0114": {
        "canonical": "hookload",
        "mnemonic": "HKLD",
        "units": "klbs",
        "physics_domain": PhysicsDomain.MECHANICAL,
        "index_type": IndexType.BRIDGES_BOTH,
        "what_it_measures": (
            "Total weight hanging from the hook of the traveling block. "
            "Changes meaning with rig state: during drilling it reflects "
            "string weight minus WOB plus friction, during tripping it "
            "is the primary drag measurement, during connections the "
            "pickup and slackoff weights indicate wellbore condition."
        ),
        "physical_phenomenon": (
            "Tension at the hook point, resulting from the combined "
            "effects of drillstring weight in the fluid (buoyed weight), "
            "wellbore friction (drag), weight applied to the bit, and "
            "any dynamic forces from vibration or acceleration."
        ),
        "trust_conditions": (
            "Trust after accounting for line count and deadline anchor "
            "friction — raw hookload from the deadline sensor must be "
            "corrected for sheave efficiency. Calibration should be "
            "verified at known string weights (e.g., empty hole)."
        ),
        "common_misinterpretations": [
            "Hookload is NOT just string weight — it includes friction, "
            "WOB effects, and dynamic forces that vary with rig state.",
            "Comparing hookload between wells without normalizing for "
            "string weight, mud weight, and wellbore geometry is invalid.",
            "Pickup weight exceeding free-rotating weight does not always "
            "indicate a problem — it may be normal wellbore drag in "
            "high-angle or extended-reach wells.",
            "Hookload resolution degrades with higher line counts due to "
            "sheave friction losses in the block system.",
        ],
    },

    "0115": {
        "canonical": "torque",
        "mnemonic": "TRQ",
        "units": "ft-lbs",
        "physics_domain": PhysicsDomain.MECHANICAL,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Surface rotary torque applied to turn the drillstring. "
            "Reflects the total torsional resistance from the bit, "
            "string-to-wellbore contact, and fluid viscous drag along "
            "the entire drillstring."
        ),
        "physical_phenomenon": (
            "Torsional friction from drillstring rotation against the "
            "wellbore wall, bit cutting resistance, and viscous drag "
            "from drilling fluid. Torque increases with contact area, "
            "differential sticking tendency, and formation hardness."
        ),
        "trust_conditions": (
            "Trust when rotating. Zero or near-zero values during slide "
            "mode are expected and valid. Surface torque measurement "
            "location means it includes all drillstring friction, not "
            "just bit torque."
        ),
        "common_misinterpretations": [
            "Surface torque is not bit torque — friction along the "
            "entire drillstring is included in the measurement.",
            "Torque spikes during connections are mechanical events "
            "(makeup torque), not drilling torque.",
            "Increasing torque trend does not always indicate a downhole "
            "problem — it may reflect normal hole-drag increase with depth "
            "or inclination buildup.",
        ],
    },

    "0116": {
        "canonical": "rpm",
        "mnemonic": "RPM",
        "units": "rpm",
        "physics_domain": PhysicsDomain.MECHANICAL,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Surface rotary speed — how fast the top drive or rotary "
            "table is turning the drillstring. One of the three primary "
            "channels for rig state detection (pumps, rotation, block)."
        ),
        "physical_phenomenon": (
            "Rotational velocity applied at surface. The drillstring acts "
            "as a torsional spring, so downhole RPM may differ from "
            "surface RPM due to stick-slip dynamics, especially in hard "
            "formations or high-angle wells."
        ),
        "trust_conditions": (
            "Trust the surface measurement as a true surface value. "
            "Bimodal distribution (on/off) makes it reliable for state "
            "detection. Does not represent downhole RPM — use downhole "
            "RPM sensors for that."
        ),
        "common_misinterpretations": [
            "Surface RPM does not equal downhole RPM — stick-slip can "
            "cause the bit to momentarily stop while surface rotates.",
            "RPM during slide mode should be zero or near-zero; any "
            "residual RPM indicates the string is still rotating.",
            "Motor RPM is additive to surface RPM at the bit — total "
            "bit RPM = surface RPM + motor RPM.",
        ],
    },

    "0117": {
        "canonical": "wob",
        "mnemonic": "WOB",
        "units": "klbs",
        "physics_domain": PhysicsDomain.MECHANICAL,
        "index_type": IndexType.BRIDGES_BOTH,
        "what_it_measures": (
            "Weight on bit — the axial force applied to the drill bit "
            "to fracture rock. Calculated as the difference between "
            "off-bottom hookload (free-rotating string weight) and "
            "on-bottom hookload while drilling."
        ),
        "physical_phenomenon": (
            "Compressive axial force at the bit face from the weight of "
            "the drillstring above the neutral point. Governed by buoyed "
            "string weight, wellbore friction, and how much the driller "
            "slacks off at surface."
        ),
        "trust_conditions": (
            "Trust only during DRILLING and SLIDING rig states when the "
            "bit is on bottom. Requires accurate off-bottom weight "
            "reference, which changes with depth. Surface-derived WOB "
            "inherits all hookload measurement limitations."
        ),
        "common_misinterpretations": [
            "Surface WOB differs from downhole WOB — friction effects "
            "in deviated wells mean less weight reaches the bit than "
            "what the surface measurement indicates.",
            "String weight changes with depth, so the off-bottom reference "
            "must be updated after each connection.",
            "Negative WOB values indicate the string is in tension at "
            "the bit (pulling), which can happen in high-angle wells.",
            "WOB during slide mode behaves differently than rotary WOB — "
            "friction patterns change without rotation.",
        ],
    },

    "0118": {
        "canonical": "rotary_torque_2",
        "mnemonic": "TRQ2",
        "units": "ft-lbs",
        "physics_domain": PhysicsDomain.MECHANICAL,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Secondary rotary torque channel. May represent a backup "
            "torque sensor, a different measurement point on the drive "
            "system, or a torque measurement from a secondary device."
        ),
        "physical_phenomenon": (
            "Same torsional mechanics as primary torque — rotational "
            "resistance from drillstring-to-wellbore contact and bit "
            "cutting forces. May differ from primary due to measurement "
            "location or sensor type."
        ),
        "trust_conditions": (
            "Trust when cross-referenced against the primary torque "
            "channel. If both are present, significant divergence "
            "indicates a sensor calibration issue on one channel."
        ),
        "common_misinterpretations": [
            "Not always a true backup — may measure torque at a different "
            "point in the drive train, yielding different absolute values.",
            "Units or scaling may differ from the primary torque channel "
            "depending on the data acquisition system configuration.",
        ],
    },

    "0119": {
        "canonical": "rotary_torque",
        "mnemonic": "RTRQ",
        "units": "ft-lbs",
        "physics_domain": PhysicsDomain.MECHANICAL,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Rotary torque measured at the top drive or rotary table. "
            "This is the primary torque channel representing total "
            "torsional load on the drillstring during rotation."
        ),
        "physical_phenomenon": (
            "Combined torsional resistance from bit-rock interaction, "
            "drillstring-to-casing and drillstring-to-formation friction, "
            "and fluid viscous drag. Increases with depth, inclination, "
            "and formation hardness."
        ),
        "trust_conditions": (
            "Trust when surface rotation is active. The measurement is "
            "at surface, so it includes all friction contributions along "
            "the drillstring, not just bit torque. Sensor calibration "
            "should be verified against a known reference."
        ),
        "common_misinterpretations": [
            "Surface rotary torque includes all friction sources — it is "
            "not isolating bit torque from string friction.",
            "Torque fluctuations during stick-slip are real but reflect "
            "surface response, not necessarily downhole dynamics.",
            "Comparison between rotary_torque and torque channels may "
            "show different values if they measure at different points.",
        ],
    },

    "0120": {
        "canonical": "rotary_speed",
        "mnemonic": "RSPD",
        "units": "rpm",
        "physics_domain": PhysicsDomain.MECHANICAL,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Rotary speed of the drillstring at surface, measured at the "
            "rotary table or top drive. May represent the same physical "
            "measurement as RPM (0116) from a different sensor or data "
            "path."
        ),
        "physical_phenomenon": (
            "Angular velocity of the drillstring at surface. Subject to "
            "the same stick-slip dynamics as the primary RPM channel — "
            "downhole RPM can differ significantly from surface RPM."
        ),
        "trust_conditions": (
            "Trust as a surface measurement. Cross-reference with "
            "primary RPM channel if both are present — they should "
            "agree. Useful as a fallback if the primary RPM channel "
            "is unavailable."
        ),
        "common_misinterpretations": [
            "Same caveats as surface RPM — does not equal bit RPM, "
            "especially during stick-slip.",
            "May be scaled differently than the primary RPM channel "
            "depending on the data acquisition system.",
        ],
    },

    "0121": {
        "canonical": "standpipe_pressure",
        "mnemonic": "SPP",
        "units": "psi",
        "physics_domain": PhysicsDomain.PRESSURE,
        "index_type": IndexType.BRIDGES_BOTH,
        "what_it_measures": (
            "Standpipe pressure — the total circulating system pressure "
            "measured at the standpipe manifold on the rig floor. "
            "Represents the sum of all friction losses from pump "
            "discharge through surface lines, drillstring, bit nozzles, "
            "and annulus back to surface."
        ),
        "physical_phenomenon": (
            "Fluid friction losses across the entire circulating system. "
            "Dominated by bit pressure drop, drillstring friction, and "
            "annular friction. Varies with flow rate (approximately "
            "with the square of flow rate), mud properties, and geometry."
        ),
        "trust_conditions": (
            "Trust only when pumps are actively circulating. Zero or "
            "near-zero SPP with pumps off is expected. A sudden drop "
            "while pumping indicates a washout (drillstring failure) "
            "or lost circulation event."
        ),
        "common_misinterpretations": [
            "SPP is NOT bottomhole pressure — it is total system friction "
            "loss. BHP requires SPP decomposition plus hydrostatic head.",
            "Washouts (drillstring failures) cause sudden SPP drops "
            "because fluid bypasses the bit nozzles through the failure "
            "point, reducing total friction.",
            "SPP changes with flow rate, so comparing values at different "
            "pump rates without normalization is misleading.",
            "Plugged bit nozzles increase SPP — this looks similar to a "
            "tight annulus but has a different cause and different "
            "operational response.",
        ],
    },

    "0123": {
        "canonical": "spm1",
        "mnemonic": "SPM1",
        "units": "spm",
        "physics_domain": PhysicsDomain.FLOW,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Strokes per minute for mud pump number one. Combined with "
            "pump liner size and efficiency, SPM converts to flow rate. "
            "The raw indicator of pump output before efficiency losses."
        ),
        "physical_phenomenon": (
            "Reciprocating pump piston cycling rate. Each stroke "
            "displaces a fixed geometric volume determined by liner "
            "diameter and stroke length, but actual output is reduced "
            "by volumetric efficiency losses (valve leakage, fluid "
            "compressibility)."
        ),
        "trust_conditions": (
            "Trust as a direct mechanical measurement of pump cycling. "
            "The relationship between SPM and actual flow rate depends "
            "on liner size and pump efficiency, which degrade over time "
            "and must be calibrated."
        ),
        "common_misinterpretations": [
            "SPM is not flow rate — it must be multiplied by displacement "
            "per stroke and corrected for pump efficiency.",
            "Same SPM on different pumps yields different flow rates if "
            "liner sizes differ.",
            "Pump efficiency can degrade significantly without a change "
            "in SPM — the pump strokes the same but moves less fluid.",
        ],
    },

    "0124": {
        "canonical": "spm2",
        "mnemonic": "SPM2",
        "units": "spm",
        "physics_domain": PhysicsDomain.FLOW,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Strokes per minute for mud pump number two. Same physics "
            "as SPM1 — combined pump outputs determine total system "
            "flow rate."
        ),
        "physical_phenomenon": (
            "Reciprocating pump piston cycling rate for the second pump. "
            "When running multiple pumps, total flow is the sum of "
            "individual pump outputs, each with its own efficiency."
        ),
        "trust_conditions": (
            "Trust as a direct mechanical measurement. Same calibration "
            "requirements as SPM1 — liner size and efficiency must be "
            "known to convert to flow rate."
        ),
        "common_misinterpretations": [
            "Adding SPM1 + SPM2 does not give total flow rate unless "
            "both pumps have identical liner sizes and efficiencies.",
            "Pump efficiency varies independently between pumps — one "
            "may degrade faster than the other.",
        ],
    },

    "0125": {
        "canonical": "spm3",
        "mnemonic": "SPM3",
        "units": "spm",
        "physics_domain": PhysicsDomain.FLOW,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Strokes per minute for mud pump number three. Third pump "
            "is used on rigs with high flow rate requirements or as a "
            "backup when servicing another pump."
        ),
        "physical_phenomenon": (
            "Reciprocating pump piston cycling rate for the third pump. "
            "Same displacement mechanics as pumps one and two."
        ),
        "trust_conditions": (
            "Trust as a direct mechanical measurement. May read zero if "
            "the third pump is offline or the rig only runs two pumps. "
            "Zero SPM3 does not indicate a problem if the rig does not "
            "use a third pump."
        ),
        "common_misinterpretations": [
            "Zero readings may be normal — not all rigs run three pumps.",
            "Same liner-size and efficiency caveats as SPM1 and SPM2 "
            "apply to this pump.",
        ],
    },

    "0128": {
        "canonical": "flow_out_pct",
        "mnemonic": "FLWOUT%",
        "units": "%",
        "physics_domain": PhysicsDomain.FLOW,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Flow out percentage — relative measurement of mud return "
            "flow at surface, typically from a paddle or sensor in the "
            "flowline. Expressed as a percentage of a baseline value "
            "rather than an absolute volumetric rate."
        ),
        "physical_phenomenon": (
            "Fluid returning from the annulus through the flowline. "
            "Under normal conditions, flow out should closely track "
            "flow in (conservation of mass). Deviations indicate fluid "
            "gain (kick/influx) or loss (lost circulation)."
        ),
        "trust_conditions": (
            "Trust as a relative trend indicator, not an absolute flow "
            "measurement. Sensor is typically a paddle in the flowline "
            "whose response depends on fluid level, viscosity, and "
            "flowline geometry. Requires periodic recalibration."
        ),
        "common_misinterpretations": [
            "Flow out percentage is a relative measurement — absolute "
            "volume comparisons with flow in are not directly valid.",
            "Cuttings loading and gas-cut mud alter flowline behavior, "
            "causing flow out variations that are not real volume changes.",
            "Pump rate changes cause transient flow-out responses that "
            "lag the input change by the annular volume lag time.",
        ],
    },

    "0130": {
        "canonical": "flow_in",
        "mnemonic": "FLWIN",
        "units": "gpm",
        "physics_domain": PhysicsDomain.FLOW,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Total flow rate of drilling fluid being pumped into the "
            "wellbore. Typically derived from the sum of individual pump "
            "SPM values multiplied by pump displacement and efficiency. "
            "One of the three primary channels for rig state detection."
        ),
        "physical_phenomenon": (
            "Volumetric flow rate of drilling fluid entering the "
            "drillstring. Drives all hydraulic functions: bottomhole "
            "cleaning, cuttings transport, MWD signal transmission, "
            "and equivalent circulating density."
        ),
        "trust_conditions": (
            "Trust when calibrated to pump efficiency and liner size. "
            "SPM-derived flow rate is only as accurate as the pump "
            "efficiency factor, which degrades with pump wear. "
            "Electromagnetic flow meters provide more accurate readings "
            "when available."
        ),
        "common_misinterpretations": [
            "Pump efficiency degrades over time — the displayed flow rate "
            "may overstate actual flow if efficiency is not updated.",
            "Liner size changes (swapping pump liners) change the "
            "displacement per stroke — flow calculation must be updated.",
            "Flow in does not equal flow at the bit — fluid compressibility "
            "and drillstring expansion/contraction cause transient "
            "differences, especially during pump startup.",
        ],
    },

    "0132": {
        "canonical": "mud_weight_in",
        "mnemonic": "MWIN",
        "units": "ppg",
        "physics_domain": PhysicsDomain.FLOW,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Density of the drilling fluid being pumped into the "
            "wellbore, measured at surface. Fundamental to all pressure "
            "calculations — hydrostatic pressure is the product of "
            "mud weight, true vertical depth, and a conversion constant."
        ),
        "physical_phenomenon": (
            "Fluid density at surface conditions. Drilling fluid density "
            "is engineered to maintain hydrostatic pressure within the "
            "pore pressure / fracture gradient window for well control. "
            "Barite or other weighting agents are added to increase "
            "density."
        ),
        "trust_conditions": (
            "Trust as a surface measurement. Downhole mud weight may "
            "differ due to temperature and pressure effects on fluid "
            "compressibility (ECD effects). Accurate only if the mud "
            "balance or Coriolis meter is properly calibrated."
        ),
        "common_misinterpretations": [
            "Surface mud weight does not equal downhole mud weight — "
            "temperature and pressure effects change fluid density "
            "at depth.",
            "Mud weight in may differ from mud weight out due to gas "
            "cutting, cuttings loading, or formation fluid influx.",
            "Small changes in mud weight have large pressure effects "
            "at depth — this is not a channel to ignore even when "
            "it appears stable.",
        ],
    },

    "0139": {
        "canonical": "mud_weight_out",
        "mnemonic": "MWOUT",
        "units": "ppg",
        "physics_domain": PhysicsDomain.FLOW,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Density of drilling fluid returning from the wellbore, "
            "measured at the flowline or shale shaker. Comparison with "
            "mud weight in is a primary well control indicator."
        ),
        "physical_phenomenon": (
            "Fluid density at the annulus outlet, reflecting the combined "
            "effects of the input mud density plus any downhole "
            "contamination: gas cutting reduces density, cuttings and "
            "formation fluid influx can raise or lower it depending "
            "on the influx fluid density."
        ),
        "trust_conditions": (
            "Trust as a relative indicator when compared to mud weight "
            "in. Absolute accuracy depends on the measurement device — "
            "flowline sensors are less precise than lab measurements. "
            "Gas-cut mud will show artificially low values."
        ),
        "common_misinterpretations": [
            "Mud weight out lower than mud weight in does not always mean "
            "a kick — gas cutting from drilled gas can reduce density "
            "without a well control event.",
            "Cuttings loading temporarily increases mud weight out — "
            "this is normal during active drilling.",
            "The lag time between a downhole event and its appearance in "
            "mud weight out depends on annular volume and flow rate.",
        ],
    },

    "0140": {
        "canonical": "rpm_surface",
        "mnemonic": "RPMS",
        "units": "rpm",
        "physics_domain": PhysicsDomain.MECHANICAL,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Surface RPM measurement — may be a redundant channel from "
            "a different sensor than 0116 RPM, or the same measurement "
            "routed through a different data path."
        ),
        "physical_phenomenon": (
            "Same angular velocity measurement as primary RPM. "
            "Represents surface rotary speed of the drillstring."
        ),
        "trust_conditions": (
            "Trust when cross-referenced with primary RPM channel. "
            "If both are present and agree, either can serve as the "
            "rotation input for state detection. If they diverge, "
            "investigate which sensor is correct."
        ),
        "common_misinterpretations": [
            "May duplicate the primary RPM channel — check if both "
            "carry the same signal before using both in analysis.",
            "Surface RPM remains distinct from downhole RPM regardless "
            "of which surface sensor measures it.",
        ],
    },

    "0171": {
        "canonical": "differential_pressure",
        "mnemonic": "DIFFP",
        "units": "psi",
        "physics_domain": PhysicsDomain.PRESSURE,
        "index_type": IndexType.BRIDGES_BOTH,
        "what_it_measures": (
            "Differential pressure across a specified component or "
            "system segment — typically the pressure drop across the "
            "MWD tool, motor, or a surface choke. Context-dependent "
            "on the data source configuration."
        ),
        "physical_phenomenon": (
            "Pressure difference between two measurement points. In MPD "
            "context, often represents the choke pressure drop or the "
            "difference between drillpipe and annular pressures. The "
            "specific meaning depends on how the data acquisition system "
            "is configured."
        ),
        "trust_conditions": (
            "Trust when both reference pressure points are known and "
            "their sensors are calibrated. The meaning of this channel "
            "is configuration-dependent — verify what pressures are "
            "being differenced before interpretation."
        ),
        "common_misinterpretations": [
            "Differential pressure meaning is not universal — it depends "
            "on which two pressures are being differenced in the data "
            "acquisition system.",
            "Changes in differential pressure can result from changes "
            "at either reference point, not just one.",
        ],
    },

    # ── Record 04: MPD / annular pressure ─────────────────────────

    "0419": {
        "canonical": "annular_pressure",
        "mnemonic": "APWD",
        "units": "psi",
        "physics_domain": PhysicsDomain.PRESSURE,
        "index_type": IndexType.BRIDGES_BOTH,
        "what_it_measures": (
            "Downhole annular pressure measured by an MWD/LWD tool in "
            "the bottomhole assembly. The most direct measurement of "
            "bottomhole pressure available during drilling operations, "
            "critical for MPD (Managed Pressure Drilling) applications."
        ),
        "physical_phenomenon": (
            "Hydrostatic pressure from the mud column plus annular "
            "friction losses plus any applied surface backpressure. "
            "Represents the actual pressure the formation sees at the "
            "tool depth — the key parameter for staying within the "
            "pore pressure / fracture gradient window."
        ),
        "trust_conditions": (
            "Trust with awareness that the tool is not at the bit — "
            "the measurement point is typically tens of feet above bit "
            "depth, so the actual bit-face pressure differs by the "
            "hydrostatic and friction delta between tool and bit. "
            "Memory mode data may lag real-time; real-time telemetry "
            "has lower resolution than memory."
        ),
        "common_misinterpretations": [
            "APWD measures pressure at the tool, not at the bit face — "
            "the pressure at bit depth is higher by the hydrostatic and "
            "friction contribution of the interval between tool and bit.",
            "Memory mode and real-time mode may show different values for "
            "the same event — memory is higher resolution but delayed, "
            "real-time is immediate but lower resolution.",
            "Static APWD (pumps off) gives hydrostatic pressure only — "
            "this is useful for calibrating mud weight but is not the "
            "circulating pressure the formation sees while drilling.",
            "APWD responds to surface backpressure changes in MPD — a "
            "choke adjustment at surface will be visible in APWD after "
            "a pressure wave propagation delay.",
        ],
    },

    # ── Record 07: MWD / directional ─────────────────────────────

    "0709": {
        "canonical": "tvd",
        "mnemonic": "TVD",
        "units": "ft",
        "physics_domain": PhysicsDomain.DEPTH,
        "index_type": IndexType.DEPTH_ONLY,
        "what_it_measures": (
            "True vertical depth — the vertical component of the "
            "wellbore position. Critical for all pressure calculations "
            "because hydrostatic pressure depends on vertical height of "
            "the fluid column, not measured depth."
        ),
        "physical_phenomenon": (
            "Geometric projection of the wellbore trajectory onto the "
            "vertical axis. Calculated from survey stations using "
            "minimum curvature or other directional survey calculation "
            "methods, based on measured depth, inclination, and azimuth."
        ),
        "trust_conditions": (
            "Trust to the accuracy of the directional survey — "
            "survey tool accuracy, station spacing, and calculation "
            "method all affect TVD quality. Between survey stations "
            "TVD is interpolated, not measured."
        ),
        "common_misinterpretations": [
            "TVD is not measured depth — in deviated wells, TVD can be "
            "significantly less than MD. A well at high inclination may "
            "drill hundreds of feet of MD with minimal TVD change.",
            "TVD between survey stations is interpolated — actual "
            "wellbore trajectory between stations may differ from the "
            "assumed path.",
            "TVD datum (KB, DF, MSL) must be consistent across all "
            "calculations — mixing datums creates systematic errors.",
        ],
    },

    "0713": {
        "canonical": "inclination",
        "mnemonic": "INC",
        "units": "deg",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.DEPTH_ONLY,
        "what_it_measures": (
            "Wellbore inclination from vertical at the MWD tool depth. "
            "Zero degrees is vertical (straight down), ninety degrees "
            "is horizontal. The primary directional control parameter "
            "along with azimuth."
        ),
        "physical_phenomenon": (
            "Angle between the wellbore axis and the vertical (gravity) "
            "vector, measured by accelerometers in the MWD tool. "
            "Gravity-referenced, so it is independent of magnetic "
            "interference."
        ),
        "trust_conditions": (
            "Trust at survey stations where the tool is stationary and "
            "measurements are quality-checked. During drilling, "
            "continuous inclination is interpolated or extrapolated and "
            "has lower accuracy than stationary surveys."
        ),
        "common_misinterpretations": [
            "Continuous inclination during drilling is less accurate than "
            "stationary survey inclination — use survey values for "
            "wellbore position calculations.",
            "Inclination is measured at the MWD tool, not at the bit — "
            "the bit may be building or dropping differently than what "
            "the tool reads, especially with a long gauge length.",
            "Magnetic interference from casing, nearby wells, or "
            "formation minerals does not affect inclination (gravity-based) "
            "but does affect azimuth.",
        ],
    },

    "0715": {
        "canonical": "azimuth",
        "mnemonic": "AZI",
        "units": "deg",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.DEPTH_ONLY,
        "what_it_measures": (
            "Wellbore azimuth — the compass direction the wellbore is "
            "heading at the MWD tool depth. Measured from north "
            "(magnetic or true, depending on correction applied) "
            "clockwise to the wellbore direction."
        ),
        "physical_phenomenon": (
            "Orientation of the wellbore trajectory in the horizontal "
            "plane, measured by magnetometers in the MWD tool relative "
            "to Earth's magnetic field. Requires declination correction "
            "to convert from magnetic north to true north."
        ),
        "trust_conditions": (
            "Trust at survey stations where the tool is stationary and "
            "magnetic interference is assessed. Susceptible to magnetic "
            "interference from casing, drillstring components, and "
            "formation minerals. Quality indicators (magnetic field "
            "strength, dip angle) should be within expected ranges."
        ),
        "common_misinterpretations": [
            "Magnetic azimuth must be corrected for local declination to "
            "get true azimuth — using raw magnetic azimuth for well "
            "planning creates systematic directional errors.",
            "Near-vertical wells have poorly defined azimuth — small "
            "measurement errors translate to large azimuth swings when "
            "inclination is low.",
            "Magnetic interference from nearby cased wells (anti-collision "
            "concern) degrades azimuth accuracy without any obvious "
            "indication in the inclination data.",
        ],
    },

    "0716": {
        "canonical": "mtf",
        "mnemonic": "MTF",
        "units": "deg",
        "physics_domain": PhysicsDomain.SURVEY,
        "index_type": IndexType.DEPTH_ONLY,
        "what_it_measures": (
            "Magnetic toolface — the orientation of the mud motor bend "
            "relative to magnetic north, projected onto a plane "
            "perpendicular to the wellbore axis. Used for directional "
            "control at lower inclinations where gravity toolface is "
            "less reliable."
        ),
        "physical_phenomenon": (
            "Angular orientation of the BHA bend in the magnetic "
            "reference frame. Measured by combining accelerometer and "
            "magnetometer data from the MWD tool. Relates the motor "
            "bend direction to the high side and compass directions."
        ),
        "trust_conditions": (
            "Trust at low to moderate inclinations where the magnetic "
            "reference is well-defined. At higher inclinations, gravity "
            "toolface becomes more reliable. Susceptible to magnetic "
            "interference from drillstring components or nearby casing."
        ),
        "common_misinterpretations": [
            "Magnetic toolface is used at low inclinations, not high — "
            "at high inclinations, gravity toolface is preferred.",
            "Magnetic interference invalidates MTF without obvious "
            "indication — always check magnetic quality indicators.",
            "MTF orientation is relative to high side, not geographic "
            "north, despite using the magnetic reference frame.",
        ],
    },

    "0717": {
        "canonical": "gtf",
        "mnemonic": "GTF",
        "units": "deg",
        "physics_domain": PhysicsDomain.SURVEY,
        "index_type": IndexType.DEPTH_ONLY,
        "what_it_measures": (
            "Gravity toolface — the orientation of the mud motor bend "
            "relative to the high side of the wellbore, measured using "
            "accelerometers. The primary steering reference at moderate "
            "to high inclinations."
        ),
        "physical_phenomenon": (
            "Angular position of the motor bend relative to the gravity "
            "high-side, measured by the gravity (accelerometer) sensors "
            "in the MWD tool. At zero GTF the motor bend points to the "
            "high side (building angle), at ninety degrees it points "
            "right (turning)."
        ),
        "trust_conditions": (
            "Trust at inclinations high enough for the gravity vector "
            "to have a meaningful component perpendicular to the "
            "wellbore axis — generally above a transition inclination "
            "where gravity toolface becomes more stable than magnetic "
            "toolface."
        ),
        "common_misinterpretations": [
            "GTF is unreliable at very low inclinations — the gravity "
            "vector is nearly parallel to the wellbore, making the "
            "high-side reference poorly defined.",
            "GTF values change as the drillstring rotates — only the "
            "oriented (non-rotating) value is meaningful for steering.",
            "Toolface is measured at the MWD tool, not at the bit — "
            "BHA flex and bit walk mean the bit may be cutting in a "
            "slightly different direction.",
        ],
    },

    "0722": {
        "canonical": "gamma_ray",
        "mnemonic": "GR",
        "units": "gAPI",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.BRIDGES_BOTH,
        "what_it_measures": (
            "Natural gamma ray emission from the formation surrounding "
            "the wellbore at the MWD sensor depth. Used to identify "
            "lithology — shales have high gamma, clean sands and "
            "carbonates have low gamma."
        ),
        "physical_phenomenon": (
            "Natural radioactive decay of potassium, thorium, and "
            "uranium in the formation rock. Shales concentrate these "
            "elements, so gamma ray is a shale indicator. Measured "
            "by scintillation detectors in the MWD/LWD tool."
        ),
        "trust_conditions": (
            "Trust when the tool is moving slowly enough for statistical "
            "counting accuracy. High ROP degrades gamma ray resolution "
            "because fewer counts are accumulated per depth interval. "
            "Borehole washouts also reduce the signal."
        ),
        "common_misinterpretations": [
            "High gamma does not always mean shale — uranium-rich "
            "carbonates and potassium-bearing sands can have elevated "
            "gamma without being shale.",
            "Gamma ray while drilling has lower resolution than wireline "
            "gamma ray due to tool speed and BHA standoff effects.",
            "Depth assignment for gamma ray is at the sensor, not the "
            "bit — there is a fixed offset between bit depth and gamma "
            "sensor depth that must be applied.",
        ],
    },

    "0723": {
        "canonical": "vertical_section",
        "mnemonic": "VS",
        "units": "ft",
        "physics_domain": PhysicsDomain.DEPTH,
        "index_type": IndexType.DEPTH_ONLY,
        "what_it_measures": (
            "Vertical section — the horizontal displacement of the "
            "wellbore from the surface location along a specified "
            "azimuth (the vertical section azimuth). Used for "
            "directional well planning and monitoring lateral progress "
            "toward the target."
        ),
        "physical_phenomenon": (
            "Geometric projection of the wellbore's horizontal "
            "displacement onto the vertical section plane. Calculated "
            "from survey data (northing and easting) projected onto "
            "the planned well azimuth direction."
        ),
        "trust_conditions": (
            "Trust to the accuracy of the directional survey and the "
            "consistency of the vertical section azimuth with the well "
            "plan. Changes in the VS azimuth reference will shift all "
            "vertical section values."
        ),
        "common_misinterpretations": [
            "Vertical section is NOT departure (total horizontal "
            "displacement) — it is the projection onto a specific "
            "azimuth direction.",
            "Negative vertical section means the wellbore has gone "
            "behind the vertical section plane, which can happen in "
            "S-shaped or complex well profiles.",
            "Vertical section depends on the chosen reference azimuth — "
            "different azimuths yield different VS values for the same "
            "wellbore position.",
        ],
    },

    "0730": {
        "canonical": "dip_angle",
        "mnemonic": "DIPA",
        "units": "deg",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.DEPTH_ONLY,
        "what_it_measures": (
            "Magnetic dip angle — the angle between the Earth's magnetic "
            "field vector and the horizontal plane at the tool's location. "
            "Used as a quality control indicator for MWD survey accuracy."
        ),
        "physical_phenomenon": (
            "Earth's magnetic field is not horizontal — it dips into the "
            "Earth at an angle that varies with latitude and local "
            "magnetic anomalies. The dip angle measured by the MWD tool "
            "should match the expected value for the geographic location."
        ),
        "trust_conditions": (
            "Trust when the measured dip angle matches the geomagnetic "
            "reference model for the well location. Deviation from the "
            "expected value indicates magnetic interference, which "
            "compromises azimuth accuracy."
        ),
        "common_misinterpretations": [
            "Dip angle is a QC parameter, not a formation measurement — "
            "it validates MWD survey accuracy, not formation properties.",
            "Changes in dip angle between surveys may indicate magnetic "
            "interference from nearby wells or drillstring components.",
        ],
    },

    "0731": {
        "canonical": "gravity",
        "mnemonic": "GRAV",
        "units": "g",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.DEPTH_ONLY,
        "what_it_measures": (
            "Total gravitational field magnitude measured by the MWD "
            "accelerometers. Used as a quality control indicator — the "
            "total gravity should match the expected value for the "
            "well's geographic location."
        ),
        "physical_phenomenon": (
            "Earth's gravitational acceleration measured by triaxial "
            "accelerometers in the MWD tool. The total field magnitude "
            "should be consistent regardless of tool orientation. "
            "Deviations indicate accelerometer errors or vibration."
        ),
        "trust_conditions": (
            "Trust when the tool is stationary (survey mode). During "
            "drilling, vibration and drillstring dynamics contaminate "
            "the accelerometer readings. Stationary-survey gravity "
            "values should match the local reference."
        ),
        "common_misinterpretations": [
            "Gravity field total is a QC metric, not a measurement of "
            "formation density — it validates accelerometer health.",
            "Vibration during drilling causes apparent gravity changes "
            "that are measurement noise, not real gravity variations.",
        ],
    },

    "0732": {
        "canonical": "magnetic_field",
        "mnemonic": "MAGFLD",
        "units": "nT",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.DEPTH_ONLY,
        "what_it_measures": (
            "Total magnetic field magnitude measured by the MWD "
            "magnetometers. Used as a quality control indicator — the "
            "total field should match the geomagnetic reference model "
            "for the well location."
        ),
        "physical_phenomenon": (
            "Earth's magnetic field measured by triaxial magnetometers "
            "in the MWD tool. The total field magnitude should be "
            "consistent with the International Geomagnetic Reference "
            "Field (IGRF) model for the geographic location."
        ),
        "trust_conditions": (
            "Trust when the total field matches the geomagnetic reference "
            "within acceptable tolerances. Departure from the reference "
            "indicates magnetic interference from casing, drillstring "
            "components, or geologic sources."
        ),
        "common_misinterpretations": [
            "Magnetic field total is a QC metric, not a formation "
            "measurement — it validates survey quality, particularly "
            "azimuth accuracy.",
            "Elevated magnetic field total near casing indicates "
            "magnetic interference that may corrupt azimuth readings "
            "even if inclination appears normal.",
        ],
    },

    "0738": {
        "canonical": "continuous_rpm",
        "mnemonic": "CRPM",
        "units": "rpm",
        "physics_domain": PhysicsDomain.MECHANICAL,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Continuous downhole RPM measured by the MWD tool. Unlike "
            "surface RPM, this reflects actual rotational speed at the "
            "BHA depth, capturing stick-slip dynamics that surface "
            "measurements cannot see."
        ),
        "physical_phenomenon": (
            "Angular velocity of the drillstring at the MWD tool depth. "
            "In torsionally compliant drillstrings, the bit and BHA "
            "may experience significant RPM variations (stick-slip) "
            "even when surface RPM is constant."
        ),
        "trust_conditions": (
            "Trust as a downhole measurement that captures dynamics "
            "invisible to surface sensors. Real-time telemetry provides "
            "averaged values; memory data provides full-resolution "
            "dynamics."
        ),
        "common_misinterpretations": [
            "Continuous downhole RPM may differ dramatically from "
            "surface RPM during stick-slip — the BHA may momentarily "
            "stop or spin at multiples of surface RPM.",
            "The averaging inherent in real-time telemetry may smooth "
            "out severe stick-slip events, making them appear less "
            "severe than they are.",
        ],
    },

    "0757": {
        "canonical": "rotary_status",
        "mnemonic": "RSTAT",
        "units": "code",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Directional tool rotary status code — indicates the "
            "operational mode of the directional BHA as determined "
            "by the MWD tool. Encodes whether the tool detects rotation "
            "or slide mode."
        ),
        "physical_phenomenon": (
            "Derived from the MWD tool's internal sensors detecting "
            "whether the BHA is rotating or stationary. The tool "
            "classifies its own operational state based on accelerometer "
            "and magnetometer dynamics."
        ),
        "trust_conditions": (
            "Trust as the MWD tool's own assessment of its operational "
            "mode. May disagree with surface-based slide detection "
            "during transition periods or partial-rotation techniques."
        ),
        "common_misinterpretations": [
            "Rotary status codes are tool-vendor-specific — the same "
            "code number may mean different things for different MWD "
            "tool brands.",
            "Transition between rotary and slide modes may show "
            "intermediate or ambiguous status codes.",
        ],
    },

    "0758": {
        "canonical": "rotary_status_2",
        "mnemonic": "RSTAT2",
        "units": "code",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Secondary rotary status code from the directional tool. "
            "May encode additional operational state information beyond "
            "the primary rotary status, such as steering mode or tool "
            "health status."
        ),
        "physical_phenomenon": (
            "Additional state information from the MWD tool's internal "
            "logic. Vendor-specific encoding of tool operational "
            "parameters or diagnostic states."
        ),
        "trust_conditions": (
            "Trust in conjunction with the primary rotary status. "
            "Meaning is vendor-specific and may require the tool "
            "vendor's decoding documentation."
        ),
        "common_misinterpretations": [
            "Code meanings are vendor-specific and may not be documented "
            "in standard WITS references.",
            "This channel may not be populated by all MWD tool vendors.",
        ],
    },

    "0759": {
        "canonical": "ih_target",
        "mnemonic": "IHT",
        "units": "deg",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Inclination hold target — the target inclination the "
            "directional tool or RSS is trying to maintain. Set by "
            "the directional driller to command the tool to hold a "
            "specific wellbore inclination."
        ),
        "physical_phenomenon": (
            "A command parameter, not a physical measurement. Represents "
            "the desired inclination the downhole tool's control loop "
            "is steering toward. The tool adjusts its pads or bent "
            "housing orientation to achieve this target."
        ),
        "trust_conditions": (
            "Trust as a command input — this is what the directional "
            "driller is telling the tool to do. Does not indicate "
            "actual inclination — compare with measured inclination "
            "to assess whether the tool is achieving the target."
        ),
        "common_misinterpretations": [
            "IH target is a command, not a measurement — actual "
            "inclination may differ significantly if the formation "
            "or BHA is not responding as expected.",
            "A constant IH target does not mean constant inclination — "
            "formation tendencies, bit walk, and BHA behavior all "
            "create deviations from the target.",
        ],
    },

    "0760": {
        "canonical": "ultra_rpm",
        "mnemonic": "URPM",
        "units": "rpm",
        "physics_domain": PhysicsDomain.MECHANICAL,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Ultra-high-frequency downhole RPM measurement — a higher "
            "sampling rate version of continuous RPM that captures "
            "rapid rotational dynamics including whirl and severe "
            "stick-slip events."
        ),
        "physical_phenomenon": (
            "Angular velocity of the BHA measured at high temporal "
            "resolution. Captures fast torsional dynamics that standard "
            "continuous RPM may average out, including lateral and "
            "backward whirl."
        ),
        "trust_conditions": (
            "Trust as a high-resolution downhole measurement. May only "
            "be available in memory mode due to telemetry bandwidth "
            "limitations. When available in real-time, the data is "
            "typically decimated or summarized."
        ),
        "common_misinterpretations": [
            "Ultra RPM values can show apparent negative RPM during "
            "backward whirl — this is a real dynamic condition, not a "
            "measurement error.",
            "Real-time ultra RPM is typically heavily averaged — only "
            "memory data shows true high-frequency dynamics.",
        ],
    },

    "0762": {
        "canonical": "downlink",
        "mnemonic": "DLINK",
        "units": "code",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Downlink command status — indicates whether a command has "
            "been sent from surface to the MWD/directional tool via "
            "mud pulse or flow-rate modulation (downlinking). Tracks "
            "communication from surface to downhole."
        ),
        "physical_phenomenon": (
            "Communication channel from surface to downhole tool. "
            "Commands are sent by modulating pump flow rate or pressure "
            "in a coded sequence that the downhole tool interprets. "
            "This channel records the status of that communication."
        ),
        "trust_conditions": (
            "Trust as an operational status indicator. A successful "
            "downlink should be confirmed by the tool's response "
            "(change in steering behavior or acknowledgment in uplink "
            "data)."
        ),
        "common_misinterpretations": [
            "A sent downlink is not a confirmed downlink — the tool "
            "must acknowledge receipt before assuming the command was "
            "received.",
            "Downlink sequences require specific flow rate patterns — "
            "operational disruptions during downlinking can cause "
            "partial or failed commands.",
        ],
    },

    "0763": {
        "canonical": "possum",
        "mnemonic": "POSSUM",
        "units": "code",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Position summary — a vendor-specific encoded summary of "
            "the directional tool's current position and operational "
            "state. Typically a composite code combining multiple "
            "downhole parameters into a single status word."
        ),
        "physical_phenomenon": (
            "Composite status encoding from the MWD tool's telemetry "
            "system. Packs multiple pieces of downhole information "
            "(toolface, status flags, mode) into a single transmission "
            "to conserve telemetry bandwidth."
        ),
        "trust_conditions": (
            "Trust when decoded according to the specific tool vendor's "
            "encoding scheme. Raw code values are meaningless without "
            "the vendor's decoding documentation."
        ),
        "common_misinterpretations": [
            "POSSUM encoding is vendor-specific — the same numeric "
            "code means completely different things for different "
            "MWD tool platforms.",
            "Treating POSSUM as a simple numeric value rather than "
            "a bit-packed status word leads to nonsensical analysis.",
        ],
    },

    "0764": {
        "canonical": "gv7",
        "mnemonic": "GV7",
        "units": "code",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Vendor-specific channel — typically a diagnostic or "
            "status code from the directional tool system. Meaning "
            "depends on the specific MWD/RSS tool platform in use."
        ),
        "physical_phenomenon": (
            "Vendor-specific encoding — may represent tool health "
            "diagnostics, configuration state, or operational mode "
            "flags. Requires vendor documentation for interpretation."
        ),
        "trust_conditions": (
            "Trust only when the vendor documentation for the specific "
            "tool in use is available to decode the values. Without "
            "context, this channel cannot be meaningfully interpreted."
        ),
        "common_misinterpretations": [
            "Vendor-specific channel — generic interpretation without "
            "knowing the specific tool platform will be incorrect.",
            "May contain packed bit-field data rather than a single "
            "scalar measurement.",
        ],
    },

    "0789": {
        "canonical": "continuous_azimuth",
        "mnemonic": "CAZI",
        "units": "deg",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.DEPTH_ONLY,
        "what_it_measures": (
            "Continuous azimuth measured by the MWD tool while drilling. "
            "Unlike stationary survey azimuth, this provides azimuth "
            "estimates during rotation and drilling, but at lower "
            "accuracy."
        ),
        "physical_phenomenon": (
            "Magnetic azimuth derived from magnetometer readings during "
            "drillstring rotation. The tool uses rotation-averaged "
            "magnetometer data to extract the wellbore azimuth even "
            "while rotating, unlike stationary surveys that require "
            "the tool to be still."
        ),
        "trust_conditions": (
            "Trust as a trend indicator with lower accuracy than "
            "stationary surveys. Continuous azimuth during rotation is "
            "inherently noisier and less accurate than a properly "
            "quality-checked survey station."
        ),
        "common_misinterpretations": [
            "Continuous azimuth is an estimate, not a survey-quality "
            "measurement — do not use it for wellbore position "
            "calculations or anti-collision analysis.",
            "Same magnetic interference susceptibility as stationary "
            "azimuth, but with less ability to quality-check because "
            "the tool is moving.",
        ],
    },

    "0790": {
        "canonical": "continuous_inclination",
        "mnemonic": "CINC",
        "units": "deg",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.DEPTH_ONLY,
        "what_it_measures": (
            "Continuous inclination measured by the MWD tool while "
            "drilling. Provides real-time inclination trend between "
            "survey stations, used by the directional driller to "
            "monitor trajectory during drilling."
        ),
        "physical_phenomenon": (
            "Wellbore inclination derived from accelerometer readings "
            "during drillstring rotation. The tool uses rotation-averaged "
            "gravity sensor data to estimate inclination while drilling."
        ),
        "trust_conditions": (
            "Trust as a trend indicator between survey stations. More "
            "accurate than continuous azimuth because it relies on "
            "gravity (not magnetic) reference, but still less accurate "
            "than stationary surveys due to vibration and dynamics."
        ),
        "common_misinterpretations": [
            "Continuous inclination during drilling is a trend tool, "
            "not a survey replacement — use stationary surveys for "
            "wellbore position calculations.",
            "Vibration during drilling adds noise to the inclination "
            "signal — smoothing or filtering is needed for trend "
            "analysis.",
        ],
    },

    # ── Record 08: Gamma / formation evaluation ──────────────────

    "0821": {
        "canonical": "gamma_depth",
        "mnemonic": "GDEP",
        "units": "ft",
        "physics_domain": PhysicsDomain.DEPTH,
        "index_type": IndexType.DEPTH_ONLY,
        "what_it_measures": (
            "Depth reference for gamma ray measurements — the measured "
            "depth at which the gamma ray reading was acquired. "
            "Accounts for the offset between the gamma sensor position "
            "and the bit."
        ),
        "physical_phenomenon": (
            "Computed depth index that places the gamma ray measurement "
            "at its correct formation depth by applying the known "
            "offset between the gamma sensor and the bit in the BHA."
        ),
        "trust_conditions": (
            "Trust when the BHA offset is correctly configured in the "
            "data acquisition system. Incorrect sensor offset produces "
            "systematic depth errors in all gamma data."
        ),
        "common_misinterpretations": [
            "Gamma depth is not bit depth — it is offset from bit depth "
            "by the distance between the gamma sensor and the bit in "
            "the BHA string.",
            "If the BHA is changed and the offset is not updated, all "
            "subsequent gamma depth values will be systematically wrong.",
        ],
    },

    "0822": {
        "canonical": "survey_depth",
        "mnemonic": "SDEP",
        "units": "ft",
        "physics_domain": PhysicsDomain.DEPTH,
        "index_type": IndexType.DEPTH_ONLY,
        "what_it_measures": (
            "Depth at which a directional survey was taken — the "
            "measured depth of the MWD survey tool when the survey "
            "was recorded. This is the depth reference for survey "
            "inclination and azimuth values."
        ),
        "physical_phenomenon": (
            "Measured depth of the MWD survey sensor at the time of "
            "survey recording. Calculated from bit depth minus the "
            "known distance from bit to survey sensor in the BHA."
        ),
        "trust_conditions": (
            "Trust when pipe tally is accurate and the BHA sensor "
            "offset is correctly configured. Survey depth errors "
            "propagate to all wellbore position calculations derived "
            "from that survey station."
        ),
        "common_misinterpretations": [
            "Survey depth is at the survey sensor, not at the bit — "
            "the bit is always deeper than the survey point by the "
            "BHA offset.",
            "Pipe stretch and compression affect the actual depth of "
            "the sensor, which may differ from the rigid pipe-tally "
            "calculation.",
        ],
    },

    "0824": {
        "canonical": "gamma_ray_mwd",
        "mnemonic": "GRMWD",
        "units": "gAPI",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.BRIDGES_BOTH,
        "what_it_measures": (
            "Gamma ray measurement from the MWD tool — may be a "
            "redundant or differently processed version of the primary "
            "gamma ray (0722). Some systems transmit gamma through "
            "different data records for logging purposes."
        ),
        "physical_phenomenon": (
            "Same natural radioactive decay measurement as primary "
            "gamma ray. Differences between this and 0722 may arise "
            "from different processing (windowing, filtering), "
            "different sensors in the BHA, or different telemetry "
            "paths."
        ),
        "trust_conditions": (
            "Trust with the same caveats as primary gamma ray — "
            "sensitive to ROP (counting statistics degrade at high "
            "drilling rates) and borehole conditions. Cross-reference "
            "with primary gamma for consistency."
        ),
        "common_misinterpretations": [
            "May not be an independent measurement from primary gamma "
            "ray — could be the same sensor routed through a different "
            "data record.",
            "Different processing or windowing parameters can make this "
            "channel look different from primary gamma even when "
            "measuring the same formation.",
        ],
    },

    "0826": {
        "canonical": "gamma_2",
        "mnemonic": "GR2",
        "units": "gAPI",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.BRIDGES_BOTH,
        "what_it_measures": (
            "Secondary gamma ray measurement — may represent a second "
            "gamma detector in the BHA, an azimuthal gamma sector, or "
            "a differently filtered version of the primary gamma."
        ),
        "physical_phenomenon": (
            "Natural gamma ray emission detection. If from a second "
            "detector, provides redundancy or azimuthal information. "
            "If filtered differently, may emphasize different aspects "
            "of the gamma response (e.g., longer averaging window)."
        ),
        "trust_conditions": (
            "Trust when the source of this channel is understood — "
            "is it a second detector, an azimuthal sector, or a "
            "reprocessed version of the primary? Each has different "
            "interpretation requirements."
        ),
        "common_misinterpretations": [
            "Assuming this is always a second independent detector — "
            "it may be the same sensor with different processing.",
            "If azimuthal, this represents gamma from one side of the "
            "borehole only, not the full circumferential average.",
        ],
    },

    "0827": {
        "canonical": "gamma_memory",
        "mnemonic": "GRMEM",
        "units": "gAPI",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.BRIDGES_BOTH,
        "what_it_measures": (
            "Gamma ray from memory data — the full-resolution gamma "
            "ray recorded in the MWD tool's downhole memory. Higher "
            "resolution and higher fidelity than real-time telemetered "
            "gamma because it is not limited by telemetry bandwidth."
        ),
        "physical_phenomenon": (
            "Same natural radioactivity measurement as real-time gamma, "
            "but recorded at the tool's native sampling rate rather "
            "than the decimated rate required for mud pulse telemetry."
        ),
        "trust_conditions": (
            "Trust as the highest-fidelity gamma measurement available. "
            "Only accessible after the tool is pulled out of hole and "
            "the memory is downloaded — not available in real-time "
            "during drilling."
        ),
        "common_misinterpretations": [
            "Memory gamma is not available in real-time — it can only "
            "be used for post-run analysis after memory download.",
            "Memory gamma may show features that were smoothed out or "
            "missed in the real-time gamma due to telemetry compression.",
        ],
    },

    "0836": {
        "canonical": "temperature",
        "mnemonic": "TEMP",
        "units": "degF",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.BRIDGES_BOTH,
        "what_it_measures": (
            "Downhole temperature measured by the MWD tool. Reflects "
            "the temperature at the tool's position in the wellbore, "
            "which is influenced by formation temperature, drilling "
            "fluid circulation, and the thermal history of the "
            "wellbore."
        ),
        "physical_phenomenon": (
            "Temperature at the MWD sensor depth, representing a "
            "mix of formation geothermal temperature and the cooling "
            "effect of circulating drilling fluid. The wellbore "
            "temperature profile approaches the geothermal gradient "
            "only after extended shut-in time."
        ),
        "trust_conditions": (
            "Trust as a relative measurement that tracks thermal "
            "trends. During circulation, the measured temperature is "
            "lower than true formation temperature due to cooling by "
            "the drilling fluid. The temperature increases toward "
            "formation temperature during shut-in periods."
        ),
        "common_misinterpretations": [
            "Downhole temperature while circulating is NOT formation "
            "temperature — circulation cools the wellbore below the "
            "geothermal gradient.",
            "Temperature trends during drilling reflect a combination "
            "of increasing depth (hotter) and circulation cooling — "
            "separating these effects requires modeling.",
            "MWD tool temperature limits exist — approaching the tool "
            "rating requires operational awareness but may not show "
            "up as a channel alarm.",
        ],
    },

    "0859": {
        "canonical": "rss_inclination",
        "mnemonic": "RSSINC",
        "units": "deg",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.DEPTH_ONLY,
        "what_it_measures": (
            "Inclination as measured or reported by a rotary steerable "
            "system (RSS). May represent the RSS tool's own inclination "
            "measurement used for its steering control loop, which can "
            "differ from the MWD survey inclination."
        ),
        "physical_phenomenon": (
            "Wellbore inclination from gravity measurements internal "
            "to the RSS tool. The RSS uses its own sensors for "
            "closed-loop steering — these may be at a different BHA "
            "position than the MWD survey sensors."
        ),
        "trust_conditions": (
            "Trust as the RSS tool's internal inclination reference. "
            "Cross-reference with MWD survey inclination — differences "
            "indicate sensor offset or calibration issues between the "
            "two tool systems."
        ),
        "common_misinterpretations": [
            "RSS inclination may differ from MWD inclination due to "
            "different sensor positions in the BHA — this is normal "
            "in a building or dropping section.",
            "The RSS uses this value for its steering loop — if it "
            "differs significantly from MWD surveys, the tool may "
            "be steering to the wrong target.",
        ],
    },

    "0860": {
        "canonical": "rss_toolface",
        "mnemonic": "RSSTF",
        "units": "deg",
        "physics_domain": PhysicsDomain.MWD,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Toolface orientation as reported by the RSS — the "
            "direction the RSS steering mechanism is pointing relative "
            "to the high side of the wellbore. Used to verify the RSS "
            "is steering in the intended direction."
        ),
        "physical_phenomenon": (
            "Steering vector orientation from the RSS tool's internal "
            "control system. The RSS continuously adjusts pad pressure "
            "or shaft offset to steer the wellbore; this channel "
            "reports the current steering direction."
        ),
        "trust_conditions": (
            "Trust as the RSS tool's reported steering direction. "
            "Compare with planned toolface and observed trajectory "
            "changes to verify the tool is performing as commanded."
        ),
        "common_misinterpretations": [
            "RSS toolface is where the tool is pushing, not necessarily "
            "where the wellbore is going — formation anisotropy and "
            "bit walk can cause the wellbore to deviate from the "
            "steering direction.",
            "The relationship between steering toolface and resulting "
            "trajectory depends on the specific RSS technology — "
            "push-the-bit and point-the-bit systems respond differently.",
        ],
    },

    "0861": {
        "canonical": "drpm",
        "mnemonic": "DRPM",
        "units": "rpm",
        "physics_domain": PhysicsDomain.MECHANICAL,
        "index_type": IndexType.TIME_ONLY,
        "what_it_measures": (
            "Downhole RPM measured by the directional tool system. "
            "Represents actual BHA rotational speed, distinct from "
            "surface RPM. Captures stick-slip dynamics and motor-"
            "added RPM."
        ),
        "physical_phenomenon": (
            "Angular velocity at the directional tool position in the "
            "BHA. Total bit RPM is this value plus any motor RPM. "
            "Stick-slip oscillations cause this value to fluctuate "
            "around surface RPM."
        ),
        "trust_conditions": (
            "Trust as a downhole measurement of actual BHA rotation. "
            "Real-time values may be averaged; memory data provides "
            "full dynamic resolution. Valid during rotation — "
            "meaningless during slide mode unless motor is turning."
        ),
        "common_misinterpretations": [
            "Downhole RPM does not equal surface RPM — stick-slip "
            "causes significant differences, especially in hard "
            "formations or high-angle wells.",
            "During slide mode, downhole RPM should be zero (no "
            "surface rotation) — any measured RPM during slide may "
            "indicate the string is still partially rotating.",
        ],
    },
}


# ── Public API ───────────────────────────────────────────────────────


def get_vocabulary_entry(wits_id: str) -> Optional[VocabEntry]:
    """Return the vocabulary entry for a WITS ID, or None if not found."""
    return _VOCABULARY.get(wits_id)


def has_vocabulary(wits_id: str) -> bool:
    """Return True if the WITS ID has a vocabulary entry."""
    return wits_id in _VOCABULARY


def all_vocabulary_ids() -> List[str]:
    """Return all WITS IDs that have vocabulary entries."""
    return list(_VOCABULARY.keys())
