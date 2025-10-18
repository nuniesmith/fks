def test_import_engine():
    import importlib
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    mod = importlib.import_module("main")
    assert hasattr(mod, "main")
