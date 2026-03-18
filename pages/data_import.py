"""MPD Command - Data Import & Validation Page

Allows users to load real well data from LAS files and see
immediate quality analysis, curve inventory, and validation results.
"""

import sys
import os
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc

from config import COLORS


def page_data_import():
    """Render the data import and validation page."""

    # Scan for available LAS files in the example data directory
    data_dirs = [
        os.path.join("..", "DATA_TYPES_for_System_Use_EXAMPLES"),
        os.path.join("..", "DATA_TYPES_for_System_Use_EXAMPLES", "Misc-LAS"),
        os.path.join("..", "DATA_TYPES_for_System_Use_EXAMPLES",
                      "Historical_MWD_Data_Archives_Wells"),
    ]

    las_files = []
    for d in data_dirs:
        if os.path.exists(d):
            for pattern in ["*.las", "*.LAS"]:
                las_files.extend(glob.glob(os.path.join(d, "**", pattern), recursive=True))

    # Deduplicate and sort
    las_files = sorted(set(las_files))

    # Try loading a few files for preview
    loaded_wells = []
    from data.las_parser import LASParser
    parser = LASParser()

    for f in las_files[:8]:  # Load first 8 for preview
        try:
            result = parser.parse(f)
            df = result.to_dataframe()
            if len(df) > 0:
                fname = os.path.basename(f)
                n_rows = len(df)
                n_cols = len(df.columns)
                depth_col = df.columns[0]
                depth_min = df[depth_col].min()
                depth_max = df[depth_col].max()

                loaded_wells.append({
                    "file": fname,
                    "rows": n_rows,
                    "columns": n_cols,
                    "depth_range": f"{depth_min:.0f} - {depth_max:.0f} ft",
                    "curves": list(df.columns[:10]),
                    "df": df,
                })
        except Exception:
            continue

    # Build file inventory table
    file_rows = []
    for w in loaded_wells:
        file_rows.append(html.Tr([
            html.Td(w["file"][:50], style={"fontSize": "11px"}),
            html.Td(f"{w['rows']:,}"),
            html.Td(str(w["columns"])),
            html.Td(w["depth_range"]),
            html.Td(", ".join(w["curves"][:5]) + "...",
                    style={"fontSize": "10px", "color": COLORS["text_muted"]}),
        ]))

    file_table = html.Table([
        html.Thead(html.Tr([
            html.Th("File"), html.Th("Rows"), html.Th("Curves"),
            html.Th("Depth Range"), html.Th("Key Channels"),
        ])),
        html.Tbody(file_rows),
    ], className="comparison-table") if file_rows else html.P(
        "No LAS files found in DATA_TYPES_for_System_Use_EXAMPLES/",
        style={"color": COLORS["text_muted"]},
    )

    # If we have data, show a preview plot of the first loaded well
    preview_chart = html.Div()
    if loaded_wells:
        # Pick the well with the most columns (likely the richest dataset)
        best = max(loaded_wells, key=lambda w: w["columns"])
        df = best["df"]

        fig = make_subplots(rows=1, cols=min(4, len(df.columns) - 1),
                           shared_yaxes=True,
                           subplot_titles=[c[:15] for c in df.columns[1:5]])

        depth_col = df.columns[0]
        colors = [COLORS["success"], COLORS["primary"], COLORS["warning"], COLORS["secondary"]]

        for i, col in enumerate(df.columns[1:5]):
            vals = pd.to_numeric(df[col], errors="coerce")
            vals = vals.replace(-999.25, np.nan)
            fig.add_trace(go.Scatter(
                x=vals, y=df[depth_col],
                mode="lines", name=col,
                line=dict(color=colors[i % len(colors)], width=1),
            ), row=1, col=i + 1)

        fig.update_layout(
            paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
            font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
            height=500, margin=dict(l=60, r=20, t=40, b=40),
            showlegend=False,
        )
        for i in range(1, min(5, len(df.columns))):
            fig.update_xaxes(gridcolor=COLORS["card_border"], row=1, col=i)
        fig.update_yaxes(autorange="reversed", title="Depth (ft)",
                        gridcolor=COLORS["card_border"], row=1, col=1)

        preview_chart = html.Div([
            html.Div(f"PREVIEW: {best['file']}", className="card-header"),
            dcc.Graph(figure=fig, config={"displayModeBar": True}),
        ], className="card")

    return html.Div([
        html.Div([
            html.H1("Data Import & Validation"),
            html.P("Load real well data from LAS files for analysis and V&V cross-checking",
                   className="description"),
        ], className="page-header"),

        html.Div([
            _kpi("LAS Files Found", str(len(las_files)), "cyan"),
            _kpi("Successfully Loaded", str(len(loaded_wells)), "green"),
            _kpi("Total Data Points",
                 f"{sum(w['rows'] for w in loaded_wells):,}", "gold"),
            _kpi("Total Curves",
                 f"{sum(w['columns'] for w in loaded_wells):,}", "orange"),
        ], className="kpi-row"),

        html.Div([
            html.Div("LOADED WELL DATA FILES", className="card-header"),
            file_table,
        ], className="card"),

        preview_chart,

        html.Div([
            html.Div("DATA QUALITY NOTES", className="card-header"),
            html.Ul([
                html.Li("LAS v2.0 (space-delimited, depth & time-based): Fully supported",
                        style={"fontSize": "12px", "marginBottom": "4px"}),
                html.Li("LAS v3.0 (tab-delimited, TOTCO/Pason): Supported for standard sizes",
                        style={"fontSize": "12px", "marginBottom": "4px"}),
                html.Li("Survey data (CSV, 3-column): Supported",
                        style={"fontSize": "12px", "marginBottom": "4px"}),
                html.Li("Null values (-999.25) automatically filtered in visualizations",
                        style={"fontSize": "12px", "marginBottom": "4px"}),
                html.Li(f"Vendor mnemonic mapping: 40+ curve name aliases recognized",
                        style={"fontSize": "12px"}),
            ], style={"listStyle": "none", "padding": 0, "color": COLORS["text_muted"]}),
        ], className="card"),
    ])


def _kpi(label, value, color, delta=None):
    children = [
        html.Div(label, className="kpi-label"),
        html.Div(str(value), className=f"kpi-value {color}"),
    ]
    if delta:
        children.append(html.Div(delta, className="kpi-delta positive"))
    return html.Div(children, className="kpi-card")
