"""
src/main.py  — Entry Point (slim)
==================================
Loads config, wires dependencies, and delegates to the supervisor.

Usage:
    python3.13 -m src.main              # loads infrastructure/config/futures.yaml
    TRADING_MODE=sim python3.13 -m src.main

All trading logic lives in:
    src/workers/asset_worker.py  — per-asset trading loop
    src/supervisor.py            — multi-asset orchestration + web server
    utils/indicators.py          — pure indicator functions
    utils/optimizer.py           — Optuna objective + runner
    utils/state.py               — WaveState, SignalStreak dataclasses
    services/task_runner.py      — web-triggered background tasks
"""

import asyncio

from supervisor import main

if __name__ == "__main__":
    asyncio.run(main())
