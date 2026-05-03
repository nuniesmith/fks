"""
End-to-end tests for the Pine Script Generator API.

Covers all major endpoints:
  - GET  /api/pine/stats      — module/line count statistics
  - POST /api/pine/generate   — script generation
  - GET  /api/pine/download/  — file download after generation
  - GET  /api/pine/modules    — module listing
  - GET  /api/pine/params     — params.yaml content
  - GET  /api/pine/output     — output file listing
"""

from __future__ import annotations

import os

# Disable Redis so no background connection is attempted during tests.
os.environ.setdefault("DISABLE_REDIS", "1")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ===========================================================================
# Fixture
# ===========================================================================


@pytest.fixture()
def pine_client(monkeypatch, tmp_path):
    """Pine Script Generator TestClient.

    Uses the real module files from the integration directory so the
    end-to-end generation pipeline is exercised.  Output is redirected to
    *tmp_path* so no artefacts are left in the source tree.
    """
    # Redirect generated files to an isolated temp directory.
    monkeypatch.setenv("PINE_OUTPUT_DIR", str(tmp_path))

    # Use a fresh cache directory so disk-cached scripts never short-circuit
    # the generator's processed_files population (which would produce a
    # spurious module_count of 0 in stats tests).
    monkeypatch.setenv("PINE_CACHE_DIR", str(tmp_path / "pine_cache"))

    # Reset module-level path/generator singletons so _init_paths() runs
    # fresh and picks up the new PINE_OUTPUT_DIR env-var value.
    import lib.services.data.api.pine as pine_mod  # noqa: PLC0415

    monkeypatch.setattr(pine_mod, "_BASE_DIR", None)
    monkeypatch.setattr(pine_mod, "_OUTPUT_DIR", None)
    monkeypatch.setattr(pine_mod, "_MODULES_DIR", None)
    monkeypatch.setattr(pine_mod, "_PARAMS_FILE", None)
    monkeypatch.setattr(pine_mod, "_generator", None)

    app = FastAPI()
    app.include_router(pine_mod.router)

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


# ===========================================================================
# Stats
# ===========================================================================


class TestPineStats:
    def test_pine_api_status(self, pine_client):
        """GET /api/pine/stats returns 200 with module and line count data."""
        r = pine_client.get("/api/pine/stats")
        assert r.status_code == 200

    def test_pine_stats_is_json(self, pine_client):
        r = pine_client.get("/api/pine/stats")
        d = r.json()
        assert isinstance(d, dict)

    def test_pine_stats_has_module_count(self, pine_client):
        r = pine_client.get("/api/pine/stats")
        d = r.json()
        assert "module_count" in d

    def test_pine_stats_has_total_lines(self, pine_client):
        r = pine_client.get("/api/pine/stats")
        d = r.json()
        assert "total_lines" in d

    def test_pine_stats_module_count_positive(self, pine_client):
        r = pine_client.get("/api/pine/stats")
        d = r.json()
        assert d["module_count"] > 0

    def test_pine_stats_total_lines_positive(self, pine_client):
        r = pine_client.get("/api/pine/stats")
        d = r.json()
        assert d["total_lines"] > 0

    def test_pine_stats_has_indicator_type(self, pine_client):
        r = pine_client.get("/api/pine/stats")
        d = r.json()
        assert "indicator_type" in d
        assert d["indicator_type"] == "ruby"


# ===========================================================================
# Generate
# ===========================================================================


class TestPineGenerate:
    def test_pine_generate_returns_200(self, pine_client):
        """POST /api/pine/generate returns HTTP 200."""
        r = pine_client.post("/api/pine/generate")
        assert r.status_code == 200

    def test_pine_generate_produces_output(self, pine_client):
        """POST /api/pine/generate returns ok: True and a filename field."""
        r = pine_client.post("/api/pine/generate")
        d = r.json()
        assert d.get("ok") is True

    def test_pine_generate_returns_filename(self, pine_client):
        r = pine_client.post("/api/pine/generate")
        d = r.json()
        assert "filename" in d

    def test_pine_generate_filename_is_pine(self, pine_client):
        r = pine_client.post("/api/pine/generate")
        d = r.json()
        assert d["filename"].endswith(".pine")

    def test_pine_generate_filename_is_ruby(self, pine_client):
        r = pine_client.post("/api/pine/generate")
        d = r.json()
        assert "ruby" in d["filename"].lower()

    def test_pine_generate_returns_size_kb(self, pine_client):
        r = pine_client.post("/api/pine/generate")
        d = r.json()
        assert "size_kb" in d
        assert d["size_kb"] > 0

    def test_pine_generate_returns_path(self, pine_client):
        r = pine_client.post("/api/pine/generate")
        d = r.json()
        assert "path" in d

    def test_pine_generate_with_explicit_type(self, pine_client):
        """POST /api/pine/generate with indicator_type body param works."""
        r = pine_client.post(
            "/api/pine/generate",
            json={"indicator_type": "ruby"},
        )
        assert r.status_code == 200
        assert r.json().get("ok") is True


# ===========================================================================
# Download
# ===========================================================================


class TestPineDownload:
    def test_pine_download_file(self, pine_client):
        """GET /api/pine/download/{filename} returns 200 after generation."""
        gen_r = pine_client.post("/api/pine/generate")
        assert gen_r.status_code == 200
        filename = gen_r.json()["filename"]

        dl_r = pine_client.get(f"/api/pine/download/{filename}")
        assert dl_r.status_code == 200

    def test_pine_download_content_non_empty(self, pine_client):
        gen_r = pine_client.post("/api/pine/generate")
        filename = gen_r.json()["filename"]

        dl_r = pine_client.get(f"/api/pine/download/{filename}")
        assert len(dl_r.text) > 0

    def test_pine_download_contains_pine_script_syntax(self, pine_client):
        """Downloaded file should contain Pine Script indicator declaration."""
        gen_r = pine_client.post("/api/pine/generate")
        filename = gen_r.json()["filename"]

        dl_r = pine_client.get(f"/api/pine/download/{filename}")
        content = dl_r.text
        # Pine scripts always start with a comment or indicator() call
        assert "//" in content or "indicator(" in content

    def test_pine_download_missing_file_returns_404(self, pine_client):
        r = pine_client.get("/api/pine/download/nonexistent_file.pine")
        assert r.status_code == 404

    def test_pine_download_path_traversal_rejected(self, pine_client):
        r = pine_client.get("/api/pine/download/../etc/passwd")
        assert r.status_code in (400, 404, 422)


# ===========================================================================
# Modules
# ===========================================================================


class TestPineListModules:
    def test_pine_list_modules(self, pine_client):
        """GET /api/pine/modules returns 200 with at least one module."""
        r = pine_client.get("/api/pine/modules")
        assert r.status_code == 200

    def test_pine_list_modules_is_json(self, pine_client):
        r = pine_client.get("/api/pine/modules")
        d = r.json()
        assert isinstance(d, dict)

    def test_pine_list_modules_has_modules_key(self, pine_client):
        r = pine_client.get("/api/pine/modules")
        d = r.json()
        assert "modules" in d

    def test_pine_list_modules_is_a_list(self, pine_client):
        r = pine_client.get("/api/pine/modules")
        d = r.json()
        assert isinstance(d["modules"], list)

    def test_pine_list_modules_non_empty(self, pine_client):
        r = pine_client.get("/api/pine/modules")
        d = r.json()
        assert len(d["modules"]) >= 1

    def test_pine_list_modules_has_count(self, pine_client):
        r = pine_client.get("/api/pine/modules")
        d = r.json()
        assert "count" in d
        assert d["count"] == len(d["modules"])

    def test_pine_list_modules_items_have_name(self, pine_client):
        r = pine_client.get("/api/pine/modules")
        modules = r.json()["modules"]
        for m in modules:
            assert "name" in m

    def test_pine_list_modules_names_end_with_pine(self, pine_client):
        r = pine_client.get("/api/pine/modules")
        modules = r.json()["modules"]
        for m in modules:
            assert m["name"].endswith(".pine"), f"unexpected module: {m['name']}"

    def test_pine_list_modules_items_have_size(self, pine_client):
        r = pine_client.get("/api/pine/modules")
        modules = r.json()["modules"]
        for m in modules:
            assert "size_kb" in m

    def test_pine_list_modules_contains_header(self, pine_client):
        """The header.pine module should always be present."""
        r = pine_client.get("/api/pine/modules")
        names = [m["name"] for m in r.json()["modules"]]
        assert any("header" in n for n in names)


# ===========================================================================
# Params
# ===========================================================================


class TestPineGetParams:
    def test_pine_get_params(self, pine_client):
        """GET /api/pine/params returns 200 with params content."""
        r = pine_client.get("/api/pine/params")
        assert r.status_code == 200

    def test_pine_get_params_is_json(self, pine_client):
        r = pine_client.get("/api/pine/params")
        d = r.json()
        assert isinstance(d, dict)

    def test_pine_get_params_has_raw_or_content(self, pine_client):
        """Response contains either 'raw' or 'content' (YAML string)."""
        r = pine_client.get("/api/pine/params")
        d = r.json()
        raw = d.get("raw") or d.get("content") or ""
        assert len(raw) > 0

    def test_pine_get_params_content_key_present(self, pine_client):
        """The 'content' key is available as an alias for 'raw'."""
        r = pine_client.get("/api/pine/params")
        d = r.json()
        assert "content" in d
        assert len(d["content"]) > 0

    def test_pine_get_params_raw_is_valid_yaml(self, pine_client):
        """The returned raw text should be parseable as YAML."""
        import yaml  # noqa: PLC0415

        r = pine_client.get("/api/pine/params")
        raw = r.json().get("raw", "")
        parsed = yaml.safe_load(raw)
        assert isinstance(parsed, dict)

    def test_pine_get_params_has_params_key(self, pine_client):
        r = pine_client.get("/api/pine/params")
        d = r.json()
        assert "params" in d
        assert isinstance(d["params"], dict)


# ===========================================================================
# Output listing
# ===========================================================================


class TestPineOutputList:
    def test_pine_output_list(self, pine_client):
        """GET /api/pine/output returns 200 with a 'files' list."""
        r = pine_client.get("/api/pine/output")
        assert r.status_code == 200

    def test_pine_output_list_is_json(self, pine_client):
        r = pine_client.get("/api/pine/output")
        d = r.json()
        assert isinstance(d, dict)

    def test_pine_output_list_has_files_key(self, pine_client):
        r = pine_client.get("/api/pine/output")
        d = r.json()
        assert "files" in d

    def test_pine_output_list_files_is_list(self, pine_client):
        r = pine_client.get("/api/pine/output")
        d = r.json()
        assert isinstance(d["files"], list)

    def test_pine_output_list_empty_before_generate(self, pine_client):
        """Before generation the output list should be empty (fresh tmp_path)."""
        r = pine_client.get("/api/pine/output")
        d = r.json()
        assert d["files"] == []

    def test_pine_output_list_non_empty_after_generate(self, pine_client):
        """After generation the output list should contain at least one file."""
        pine_client.post("/api/pine/generate")
        r = pine_client.get("/api/pine/output")
        d = r.json()
        assert len(d["files"]) >= 1

    def test_pine_output_list_files_end_with_pine(self, pine_client):
        pine_client.post("/api/pine/generate")
        r = pine_client.get("/api/pine/output")
        files = r.json()["files"]
        for f in files:
            assert f["name"].endswith(".pine")

    def test_pine_output_list_files_have_size_kb(self, pine_client):
        pine_client.post("/api/pine/generate")
        r = pine_client.get("/api/pine/output")
        for f in r.json()["files"]:
            assert "size_kb" in f
