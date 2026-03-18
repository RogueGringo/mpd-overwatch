"""MPD Command - Synthetic Demo Data Generator

Generates realistic Delaware Basin Wolfcamp well data for demonstration purposes.
All values based on published literature and training materials.
"""

import numpy as np
import pandas as pd


def generate_demo_well_data() -> dict:
    """Generate a complete synthetic Delaware Basin Wolfcamp horizontal well dataset.

    Returns dict with:
        - well_info: basic well metadata
        - survey: directional survey (MD, TVD, inclination)
        - pressure_profile: pore pressure and fracture gradient vs depth
        - drilling_data: EDR + MWD data along the lateral
        - conventional_comparison: what conventional drilling would look like
    """
    np.random.seed(42)

    well_info = {
        "well_name": "Hensley 1-24H",
        "operator": "Precision MPD Operations LLC",
        "field": "Red Hills",
        "basin": "Delaware Basin",
        "county": "Reeves",
        "state": "Texas",
        "api_number": "42-389-12345",
        "spud_date": "2026-01-15",
        "formation": "Wolfcamp A",
        "total_depth_md": 20500,
        "total_depth_tvd": 10500,
        "lateral_length": 10000,
        "kick_off_point_md": 10200,
        "kick_off_point_tvd": 10200,
        "landing_point_md": 10500,
        "landing_point_tvd": 10500,
    }

    # --- Directional Survey ---
    # Vertical section: 0 to 10200 ft MD = 10200 ft TVD
    # Build section: 10200-10500 ft MD, TVD stays ~10500
    # Lateral: 10500-20500 ft MD, TVD ~10500 ft (slight undulation)
    n_vertical = 50
    n_build = 10
    n_lateral = 200

    md_vertical = np.linspace(0, 10200, n_vertical)
    tvd_vertical = md_vertical.copy()
    inc_vertical = np.zeros(n_vertical)

    md_build = np.linspace(10200, 10500, n_build)
    tvd_build = np.linspace(10200, 10500, n_build)
    inc_build = np.linspace(0, 90, n_build)

    md_lateral = np.linspace(10500, 20500, n_lateral)
    # Slight TVD undulation in lateral (geosteering)
    tvd_lateral = 10500 + 15 * np.sin(np.linspace(0, 4 * np.pi, n_lateral)) + \
                  np.random.normal(0, 2, n_lateral)
    inc_lateral = 90 + np.random.normal(0, 0.5, n_lateral)

    survey = pd.DataFrame({
        "MD": np.concatenate([md_vertical, md_build, md_lateral]),
        "TVD": np.concatenate([tvd_vertical, tvd_build, tvd_lateral]),
        "Inclination": np.concatenate([inc_vertical, inc_build, inc_lateral]),
    })

    # --- Pressure Profile (vs TVD) ---
    tvd_profile = np.linspace(0, 12000, 120)
    # Pore pressure: overpressured Wolfcamp ~0.60 psi/ft
    pp_gradient = np.where(
        tvd_profile < 5000,
        0.465,  # normal above 5000 ft
        0.465 + (tvd_profile - 5000) / 20000 * 0.20  # ramps to ~0.60 at depth
    )
    pore_pressure_ppg = pp_gradient / 0.052

    # Fracture gradient: ~0.80-0.90 psi/ft
    fg_gradient = np.where(
        tvd_profile < 3000,
        0.75,
        0.75 + (tvd_profile - 3000) / 15000 * 0.15
    )
    frac_gradient_ppg = fg_gradient / 0.052

    pressure_profile = pd.DataFrame({
        "TVD": tvd_profile,
        "PP_gradient": pp_gradient,
        "FG_gradient": fg_gradient,
        "PP_ppg": pore_pressure_ppg,
        "FG_ppg": frac_gradient_ppg,
        "PP_psi": pp_gradient * tvd_profile,
        "FG_psi": fg_gradient * tvd_profile,
    })

    # --- Lateral Drilling Data (the main dataset) ---
    n_pts = 500  # data points along the lateral
    lat_md = np.linspace(10500, 20500, n_pts)
    lat_tvd = 10500 + 15 * np.sin(np.linspace(0, 4 * np.pi, n_pts)) + \
              np.random.normal(0, 2, n_pts)

    # Gamma Ray - varies to show lithology changes
    # Base Wolfcamp A gamma ~80-120 API, with shale stringers at 150+
    gamma_base = 90 + 20 * np.sin(np.linspace(0, 8 * np.pi, n_pts))
    # Add shale stringers (high gamma spikes)
    shale_zones = [50, 120, 180, 280, 350, 420]
    for sz in shale_zones:
        if sz < n_pts:
            width = np.random.randint(5, 15)
            gamma_base[sz:min(sz + width, n_pts)] += np.random.uniform(40, 80)
    gamma_ray = gamma_base + np.random.normal(0, 5, n_pts)
    gamma_ray = np.clip(gamma_ray, 20, 200)

    # ROP - varies with lithology (inverse correlation with gamma somewhat)
    rop_base = 120 - 0.3 * (gamma_ray - 80) + np.random.normal(0, 10, n_pts)
    # Add some ROP spikes (fractured zones)
    fractured_zones = [90, 210, 310, 460]
    for fz in fractured_zones:
        if fz < n_pts:
            rop_base[fz:min(fz + 8, n_pts)] += np.random.uniform(30, 60)
    rop = np.clip(rop_base, 30, 250)

    # APWD (Annular Pressure While Drilling) - psi
    # Base: hydrostatic at ~11.8 ppg + friction
    base_apwd = 0.052 * 11.8 * lat_tvd + 150  # hydrostatic + ~150 psi friction
    apwd_anomalies = np.zeros(n_pts)
    # Depleted zone (lower APWD)
    depleted_start, depleted_end = 150, 175
    apwd_anomalies[depleted_start:depleted_end] = -300

    # Overpressured zone (higher APWD)
    op_start, op_end = 250, 275
    apwd_anomalies[op_start:op_end] = 400

    # Loss zone (APWD drops)
    for fz in fractured_zones:
        if fz < n_pts:
            apwd_anomalies[fz:min(fz + 5, n_pts)] = -200

    apwd = base_apwd + apwd_anomalies + np.random.normal(0, 20, n_pts)

    # Choke pressure (MPD surface back pressure)
    choke_base = 150 + np.random.normal(0, 10, n_pts)
    # Increase choke in depleted zones, decrease in overpressured
    choke_base[depleted_start:depleted_end] += 200
    choke_base[op_start:op_end] -= 50
    choke_pressure = np.clip(choke_base, 0, 500)

    # Flow in/out (gpm) - should be nearly balanced with MPD
    flow_in = 650 + np.random.normal(0, 5, n_pts)
    flow_out = flow_in.copy() + np.random.normal(0, 3, n_pts)
    # Loss zones: flow out drops
    for fz in fractured_zones:
        if fz < n_pts:
            flow_out[fz:min(fz + 5, n_pts)] -= np.random.uniform(20, 50)
    # Influx in overpressured: flow out increases slightly
    flow_out[op_start:op_end] += np.random.uniform(5, 15)

    # WOB, torque, RPM
    wob = 25 + np.random.normal(0, 3, n_pts)  # klbs
    torque = 12000 + 2000 * np.sin(np.linspace(0, 6 * np.pi, n_pts)) + \
             np.random.normal(0, 500, n_pts)  # ft-lbs
    rpm = 120 + np.random.normal(0, 5, n_pts)
    spp = 3200 + np.random.normal(0, 80, n_pts)  # psi
    hookload = 280 + np.random.normal(0, 10, n_pts)  # klbs

    # Timestamps (simulate ~4 days of lateral drilling)
    start_time = pd.Timestamp("2026-02-10 06:00:00")
    timestamps = pd.date_range(start=start_time, periods=n_pts, freq="12min")

    drilling_data = pd.DataFrame({
        "MD": lat_md,
        "TVD": lat_tvd,
        "Gamma_Ray": gamma_ray,
        "ROP": rop,
        "APWD": apwd,
        "Choke_Pressure": choke_pressure,
        "Flow_In": flow_in,
        "Flow_Out": flow_out,
        "WOB": wob,
        "Torque": torque,
        "RPM": rpm,
        "SPP": spp,
        "Hookload": hookload,
        "Timestamp": timestamps,
    })

    # --- Conventional comparison metrics ---
    conventional = {
        "mud_weight_ppg": 13.0,
        "overbalance_psi": 500,
        "npt_days": 4.5,
        "mud_losses_bbl": 1200,
        "lcm_cost": 85000,
        "cement_remedial_cost": 120000,
        "rop_avg_fthr": 85,
        "drilling_days": 18,
        "ip_bopd": 950,
        "eur_boe": 580000,
        "skin_factor": 8.0,
        "total_well_cost": 8500000,
    }

    mpd_results = {
        "mud_weight_ppg": 11.8,
        "overbalance_psi": 50,
        "npt_days": 0.5,
        "mud_losses_bbl": 200,
        "lcm_cost": 5000,
        "cement_remedial_cost": 15000,
        "rop_avg_fthr": 115,
        "drilling_days": 13,
        "ip_bopd": 1250,
        "eur_boe": 720000,
        "skin_factor": 0.5,
        "mpd_service_cost": 150000,
        "total_well_cost": 7200000,
    }

    return {
        "well_info": well_info,
        "survey": survey,
        "pressure_profile": pressure_profile,
        "drilling_data": drilling_data,
        "conventional": conventional,
        "mpd": mpd_results,
    }


def generate_decline_curves(ip_conv: float = 950, ip_mpd: float = 1250,
                            di_conv: float = 0.08, di_mpd: float = 0.075,
                            b_conv: float = 1.2, b_mpd: float = 1.1,
                            months: int = 120) -> pd.DataFrame:
    """Generate hyperbolic decline curves for conventional vs MPD wells.

    Args:
        ip_conv: Initial production rate conventional (BOPD)
        ip_mpd: Initial production rate MPD (BOPD)
        di_conv: Initial decline rate conventional (1/month)
        di_mpd: Initial decline rate MPD (1/month)
        b_conv: Hyperbolic exponent conventional
        b_mpd: Hyperbolic exponent MPD
        months: Number of months to project

    Returns:
        DataFrame with monthly production rates and cumulative production
    """
    t = np.arange(1, months + 1)

    # Hyperbolic decline: q(t) = qi / (1 + b*Di*t)^(1/b)
    q_conv = ip_conv / (1 + b_conv * di_conv * t) ** (1 / b_conv)
    q_mpd = ip_mpd / (1 + b_mpd * di_mpd * t) ** (1 / b_mpd)

    # Cumulative (approximate by monthly sum * 30.4 days)
    cum_conv = np.cumsum(q_conv * 30.4)
    cum_mpd = np.cumsum(q_mpd * 30.4)

    return pd.DataFrame({
        "Month": t,
        "Q_Conventional_BOPD": q_conv,
        "Q_MPD_BOPD": q_mpd,
        "Cum_Conventional_BBL": cum_conv,
        "Cum_MPD_BBL": cum_mpd,
        "Delta_Monthly_BBL": (q_mpd - q_conv) * 30.4,
        "Delta_Cum_BBL": cum_mpd - cum_conv,
    })
