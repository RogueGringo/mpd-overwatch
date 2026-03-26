"""MPD Overwatch - Command Line Interface.

Usage:
    mpd-overwatch serve              Start the dashboard (default port 8050)
    mpd-overwatch vv                 Run V&V benchmark suite
    mpd-overwatch report <file>      Generate HTML report from a SQL EDR dump
    mpd-overwatch analyze <dir>      Analyze all SQL files in a directory
    mpd-overwatch info               Show platform version and hardware
    mpd-overwatch pipeline <file>    Run full analysis pipeline on a SQL EDR dump
"""

import argparse
import logging
import sys

from mpd_overwatch import __version__
from mpd_overwatch.logging_config import setup_logging


def main(argv=None):
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="mpd-overwatch",
        description="Managed Pressure Drilling computation platform.",
    )
    parser.add_argument(
        "--version", action="version", version=f"mpd-overwatch {__version__}"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity (default: INFO)",
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # serve
    p_serve = sub.add_parser("serve", help="Start the dashboard web server")
    p_serve.add_argument("--port", type=int, default=8050, help="Port (default: 8050)")
    p_serve.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    p_serve.add_argument("--no-debug", action="store_true", help="Disable debug mode")

    # vv
    sub.add_parser("vv", help="Run verification & validation benchmarks")

    # report
    p_report = sub.add_parser("report", help="Generate HTML report from SQL EDR dump")
    p_report.add_argument("sql_file", help="Path to SQL EDR dump file")
    p_report.add_argument("-o", "--output", default="report.html", help="Output HTML path")

    # analyze
    p_analyze = sub.add_parser("analyze", help="Analyze all SQL files in directory")
    p_analyze.add_argument("directory", help="Directory containing SQL EDR dump files")

    # info
    sub.add_parser("info", help="Show platform version and detected hardware")

    # pipeline
    p_pipe = sub.add_parser("pipeline", help="Run full analysis pipeline on a SQL EDR dump")
    p_pipe.add_argument("sql_file", help="Path to SQL EDR dump file")
    p_pipe.add_argument("--output-dir", default=".", help="Output directory for results")
    p_pipe.add_argument("--no-plots", action="store_true",
                         help="Skip PNG export")

    args = parser.parse_args(argv)
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "serve":
        return _cmd_serve(args, logger)
    elif args.command == "vv":
        return _cmd_vv(logger)
    elif args.command == "report":
        return _cmd_report(args, logger)
    elif args.command == "analyze":
        return _cmd_analyze(args, logger)
    elif args.command == "info":
        return _cmd_info(logger)
    elif args.command == "pipeline":
        return _cmd_pipeline(args, logger)

    return 0


def _cmd_serve(args, logger):
    """Start the Dash dashboard via the launcher."""
    logger.info("Starting MPD Overwatch dashboard on %s:%d", args.host, args.port)
    try:
        from mpd_overwatch.launcher import launch
        log_level = "DEBUG" if not args.no_debug else "INFO"
        launch(port=args.port, host=args.host, log_level=log_level)
    except ImportError as e:
        logger.error("Dashboard dependencies not available: %s", e)
        return 1
    return 0


def _cmd_vv(logger):
    """Run V&V benchmarks."""
    logger.info("Running V&V benchmark suite...")
    try:
        from mpd_overwatch.vv.runner import run_all_benchmarks
        report = run_all_benchmarks()
        print(report.get("summary_text", ""))
        passed = report["total_passed"]
        total = report["total_tests"]
        if passed == total:
            logger.info("V&V PASS: %d/%d benchmarks, Grade %s", passed, total, report["overall_grade"])
            return 0
        else:
            logger.error("V&V FAIL: %d/%d benchmarks passed", passed, total)
            return 1
    except Exception as e:
        logger.error("V&V failed: %s", e)
        return 1


def _cmd_report(args, logger):
    """Generate HTML report from a SQL EDR dump using MPD Operations intent."""
    import os
    if not os.path.exists(args.sql_file):
        logger.error("File not found: %s", args.sql_file)
        return 1

    logger.info("Loading %s", args.sql_file)
    try:
        from mpd_overwatch.data.sql_parser import ingest
        from mpd_overwatch.data.engine_manifest import auto_suggest_assignments
        from mpd_overwatch.core.engine_wrappers import (
            compute_ecd,
            compute_mse,
        )
        from mpd_overwatch.report_generator import generate_full_report

        db = ingest(args.sql_file)
        suggestions = auto_suggest_assignments(db)
        n_channels = len(db.channels)
        total_points = sum(cf.n_points for cf in db.channels.values())
        logger.info("Loaded %d channels, %d total points", n_channels, total_points)

        # Build well header
        well_header = {
            "well_name": db.source_ip,
            "source_file": args.sql_file,
            "dump_timestamp": db.dump_timestamp,
            "channels": n_channels,
        }

        # Auto-select MPD Operations channels and compute results
        results = []

        # Apply suggestions as assignments for computation
        for canonical, wits_id in suggestions.items():
            db.assignments[canonical] = wits_id

        # ECD: requires mud_weight_in, annular_pressure, hole_depth
        if db.has_required(["mud_weight_in", "annular_pressure", "hole_depth"]):
            mw_cf = db.assigned("mud_weight_in")
            ap_cf = db.assigned("annular_pressure")
            hd_cf = db.assigned("hole_depth")
            mid = mw_cf.n_points // 2
            try:
                ecd_res = compute_ecd(
                    float(mw_cf.calibrated_value[mid]),
                    float(ap_cf.calibrated_value[mid]),
                    float(hd_cf.calibrated_value[mid]),
                )
                results.append(ecd_res)
            except Exception as e:
                logger.debug("ECD computation skipped: %s", e)

        logger.info("Computed %d engineering results", len(results))

        html_str = generate_full_report(
            results=results,
            well_header=well_header,
            output_path=args.output,
        )
        print(f"Report written: {args.output}")
        print(f"  Source: {well_header['well_name']}")
        print(f"  Channels: {n_channels}, total points: {total_points}")
        print(f"  Engineering results: {len(results)}")
    except Exception as e:
        logger.error("Failed to process %s: %s", args.sql_file, e)
        return 1
    return 0


def _cmd_analyze(args, logger):
    """Batch-analyze all SQL EDR dump files in a directory."""
    import os
    from pathlib import Path
    if not os.path.isdir(args.directory):
        logger.error("Directory not found: %s", args.directory)
        return 1

    sql_files = sorted(Path(args.directory).rglob("*.sql"))
    # Skip time files (they require a depth companion)
    sql_files = [f for f in sql_files if "_timedata_" not in f.name]
    logger.info("Found %d SQL depth files in %s", len(sql_files), args.directory)

    from mpd_overwatch.data.sql_parser import ingest
    from mpd_overwatch.data.engine_manifest import auto_suggest_assignments
    from mpd_overwatch.report_generator import generate_full_report

    loaded = 0
    reports = 0

    for f in sql_files:
        try:
            db = ingest(str(f))
            n_channels = len(db.channels)
            total_points = sum(cf.n_points for cf in db.channels.values())
            if total_points <= 5:
                continue
            loaded += 1
            print(f"  {f.name}: {n_channels} channels, {total_points} points")

            # Build well header
            stem = f.stem
            well_header = {
                "well_name": db.source_ip or stem,
                "source_file": str(f),
                "dump_timestamp": db.dump_timestamp,
            }

            # Auto-suggest and compute
            suggestions = auto_suggest_assignments(db)
            for canonical, wits_id in suggestions.items():
                db.assignments[canonical] = wits_id

            eng_results = []
            # (Engineering computations could be added here as needed)

            out_html = os.path.join(args.directory, f"{stem}_report.html")
            generate_full_report(
                results=eng_results,
                well_header=well_header,
                output_path=out_html,
            )
            reports += 1
            logger.info("Report: %s (%d results)", out_html, len(eng_results))

        except Exception as e:
            logger.debug("Failed to load %s: %s", f, e)

    print(f"\nLoaded {loaded}/{len(sql_files)} files, generated {reports} HTML reports.")
    return 0


def _cmd_info(logger):
    """Show platform info, hardware, GPU capabilities and channel budget."""
    print(f"MPD Overwatch v{__version__}")
    print()

    # Hardware / compute backend
    try:
        from mpd_overwatch.pointcloud.hardware import detect_compute_backend
        hw = detect_compute_backend()
        print(f"Compute backend: {hw['backend']}")
        if hw.get("gpu_name"):
            print(f"GPU:             {hw['gpu_name']}")
        if hw.get("gpu_memory_gb"):
            print(f"GPU memory:      {hw['gpu_memory_gb']:.1f} GB")
        if hw.get("cuda_version"):
            print(f"CUDA version:    {hw['cuda_version']}")
        if hw.get("gpu_compute_capability"):
            print(f"Compute cap.:    {hw['gpu_compute_capability']}")
        print(f"CPU cores:       {hw['cpu_cores']}")
        print(f"RAM:             {hw['ram_gb']:.1f} GB")
    except Exception as e:
        print(f"Hardware detection: {e}")

    # Channel budget (from channel registry)
    print()
    try:
        from mpd_overwatch.core.engine_wrappers import (
            compute_ecd, compute_mse, compute_hydrostatic,
            compute_bhp_static, compute_bhp_dynamic, compute_annular_velocity,
            compute_ucs, compute_brittleness, compute_d_exponent,
            compute_eaton_pp, compute_skin_factor,
            compute_productivity_index,
        )
        wrappers = [
            "compute_ecd", "compute_mse", "compute_hydrostatic",
            "compute_bhp_static", "compute_bhp_dynamic", "compute_annular_velocity",
            "compute_ucs", "compute_brittleness", "compute_d_exponent",
            "compute_eaton_pp", "compute_skin_factor",
            "compute_productivity_index",
        ]
        print(f"Engine wrappers: {len(wrappers)} available")
        for w in wrappers:
            print(f"  {w}")
    except Exception as e:
        print(f"Engine wrappers: {e}")

    # Channel registry tier summary
    print()
    try:
        from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry, DEFAULT_CHANNELS
        registry = ChannelRegistry()
        total_channels = len(DEFAULT_CHANNELS)
        print(f"Channel registry: {total_channels} channels")
        print(f"  Aliases:  {len(registry._aliases)} mnemonic aliases")
    except Exception as e:
        print(f"Channel registry: {e}")

    # V&V summary
    print()
    try:
        from mpd_overwatch.vv.runner import run_all_benchmarks
        r = run_all_benchmarks()
        print(f"V&V: {r['total_passed']}/{r['total_tests']} pass, Grade {r['overall_grade']}")
    except Exception as e:
        print(f"V&V: {e}")

    return 0


def _cmd_pipeline(args, logger):
    """Run full analysis pipeline on a SQL EDR dump."""
    import time as _time
    from pathlib import Path

    filepath = args.sql_file
    if not Path(filepath).exists():
        logger.error("File not found: %s", filepath)
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # --- Register in central data index ---
        from mpd_overwatch.data.data_index import DataIndex
        data_index = DataIndex()
        idx_entry = data_index.register(filepath)
        logger.info("Indexed as %s", idx_entry["file_hash"])

        # --- Step 1: Ingest via SQL parser ---
        t0 = _time.perf_counter()
        from mpd_overwatch.data.sql_parser import ingest
        db = ingest(filepath)
        ingest_ms = int((_time.perf_counter() - t0) * 1000)

        n_channels = len(db.channels)
        total_points = sum(cf.n_points for cf in db.channels.values())
        well_name = db.source_ip or Path(filepath).stem

        logger.info("Loaded %s: %d channels, %d total points",
                     well_name, n_channels, total_points)

        # --- Step 2: Auto-suggest channel assignments (idtable IS characterization) ---
        t0 = _time.perf_counter()
        from mpd_overwatch.data.engine_manifest import auto_suggest_assignments
        suggestions = auto_suggest_assignments(db)
        for canonical, wits_id in suggestions.items():
            db.assignments[canonical] = wits_id
        map_ms = int((_time.perf_counter() - t0) * 1000)

        logger.info("Mapped %d / %d channels via WITS codes",
                     len(suggestions), n_channels)

        # --- Step 3: PointCloud4D from WellDatabase ---
        pc = None
        if len(db.assignments) >= 2:
            t0 = _time.perf_counter()
            try:
                from mpd_overwatch.pointcloud.ingestion import ingest_dataframe
                import pandas as pd

                # Build DataFrame from assigned channels
                canonical_data = {}
                for canonical, wits_id in db.assignments.items():
                    cf = db.channels[wits_id]
                    canonical_data[canonical] = cf.calibrated_value

                # Align arrays to same length (min across all)
                min_len = min(len(v) for v in canonical_data.values())
                for k in canonical_data:
                    canonical_data[k] = canonical_data[k][:min_len]

                df = pd.DataFrame(canonical_data)
                depth_col = "hole_depth" if "hole_depth" in df.columns else df.columns[0]
                pc = ingest_dataframe(
                    df, depth_col=depth_col,
                    well_name=well_name,
                    metadata={"source": filepath},
                )
                pc_ms = int((_time.perf_counter() - t0) * 1000)

                pc.save(output_dir / "pointcloud")
                logger.info("PointCloud4D: %d points, %d channels (%dms)",
                            pc.n_points, pc.n_channels, pc_ms)
            except Exception as e:
                logger.warning("PointCloud4D construction failed: %s", e)
                pc = None
        else:
            logger.warning("Too few assigned channels (%d) for point cloud",
                          len(db.assignments))

        # --- PNG Export ---
        if not args.no_plots:
            try:
                from mpd_overwatch.core.plot_factory import (
                    plot_raw_channels,
                    export_figure_png,
                )
                plots_dir = output_dir / "plots"
                plots_dir.mkdir(parents=True, exist_ok=True)

                if db.assignments:
                    canonical_data = {}
                    for canonical, wits_id in db.assignments.items():
                        cf = db.channels[wits_id]
                        canonical_data[canonical] = cf.calibrated_value
                    fig = plot_raw_channels(canonical_data)
                    export_figure_png(fig, plots_dir / "01_raw_channels.png")
                    logger.info("Exported 01_raw_channels.png")

            except Exception as e:
                logger.warning("Plot export failed: %s", e)

        # --- Summary ---
        print(f"\n{'='*60}")
        print(f"  PIPELINE COMPLETE: {well_name}")
        print(f"{'='*60}")
        print(f"  [001_ingest] SQL EDR Ingested ({ingest_ms}ms)")
        print(f"    {n_channels} channels, {total_points} points")
        print(f"  [002_map] Channel Assignment ({map_ms}ms)")
        print(f"    {len(suggestions)} of {n_channels} channels mapped via WITS codes")
        if pc:
            print(f"  [003_pointcloud] Point Cloud Constructed")
            print(f"    {pc.n_points:,} points, {pc.n_channels} channels")
        if not args.no_plots:
            print(f"  Plots:   {output_dir / 'plots'}/")
        print(f"{'='*60}\n")

        return 0

    except Exception as e:
        logger.error("Pipeline failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
