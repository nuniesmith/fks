"""
Shared library for Ruby.

All business logic modules live under organised sub-packages:

    # Core infrastructure
    from core.cache import cache_get, cache_set
    from core.models import init_db, ASSETS
    from core.alerts import get_dispatcher
    from core.logging_config import setup_logging, get_logger
    from core.breakout_types import BreakoutType, get_range_config
    from core.multi_session import get_session, all_sessions, RBSession, ORBSession

    # Analysis modules
    from analysis.volatility import kmeans_volatility_clusters
    from analysis.wave_analysis import calculate_wave_analysis
    from analysis.ict import detect_fvgs, detect_order_blocks
    from analysis.cvd import compute_cvd
    from analysis.confluence import check_confluence
    from analysis.regime import RegimeDetector
    from analysis.scorer import PreMarketScorer
    from analysis.signal_quality import compute_signal_quality
    from analysis.volume_profile import compute_volume_profile
    from analysis.rendering.chart_renderer import render_ruby_snapshot
    from analysis.rendering.chart_renderer_parity import render_parity_snapshot

    # Trading modules
    from trading.engine import get_engine, DashboardEngine

    # External integrations
    from integrations.grok_helper import GrokSession
    from integrations.massive_client import get_massive_provider

Services (engine, data, web, training) are sub-packages:

    from services.engine.focus import compute_daily_focus
    from services.data.main import app
    from services.web.main import app
    from services.training.trainer_server import app
    from services.training.dataset_generator import generate_dataset, DatasetConfig
    from services.training.rb_simulator import simulate_batch, BracketConfig

Install in editable mode for development:

    pip install -e .          # CPU-only (engine, web, dashboard)
    pip install -e ".[gpu]"   # + PyTorch/CUDA for training
"""
