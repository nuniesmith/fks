def test_config_stubs_or_shared():
    """Service should function whether or not shared packages are installed.

    Preference order when USE_SHARED=1:
    1. shared_python
    2. shared_python (legacy alias)
    3. standalone_shared stubs
    """
    import os

    use_shared = os.getenv("USE_SHARED", "0") == "1"
    if use_shared:
        load_config = None  # type: ignore
        for mod_name in ("shared_python", "shared_python"):
            try:  # pragma: no cover - dynamic import path variance
                mod = __import__(mod_name, fromlist=["load_config"])  # type: ignore
                if hasattr(mod, "load_config"):
                    load_config = getattr(mod, "load_config")
                    break
            except Exception:  # noqa: BLE001
                continue
        if load_config is None:  # fallback to stubs
            from standalone_shared import load_config  # type: ignore
    else:
        from standalone_shared import load_config  # type: ignore

    cfg = load_config()
    assert isinstance(cfg, dict)
    assert "environment" in cfg
