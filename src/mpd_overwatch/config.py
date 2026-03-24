"""MPD Command - Configuration"""

APP_NAME = "MPD Command"
APP_VERSION = "0.4.0"
APP_TITLE = "MPD Command | Managed Pressure Drilling Operations Platform"

# Visual theme colors (dark command-center aesthetic)
COLORS = {
    "background": "#0a0e17",
    "card": "#131a2b",
    "card_border": "#1e2d4a",
    "primary": "#00d4ff",      # Electric cyan
    "secondary": "#ff6b35",    # Alert orange
    "success": "#00ff88",      # Signal green
    "warning": "#ffd700",      # Gold warning
    "danger": "#ff4757",       # Red danger
    "text": "#e2e8f0",         # Light gray
    "text_muted": "#8892a4",   # Muted gray
    "text_dim": "#4a5568",     # Dim text
    "pore_pressure": "#ff6b35",    # Orange for pore pressure
    "frac_gradient": "#ff4757",    # Red for fracture gradient
    "mud_weight": "#00d4ff",       # Cyan for mud weight
    "ecd": "#ffd700",              # Gold for ECD
    "mpd_window": "rgba(0, 212, 255, 0.15)",  # Translucent cyan
    "conv_window": "rgba(255, 107, 53, 0.10)",  # Translucent orange
    # Provenance badge colors
    "badge_measured": "#2aaa66",
    "badge_survey": "#e8a840",
    "badge_derived": "#4a9eff",
    "badge_modeled": "#c084fc",
    "badge_computed": "#2dd4bf",
}

# Default Delaware Basin parameters
DEFAULTS = {
    "basin": "Delaware Basin",
    "formation": "Wolfcamp A",
    "pore_pressure_gradient": 0.60,    # psi/ft (overpressured)
    "fracture_gradient": 0.85,          # psi/ft
    "conventional_mud_weight": 13.0,    # ppg
    "mpd_mud_weight": 11.5,             # ppg
    "mpd_sbp_range": (50, 300),         # psi surface back pressure
    "conventional_overbalance": 500,    # psi typical
    "mpd_overbalance": 50,              # psi typical
    "lateral_length": 10000,            # ft
    "total_depth_tvd": 10500,           # ft
    "total_depth_md": 20500,            # ft
}

# Zone intelligence thresholds
ZONE_THRESHOLDS = {
    "gamma_low": 0.85,           # fraction of baseline = "clean" rock
    "gamma_high": 1.15,          # fraction of baseline = shale
    "apwd_deviation_psi": 200,   # psi deviation triggers flag
    "ecd_deviation_ppg": 0.2,    # ppg deviation triggers flag
    "flow_discrepancy_pct": 5,   # % flow in/out mismatch
    "rop_spike_factor": 1.5,     # ROP > 1.5x baseline = spike
    "rop_drop_factor": 0.5,      # ROP < 0.5x baseline = drop
    "connection_swab_psi": 100,  # psi drop on connection = risk
}

# Page routing — matches tab structure in app.py NAV_SECTIONS
PAGES = {
    # Entry points (always accessible)
    "/": "File Manager",
    "/files": "File Manager",
    "/channels": "Channel Selector",
    # OPERATIONS
    "/well-overview": "Well Overview",
    "/hmu": "HMU Cockpit",
    "/supervisory": "Supervisory",
    # ANALYSIS
    "/hydraulics": "Hydraulics",
    "/geomechanics": "Geomechanics",
    "/pore-pressure": "Pore Pressure",
    "/formation-damage": "Formation Damage",
    # TOPOLOGY
    "/topology": "Coherence Log",
    "/atft": "ATFT Engine",
    "/persistent-homology": "Persistent Homology",
    # ENGINEERING
    "/formulas": "Formula Verifier",
    "/vv-report": "V&V Report",
    "/controls": "Controls",
    "/pipeline-results": "Pipeline Results",
}

# Vendor mnemonic mapping — single authoritative source for all code paths.
# Covers Sperry, Halliburton, SLB, Pason, Totco, and common LAS mnemonics.
MNEMONIC_MAP = {
    # ---- Depth ----
    "DEPT": "depth_md", "DEPTH": "depth_md", "MD": "depth_md",
    "DMEA": "depth_md", "TDEP": "depth_md",
    "Hole.ft": "depth_md", "Hole": "depth_md",
    "NOMD": "depth_md",  # Pason nominal depth
    "BDEP": "bit_depth", "HDEP": "hole_depth",
    "TVD": "tvd", "TVDSS": "tvd", "DTVD": "tvd", "TVDE": "tvd",
    "MTTVD": "tvd", "TVD.ft": "tvd",
    "BTVD": "bit_tvd", "HTVD": "hole_tvd",
    # ---- Pressure ----
    "SPP": "spp", "SPPA": "spp", "SPP I": "spp",
    "PUMP_PRESS": "spp", "Pump.psi": "spp", "Pump Pressure": "spp",
    "APRS": "apwd", "APWD": "apwd",
    "ECD": "ecd", "ECDA": "ecd",
    "PCAS": "casing_pressure",
    "DIFF": "differential_pressure", "Diff.psi": "differential_pressure",
    "CHOKE_PRESS": "choke_pressure", "SBP": "choke_pressure", "ABP": "choke_pressure",
    "BHP": "bhp",
    # ---- Drilling mechanics ----
    "ROP": "rop", "ROP5": "rop", "ROPA": "rop", "MROP": "rop",
    "OBR": "rop", "ROP.FT/HR": "rop",
    "WOB": "wob", "WOBX": "wob", "SWOB": "wob", "Bit.klb": "wob",
    "BIT": "wob",  # Pason bit weight
    "TQA": "torque", "TRQ": "torque", "TORQUE": "torque", "STOR": "torque",
    "TOR": "torque", "Rota.A": "torque", "Top.ft-lbf": "torque",
    "ROTA": "rpm",  # Pason rotary (RPM variant; torque variant uses :N suffix)
    "RPM": "rpm", "RPMA": "rpm", "SRPM": "rpm",
    "RPM_P": "rpm", "Rota.RPM": "rpm", "Top.RPM": "rpm",
    "TOP": "rpm",  # Pason top drive RPM
    "HKLA": "hookload", "HOOKLOAD": "hookload", "HKL": "hookload",
    "HKLD": "hookload", "HKL I": "hookload", "HL": "hookload",
    "Hook.klb": "hookload", "HOOK": "hookload",  # Pason hookload
    "BPOS": "block_position", "BLOC": "block_position",  # Pason block
    # ---- Flow ----
    "FLOW": "flow_out_pct", "Flow.%": "flow_out_pct",
    "FLOWIN": "flow_in", "FLOW_IN": "flow_in", "MFIA": "flow_in",
    "TPO": "flow_in", "Flow.galUS/min": "flow_in",
    "FLOWOUT": "flow_out", "FLOW_OUT": "flow_out", "MFOA": "flow_out",
    "Mud.bbl": "mud_volume", "MV": "mud_volume",
    "MUD": "mud_weight",  # Pason mud weight (lb/galUS variant)
    # ---- MWD / Gamma ray ----
    "GR": "gamma_ray", "GRC": "gamma_ray", "GRC_P": "gamma_ray",
    "GR_EDRC": "gamma_ray", "GR_ARC": "gamma_ray", "SGR": "gamma_ray",
    "CGR": "gamma_ray", "HCGR": "gamma_ray", "ECGR": "gamma_ray",
    "GREXT": "gamma_ray",
    # ---- Directional survey ----
    "INC": "inclination", "INC_P": "inclination", "INCL": "inclination",
    "DINC_P": "delta_inclination",
    "DAZM_P": "azimuth", "AZM_P": "azimuth", "AZIM": "azimuth",
    "DLS": "dls",
    "DTF": "toolface",
    # ---- Temperature ----
    "TLTS": "temperature", "DTEMP": "temperature", "TEMP": "temperature",
    "TTEM": "temperature", "TEMPG": "temperature_gradient",
    # ---- Mud weight ----
    "Mud.lb/galUS": "mud_weight",
    # ---- Petrophysics (informational — kept in dataframe for formation eval) ----
    "RHOB": "bulk_density", "RHOZ": "bulk_density", "ZDEN": "bulk_density",
    "NPHI": "neutron_porosity", "TNPH": "neutron_porosity", "NPOR": "neutron_porosity",
    "RT": "resistivity_deep", "ILD": "resistivity_deep", "LLD": "resistivity_deep",
    "AT90": "resistivity_deep", "RD": "resistivity_deep",
    "RS": "resistivity_shallow", "ILM": "resistivity_shallow", "LLS": "resistivity_shallow",
    "AT10": "resistivity_shallow",
    # ---- Timestamps ----
    "DateTime": "timestamp", "DateTime.S": "timestamp",
}
