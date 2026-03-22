"""Launcher — CMD staging ground for MPD Overwatch.

Orchestrates: hardware detection, log initialization, server start.
"""

import sys
from mpd_overwatch.computation_log import init_log
from mpd_overwatch.pointcloud.hardware import detect_compute_backend
from mpd_overwatch.pointcloud.channel_registry import max_channels
from mpd_overwatch.config import APP_VERSION


def launch(port=8050, host="127.0.0.1", log_level="INFO"):
    # 1. Hardware detection
    hw = detect_compute_backend()
    vram = hw.get("gpu_memory_gb") or 0.0
    sm_count = 0
    try:
        import torch
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            sm_count = props.multi_processor_count
    except ImportError:
        pass

    # 2. Channel budget
    budget = max_channels(vram, sm_count)

    # 3. Init computation log
    log = init_log()
    log.session(f"MPD Overwatch {APP_VERSION}")
    log.session(f"GPU: {hw.get('gpu_name', 'None')} | {vram:.0f} GB VRAM | {sm_count} SMs")
    log.session(f"CPU: {hw.get('cpu_cores', '?')} cores | {hw.get('ram_gb', '?')} GB RAM")
    log.session(f"Channel budget: {budget} max (hardware-adaptive)")

    # 4. Print terminal status
    gpu_label = hw.get("gpu_name", "CPU-only")
    print(f"MPD Overwatch {APP_VERSION} | {gpu_label} ({budget} ch max) | http://{host}:{port}")
    print(f"Log: {log.filepath}")

    # 5. Start Dash server
    from mpd_overwatch.app import create_app
    app = create_app()
    app.run(host=host, port=port, debug=(log_level == "DEBUG"))
