"""MPD Command - Pipeline Results Page

Displays results from a completed pipeline run: .mow archive contents,
analysis layer provenance chain, channel characterization summary,
and point cloud metrics. Also allows running the pipeline from the UI.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from dash import html, dcc

from mpd_overwatch.config import COLORS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# .mow archive inspection
# ---------------------------------------------------------------------------

def _load_mow_summary(mow_path: str) -> Optional[Dict[str, Any]]:
    """Load a .mow archive and return summary info without heavy arrays.

    Note: .mow archives are a legacy format from the LAS-based pipeline.
    This function attempts to load them for backward compatibility but
    returns None if the archive cannot be read.
    """
    try:
        import json
        import zipfile
        with zipfile.ZipFile(mow_path, "r") as zf:
            manifest = json.loads(zf.read("manifest.json"))
        layers = manifest.get("layers", [])
        # Check for pointcloud arrays
        has_pc = False
        pc_shape = None
        try:
            with zipfile.ZipFile(mow_path, "r") as zf:
                if "004_pointcloud__points.npy" in zf.namelist():
                    has_pc = True
                    import io
                    with zf.open("004_pointcloud__points.npy") as npy_f:
                        pts = np.load(io.BytesIO(npy_f.read()))
                        pc_shape = pts.shape
        except Exception:
            pass
        return {
            "well_name": manifest.get("well_name", ""),
            "metadata": manifest.get("metadata", {}),
            "layer_count": len(layers),
            "layers": layers,
            "has_pointcloud": has_pc,
            "pointcloud_shape": pc_shape,
        }
    except Exception as exc:
        logger.warning("Failed to load .mow archive %s: %s", mow_path, exc)
        return None


def _find_pipeline_outputs() -> List[Dict[str, Any]]:
    """Search common output locations for pipeline results."""
    results = []
    search_dirs = [
        Path.cwd() / "output",
        Path.home() / ".mpd-overwatch" / "output",
    ]

    # Also search subdirectories of output/
    output_dir = Path.cwd() / "output"
    if output_dir.exists():
        try:
            for sub in output_dir.iterdir():
                if sub.is_dir():
                    search_dirs.append(sub)
        except OSError:
            pass

    seen_paths = set()
    for d in search_dirs:
        if not d.exists():
            continue
        for mow_file in d.glob("*.mow"):
            if str(mow_file) in seen_paths:
                continue
            seen_paths.add(str(mow_file))
            summary = _load_mow_summary(str(mow_file))
            if summary:
                # Check for companion files
                parent = mow_file.parent
                plots_dir = parent / "plots"
                pngs = sorted(plots_dir.glob("*.png")) if plots_dir.exists() else []
                pc_json = parent / "pointcloud.json"
                pc_npz = parent / "pointcloud.npz"

                results.append({
                    "mow_path": str(mow_file),
                    "mow_name": mow_file.name,
                    "parent_dir": str(parent),
                    "summary": summary,
                    "png_files": [str(p) for p in pngs],
                    "has_pointcloud_files": pc_json.exists() and pc_npz.exists(),
                })

    return results


# ---------------------------------------------------------------------------
# Layout builders
# ---------------------------------------------------------------------------

def _layer_card(layer: Dict[str, Any], idx: int) -> html.Div:
    """Render a single analysis layer as a card row."""
    duration = f"{layer['duration_ms']}ms" if layer['duration_ms'] else "—"
    layer_type = layer.get("layer_type", "unknown")

    type_colors = {
        "ingest": COLORS["primary"],
        "channel_characterization": COLORS["secondary"],
        "channel_mapping": COLORS["success"],
        "pointcloud": COLORS["warning"],
        "topology": "#c084fc",
        "coherence": "#c084fc",
    }
    badge_color = type_colors.get(layer_type, COLORS["text_muted"])

    outputs = layer.get("outputs", {})
    output_items = []
    for k, v in outputs.items():
        output_items.append(
            html.Span(f"{k}: {v}", style={
                "fontSize": "11px", "color": COLORS["text_muted"],
                "marginRight": "12px",
            })
        )

    return html.Div([
        html.Div([
            # Layer badge
            html.Span(layer["layer_id"], style={
                "color": badge_color,
                "fontWeight": "700",
                "fontSize": "12px",
                "fontFamily": "Consolas, monospace",
                "marginRight": "12px",
                "minWidth": "120px",
                "display": "inline-block",
            }),
            # Value term
            html.Span(layer.get("value_term", ""), style={
                "color": COLORS["text"],
                "fontSize": "13px",
                "fontWeight": "600",
            }),
            # Duration
            html.Span(duration, style={
                "color": COLORS["text_dim"],
                "fontSize": "11px",
                "fontFamily": "Consolas, monospace",
                "marginLeft": "auto",
                "paddingLeft": "16px",
            }),
        ], style={
            "display": "flex",
            "alignItems": "center",
            "marginBottom": "4px",
        }),
        # Value description
        html.Div(layer.get("value_description", ""), style={
            "color": COLORS["text_muted"],
            "fontSize": "12px",
            "paddingLeft": "132px",
            "marginBottom": "4px",
        }),
        # Outputs
        html.Div(output_items, style={
            "paddingLeft": "132px",
        }) if output_items else html.Div(),
    ], style={
        "padding": "10px 16px",
        "backgroundColor": COLORS["background"] if idx % 2 == 0 else COLORS["card"],
        "borderLeft": f"3px solid {badge_color}",
    })


def _pipeline_result_card(result: Dict[str, Any]) -> html.Div:
    """Render a complete pipeline result (one .mow archive)."""
    summary = result["summary"]
    well_name = summary.get("well_name", "Unknown Well")
    layer_count = summary.get("layer_count", 0)
    metadata = summary.get("metadata", {})
    source = metadata.get("source", "—")

    # Header stats
    stats_items = [
        _stat("Layers", str(layer_count), COLORS["primary"]),
    ]

    # Point cloud stats
    if summary.get("has_pointcloud"):
        shape = summary.get("pointcloud_shape")
        if shape:
            stats_items.append(_stat("Points", f"{shape[0]:,}", COLORS["success"]))
            stats_items.append(_stat("Dimensions", str(shape[1]), COLORS["success"]))

    # Total duration
    total_ms = sum(
        l.get("duration_ms", 0) or 0 for l in summary.get("layers", [])
    )
    if total_ms > 0:
        if total_ms > 1000:
            stats_items.append(_stat("Total Time", f"{total_ms / 1000:.1f}s", COLORS["warning"]))
        else:
            stats_items.append(_stat("Total Time", f"{total_ms}ms", COLORS["warning"]))

    # PNG count
    png_count = len(result.get("png_files", []))
    if png_count > 0:
        stats_items.append(_stat("PNGs", str(png_count), COLORS["secondary"]))

    # Layer cards
    layer_cards = [
        _layer_card(layer, i)
        for i, layer in enumerate(summary.get("layers", []))
    ]

    # File paths section
    file_entries = [
        html.Div([
            html.Span("Archive: ", style={"color": COLORS["text_dim"], "fontSize": "11px"}),
            html.Span(result["mow_name"], style={
                "color": COLORS["primary"], "fontSize": "11px",
                "fontFamily": "Consolas, monospace",
            }),
        ]),
    ]
    if result.get("has_pointcloud_files"):
        file_entries.append(html.Div([
            html.Span("Point Cloud: ", style={"color": COLORS["text_dim"], "fontSize": "11px"}),
            html.Span("pointcloud.npz + pointcloud.json", style={
                "color": COLORS["success"], "fontSize": "11px",
                "fontFamily": "Consolas, monospace",
            }),
        ]))
    for png in result.get("png_files", []):
        file_entries.append(html.Div([
            html.Span("Plot: ", style={"color": COLORS["text_dim"], "fontSize": "11px"}),
            html.Span(Path(png).name, style={
                "color": COLORS["secondary"], "fontSize": "11px",
                "fontFamily": "Consolas, monospace",
            }),
        ]))

    return html.Div([
        # Well name header
        html.Div([
            html.H2(well_name, style={
                "color": COLORS["text"], "fontSize": "16px",
                "fontWeight": "700", "margin": "0 0 4px 0",
            }),
            html.Div(f"Source: {Path(source).name if source != '—' else '—'}", style={
                "color": COLORS["text_dim"], "fontSize": "11px",
                "fontFamily": "Consolas, monospace",
            }),
        ], style={"marginBottom": "12px"}),

        # Stats row
        html.Div(stats_items, style={
            "display": "flex", "gap": "10px", "flexWrap": "wrap",
            "marginBottom": "16px",
        }),

        # Provenance chain header
        html.Div("ANALYSIS PROVENANCE CHAIN", style={
            "color": COLORS["text_dim"], "fontSize": "10px",
            "fontWeight": "700", "letterSpacing": "2px",
            "marginBottom": "8px",
            "borderBottom": f"1px solid {COLORS['card_border']}",
            "paddingBottom": "6px",
        }),

        # Layer list
        html.Div(layer_cards, style={
            "borderRadius": "4px",
            "overflow": "hidden",
            "border": f"1px solid {COLORS['card_border']}",
            "marginBottom": "12px",
        }),

        # Files section
        html.Div([
            html.Div("OUTPUT FILES", style={
                "color": COLORS["text_dim"], "fontSize": "10px",
                "fontWeight": "700", "letterSpacing": "2px",
                "marginBottom": "6px",
            }),
            html.Div(file_entries, style={
                "display": "flex", "flexDirection": "column", "gap": "4px",
            }),
        ]),

    ], className="card", style={"padding": "20px", "marginBottom": "16px"})


def _stat(label: str, value: str, color: str) -> html.Div:
    """Small stat box."""
    return html.Div([
        html.Div(value, style={
            "color": color, "fontSize": "20px", "fontWeight": "700",
            "fontFamily": "Consolas, monospace", "lineHeight": "1",
        }),
        html.Div(label, style={
            "color": COLORS["text_muted"], "fontSize": "10px",
            "textTransform": "uppercase", "letterSpacing": "0.5px",
            "marginTop": "2px",
        }),
    ], style={
        "padding": "8px 12px", "backgroundColor": COLORS["background"],
        "borderRadius": "4px", "border": f"1px solid {COLORS['card_border']}",
        "minWidth": "80px",
    })


# ---------------------------------------------------------------------------
# Data Index summary
# ---------------------------------------------------------------------------

def _data_index_section() -> html.Div:
    """Render registered files from the central data index."""
    try:
        from mpd_overwatch.data.data_index import DataIndex
        idx = DataIndex()
        entries = idx.list_entries()
    except Exception:
        entries = []

    if not entries:
        return html.Div()

    rows = []
    for i, entry in enumerate(entries):
        row_bg = COLORS["background"] if i % 2 == 0 else COLORS["card"]
        cell = {"padding": "6px 10px", "fontSize": "11px", "fontFamily": "Consolas, monospace"}
        rows.append(html.Tr([
            html.Td(entry.get("file_hash", "")[:12], style={**cell, "color": COLORS["primary"]}),
            html.Td(entry.get("original_name", ""), style={**cell, "color": COLORS["text"]}),
            html.Td(
                f"{entry.get('size_bytes', 0) / 1024:.1f} KB",
                style={**cell, "color": COLORS["text_muted"], "textAlign": "right"},
            ),
            html.Td(
                entry.get("registered_at", "")[:19],
                style={**cell, "color": COLORS["text_dim"]},
            ),
        ], style={"backgroundColor": row_bg}))

    th_style = {
        "color": COLORS["text_dim"], "fontSize": "10px",
        "textTransform": "uppercase", "letterSpacing": "1px",
        "padding": "8px 10px", "textAlign": "left",
        "borderBottom": f"1px solid {COLORS['card_border']}",
    }

    return html.Div([
        html.Div("REGISTERED FILES", className="card-header"),
        html.Table([
            html.Thead(html.Tr([
                html.Th("Hash", style=th_style),
                html.Th("Filename", style=th_style),
                html.Th("Size", style={**th_style, "textAlign": "right"}),
                html.Th("Registered", style=th_style),
            ])),
            html.Tbody(rows),
        ], style={"borderCollapse": "collapse", "width": "100%"}),
    ], className="card", style={"marginBottom": "16px"})


# ---------------------------------------------------------------------------
# Public page function
# ---------------------------------------------------------------------------

def page_pipeline_results() -> html.Div:
    """Render the Pipeline Results page."""
    pipeline_results = _find_pipeline_outputs()

    if not pipeline_results:
        return html.Div([
            html.Div([
                html.H1("Pipeline Results"),
                html.P(
                    "Analysis archives, provenance chains, and verification outputs",
                    style={"color": COLORS["text_muted"], "fontSize": "13px"},
                ),
            ], className="page-header"),

            _data_index_section(),

            html.Div([
                html.Div([
                    html.Div("[~]", style={
                        "fontSize": "48px", "color": COLORS["text_dim"],
                        "fontFamily": "Consolas, monospace", "marginBottom": "16px",
                    }),
                    html.H3("No pipeline results found", style={
                        "color": COLORS["text_muted"], "marginBottom": "8px",
                    }),
                    html.P([
                        "Run the pipeline via CLI: ",
                        html.Code(
                            "mpd-overwatch pipeline <file.sql> --output-dir output/",
                            style={
                                "color": COLORS["primary"],
                                "backgroundColor": COLORS["background"],
                                "padding": "4px 8px",
                                "borderRadius": "4px",
                                "fontSize": "12px",
                            },
                        ),
                    ], style={"color": COLORS["text_dim"], "fontSize": "14px"}),
                ], style={"textAlign": "center", "padding": "60px 40px"}),
            ], className="card"),
        ])

    # Summary stats across all results
    total_layers = sum(r["summary"]["layer_count"] for r in pipeline_results)
    total_pngs = sum(len(r.get("png_files", [])) for r in pipeline_results)
    total_archives = len(pipeline_results)

    result_cards = [_pipeline_result_card(r) for r in pipeline_results]

    return html.Div([
        html.Div([
            html.H1("Pipeline Results"),
            html.P(
                "Analysis archives, provenance chains, and verification outputs",
                style={"color": COLORS["text_muted"], "fontSize": "13px"},
            ),
        ], className="page-header"),

        # Top-level stats
        html.Div([
            _stat("Archives", str(total_archives), COLORS["primary"]),
            _stat("Total Layers", str(total_layers), COLORS["success"]),
            _stat("PNG Exports", str(total_pngs), COLORS["secondary"]),
        ], style={
            "display": "flex", "gap": "10px", "flexWrap": "wrap",
            "marginBottom": "16px",
        }),

        _data_index_section(),

        # Result cards
        *result_cards,
    ])
