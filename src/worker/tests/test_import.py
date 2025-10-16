def test_import_worker():
    import importlib
    mod = importlib.import_module("main")
    assert hasattr(mod, "main")
