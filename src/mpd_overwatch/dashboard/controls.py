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

        # --- Re-select Channels ---
        html.Div([
            html.H3("Channel Selection", style={"marginTop": "32px", "marginBottom": "8px"}),
            html.P(
                "Return to the channel selector to remap input columns.",
                style={"color": "#7b8ba3", "fontSize": "12px", "marginBottom": "12px"},
            ),
            dcc.Link(
                html.Button(
                    "Re-select Channels",
                    style={
                        "padding": "10px 24px",
                        "background": "transparent",
                        "color": "#00d4ff",
                        "border": "1px solid #00d4ff",
                        "borderRadius": "4px",
                        "fontWeight": "600",
                        "fontSize": "13px",
                        "cursor": "pointer",
                    },
                ),
                href="/channels",
            ),
        ]),

        # --- Session Log Viewer ---
        html.Div([
            html.H3("Session Log", style={"marginTop": "32px", "marginBottom": "8px"}),
            _log_viewer(n_lines=40),
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
    """Render hardware detection results including GPU name, VRAM, SM count, and channel budget."""
    try:
        from mpd_overwatch.pointcloud.hardware import detect_compute_backend
        from mpd_overwatch.pointcloud.channel_registry import max_channels

        hw = detect_compute_backend()

        # Gather GPU SM count if CUDA is available
        sm_count = 0
        try:
            import torch
            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                sm_count = getattr(props, "multi_processor_count", 0)
        except Exception:
            sm_count = 0

        vram_gb = hw.get("gpu_memory_gb") or 0.0
        channel_budget = max_channels(vram_gb, sm_count)

        rows = []

        # Backend
        backend = hw.get("backend", "cpu")
        backend_color = "#2aaa66" if backend in ("cuda", "rocm") else "#e8a840"
        rows.append(_hw_row("Backend", backend.upper(), color=backend_color))

        # GPU info
        gpu_name = hw.get("gpu_name")
        if gpu_name:
            rows.append(_hw_row("GPU", gpu_name))
            if vram_gb:
                rows.append(_hw_row("VRAM", f"{vram_gb:.1f} GB"))
            if sm_count > 0:
                rows.append(_hw_row("SM count", str(sm_count)))

        # CPU info
        cpu_cores = hw.get("cpu_cores")
        if cpu_cores:
            rows.append(_hw_row("CPU cores", str(cpu_cores)))

        ram_gb = hw.get("ram_gb")
        if isinstance(ram_gb, (int, float)):
            rows.append(_hw_row("RAM", f"{ram_gb:.1f} GB"))

        # Channel budget
        budget_color = "#2aaa66" if channel_budget >= 100 else "#e8a840"
        rows.append(_hw_row("Channel budget", str(channel_budget), color=budget_color))

        # Max points
        max_pts = hw.get("recommended_max_points")
        if isinstance(max_pts, (int, float)):
            rows.append(_hw_row("Max points", f"{int(max_pts):,}"))

        return html.Div(rows, style={
            "background": "#131a2b",
            "border": "1px solid #1e2d4a",
            "borderRadius": "6px",
            "padding": "16px",
            "maxWidth": "420px",
        })

    except Exception as exc:
        return html.Div(
            f"Hardware detection unavailable: {exc}",
            style={"color": "#64748b", "fontSize": "12px"},
        )


def _hw_row(label: str, value: str, color: str = "#7b8ba3") -> html.Div:
    """Render a single hardware info row."""
    return html.Div([
        html.Span(f"{label}: ", style={
            "fontSize": "12px", "color": "#4a5568",
            "fontFamily": "JetBrains Mono",
        }),
        html.Span(value, style={
            "fontSize": "12px", "color": color,
            "fontFamily": "JetBrains Mono", "fontWeight": "600",
        }),
    ], style={"marginBottom": "4px"})


def _log_viewer(n_lines: int = 40) -> html.Div:
    """Render the last N lines of the current session log.

    Wraps get_log() in a try/except so this degrades gracefully if the
    ComputationLog has not been initialized (e.g., during unit testing or
    when the app is opened before any computation has been triggered).
    """
    try:
        from mpd_overwatch.computation_log import get_log
        log_obj = get_log()
        filepath = log_obj.filepath

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                all_lines = fh.readlines()
        except OSError as exc:
            return html.Div(
                f"Log file not readable: {exc}",
                style={"color": "#64748b", "fontSize": "11px"},
            )

        tail = all_lines[-n_lines:] if len(all_lines) > n_lines else all_lines
        line_count = len(all_lines)

        log_text = "".join(tail) if tail else "(log is empty)"

        return html.Div([
            html.Div([
                html.Span(
                    f"File: {filepath}",
                    style={"fontSize": "10px", "color": "#4a5568",
                           "fontFamily": "JetBrains Mono"},
                ),
                html.Span(
                    f"  ({line_count} lines total, showing last {min(n_lines, line_count)})",
                    style={"fontSize": "10px", "color": "#4a5568"},
                ),
            ], style={"marginBottom": "6px"}),
            html.Pre(
                log_text,
                style={
                    "backgroundColor": "#0a0e17",
                    "border": "1px solid #1e2d4a",
                    "borderRadius": "4px",
                    "padding": "12px",
                    "fontSize": "10px",
                    "fontFamily": "Consolas, monospace",
                    "color": "#7b8ba3",
                    "overflowX": "auto",
                    "overflowY": "auto",
                    "maxHeight": "320px",
                    "whiteSpace": "pre-wrap",
                    "wordBreak": "break-all",
                },
            ),
        ])

    except RuntimeError:
        # ComputationLog not initialized yet — show placeholder
        return html.Div(
            "Session log not yet initialized. Log entries appear after the first computation.",
            style={
                "color": "#4a5568",
                "fontSize": "11px",
                "fontFamily": "JetBrains Mono",
                "padding": "12px",
                "background": "#0a0e17",
                "border": "1px solid #1e2d4a",
                "borderRadius": "4px",
                "maxWidth": "600px",
            },
        )

    except Exception as exc:
        return html.Div(
            f"Log viewer error: {exc}",
            style={"color": "#64748b", "fontSize": "11px"},
        )


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
