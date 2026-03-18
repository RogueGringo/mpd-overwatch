"""MPD Overwatch - Command Line Interface.

Usage:
    mpd-overwatch serve              Start the dashboard (default port 8050)
    mpd-overwatch vv                 Run V&V benchmark suite
    mpd-overwatch report <las_file>  Generate HTML report from a LAS file
    mpd-overwatch analyze <dir>      Analyze all LAS files in a directory
    mpd-overwatch info               Show platform version and hardware
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
    p_report = sub.add_parser("report", help="Generate HTML report from LAS file")
    p_report.add_argument("las_file", help="Path to LAS file")
    p_report.add_argument("-o", "--output", default="report.html", help="Output HTML path")

    # analyze
    p_analyze = sub.add_parser("analyze", help="Analyze all LAS files in directory")
    p_analyze.add_argument("directory", help="Directory containing LAS files")

    # info
    sub.add_parser("info", help="Show platform version and detected hardware")

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

    return 0


def _cmd_serve(args, logger):
    """Start the Dash dashboard."""
    logger.info("Starting MPD Overwatch dashboard on %s:%d", args.host, args.port)
    try:
        from mpd_overwatch.app import create_app
        app = create_app()
        app.run(debug=not args.no_debug, host=args.host, port=args.port)
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
    """Generate HTML report from a LAS file."""
    import os
    if not os.path.exists(args.las_file):
        logger.error("File not found: %s", args.las_file)
        return 1

    logger.info("Loading %s", args.las_file)
    try:
        from mpd_overwatch.data.las_parser import LASParser
        parser = LASParser()
        result = parser.parse(args.las_file)
        df = result.to_dataframe()
        logger.info("Loaded %d rows, %d columns", len(df), len(df.columns))
        logger.info("Report generation from real data: %s", args.output)
        # Placeholder for full report generation
        print(f"Loaded {len(df)} data points from {args.las_file}")
        print(f"Columns: {list(df.columns)}")
        print(f"Report output: {args.output}")
    except Exception as e:
        logger.error("Failed to process %s: %s", args.las_file, e)
        return 1
    return 0


def _cmd_analyze(args, logger):
    """Analyze all LAS files in a directory."""
    import os
    import glob
    if not os.path.isdir(args.directory):
        logger.error("Directory not found: %s", args.directory)
        return 1

    las_files = glob.glob(os.path.join(args.directory, "**", "*.las"), recursive=True)
    las_files += glob.glob(os.path.join(args.directory, "**", "*.LAS"), recursive=True)
    las_files = sorted(set(las_files))
    logger.info("Found %d LAS files in %s", len(las_files), args.directory)

    from mpd_overwatch.data.las_parser import LASParser
    parser = LASParser()
    loaded = 0
    for f in las_files:
        try:
            result = parser.parse(f)
            df = result.to_dataframe()
            if len(df) > 5:
                loaded += 1
                print(f"  {os.path.basename(f)}: {len(df)} rows, {len(df.columns)} cols")
        except Exception as e:
            logger.debug("Failed to load %s: %s", f, e)

    print(f"\nLoaded {loaded}/{len(las_files)} files successfully.")
    return 0


def _cmd_info(logger):
    """Show platform info and hardware."""
    print(f"MPD Overwatch v{__version__}")
    print()
    try:
        from mpd_overwatch.pointcloud.hardware import detect_compute_backend
        hw = detect_compute_backend()
        print(f"Compute backend: {hw['backend']}")
        if hw.get("gpu_name"):
            print(f"GPU: {hw['gpu_name']}")
        if hw.get("gpu_memory_gb"):
            print(f"GPU memory: {hw['gpu_memory_gb']:.1f} GB")
        print(f"CPU cores: {hw['cpu_cores']}")
        print(f"RAM: {hw['ram_gb']:.1f} GB")
    except Exception as e:
        print(f"Hardware detection: {e}")

    print()
    try:
        from mpd_overwatch.vv.runner import run_all_benchmarks
        r = run_all_benchmarks()
        print(f"V&V: {r['total_passed']}/{r['total_tests']} pass, Grade {r['overall_grade']}")
    except Exception as e:
        print(f"V&V: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
