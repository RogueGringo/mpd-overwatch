"""MPD Command - Semantic Prime Language System

Generates factual, physics-only text for the UI.
No adjectives. No claims. Only measurements, equations, and relationships.

Semantic Prime = E-Prime-style technical language where every statement
is either a measurement, a calculation, or a physical relationship.

Examples:
  YES: "BHP: 6,480 psi at 10,500 ft TVD"
  NO:  "Excellent bottom-hole pressure management"

  YES: "ECD exceeds fracture gradient by 0.3 ppg at 10,200 ft"
  NO:  "Critical ECD warning detected"

  YES: "Cluster efficiency: 0.90 (225/250 clusters contributing)"
  NO:  "High-performance cluster activation achieved"
"""


def measurement(name: str, value, unit: str, context: str = "") -> str:
    """Format a measurement statement."""
    if isinstance(value, float):
        if abs(value) >= 1000:
            text = f"{name}: {value:,.1f} {unit}"
        elif abs(value) >= 1:
            text = f"{name}: {value:.2f} {unit}"
        else:
            text = f"{name}: {value:.4f} {unit}"
    else:
        text = f"{name}: {value} {unit}"
    if context:
        text += f" ({context})"
    return text


def equation(lhs: str, rhs: str, result=None, unit: str = "") -> str:
    """Format an equation statement."""
    text = f"{lhs} = {rhs}"
    if result is not None:
        text += f" = {result}"
        if unit:
            text += f" {unit}"
    return text


def relationship(a_name: str, a_value, operator: str,
                 b_name: str, b_value, consequence: str = "") -> str:
    """Format a physical relationship statement."""
    text = f"{a_name} ({a_value}) {operator} {b_name} ({b_value})"
    if consequence:
        text += f" -> {consequence}"
    return text


def delta(name: str, before, after, unit: str = "") -> str:
    """Format a change/delta statement."""
    diff = after - before if isinstance(after, (int, float)) else "N/A"
    if isinstance(diff, (int, float)):
        sign = "+" if diff >= 0 else ""
        return f"{name}: {before} -> {after} {unit} ({sign}{diff} {unit})"
    return f"{name}: {before} -> {after} {unit}"


def ratio(name: str, numerator, denominator, unit_num: str = "",
          unit_den: str = "") -> str:
    """Format a ratio statement."""
    if isinstance(numerator, (int, float)) and isinstance(denominator, (int, float)):
        if denominator != 0:
            r = numerator / denominator
            return f"{name}: {numerator} {unit_num} / {denominator} {unit_den} = {r:.3f}"
    return f"{name}: {numerator} {unit_num} / {denominator} {unit_den}"


def condition(parameter: str, value, operator: str,
              threshold, unit: str = "", status: str = "") -> str:
    """Format a condition check statement."""
    text = f"{parameter}: {value} {unit} {operator} {threshold} {unit}"
    if status:
        text += f" [{status}]"
    return text


def layer_label(level: int) -> str:
    """Return the semantic label for an abstraction layer."""
    labels = {
        0: "Measurement",
        1: "Calculation",
        2: "Topology",
        3: "Classification",
    }
    return labels.get(level, f"Layer {level}")


def layer_description(level: int) -> str:
    """Return the factual description for an abstraction layer."""
    descriptions = {
        0: "Sensor readings indexed by depth and time. Units as recorded.",
        1: "Physical quantities derived from measurements via published equations.",
        2: "Structural features extracted from the 4D point cloud via spectral analysis.",
        3: "Depth intervals classified by multi-channel correlation patterns.",
    }
    return descriptions.get(level, "")


# Page titles in semantic prime (factual, no adjectives)
PAGE_TITLES = {
    "overview": "Well Status and Computed Metrics",
    "pressure_window": "Pressure vs Depth: Pore Pressure, Fracture Gradient, BHP",
    "zone_analysis": "Channel Correlation by Depth Interval",
    "mpd_vs_conventional": "Parameter Comparison: MPD and Conventional Methods",
    "production_impact": "Production Rate and EUR Computation",
    "completion_optimizer": "Stage Placement from Formation Data",
    "geomechanics": "MSE, UCS, and Brittleness by Measured Depth",
    "data_import": "File Inventory and Channel Mapping",
    "proposal": "MPD Value Computation for Target Well",
    "well_comparison": "Drilling Parameter Comparison: Two Wells",
    "hmu": "Pressure and Flow Measurements: Choke Operator",
    "supervisory": "Trend Data and Computed Intervals: Supervisor",
    "vv_report": "Verification Benchmarks: Expected vs Computed",
    "topology": "Point Cloud Topology: Coherence and Persistence",
}


# Status descriptions (factual)
STATUS_LABELS = {
    "within_window": "BHP between pore pressure and fracture gradient",
    "near_frac": "ECD within 0.3 ppg of fracture gradient",
    "near_pp": "BHP within 50 psi of pore pressure",
    "flow_balanced": "flow_out / flow_in between 0.95 and 1.05",
    "flow_loss": "flow_out / flow_in below 0.95",
    "flow_gain": "flow_out / flow_in above 1.05",
    "connection": "Pumps off. SBP compensating for AFP loss.",
    "drilling": "Pumps on. Circulating at target parameters.",
}
