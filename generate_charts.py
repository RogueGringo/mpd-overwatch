"""Generate publication-quality charts for the V&V report package."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import plotly.graph_objects as go
import plotly.io as pio
import numpy as np
from data.demo_generator import generate_demo_well_data, generate_decline_curves

C = {
    "bg": "#0a0e17", "card": "#131a2b", "cyan": "#00d4ff",
    "orange": "#ff6b35", "green": "#00ff88", "gold": "#ffd700",
    "red": "#ff4757", "text": "#e2e8f0", "muted": "#8892a4",
    "grid": "#1e2d4a",
}

data = generate_demo_well_data()
decline = generate_decline_curves()
outdir = "docs/vv_report"
os.makedirs(outdir, exist_ok=True)

def base_layout(title, h=500, w=900):
    return dict(
        title=dict(text=title, font=dict(color=C["text"], size=20)),
        paper_bgcolor=C["card"], plot_bgcolor=C["bg"],
        font=dict(color=C["muted"], family="Consolas", size=13),
        height=h, width=w, margin=dict(l=70, r=40, t=60, b=70),
    )


# 1. VALUE WATERFALL
items = ["NPT\nSaved", "Drilling\nDays", "Mud\nSaved", "LCM/Cement\nSaved",
         "EUR Uplift\nRevenue", "MPD\nCost", "NET\nVALUE"]
values = [140000, 175000, 30000, 185000, 9800000, -150000, 0]
values[-1] = sum(values[:-1])

fig = go.Figure(go.Waterfall(
    x=items, y=values,
    measure=["relative"] * 6 + ["total"],
    connector=dict(line=dict(color=C["grid"])),
    increasing=dict(marker=dict(color=C["green"])),
    decreasing=dict(marker=dict(color=C["red"])),
    totals=dict(marker=dict(color=C["cyan"])),
    textposition="outside",
    text=["${:,.0f}".format(v) for v in values],
    textfont=dict(color=C["text"], size=12),
))
fig.update_layout(**base_layout("MPD Value Composition - Delaware Basin Wolfcamp"))
fig.update_yaxes(title="Value ($)", gridcolor=C["grid"])
pio.write_image(fig, f"{outdir}/chart_01_value_waterfall.png", scale=2)
print("  chart_01_value_waterfall.png")


# 2. DECLINE CURVES
fig2 = go.Figure()
fig2.add_trace(go.Scatter(
    x=decline["Month"], y=decline["Q_Conventional_BOPD"],
    name="Conventional (950 IP)", mode="lines",
    line=dict(color=C["orange"], width=3),
    fill="tozeroy", fillcolor="rgba(255,107,53,0.12)",
))
fig2.add_trace(go.Scatter(
    x=decline["Month"], y=decline["Q_MPD_BOPD"],
    name="MPD Enhanced (1,250 IP)", mode="lines",
    line=dict(color=C["green"], width=3),
    fill="tozeroy", fillcolor="rgba(0,255,136,0.12)",
))
fig2.update_layout(**base_layout("Production Decline: Conventional vs MPD"))
fig2.update_xaxes(title="Months", gridcolor=C["grid"])
fig2.update_yaxes(title="Oil Rate (BOPD)", gridcolor=C["grid"])
fig2.update_layout(legend=dict(x=0.55, y=0.95, bgcolor="rgba(0,0,0,0)"))
pio.write_image(fig2, f"{outdir}/chart_02_decline_curves.png", scale=2)
print("  chart_02_decline_curves.png")


# 3. PRESSURE WINDOW
pp = data["pressure_profile"]
mask = pp["TVD"] > 500
depths = pp["TVD"][mask].values
pp_ppg = pp["PP_ppg"][mask].values
fg_ppg = pp["FG_ppg"][mask].values
bhp_mpd = pp_ppg + 0.3

fig3 = go.Figure()
fig3.add_trace(go.Scatter(x=pp_ppg, y=depths, name="Pore Pressure",
    line=dict(color=C["orange"], width=2)))
fig3.add_trace(go.Scatter(x=fg_ppg, y=depths, name="Fracture Gradient",
    line=dict(color=C["red"], width=2)))
fig3.add_trace(go.Scatter(x=pp_ppg, y=depths, showlegend=False,
    line=dict(color="rgba(0,0,0,0)")))
fig3.add_trace(go.Scatter(x=fg_ppg, y=depths, name="Safe Window",
    line=dict(color="rgba(0,0,0,0)"), fill="tonextx",
    fillcolor="rgba(0,212,255,0.06)"))
fig3.add_trace(go.Scatter(x=np.full_like(depths, 13.0), y=depths,
    name="Conv. MW 13.0 ppg", line=dict(color=C["orange"], width=2, dash="dash")))
fig3.add_trace(go.Scatter(x=bhp_mpd, y=depths,
    name="MPD BHP (Controlled)", line=dict(color=C["green"], width=3)))
fig3.update_layout(**base_layout("Wellbore Pressure Window - Wolfcamp A", h=700, w=800))
fig3.update_xaxes(title="Equivalent Mud Weight (ppg)", gridcolor=C["grid"], range=[7, 18])
fig3.update_yaxes(title="Depth (ft TVD)", gridcolor=C["grid"], autorange="reversed")
fig3.update_layout(legend=dict(x=0.55, y=0.02, bgcolor="rgba(0,0,0,0)", font=dict(size=11)))
pio.write_image(fig3, f"{outdir}/chart_03_pressure_window.png", scale=2)
print("  chart_03_pressure_window.png")


# 4. FORMATION DAMAGE
cats = ["Filtrate\nInvasion", "Solids\nPlugging", "Lost\nCirculation",
        "Induced\nFracturing", "Wellbore\nInstability", "Kick/Loss\nCycles"]
fig4 = go.Figure()
fig4.add_trace(go.Bar(x=cats, y=[8,7,8,7,6,8], name="Conventional",
    marker_color=C["orange"], opacity=0.85))
fig4.add_trace(go.Bar(x=cats, y=[2,2,1,1,2,1], name="MPD",
    marker_color=C["green"], opacity=0.85))
fig4.update_layout(**base_layout("Formation Damage Severity (1-10)", h=450))
fig4.update_layout(barmode="group")
fig4.update_yaxes(title="Severity", gridcolor=C["grid"], range=[0, 10])
fig4.update_layout(legend=dict(x=0.8, y=0.95, bgcolor="rgba(0,0,0,0)", font=dict(size=14)))
pio.write_image(fig4, f"{outdir}/chart_04_formation_damage.png", scale=2)
print("  chart_04_formation_damage.png")


# 5. CUMULATIVE PRODUCTION
fig5 = go.Figure()
fig5.add_trace(go.Scatter(
    x=decline["Month"], y=decline["Cum_Conventional_BBL"],
    name="Conventional EUR", mode="lines",
    line=dict(color=C["orange"], width=3),
))
fig5.add_trace(go.Scatter(
    x=decline["Month"], y=decline["Cum_MPD_BBL"],
    name="MPD EUR", mode="lines",
    line=dict(color=C["green"], width=3),
))
delta = decline["Cum_MPD_BBL"].iloc[-1] - decline["Cum_Conventional_BBL"].iloc[-1]
fig5.add_annotation(
    x=90,
    y=(decline["Cum_MPD_BBL"].iloc[-1] + decline["Cum_Conventional_BBL"].iloc[-1]) / 2,
    text="+{:,.0f} BOE".format(delta),
    font=dict(color=C["cyan"], size=20, family="Consolas"),
    showarrow=True, arrowcolor=C["cyan"], ax=0, ay=-50,
)
fig5.update_layout(**base_layout("Cumulative Production: 10-Year Comparison"))
fig5.update_xaxes(title="Months", gridcolor=C["grid"])
fig5.update_yaxes(title="Cumulative Oil (BBL)", gridcolor=C["grid"])
fig5.update_layout(legend=dict(x=0.05, y=0.95, bgcolor="rgba(0,0,0,0)", font=dict(size=13)))
pio.write_image(fig5, f"{outdir}/chart_05_cumulative_production.png", scale=2)
print("  chart_05_cumulative_production.png")


# 6. ROI GAUGE
fig6 = go.Figure(go.Indicator(
    mode="gauge+number",
    value=68,
    title=dict(text="Return on MPD Investment", font=dict(color=C["text"], size=18)),
    number=dict(font=dict(color=C["cyan"], size=60), suffix="x"),
    gauge=dict(
        axis=dict(range=[0, 100], tickcolor=C["muted"]),
        bar=dict(color=C["cyan"]),
        bgcolor=C["bg"],
        bordercolor=C["grid"],
        steps=[
            dict(range=[0, 10], color="rgba(255,71,87,0.2)"),
            dict(range=[10, 30], color="rgba(255,215,0,0.15)"),
            dict(range=[30, 100], color="rgba(0,255,136,0.1)"),
        ],
        threshold=dict(line=dict(color=C["green"], width=4), thickness=0.75, value=68),
    ),
))
fig6.update_layout(
    paper_bgcolor=C["card"], font=dict(color=C["muted"]),
    height=350, width=500, margin=dict(l=40, r=40, t=80, b=30),
)
pio.write_image(fig6, f"{outdir}/chart_06_roi_gauge.png", scale=2)
print("  chart_06_roi_gauge.png")


print("\nAll 6 charts generated.")
