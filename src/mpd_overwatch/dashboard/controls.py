"""MPD Command - GUI Calibration and Controls Page

Interactive calculation interface superseding CLI. Parameter inputs
with computed outputs displayed as measurements.

Language: semantic prime. No adjectives.
"""

from dash import html, dcc

from mpd_overwatch.config import COLORS


def page_controls():
    """Render the interactive controls page."""
    return html.Div([
        html.H2("Analysis Controls", style={"marginBottom": "8px"}),
        html.P(
            "Adjust parameters. Computed outputs update on submission.",
            style={"color": "#7b8ba3", "marginBottom": "24px"},
        ),

        # --- Parameter Input Panel ---
        html.Div([
            html.H3("Input Parameters", style={"marginBottom": "16px"}),

            _slider_control(
                id="ctrl-mud-weight",
                label="Mud Weight (ppg)",
                min_val=7.0, max_val=20.0, step=0.1, value=10.0,
                equation="P_hydrostatic = 0.052 * MW * TVD",
            ),
            _slider_control(
                id="ctrl-anomaly-threshold",
                label="Anomaly Threshold (sigma)",
                min_val=1.0, max_val=5.0, step=0.1, value=2.0,
                equation="flag if vertex_defect > mean + threshold * std",
            ),
            _slider_control(
                id="ctrl-window-size",
                label="Analysis Window (ft)",
                min_val=200, max_val=2000, step=100, value=500,
                equation="sliding window width for coherence_log()",
            ),
            _slider_control(
                id="ctrl-stride",
                label="Stride (ft)",
                min_val=50, max_val=500, step=50, value=100,
                equation="step between consecutive windows",
            ),
            _slider_control(
                id="ctrl-n-bins",
                label="Depth Bins",
                min_val=20, max_val=200, step=10, value=50,
                equation="n_depth_bins for sheaf vertex count",
            ),
            _slider_control(
                id="ctrl-k-eig",
                label="Eigenvalues (k)",
                min_val=5, max_val=50, step=5, value=10,
                equation="k smallest eigenvalues of sheaf Laplacian",
            ),

            # Transport weights
            html.H4("Transport Weights", style={"marginTop": "24px", "marginBottom": "12px"}),
            html.P(
                "Relative weight of each physics transport in the composite sheaf Laplacian.",
                style={"color": "#7b8ba3", "fontSize": "12px", "marginBottom": "12px"},
            ),
            _slider_control(
                id="ctrl-wt-smoothness",
                label="Smoothness",
                min_val=0.0, max_val=1.0, step=0.05, value=0.30,
                equation="all channels should vary smoothly between adjacent depths",
            ),
            _slider_control(
                id="ctrl-wt-flow",
                label="Flow Conservation",
                min_val=0.0, max_val=1.0, step=0.05, value=0.20,
                equation="flow_out ~ flow_in (mass conservation)",
            ),
            _slider_control(
                id="ctrl-wt-hydraulics",
                label="Hydraulics",
                min_val=0.0, max_val=1.0, step=0.05, value=0.20,
                equation="APWD ~ 0.052 * MW * TVD + AFP + SBP",
            ),
            _slider_control(
                id="ctrl-wt-rop-mse",
                label="ROP / MSE",
                min_val=0.0, max_val=1.0, step=0.05, value=0.15,
                equation="MSE = f(WOB, torque, RPM, ROP)",
            ),
            _slider_control(
                id="ctrl-wt-gamma-rop",
                label="Gamma / ROP Correlation",
                min_val=0.0, max_val=1.0, step=0.05, value=0.15,
                equation="high gamma (shale) -> low ROP; low gamma -> high ROP",
            ),

            # Run button
            html.Button(
                "Run ATFT Analysis",
                id="ctrl-run-btn",
                style={
                    "marginTop": "24px",
                    "padding": "12px 32px",
                    "background": "#00d4ff",
                    "color": "#0a0e17",
                    "border": "none",
                    "borderRadius": "4px",
                    "fontWeight": "700",
                    "fontSize": "14px",
                    "cursor": "pointer",
                    "width": "100%",
                },
            ),
        ], style={
            "background": "#131a2b",
            "border": "1px solid #1e2d4a",
            "borderRadius": "8px",
            "padding": "24px",
            "maxWidth": "600px",
        }),

        # --- Hardware Info ---
        html.Div([
            html.H3("Compute Backend", style={"marginTop": "32px", "marginBottom": "12px"}),
            _hardware_info(),
        ]),

        # Results placeholder
        html.Div(
            id="ctrl-results",
            style={"marginTop": "24px"},
        ),

    ], className="page-content")


def _slider_control(id, label, min_val, max_val, step, value, equation):
    """Render a labeled slider with equation reference."""
    return html.Div([
        html.Div([
            html.Span(label, style={
                "fontSize": "13px", "fontWeight": "500",
            }),
            html.Span(f" = {value}", id=f"{id}-display", style={
                "fontSize": "13px", "fontFamily": "JetBrains Mono",
                "color": "#00d4ff", "marginLeft": "8px",
            }),
        ]),
        dcc.Slider(
            id=id,
            min=min_val, max=max_val, step=step, value=value,
            marks=None,
            tooltip={"placement": "bottom", "always_visible": False},
        ),
        html.Div(equation, style={
            "fontSize": "10px", "color": "#4a5568",
            "fontFamily": "JetBrains Mono",
            "marginTop": "-8px", "marginBottom": "16px",
        }),
    ])


def _hardware_info():
    """Render hardware detection results."""
    try:
        from mpd_overwatch.pointcloud.hardware import detect_compute_backend
        hw = detect_compute_backend()

        items = [
            f"Backend: {hw.get('backend', 'cpu')}",
            f"CPU cores: {hw.get('cpu_cores', 'unknown')}",
            f"RAM: {hw.get('ram_gb', 'unknown'):.1f} GB" if isinstance(hw.get('ram_gb'), (int, float)) else "RAM: unknown",
            f"Max points: {hw.get('recommended_max_points', 'unknown'):,}" if isinstance(hw.get('recommended_max_points'), (int, float)) else "",
        ]

        if hw.get('gpu_name'):
            items.insert(1, f"GPU: {hw['gpu_name']}")
            if hw.get('gpu_memory_gb'):
                items.insert(2, f"GPU memory: {hw['gpu_memory_gb']:.1f} GB")

        return html.Div([
            html.Div(item, style={
                "fontSize": "12px", "fontFamily": "JetBrains Mono",
                "color": "#7b8ba3", "marginBottom": "4px",
            })
            for item in items if item
        ], style={
            "background": "#131a2b",
            "border": "1px solid #1e2d4a",
            "borderRadius": "6px",
            "padding": "16px",
            "maxWidth": "400px",
        })
    except Exception:
        return html.Div("Hardware detection unavailable.", style={"color": "#64748b"})


# Role-based navigation filtering
ROLE_NAV = {
    "hmu_operator": ["/", "/hmu", "/scenarios"],
    "drilling_supervisor": ["/", "/scenarios", "/well-comparison", "/geomechanics",
                            "/topology", "/atft", "/hmu", "/supervisory"],
    "consultant": ["/", "/scenarios", "/well-comparison", "/geomechanics",
                   "/topology", "/atft", "/controls", "/hmu", "/supervisory",
                   "/data-import", "/proposal"],
}


def filter_nav_for_role(role, nav_sections):
    """Filter navigation sections based on user role.

    Parameters
    ----------
    role : str
        One of: hmu_operator, drilling_supervisor, consultant.
    nav_sections : list of dict
        Navigation sections with 'heading' and 'links' keys.

    Returns
    -------
    list of dict
        Filtered navigation sections.
    """
    allowed = ROLE_NAV.get(role, ROLE_NAV["consultant"])
    filtered = []
    for section in nav_sections:
        filtered_links = [
            link for link in section["links"]
            if link[0] in allowed
        ]
        if filtered_links:
            filtered.append({
                "heading": section["heading"],
                "links": filtered_links,
            })
    return filtered
