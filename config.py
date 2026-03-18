"""MPD Command - Configuration"""

APP_NAME = "MPD Command"
APP_VERSION = "0.3.0-beta"
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
    "rig_rate": 35000,                  # $/day
    "oil_price": 70,                    # $/bbl
    "gas_price": 3.50,                  # $/mcf
    "mpd_service_cost": 150000,         # $ per well (equipment + personnel)
    "conventional_eur": 600000,         # BOE baseline
    "conventional_ip": 1000,            # BOPD
    "cluster_efficiency_conventional": 0.70,
    "cluster_efficiency_mpd": 0.90,
    "stages": 50,
    "clusters_per_stage": 5,
    "npt_reduction_pct": 35,            # % NPT reduction with MPD
    "mud_loss_reduction_pct": 83,       # % mud loss reduction
    "rop_increase_pct": 35,             # % ROP improvement
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

# Page routing
PAGES = {
    "/": "Executive Overview",
    "/pressure-window": "Pressure Window Navigator",
    "/zone-analysis": "Zone Intelligence Map",
    "/mpd-vs-conventional": "MPD vs Conventional",
    "/production-impact": "Production Impact Calculator",
    "/completion-optimizer": "Completion Optimizer",
    "/hmu": "HMU Operator Panel",
    "/supervisory": "Supervisory Panel",
    "/vv-report": "V&V Benchmark Report",
}

# Vendor mnemonic mapping (from DATA_TYPES_for_System_Use_EXAMPLES analysis)
MNEMONIC_MAP = {
    # Depth
    "DEPT": "depth_md", "BDEP": "bit_depth", "HDEP": "hole_depth",
    "Hole.ft": "depth_md", "Hole": "depth_md",
    "MTTVD": "tvd", "BTVD": "bit_tvd", "HTVD": "hole_tvd",
    "TVD.ft": "tvd", "TVD": "tvd",
    # Pressure
    "SPPA": "spp", "SPP I": "spp", "SPP": "spp",
    "Pump.psi": "spp", "Pump Pressure": "spp",
    "APRS": "apwd", "PCAS": "casing_pressure",
    "Diff.psi": "differential_pressure",
    # Drilling mechanics
    "ROP": "rop", "OBR": "rop", "ROP.FT/HR": "rop",
    "HKLD": "hookload", "HKL I": "hookload", "HL": "hookload",
    "Hook.klb": "hookload",
    "SWOB": "wob", "WOB": "wob", "Bit.klb": "wob",
    "TQA": "torque", "TOR": "torque", "Rota.A": "torque",
    "Top.ft-lbf": "torque",
    "RPM": "rpm", "RPM_P": "rpm", "Rota.RPM": "rpm", "Top.RPM": "rpm",
    # Flow
    "FLOW": "flow_out_pct", "Flow.%": "flow_out_pct",
    "TPO": "flow_in", "Flow.galUS/min": "flow_in",
    "Mud.bbl": "mud_volume", "MV": "mud_volume",
    # MWD
    "GRC": "gamma_ray", "GRC_P": "gamma_ray", "GREXT": "gamma_ray",
    "INC": "inclination", "INC_P": "inclination",
    "DINC_P": "azimuth",
    "DTF": "toolface",
    "TLTS": "temperature", "DTEMP": "temperature",
    # Mud weight
    "Mud.lb/galUS": "mud_weight",
    # Timestamps
    "DateTime": "timestamp", "DateTime.S": "timestamp",
    "DATE": "date", "TIME": "time",
}
