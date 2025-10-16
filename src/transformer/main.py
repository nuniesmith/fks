"""
TRANSFORMER Service Entry Point
This module serves as the entry point for the TRANSFORMER service, integrating with the main application
and utilizing the service template for service management. It also supports direct ML training mode.
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any


def _import_hmm_transformer() -> tuple[Any, Any]:
    """Robustly import HMMTransformer and HMMConfig.

    Returns (HMMTransformer, HMMConfig) or (None, None) if unavailable.
    """
    # 1) Preferred absolute import
    logger.info(f"[_import_hmm_transformer] sys.path head: {sys.path[:5]}")
    try:
        from services.transformer.models.hmm_transformer import (  # type: ignore
            HMMTransformer,
            HMMConfig,
        )
        return HMMTransformer, HMMConfig
    except Exception as e1:
        logger.info(f"services.* import failed: {e1}")

    # 2) Ensure typical source paths are on sys.path, then retry
    for p in ["/app/src/python", "/app/src", "/app"]:
        if p not in sys.path and os.path.isdir(p):
            sys.path.insert(0, p)
    try:
        from services.transformer.models.hmm_transformer import (  # type: ignore
            HMMTransformer,
            HMMConfig,
        )
        return HMMTransformer, HMMConfig
    except Exception as e2:
        logger.info(f"Retry import after sys.path update failed: {e2}")

    # 3) Final fallback: import by file path (use a flat temp module name)
    try:
        import importlib.util

        model_paths = [
            "/app/src/python/services/transformer/models/hmm_transformer.py",
            "/app/src/services/transformer/models/hmm_transformer.py",
        ]
        logger.info(f"Trying file-path import candidates: {model_paths}")
        for idx, mp in enumerate(model_paths):
            if os.path.isfile(mp):
                logger.info(f"Attempting file-path import: {mp}")
                # Use a simple module name to avoid parent package resolution issues
                mod_name = f"_hmm_transformer_fp_{idx}"
                spec = importlib.util.spec_from_file_location(mod_name, mp)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    # Ensure module is present in sys.modules during execution (required by dataclasses)
                    sys.modules[mod_name] = module
                    spec.loader.exec_module(module)
                    HMMTransformer = getattr(module, "HMMTransformer", None)
                    HMMConfig = getattr(module, "HMMConfig", None)
                    if HMMTransformer and HMMConfig:
                        return HMMTransformer, HMMConfig
    except Exception as e3:
        logger.info(f"File-path import failed: {e3}")

    # 4) Last resort: exec the module source into a new namespace
    try:
        import types
        for mp in [
            "/app/src/services/transformer/models/hmm_transformer.py",
            "/app/src/python/services/transformer/models/hmm_transformer.py",
        ]:
            if os.path.isfile(mp):
                logger.info(f"Attempting exec fallback for: {mp}")
                with open(mp, "r", encoding="utf-8") as f:
                    code = f.read()
                mod_name = "hmm_transformer_exec"
                module = types.ModuleType(mod_name)
                module.__file__ = mp
                # Register in sys.modules so dataclasses can resolve the module
                sys.modules[mod_name] = module
                exec(compile(code, mp, "exec"), module.__dict__)
                HMMTransformer = getattr(module, "HMMTransformer", None)
                HMMConfig = getattr(module, "HMMConfig", None)
                if HMMTransformer and HMMConfig:
                    return HMMTransformer, HMMConfig
    except Exception as e4:
        logger.info(f"Exec fallback failed: {e4}")

    return None, None

# Robust logging setup that avoids write errors at import time
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
_sh = logging.StreamHandler()
_sh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.handlers = []
logger.addHandler(_sh)

_logs_dir = os.environ.get("LOGS_DIR", "/app/logs")
try:
    Path(_logs_dir).mkdir(parents=True, exist_ok=True)
    _fh = logging.FileHandler(str(Path(_logs_dir) / "transformer_service.log"))
    _fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(_fh)
    logger.info(f"File logging enabled at {_logs_dir}")
except Exception:
    # Fall back to stream-only logging
    logger.info("File logging not available; using stream handler only")

# Service imports - make them optional
try:
    from framework.services.template import (
        start_template_service as _framework_start_template_service,
    )

    HAS_TEMPLATE_SERVICE = True
    logger.info("Successfully imported service template")
except ImportError as e:
    logger.warning(f"Could not import service template: {e}")
    HAS_TEMPLATE_SERVICE = False

# ML Pipeline imports
try:
    # Try absolute import first
    from transformer.main import main as transformer_main
    from transformer.main import save_results

    ML_IMPORTS_AVAILABLE = True
    logger.info("Successfully imported transformer.main")
except ImportError:
    try:
        # Try relative import with sys.path adjustment
        sys.path.insert(0, "/app/src")
        from transformer.main import main as transformer_main
        from transformer.main import save_results

        ML_IMPORTS_AVAILABLE = True
        logger.info("Successfully imported transformer.main via sys.path")
    except ImportError as e:
        ML_IMPORTS_AVAILABLE = False
        ML_IMPORT_ERROR = str(e)
        logger.error(f"Could not import transformer.main: {e}")


def run_ml_training(config_path: str = ""):
    """Run the ML training pipeline using transformer.main.main()"""
    if not ML_IMPORTS_AVAILABLE:
        logger.error(f"ML dependencies not available: {ML_IMPORT_ERROR}")
        return 1

    # Set config path in environment if provided
    if config_path:
        os.environ["CONFIG_PATH"] = config_path

    # Pass config path as CLI arg to transformer.main.main()
    sys_argv_backup = sys.argv.copy()
    sys.argv = [sys.argv[0], "--config", config_path] if config_path else [sys.argv[0]]
    try:
        return transformer_main()
    except Exception as e:
        logger.error(f"Training failed: {str(e)}", exc_info=True)
        return 1
    finally:
        sys.argv = sys_argv_backup


"""Configuration validation utilities"""


def validate_transformer_config(config):
    """Validate transformer-specific configuration"""
    if not hasattr(config, "model"):
        raise ValueError("Configuration missing 'model' section")

    if not hasattr(config, "data"):
        raise ValueError("Configuration missing 'data' section")

    if not hasattr(config, "training"):
        raise ValueError("Configuration missing 'training' section")

    return True


def validate_data_config(data_config):
    """Validate data configuration"""
    required_fields = ["seq_length", "pred_length", "batch_size"]
    for field in required_fields:
        if not hasattr(data_config, field):
            raise ValueError(f"Missing required data config field: {field}")
    return True


def _custom_endpoints():
    """Build custom endpoints dict for the template to register."""
    try:
        import numpy as np
    except Exception as e:
        logger.warning(f"Predict endpoint unavailable (numpy import failed): {e}")
        return {}

    model_holder: dict[str, Any] = {"model": None, "cls": None}

    def predict_handler():
        from flask import jsonify, request

        # Lazy-load model classes on first request
        if model_holder.get("cls") is None:
            HMMTransformer, HMMConfig = _import_hmm_transformer()
            if not HMMTransformer or not HMMConfig:
                return jsonify({"ok": False, "error": "HMM model import failed"}), 503
            model_holder["cls"] = (HMMTransformer, HMMConfig)

        HMMTransformer, HMMConfig = model_holder["cls"]  # type: ignore

        # Initialize model if needed
        mdl = model_holder.get("model")
        if mdl is None:
            model = HMMTransformer(in_features=2, hmm_cfg=HMMConfig(n_states=3))
            model_holder["model"] = model
        else:
            model = mdl

        # CORS preflight shortcut
        if request.method == "OPTIONS":
            return ("", 204)

        # Branch on method: POST can accept a series payload; GET uses demo data
        if request.method == "POST":
            try:
                data = request.get_json(silent=True) or {}
                series = data.get("series")
                # Optional: window length
                try:
                    window = int(data.get("window", 64))
                except Exception:
                    window = 64
                window = max(16, min(256, window))
                if not isinstance(series, (list, tuple)) or len(series) < 10:
                    return (
                        jsonify({
                            "ok": False,
                            "error": "Provide JSON {series:[numbers...]} with >=10 points",
                        }),
                        400,
                    )
                import numpy as _np
                prices = _np.asarray(series, dtype=float)
                ret = _np.diff(_np.log(prices))
                obs = ret.reshape(-1, 1)
                # (Re)fit a tiny HMM quickly on provided data
                model.fit_hmm(obs)
                feats = _np.stack([ret, _np.abs(ret)], axis=-1)
                # Window for prediction
                S = min(window, feats.shape[0])
                xw = feats[-S:]
                ow = obs[-S:]
                y = model.predict_sequence(xw, ow)
                # Regime posteriors for tail diagnostics
                try:
                    posts = model.regime_posteriors(ow)
                    regimes_tail = posts[-5:].tolist()
                    regime_states_tail = _np.argmax(posts, axis=1)[-5:].tolist()
                    regime_probs_last = posts[-1].tolist()
                    regime_last = int(_np.argmax(posts[-1]))
                    confidence = float(_np.max(posts[-1]))
                except Exception:
                    regimes_tail = []
                    regime_states_tail = []
                    regime_probs_last = []
                    regime_last = None
                    confidence = None
                # Summaries
                y_tail = _np.asarray(y).reshape(-1, y.shape[-1])[-5:, 0].tolist() if y.ndim >= 2 else _np.asarray(y).ravel()[-5:].tolist()
                horizon_pred = float(y[-1][0]) if y.ndim == 2 and y.shape[1] >= 1 else float(_np.asarray(y).ravel()[-1])
                return jsonify({
                    "ok": True,
                    "shape": list(y.shape),
                    "window": int(S),
                    "horizon_pred": horizon_pred,
                    "y_tail": y_tail,
                    "regimes_tail": regimes_tail,
                    "regime_states_tail": regime_states_tail,
                    "regime_probs_last": regime_probs_last,
                    "regime_last": regime_last,
                    "confidence": confidence,
                    "device": ("cuda" if __import__("torch").cuda.is_available() else "cpu"),
                })
            except Exception as ex:
                logger.exception(f"/predict POST error: {ex}")
                return jsonify({"ok": False, "error": str(ex)}), 500
        else:
            # GET demo behavior: generate synthetic random walk
            try:
                window = int(request.args.get("window", 64))
            except Exception:
                window = 64
            window = max(16, min(256, window))
            prices = np.cumprod(1 + 0.001 + 0.01 * np.random.randn(256)) * 100
            ret = np.diff(np.log(prices))
            obs = ret.reshape(-1, 1)
            model.fit_hmm(obs)
            feats = np.stack([ret, np.abs(ret)], axis=-1)
            S = min(window, feats.shape[0])
            xw = feats[-S:]
            ow = obs[-S:]
            y = model.predict_sequence(xw, ow)
            try:
                posts = model.regime_posteriors(ow)
                regimes_tail = posts[-5:].tolist()
                regime_states_tail = np.argmax(posts, axis=1)[-5:].tolist()
                regime_probs_last = posts[-1].tolist()
                regime_last = int(np.argmax(posts[-1]))
                confidence = float(np.max(posts[-1]))
            except Exception:
                regimes_tail = []
                regime_states_tail = []
                regime_probs_last = []
                regime_last = None
                confidence = None
            y_tail = np.asarray(y).reshape(-1, y.shape[-1])[-5:, 0].tolist() if y.ndim >= 2 else np.asarray(y).ravel()[-5:].tolist()
            horizon_pred = float(y[-1][0]) if y.ndim == 2 and y.shape[1] >= 1 else float(np.asarray(y).ravel()[-1])
            return jsonify({
                "ok": True,
                "shape": list(y.shape),
                "window": int(S),
                "horizon_pred": horizon_pred,
                "y_tail": y_tail,
                "regimes_tail": regimes_tail,
                "regime_states_tail": regime_states_tail,
                "regime_probs_last": regime_probs_last,
                "regime_last": regime_last,
                "confidence": confidence,
                "device": ("cuda" if __import__("torch").cuda.is_available() else "cpu"),
            })

    # Register endpoint with explicit methods support
    return {"/predict": (predict_handler, ["GET", "POST", "OPTIONS"])}


def run_service():
    """Run the transformer service"""
    # Set the service name and port from environment variables or defaults
    service_name = os.getenv("TRANSFORMER_SERVICE_NAME", "transformer")
    port = os.getenv("TRANSFORMER_SERVICE_PORT", os.getenv("SERVICE_PORT", "8004"))

    # Log the service startup
    logger.info(f"Starting {service_name} service on port {port}")

    if HAS_TEMPLATE_SERVICE:
        # Start the service using the template with our custom endpoints
        try:
            _framework_start_template_service(
                service_name=service_name,
                service_port=int(port),
                custom_endpoints=_custom_endpoints(),
            )
            return
        except Exception as _:
            # Fall back to template without custom endpoints
            _framework_start_template_service(
                service_name=service_name, service_port=int(port)
            )
            return
    else:
        # Fallback: run a simple Flask service
        logger.warning("Template service not available, running simple fallback")
        from flask import Flask, jsonify

        app = Flask(service_name)

        @app.route("/health")
        def health():
            return jsonify(
                {
                    "status": "healthy",
                    "service": service_name,
                    "ml_available": ML_IMPORTS_AVAILABLE,
                }
            )

        @app.route("/info")
        def info():
            return jsonify(
                {
                    "service": service_name,
                    "status": "running",
                    "mode": "service",
                    "ml_available": ML_IMPORTS_AVAILABLE,
                    "template_service_available": HAS_TEMPLATE_SERVICE,
                }
            )

        @app.route("/")
        def root():
            return jsonify(
                {
                    "service": service_name,
                    "status": "running",
                    "mode": "service",
                    "endpoints": ["/health", "/info"],
                    "ml_training_available": ML_IMPORTS_AVAILABLE,
                }
            )

        # Optional: lightweight inference stub using the HMM-Transformer
        try:
            import numpy as np
            from services.transformer.models.hmm_transformer import (
                HMMTransformer,
                HMMConfig,
            )

            model_holder: dict[str, Any] = {"model": None}

            @app.route("/predict", methods=["GET", "POST", "OPTIONS"])
            def predict():
                from flask import request
                if request.method == "OPTIONS":
                    return ("", 204)
                # Demo endpoint; POST accepts {series:[...]} otherwise generate sample
                if model_holder.get("model") is None:
                    model = HMMTransformer(in_features=2, hmm_cfg=HMMConfig(n_states=3))
                    model_holder["model"] = model
                else:
                    model = model_holder["model"]  # type: ignore

                if request.method == "POST":
                    data = request.get_json(silent=True) or {}
                    series = data.get("series")
                    if not isinstance(series, (list, tuple)) or len(series) < 10:
                        return jsonify({
                            "ok": False,
                            "error": "Provide JSON {series:[numbers...]} with >=10 points",
                        }), 400
                    try:
                        window = int(data.get("window", 64))
                    except Exception:
                        window = 64
                    window = max(16, min(256, window))
                    prices = np.asarray(series, dtype=float)
                else:
                    try:
                        window = int(request.args.get("window", 64))
                    except Exception:
                        window = 64
                    window = max(16, min(256, window))
                    prices = np.cumprod(1 + 0.001 + 0.01 * np.random.randn(256)) * 100

                ret = np.diff(np.log(prices))
                obs = ret.reshape(-1, 1)
                model.fit_hmm(obs)
                feats = np.stack([ret, np.abs(ret)], axis=-1)
                S = min(window, feats.shape[0])
                xw = feats[-S:]
                ow = obs[-S:]
                y = model.predict_sequence(xw, ow)
                try:
                    posts = model.regime_posteriors(ow)
                    regimes_tail = posts[-5:].tolist()
                    regime_states_tail = np.argmax(posts, axis=1)[-5:].tolist()
                    regime_probs_last = posts[-1].tolist()
                    regime_last = int(np.argmax(posts[-1]))
                    confidence = float(np.max(posts[-1]))
                except Exception:
                    regimes_tail = []
                    regime_states_tail = []
                    regime_probs_last = []
                    regime_last = None
                    confidence = None
                y_tail = np.asarray(y).reshape(-1, y.shape[-1])[-5:, 0].tolist() if y.ndim >= 2 else np.asarray(y).ravel()[-5:].tolist()
                horizon_pred = float(y[-1][0]) if y.ndim == 2 and y.shape[1] >= 1 else float(np.asarray(y).ravel()[-1])
                return jsonify({
                    "ok": True,
                    "shape": list(y.shape),
                    "window": int(S),
                    "horizon_pred": horizon_pred,
                    "y_tail": y_tail,
                    "regimes_tail": regimes_tail,
                    "regime_states_tail": regime_states_tail,
                    "regime_probs_last": regime_probs_last,
                    "regime_last": regime_last,
                    "confidence": confidence,
                    "device": ("cuda" if __import__("torch").cuda.is_available() else "cpu"),
                })
        except Exception as _:
            pass

        logger.info(f"Fallback service starting on http://0.0.0.0:{port}")
        app.run(host="0.0.0.0", port=int(port), debug=False)


def main():
    """Main entry point with mode selection"""
    parser = argparse.ArgumentParser(
        description="Transformer Service/Training Entry Point"
    )
    parser.add_argument(
        "--mode",
        choices=["service", "train"],
        default="service",
        help="Run mode: service (default) or train",
    )
    parser.add_argument(
        "--config", help="Path to configuration file (for training mode)"
    )
    parser.add_argument(
        "--service-name",
        default=os.getenv("TRANSFORMER_SERVICE_NAME", "transformer"),
        help="Service name (for service mode)",
    )
    parser.add_argument(
        "--port",
        default=os.getenv("TRANSFORMER_SERVICE_PORT", "8089"),
        help="Service port (for service mode)",
    )

    args = parser.parse_args()

    logger.info(f"Transformer service starting in {args.mode} mode")

    if args.mode == "train":
        logger.info("Running in ML training mode")
        if not ML_IMPORTS_AVAILABLE:
            logger.error(f"Cannot run training mode: {ML_IMPORT_ERROR}")
            return 1
        return run_ml_training(args.config)

    elif args.mode == "service":
        logger.info("Running in service mode")
        # Override environment variables if provided via args
        if args.service_name != os.getenv("TRANSFORMER_SERVICE_NAME", "transformer"):
            os.environ["TRANSFORMER_SERVICE_NAME"] = args.service_name
        if args.port != os.getenv("TRANSFORMER_SERVICE_PORT", "8089"):
            os.environ["TRANSFORMER_SERVICE_PORT"] = args.port

        run_service()
        return 0

    else:
        logger.error(f"Unknown mode: {args.mode}")
        return 1


if __name__ == "__main__":
    sys.exit(main())


# Service-runner integration: provide a stable start function name the dispatcher expects
def start_transformer(service_name: str | None = None, service_port: int | str | None = None):
    """
    Entry point used by the enhanced dispatcher to start the transformer service.
    Ensures our module (with custom /predict endpoint) is used instead of a generic template.
    """
    if service_name:
        os.environ["TRANSFORMER_SERVICE_NAME"] = str(service_name)
    if service_port is not None:
        os.environ["TRANSFORMER_SERVICE_PORT"] = str(service_port)

    # Delegate to the standard service runner in this module
    run_service()


def start_template_service(service_name: str | None = None, service_port: int | str | None = None):
    """Wrapper so the runner can call this and still get our custom endpoints."""
    if service_name:
        os.environ["TRANSFORMER_SERVICE_NAME"] = str(service_name)
    if service_port is not None:
        os.environ["TRANSFORMER_SERVICE_PORT"] = str(service_port)

    name = os.getenv("TRANSFORMER_SERVICE_NAME", "transformer")
    port = int(os.getenv("TRANSFORMER_SERVICE_PORT", "8089"))

    if HAS_TEMPLATE_SERVICE:
        _framework_start_template_service(
            service_name=name, service_port=port, custom_endpoints=_custom_endpoints()
        )
    else:
        run_service()
