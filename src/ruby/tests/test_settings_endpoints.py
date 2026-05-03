"""
Comprehensive tests for the settings API endpoints.

Tests all settings-related routes without requiring Redis, Postgres, or a
running engine.  Uses FastAPI's TestClient with an in-process SQLite DB
for key_manager operations.

Covers:
  GET  /settings/services/config
  POST /settings/services/update
  GET  /settings/features/config
  POST /settings/features/update
  GET  /settings/risk/config
  POST /settings/risk/update
  GET  /settings/keys/status
  GET  /settings/keys/list
  POST /settings/keys/set
  DELETE /settings/keys/{name}
  POST /settings/keys/validate
  GET  /settings/keys/audit

Skipped (per spec):
  GET  /settings               — HTML page, no JSON to assert
  GET  /settings/services/probe — makes real outbound HTTP calls
"""

from __future__ import annotations

import os
import sqlite3

import pytest

# Disable Redis before any settings-module import so cache_get/cache_set
# are no-ops throughout every test in this file.
os.environ.setdefault("DISABLE_REDIS", "1")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    """Minimal FastAPI app containing only the settings router.

    Suitable for all endpoint groups that do NOT require key_manager DB
    operations (service config, features, risk, legacy key status, validate).
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from lib.services.data.api.settings import router as settings_router

    app = FastAPI()
    app.include_router(settings_router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def km_patched(monkeypatch, tmp_path):
    """Patch key_manager to use an isolated SQLite DB with a live Fernet key.

    Mirrors the ``sqlite_km`` fixture in test_key_manager.py so that all
    DB-backed key operations (list, set, delete, audit) run against a clean
    temporary database instead of whatever the host system has configured.

    Returns the already-imported ``lib.core.key_manager`` module so callers
    can access ``KNOWN_KEYS``, ``ensure_tables_exist``, etc.
    """
    from cryptography.fernet import Fernet

    # Inject a valid encryption secret so Fernet works.
    monkeypatch.setenv("API_KEY_ENCRYPTION_SECRET", Fernet.generate_key().decode())
    # Force SQLite path inside key_manager (DATABASE_URL="" → not postgres).
    monkeypatch.setenv("DATABASE_URL", "")

    db_path = tmp_path / "km_settings_test.db"

    def _make_conn():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn

    import lib.core.key_manager as km

    monkeypatch.setattr(km, "_get_conn", _make_conn)
    monkeypatch.setattr(km, "_row_to_dict", lambda r: dict(r))
    monkeypatch.setattr(km, "_is_postgres", lambda: False)
    # Reset the cached Fernet singleton so it re-initialises with the new secret.
    monkeypatch.setattr(km, "_fernet", None)

    km.ensure_tables_exist()
    return km


@pytest.fixture()
def km_client(km_patched):
    """TestClient built *after* key_manager patching is in effect.

    Use this fixture for any test that exercises /settings/keys/list,
    /settings/keys/set, DELETE /settings/keys/{name}, or
    /settings/keys/audit — all of which require the api_keys /
    api_key_audit tables to be present.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from lib.services.data.api.settings import router as settings_router

    app = FastAPI()
    app.include_router(settings_router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ===========================================================================
# TestServiceConfig
# ===========================================================================


class TestServiceConfig:
    """GET /settings/services/config  and  POST /settings/services/update."""

    def test_get_service_config_returns_200(self, client):
        resp = client.get("/settings/services/config")
        assert resp.status_code == 200

    def test_get_service_config_has_data_service_url(self, client):
        resp = client.get("/settings/services/config")
        assert "data_service_url" in resp.json()

    def test_get_service_config_has_trainer_service_url(self, client):
        resp = client.get("/settings/services/config")
        assert "trainer_service_url" in resp.json()

    def test_get_service_config_urls_are_strings(self, client):
        data = client.get("/settings/services/config").json()
        assert isinstance(data["data_service_url"], str)
        assert isinstance(data["trainer_service_url"], str)

    def test_get_service_config_default_urls_are_non_empty(self, client):
        data = client.get("/settings/services/config").json()
        assert data["data_service_url"]
        assert data["trainer_service_url"]

    def test_update_service_data_url_returns_ok(self, client):
        resp = client.post(
            "/settings/services/update",
            json={"data_service_url": "http://new-data:8000"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_update_service_trainer_url_returns_ok(self, client):
        resp = client.post(
            "/settings/services/update",
            json={"trainer_service_url": "http://new-trainer:8200"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_update_service_both_urls_returns_ok(self, client):
        resp = client.post(
            "/settings/services/update",
            json={
                "data_service_url": "http://data:8000",
                "trainer_service_url": "http://trainer:8200",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_update_service_empty_body_returns_ok(self, client):
        """An empty update body is valid — no fields changed but still 200."""
        resp = client.post("/settings/services/update", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_update_service_response_contains_services_key(self, client):
        resp = client.post(
            "/settings/services/update",
            json={"data_service_url": "http://check:8000"},
        )
        body = resp.json()
        assert "services" in body

    def test_update_service_unknown_fields_ignored_gracefully(self, client):
        """Extra keys in the body should not cause a 4xx/5xx error."""
        resp = client.post(
            "/settings/services/update",
            json={"unknown_service_xyz": "http://nope:1234"},
        )
        assert resp.status_code == 200


# ===========================================================================
# TestFeaturesConfig
# ===========================================================================


class TestFeaturesConfig:
    """GET /settings/features/config  and  POST /settings/features/update."""

    _ALL_BOOL_KEYS = [
        "enable_live_positions",
        "enable_kraken_crypto",
        "massive_autostart",
        "enable_grok",
        "orb_cnn_gate",
        "orb_filter_gate",
        "mtf_alignment_check",
        "enable_sar",
        "tpt_mode",
        "enable_tp3_trailing",
        "enable_auto_brackets",
        "enable_debug_logging",
    ]

    def test_get_features_config_returns_200(self, client):
        resp = client.get("/settings/features/config")
        assert resp.status_code == 200

    def test_get_features_config_has_enable_kraken_crypto(self, client):
        resp = client.get("/settings/features/config")
        assert "enable_kraken_crypto" in resp.json()

    def test_get_features_config_has_orb_cnn_gate(self, client):
        resp = client.get("/settings/features/config")
        assert "orb_cnn_gate" in resp.json()

    def test_get_features_config_has_orb_filter_gate(self, client):
        resp = client.get("/settings/features/config")
        assert "orb_filter_gate" in resp.json()

    def test_get_features_config_has_enable_grok(self, client):
        resp = client.get("/settings/features/config")
        assert "enable_grok" in resp.json()

    def test_get_features_config_all_keys_present(self, client):
        data = client.get("/settings/features/config").json()
        for key in self._ALL_BOOL_KEYS:
            assert key in data, f"Expected key '{key}' in features config"

    def test_get_features_config_all_values_are_boolean(self, client):
        data = client.get("/settings/features/config").json()
        for key in self._ALL_BOOL_KEYS:
            assert isinstance(data[key], bool), (
                f"Feature '{key}' should be bool, got {type(data[key]).__name__}: {data[key]!r}"
            )

    def test_update_features_enable_kraken_crypto_returns_ok(self, client):
        resp = client.post(
            "/settings/features/update",
            json={"enable_kraken_crypto": True},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_update_features_returns_changed_dict(self, client):
        resp = client.post(
            "/settings/features/update",
            json={"enable_kraken_crypto": True},
        )
        body = resp.json()
        assert "changed" in body
        assert isinstance(body["changed"], dict)

    def test_update_features_changed_contains_updated_key(self, client):
        resp = client.post(
            "/settings/features/update",
            json={"enable_kraken_crypto": True},
        )
        changed = resp.json()["changed"]
        assert "enable_kraken_crypto" in changed
        assert changed["enable_kraken_crypto"] is True

    def test_update_features_unknown_key_returns_200(self, client):
        """Unknown feature keys should be silently ignored, not raise 4xx."""
        resp = client.post(
            "/settings/features/update",
            json={"totally_fake_feature_xyz": True},
        )
        assert resp.status_code == 200

    def test_update_features_unknown_key_not_in_changed(self, client):
        resp = client.post(
            "/settings/features/update",
            json={"totally_fake_feature_xyz": True},
        )
        assert "totally_fake_feature_xyz" not in resp.json().get("changed", {})

    def test_update_features_orb_filter_gate_false_in_changed(self, client):
        resp = client.post(
            "/settings/features/update",
            json={"orb_filter_gate": False},
        )
        assert resp.status_code == 200
        changed = resp.json()["changed"]
        assert "orb_filter_gate" in changed
        assert changed["orb_filter_gate"] is False

    def test_update_features_mixed_valid_and_unknown_keys(self, client):
        resp = client.post(
            "/settings/features/update",
            json={"enable_grok": True, "not_a_real_toggle": True},
        )
        assert resp.status_code == 200
        changed = resp.json()["changed"]
        assert "enable_grok" in changed
        assert "not_a_real_toggle" not in changed

    def test_update_features_multiple_known_keys(self, client):
        resp = client.post(
            "/settings/features/update",
            json={
                "orb_cnn_gate": True,
                "orb_filter_gate": False,
                "enable_debug_logging": True,
            },
        )
        assert resp.status_code == 200
        changed = resp.json()["changed"]
        assert changed.get("orb_cnn_gate") is True
        assert changed.get("orb_filter_gate") is False
        assert changed.get("enable_debug_logging") is True

    def test_update_features_empty_body_returns_ok(self, client):
        resp = client.post("/settings/features/update", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_update_features_empty_body_changed_is_empty(self, client):
        resp = client.post("/settings/features/update", json={})
        assert resp.json()["changed"] == {}

    def test_update_features_coerces_truthy_values_to_bool(self, client):
        """Non-boolean truthy values (e.g. 1) should be stored as True."""
        resp = client.post(
            "/settings/features/update",
            json={"enable_sar": 1},
        )
        assert resp.status_code == 200
        changed = resp.json()["changed"]
        assert changed.get("enable_sar") is True


# ===========================================================================
# TestRiskConfig
# ===========================================================================


class TestRiskConfig:
    """GET /settings/risk/config  and  POST /settings/risk/update."""

    _INT_KEYS = [
        "max_contracts",
        "max_concurrent_positions",
        "entry_cooldown_minutes",
        "default_sl_ticks",
        "default_tp_ticks",
        "sar_cooldown_minutes",
        "cnn_lookback_bars",
        "volume_avg_period",
        "orb_minutes",
    ]

    _FLOAT_KEYS = [
        "risk_percent_per_trade",
        "sl_atr_mult",
        "tp1_atr_mult",
        "tp2_atr_mult",
        "tp3_atr_mult",
        "sar_min_cnn_prob",
        "sar_min_mtf_score",
        "sar_chase_max_atr_fraction",
        "sar_winning_cnn_prob",
        "sar_high_winner_r_mult",
        "volume_surge_mult",
        "min_orb_atr_ratio",
    ]

    def test_get_risk_config_returns_200(self, client):
        resp = client.get("/settings/risk/config")
        assert resp.status_code == 200

    def test_get_risk_config_has_risk_percent_per_trade(self, client):
        resp = client.get("/settings/risk/config")
        assert "risk_percent_per_trade" in resp.json()

    def test_get_risk_config_has_sl_atr_mult(self, client):
        resp = client.get("/settings/risk/config")
        assert "sl_atr_mult" in resp.json()

    def test_get_risk_config_has_max_contracts(self, client):
        resp = client.get("/settings/risk/config")
        assert "max_contracts" in resp.json()

    def test_get_risk_config_has_require_vwap(self, client):
        resp = client.get("/settings/risk/config")
        assert "require_vwap" in resp.json()

    def test_get_risk_config_all_numeric_keys_present(self, client):
        data = client.get("/settings/risk/config").json()
        for key in self._INT_KEYS + self._FLOAT_KEYS:
            assert key in data, f"Expected numeric key '{key}' in risk config"

    def test_get_risk_config_int_fields_are_numeric(self, client):
        data = client.get("/settings/risk/config").json()
        for key in self._INT_KEYS:
            assert isinstance(data[key], (int, float)), (
                f"Risk param '{key}' should be numeric, got {type(data[key]).__name__}: {data[key]!r}"
            )

    def test_get_risk_config_float_fields_are_numeric(self, client):
        data = client.get("/settings/risk/config").json()
        for key in self._FLOAT_KEYS:
            assert isinstance(data[key], (int, float)), (
                f"Risk param '{key}' should be numeric, got {type(data[key]).__name__}: {data[key]!r}"
            )

    def test_get_risk_config_no_string_values_for_numeric_fields(self, client):
        data = client.get("/settings/risk/config").json()
        for key in self._INT_KEYS + self._FLOAT_KEYS:
            assert not isinstance(data[key], str), f"Risk param '{key}' must not be a string, got {data[key]!r}"

    def test_update_risk_sl_atr_mult_returns_ok(self, client):
        resp = client.post(
            "/settings/risk/update",
            json={"sl_atr_mult": 2.0},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_update_risk_sl_atr_mult_in_changed(self, client):
        resp = client.post(
            "/settings/risk/update",
            json={"sl_atr_mult": 2.0},
        )
        changed = resp.json()["changed"]
        assert "sl_atr_mult" in changed
        assert changed["sl_atr_mult"] == 2.0

    def test_update_risk_max_contracts_coerced_to_int(self, client):
        resp = client.post(
            "/settings/risk/update",
            json={"max_contracts": 3},
        )
        assert resp.status_code == 200
        changed = resp.json()["changed"]
        assert "max_contracts" in changed
        assert isinstance(changed["max_contracts"], int)
        assert changed["max_contracts"] == 3

    def test_update_risk_entry_cooldown_coerced_to_int(self, client):
        resp = client.post(
            "/settings/risk/update",
            json={"entry_cooldown_minutes": 15},
        )
        assert resp.status_code == 200
        changed = resp.json()["changed"]
        assert isinstance(changed["entry_cooldown_minutes"], int)
        assert changed["entry_cooldown_minutes"] == 15

    def test_update_risk_unknown_key_silently_ignored(self, client):
        resp = client.post(
            "/settings/risk/update",
            json={"not_a_real_param": 999},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert "not_a_real_param" not in resp.json().get("changed", {})

    def test_update_risk_empty_body_returns_ok(self, client):
        resp = client.post("/settings/risk/update", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_update_risk_empty_body_changed_is_empty(self, client):
        resp = client.post("/settings/risk/update", json={})
        assert resp.json()["changed"] == {}

    def test_update_risk_multiple_params_all_in_changed(self, client):
        resp = client.post(
            "/settings/risk/update",
            json={
                "sl_atr_mult": 1.8,
                "tp1_atr_mult": 2.5,
                "max_contracts": 10,
            },
        )
        assert resp.status_code == 200
        changed = resp.json()["changed"]
        assert changed["sl_atr_mult"] == 1.8
        assert changed["tp1_atr_mult"] == 2.5
        assert changed["max_contracts"] == 10

    def test_update_risk_returns_changed_dict(self, client):
        resp = client.post(
            "/settings/risk/update",
            json={"sl_atr_mult": 1.5},
        )
        body = resp.json()
        assert "changed" in body
        assert isinstance(body["changed"], dict)

    def test_update_risk_mixed_valid_and_unknown_keys(self, client):
        resp = client.post(
            "/settings/risk/update",
            json={"sl_atr_mult": 2.2, "bogus_key": 99},
        )
        assert resp.status_code == 200
        changed = resp.json()["changed"]
        assert "sl_atr_mult" in changed
        assert "bogus_key" not in changed

    def test_update_risk_require_vwap_as_bool(self, client):
        resp = client.post(
            "/settings/risk/update",
            json={"require_vwap": False},
        )
        assert resp.status_code == 200
        changed = resp.json()["changed"]
        assert "require_vwap" in changed
        assert changed["require_vwap"] is False

    def test_update_risk_cnn_session_key_as_string(self, client):
        resp = client.post(
            "/settings/risk/update",
            json={"cnn_session_key": "london"},
        )
        assert resp.status_code == 200
        changed = resp.json()["changed"]
        assert changed.get("cnn_session_key") == "london"


# ===========================================================================
# TestKeyStatus  (legacy env-based endpoint)
# ===========================================================================


class TestKeyStatus:
    """GET /settings/keys/status — reads env vars only, no DB involved."""

    def test_get_key_status_returns_200(self, client):
        resp = client.get("/settings/keys/status")
        assert resp.status_code == 200

    def test_get_key_status_has_keys_list(self, client):
        data = client.get("/settings/keys/status").json()
        assert "keys" in data
        assert isinstance(data["keys"], list)

    def test_key_status_is_non_empty(self, client):
        keys = client.get("/settings/keys/status").json()["keys"]
        assert len(keys) >= 5, "Expected at least 5 keys in legacy status list"

    def test_key_status_entries_have_name_field(self, client):
        keys = client.get("/settings/keys/status").json()["keys"]
        for entry in keys:
            assert "name" in entry, f"Entry missing 'name': {entry}"

    def test_key_status_entries_have_configured_field(self, client):
        keys = client.get("/settings/keys/status").json()["keys"]
        for entry in keys:
            assert "configured" in entry, f"Entry missing 'configured': {entry}"

    def test_key_status_configured_is_boolean(self, client):
        keys = client.get("/settings/keys/status").json()["keys"]
        for entry in keys:
            assert isinstance(entry["configured"], bool), (
                f"'configured' for {entry['name']} is {type(entry['configured']).__name__}, expected bool"
            )

    def test_key_status_contains_kraken_api_key(self, client):
        keys = client.get("/settings/keys/status").json()["keys"]
        names = {e["name"] for e in keys}
        assert "KRAKEN_API_KEY" in names

    def test_key_status_contains_massive_api_key(self, client):
        keys = client.get("/settings/keys/status").json()["keys"]
        names = {e["name"] for e in keys}
        assert "MASSIVE_API_KEY" in names

    def test_key_status_contains_xai_api_key(self, client):
        keys = client.get("/settings/keys/status").json()["keys"]
        names = {e["name"] for e in keys}
        assert "XAI_API_KEY" in names

    def test_key_status_configured_false_when_env_unset(self, client, monkeypatch):
        """KRAKEN_API_KEY configured=False when the env var is absent."""
        monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
        keys = client.get("/settings/keys/status").json()["keys"]
        entry = next((e for e in keys if e["name"] == "KRAKEN_API_KEY"), None)
        assert entry is not None
        assert entry["configured"] is False

    def test_key_status_configured_true_when_env_set(self, client, monkeypatch):
        """KRAKEN_API_KEY configured=True when the env var is non-empty."""
        monkeypatch.setenv("KRAKEN_API_KEY", "dummy-key-for-test")
        keys = client.get("/settings/keys/status").json()["keys"]
        entry = next((e for e in keys if e["name"] == "KRAKEN_API_KEY"), None)
        assert entry is not None
        assert entry["configured"] is True


# ===========================================================================
# TestKeyList  (full resolution chain — requires km_patched DB)
# ===========================================================================


class TestKeyList:
    """GET /settings/keys/list — reads DB + env via key_manager."""

    _REQUIRED_FIELDS = [
        "name",
        "label",
        "description",
        "source",
        "masked_value",
        "configured",
        "db_stored",
    ]

    def test_get_key_list_returns_200(self, km_client):
        resp = km_client.get("/settings/keys/list")
        assert resp.status_code == 200

    def test_get_key_list_has_keys_field(self, km_client):
        data = km_client.get("/settings/keys/list").json()
        assert "keys" in data
        assert isinstance(data["keys"], list)

    def test_get_key_list_returns_at_least_10_entries(self, km_client):
        keys = km_client.get("/settings/keys/list").json()["keys"]
        assert len(keys) >= 10, f"Expected >= 10 entries (one per KNOWN_KEY), got {len(keys)}"

    def test_get_key_list_each_entry_has_required_fields(self, km_client):
        keys = km_client.get("/settings/keys/list").json()["keys"]
        assert len(keys) > 0
        for entry in keys:
            for field in self._REQUIRED_FIELDS:
                assert field in entry, f"Entry for '{entry.get('name', '?')}' missing field '{field}'"

    def test_get_key_list_name_is_string(self, km_client):
        keys = km_client.get("/settings/keys/list").json()["keys"]
        for entry in keys:
            assert isinstance(entry["name"], str)

    def test_get_key_list_label_is_string(self, km_client):
        keys = km_client.get("/settings/keys/list").json()["keys"]
        for entry in keys:
            assert isinstance(entry["label"], str)

    def test_get_key_list_configured_is_boolean(self, km_client):
        keys = km_client.get("/settings/keys/list").json()["keys"]
        for entry in keys:
            assert isinstance(entry["configured"], bool), f"'configured' for {entry['name']} should be bool"

    def test_get_key_list_db_stored_is_boolean(self, km_client):
        keys = km_client.get("/settings/keys/list").json()["keys"]
        for entry in keys:
            assert isinstance(entry["db_stored"], bool), f"'db_stored' for {entry['name']} should be bool"

    def test_get_key_list_source_is_valid_value(self, km_client):
        valid_sources = {"database", "env", "missing"}
        keys = km_client.get("/settings/keys/list").json()["keys"]
        for entry in keys:
            assert entry["source"] in valid_sources, (
                f"'{entry['name']}' source={entry['source']!r} not in {valid_sources}"
            )

    def test_get_key_list_no_env_no_db_all_missing(self, km_client, km_patched, monkeypatch):
        """When no keys are set (env or DB), every entry should be 'missing'."""
        for key_name in km_patched.KNOWN_KEYS:
            monkeypatch.delenv(key_name, raising=False)

        keys = km_client.get("/settings/keys/list").json()["keys"]
        for entry in keys:
            assert entry["source"] == "missing", (
                f"'{entry['name']}' should be 'missing' but got source={entry['source']!r}"
            )
            assert entry["configured"] is False
            assert entry["db_stored"] is False
            assert entry["masked_value"] == ""

    def test_get_key_list_env_key_shows_env_source(self, km_client, monkeypatch):
        monkeypatch.setenv("MASSIVE_API_KEY", "env-massive-key-1234")
        keys = km_client.get("/settings/keys/list").json()["keys"]
        entry = next((e for e in keys if e["name"] == "MASSIVE_API_KEY"), None)
        assert entry is not None
        assert entry["source"] == "env"
        assert entry["configured"] is True
        assert entry["db_stored"] is False

    def test_get_key_list_env_key_has_masked_value(self, km_client, monkeypatch):
        monkeypatch.setenv("XAI_API_KEY", "super-secret-xai-key-abcd")
        keys = km_client.get("/settings/keys/list").json()["keys"]
        entry = next((e for e in keys if e["name"] == "XAI_API_KEY"), None)
        assert entry is not None
        # masked_value should end with the last 4 chars of the raw value
        assert entry["masked_value"].endswith("abcd")
        assert "*" in entry["masked_value"]

    def test_get_key_list_contains_all_known_key_names(self, km_client, km_patched):
        keys = km_client.get("/settings/keys/list").json()["keys"]
        returned_names = {e["name"] for e in keys}
        for known_name in km_patched.KNOWN_KEYS:
            assert known_name in returned_names, f"KNOWN_KEY '{known_name}' not in /settings/keys/list response"


# ===========================================================================
# TestKeySet
# ===========================================================================


class TestKeySet:
    """POST /settings/keys/set — encrypt and store a key in the DB."""

    def test_set_valid_key_returns_200(self, km_client):
        resp = km_client.post(
            "/settings/keys/set",
            json={"name": "KRAKEN_API_KEY", "value": "test-api-key-value"},
        )
        assert resp.status_code == 200

    def test_set_valid_key_returns_status_ok(self, km_client):
        resp = km_client.post(
            "/settings/keys/set",
            json={"name": "KRAKEN_API_KEY", "value": "test-api-key-value"},
        )
        assert resp.json()["status"] == "ok"

    def test_set_key_missing_name_returns_400(self, km_client):
        resp = km_client.post(
            "/settings/keys/set",
            json={"value": "some-value"},
        )
        assert resp.status_code == 400

    def test_set_key_empty_name_returns_400(self, km_client):
        resp = km_client.post(
            "/settings/keys/set",
            json={"name": "", "value": "some-value"},
        )
        assert resp.status_code == 400

    def test_set_key_whitespace_name_returns_400(self, km_client):
        resp = km_client.post(
            "/settings/keys/set",
            json={"name": "   ", "value": "some-value"},
        )
        assert resp.status_code == 400

    def test_set_key_missing_value_returns_400(self, km_client):
        resp = km_client.post(
            "/settings/keys/set",
            json={"name": "KRAKEN_API_KEY"},
        )
        assert resp.status_code == 400

    def test_set_key_empty_value_returns_400(self, km_client):
        resp = km_client.post(
            "/settings/keys/set",
            json={"name": "KRAKEN_API_KEY", "value": ""},
        )
        assert resp.status_code == 400

    def test_set_key_whitespace_value_returns_400(self, km_client):
        resp = km_client.post(
            "/settings/keys/set",
            json={"name": "KRAKEN_API_KEY", "value": "   "},
        )
        assert resp.status_code == 400

    def test_set_unknown_key_name_returns_400(self, km_client):
        resp = km_client.post(
            "/settings/keys/set",
            json={"name": "TOTALLY_UNKNOWN_KEY_XYZ", "value": "some-value"},
        )
        assert resp.status_code == 400

    def test_set_unknown_key_error_in_response(self, km_client):
        resp = km_client.post(
            "/settings/keys/set",
            json={"name": "TOTALLY_UNKNOWN_KEY_XYZ", "value": "some-value"},
        )
        assert "error" in resp.json()

    def test_set_key_then_list_shows_database_source(self, km_client):
        km_client.post(
            "/settings/keys/set",
            json={"name": "KRAKEN_API_KEY", "value": "my-secret-key"},
        )
        keys = km_client.get("/settings/keys/list").json()["keys"]
        entry = next((e for e in keys if e["name"] == "KRAKEN_API_KEY"), None)
        assert entry is not None
        assert entry["source"] == "database"
        assert entry["db_stored"] is True
        assert entry["configured"] is True

    def test_set_key_then_list_shows_masked_value(self, km_client):
        km_client.post(
            "/settings/keys/set",
            json={"name": "XAI_API_KEY", "value": "xai-secret-1234"},
        )
        keys = km_client.get("/settings/keys/list").json()["keys"]
        entry = next((e for e in keys if e["name"] == "XAI_API_KEY"), None)
        assert entry is not None
        # Last 4 chars of "xai-secret-1234" are "1234"
        assert entry["masked_value"].endswith("1234")

    def test_set_key_db_overrides_env(self, km_client, monkeypatch):
        """DB value should take priority over env var in list output."""
        monkeypatch.setenv("MASSIVE_API_KEY", "env-value-9999")
        km_client.post(
            "/settings/keys/set",
            json={"name": "MASSIVE_API_KEY", "value": "db-value-abcd"},
        )
        keys = km_client.get("/settings/keys/list").json()["keys"]
        entry = next((e for e in keys if e["name"] == "MASSIVE_API_KEY"), None)
        assert entry is not None
        assert entry["source"] == "database"
        # masked_value should reflect the DB value, not env value
        assert entry["masked_value"].endswith("abcd")

    def test_set_all_known_keys_are_accepted(self, km_client, km_patched):
        """Every key in KNOWN_KEYS should be accepted by the set endpoint."""
        for name in km_patched.KNOWN_KEYS:
            resp = km_client.post(
                "/settings/keys/set",
                json={"name": name, "value": f"dummy-{name}-test-value"},
            )
            assert resp.status_code == 200, f"Expected 200 for key '{name}', got {resp.status_code}: {resp.text}"


# ===========================================================================
# TestKeyDelete
# ===========================================================================


class TestKeyDelete:
    """DELETE /settings/keys/{name} — remove DB-stored copy of a key."""

    def test_delete_known_key_with_no_prior_set_returns_200(self, km_client):
        """Deleting a key that was never stored should still return 200."""
        resp = km_client.delete("/settings/keys/KRAKEN_API_KEY")
        assert resp.status_code == 200

    def test_delete_known_key_returns_status_ok(self, km_client):
        resp = km_client.delete("/settings/keys/XAI_API_KEY")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_delete_unknown_key_returns_400(self, km_client):
        resp = km_client.delete("/settings/keys/UNKNOWN_KEY_THAT_DOES_NOT_EXIST")
        assert resp.status_code == 400

    def test_delete_unknown_key_has_error_in_response(self, km_client):
        resp = km_client.delete("/settings/keys/UNKNOWN_KEY_THAT_DOES_NOT_EXIST")
        assert "error" in resp.json()

    def test_delete_after_set_reverts_source_to_missing(self, km_client, monkeypatch):
        """After set → delete, the source should revert away from 'database'."""
        # Ensure the env var is absent so fallback is 'missing', not 'env'
        monkeypatch.delenv("KRAKEN_API_KEY", raising=False)

        # Store a key
        set_resp = km_client.post(
            "/settings/keys/set",
            json={"name": "KRAKEN_API_KEY", "value": "will-be-deleted"},
        )
        assert set_resp.status_code == 200

        # Confirm it appears as database source
        keys_before = km_client.get("/settings/keys/list").json()["keys"]
        entry_before = next(e for e in keys_before if e["name"] == "KRAKEN_API_KEY")
        assert entry_before["source"] == "database"

        # Delete it
        del_resp = km_client.delete("/settings/keys/KRAKEN_API_KEY")
        assert del_resp.status_code == 200

        # Confirm source is no longer 'database'
        keys_after = km_client.get("/settings/keys/list").json()["keys"]
        entry_after = next(e for e in keys_after if e["name"] == "KRAKEN_API_KEY")
        assert entry_after["source"] in ("env", "missing")
        assert entry_after["db_stored"] is False

    def test_delete_after_set_with_env_fallback(self, km_client, monkeypatch):
        """After set → delete, env var fallback should take over."""
        monkeypatch.setenv("MASSIVE_API_KEY", "env-fallback-zzzz")

        km_client.post(
            "/settings/keys/set",
            json={"name": "MASSIVE_API_KEY", "value": "db-copy-temp"},
        )

        del_resp = km_client.delete("/settings/keys/MASSIVE_API_KEY")
        assert del_resp.status_code == 200

        keys = km_client.get("/settings/keys/list").json()["keys"]
        entry = next(e for e in keys if e["name"] == "MASSIVE_API_KEY")
        assert entry["source"] == "env"
        assert entry["db_stored"] is False
        assert entry["configured"] is True

    def test_double_delete_is_idempotent(self, km_client):
        """Two consecutive deletes on the same key should both return 200."""
        km_client.post(
            "/settings/keys/set",
            json={"name": "FINNHUB_API_KEY", "value": "test-finnhub"},
        )
        resp1 = km_client.delete("/settings/keys/FINNHUB_API_KEY")
        resp2 = km_client.delete("/settings/keys/FINNHUB_API_KEY")
        assert resp1.status_code == 200
        assert resp2.status_code == 200


# ===========================================================================
# TestKeyValidate
# ===========================================================================


class TestKeyValidate:
    """POST /settings/keys/validate — test a key value without storing it.

    Deferred validators (RITHMIC, KRAKEN_API_KEY, REDDIT, ALPHA_VANTAGE, etc.)
    return ok=True immediately without network calls, making them safe to use
    in unit tests.  The audit write on the endpoint silently fails if the
    api_key_audit table is absent — that's expected with the basic `client`.
    """

    def test_validate_missing_name_returns_400(self, client):
        resp = client.post(
            "/settings/keys/validate",
            json={"value": "some-value"},
        )
        assert resp.status_code == 400

    def test_validate_empty_name_returns_400(self, client):
        resp = client.post(
            "/settings/keys/validate",
            json={"name": "", "value": "some-value"},
        )
        assert resp.status_code == 400

    def test_validate_whitespace_name_returns_400(self, client):
        resp = client.post(
            "/settings/keys/validate",
            json={"name": "   ", "value": "some-value"},
        )
        assert resp.status_code == 400

    def test_validate_missing_value_returns_400(self, client):
        resp = client.post(
            "/settings/keys/validate",
            json={"name": "RITHMIC_USER"},
        )
        assert resp.status_code == 400

    def test_validate_empty_value_returns_400(self, client):
        resp = client.post(
            "/settings/keys/validate",
            json={"name": "RITHMIC_USER", "value": ""},
        )
        assert resp.status_code == 400

    def test_validate_whitespace_value_returns_400(self, client):
        resp = client.post(
            "/settings/keys/validate",
            json={"name": "RITHMIC_USER", "value": "   "},
        )
        assert resp.status_code == 400

    def test_validate_rithmic_user_returns_200(self, client):
        resp = client.post(
            "/settings/keys/validate",
            json={"name": "RITHMIC_USER", "value": "testuser"},
        )
        assert resp.status_code == 200

    def test_validate_rithmic_user_ok_is_true(self, client):
        resp = client.post(
            "/settings/keys/validate",
            json={"name": "RITHMIC_USER", "value": "testuser"},
        )
        assert resp.json()["ok"] is True

    def test_validate_kraken_api_key_returns_200(self, client):
        """KRAKEN_API_KEY validator is deferred — does not make network calls."""
        resp = client.post(
            "/settings/keys/validate",
            json={"name": "KRAKEN_API_KEY", "value": "testkey"},
        )
        assert resp.status_code == 200

    def test_validate_kraken_api_key_ok_is_true(self, client):
        resp = client.post(
            "/settings/keys/validate",
            json={"name": "KRAKEN_API_KEY", "value": "testkey"},
        )
        assert resp.json()["ok"] is True

    def test_validate_kraken_futures_api_key_ok_is_true(self, client):
        """KRAKEN_FUTURES_API_KEY validator is also deferred."""
        resp = client.post(
            "/settings/keys/validate",
            json={"name": "KRAKEN_FUTURES_API_KEY", "value": "futures-test-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_validate_rithmic_password_ok_is_true(self, client):
        resp = client.post(
            "/settings/keys/validate",
            json={"name": "RITHMIC_PASSWORD", "value": "testpassword"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_validate_reddit_client_id_ok_is_true(self, client):
        resp = client.post(
            "/settings/keys/validate",
            json={"name": "REDDIT_CLIENT_ID", "value": "myredditid"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_validate_reddit_client_secret_ok_is_true(self, client):
        resp = client.post(
            "/settings/keys/validate",
            json={"name": "REDDIT_CLIENT_SECRET", "value": "myredditscrt"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_validate_alpha_vantage_no_validator_ok_true(self, client):
        """Keys with no registered validator return ok=True with detail='skipped'."""
        resp = client.post(
            "/settings/keys/validate",
            json={"name": "ALPHA_VANTAGE_API_KEY", "value": "dummy"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_validate_response_always_has_ok_field(self, client):
        resp = client.post(
            "/settings/keys/validate",
            json={"name": "RITHMIC_USER", "value": "testuser"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "ok" in body
        assert isinstance(body["ok"], bool)

    def test_validate_response_always_has_message_field(self, client):
        resp = client.post(
            "/settings/keys/validate",
            json={"name": "RITHMIC_USER", "value": "testuser"},
        )
        body = resp.json()
        assert "message" in body
        assert isinstance(body["message"], str)

    def test_validate_response_always_has_detail_field(self, client):
        resp = client.post(
            "/settings/keys/validate",
            json={"name": "RITHMIC_USER", "value": "testuser"},
        )
        body = resp.json()
        assert "detail" in body
        assert isinstance(body["detail"], str)

    def test_validate_deferred_validator_has_non_empty_message(self, client):
        resp = client.post(
            "/settings/keys/validate",
            json={"name": "KRAKEN_API_KEY", "value": "anykey"},
        )
        assert resp.json()["message"]  # must be a non-empty string


# ===========================================================================
# TestKeyAudit
# ===========================================================================


class TestKeyAudit:
    """GET /settings/keys/audit — audit log for key changes."""

    def test_get_audit_returns_200(self, km_client):
        resp = km_client.get("/settings/keys/audit")
        assert resp.status_code == 200

    def test_get_audit_has_entries_field(self, km_client):
        data = km_client.get("/settings/keys/audit").json()
        assert "entries" in data
        assert isinstance(data["entries"], list)

    def test_get_audit_empty_by_default(self, km_client):
        """Fresh DB should have no audit entries."""
        resp = km_client.get("/settings/keys/audit")
        assert resp.json()["entries"] == []

    def test_get_audit_has_entry_after_set(self, km_client):
        km_client.post(
            "/settings/keys/set",
            json={"name": "KRAKEN_API_KEY", "value": "audit-test-key"},
        )
        resp = km_client.get("/settings/keys/audit")
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        assert len(entries) > 0

    def test_get_audit_entry_has_key_name_field(self, km_client):
        km_client.post(
            "/settings/keys/set",
            json={"name": "XAI_API_KEY", "value": "audit-check"},
        )
        entries = km_client.get("/settings/keys/audit").json()["entries"]
        assert len(entries) > 0
        for entry in entries:
            assert "key_name" in entry

    def test_get_audit_entry_has_action_field(self, km_client):
        km_client.post(
            "/settings/keys/set",
            json={"name": "XAI_API_KEY", "value": "audit-check"},
        )
        entries = km_client.get("/settings/keys/audit").json()["entries"]
        for entry in entries:
            assert "action" in entry

    def test_get_audit_entry_has_performed_at_field(self, km_client):
        km_client.post(
            "/settings/keys/set",
            json={"name": "XAI_API_KEY", "value": "audit-check"},
        )
        entries = km_client.get("/settings/keys/audit").json()["entries"]
        for entry in entries:
            assert "performed_at" in entry

    def test_get_audit_set_action_recorded(self, km_client):
        km_client.post(
            "/settings/keys/set",
            json={"name": "MASSIVE_API_KEY", "value": "massive-audit"},
        )
        entries = km_client.get("/settings/keys/audit").json()["entries"]
        actions = [e["action"] for e in entries]
        assert "set" in actions

    def test_get_audit_delete_action_recorded(self, km_client):
        km_client.post(
            "/settings/keys/set",
            json={"name": "MASSIVE_API_KEY", "value": "will-delete"},
        )
        km_client.delete("/settings/keys/MASSIVE_API_KEY")
        entries = km_client.get("/settings/keys/audit").json()["entries"]
        actions = [e["action"] for e in entries]
        assert "delete" in actions

    def test_get_audit_limit_param_restricts_count(self, km_client):
        """Setting limit=3 should return at most 3 entries."""
        # Generate more than 3 entries
        for i in range(6):
            km_client.post(
                "/settings/keys/set",
                json={"name": "KRAKEN_API_KEY", "value": f"limit-test-key-{i}"},
            )
        resp = km_client.get("/settings/keys/audit?limit=3")
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        assert len(entries) <= 3

    def test_get_audit_limit_5_returns_at_most_5(self, km_client):
        for i in range(8):
            km_client.post(
                "/settings/keys/set",
                json={"name": "XAI_API_KEY", "value": f"key-batch-{i}"},
            )
        resp = km_client.get("/settings/keys/audit?limit=5")
        assert resp.status_code == 200
        assert len(resp.json()["entries"]) <= 5

    def test_get_audit_default_limit_at_most_50(self, km_client):
        resp = km_client.get("/settings/keys/audit")
        assert len(resp.json()["entries"]) <= 50

    def test_get_audit_filter_by_key_name(self, km_client):
        """?key=KRAKEN_API_KEY should return only entries for that key."""
        km_client.post(
            "/settings/keys/set",
            json={"name": "KRAKEN_API_KEY", "value": "kraken-filter-test"},
        )
        km_client.post(
            "/settings/keys/set",
            json={"name": "XAI_API_KEY", "value": "xai-filter-test"},
        )
        resp = km_client.get("/settings/keys/audit?key=KRAKEN_API_KEY")
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        assert len(entries) > 0
        for entry in entries:
            assert entry["key_name"] == "KRAKEN_API_KEY", (
                f"Filter by KRAKEN_API_KEY returned entry for {entry['key_name']!r}"
            )

    def test_get_audit_filter_excludes_other_keys(self, km_client):
        """Filtering by one key should exclude entries for other keys."""
        km_client.post(
            "/settings/keys/set",
            json={"name": "KRAKEN_API_KEY", "value": "kraken-excl-test"},
        )
        km_client.post(
            "/settings/keys/set",
            json={"name": "FINNHUB_API_KEY", "value": "finnhub-excl-test"},
        )
        entries = km_client.get("/settings/keys/audit?key=FINNHUB_API_KEY").json()["entries"]
        assert all(e["key_name"] == "FINNHUB_API_KEY" for e in entries)

    def test_get_audit_without_filter_returns_all_keys(self, km_client):
        """No ?key filter should return entries from multiple keys."""
        km_client.post(
            "/settings/keys/set",
            json={"name": "KRAKEN_API_KEY", "value": "multi-k"},
        )
        km_client.post(
            "/settings/keys/set",
            json={"name": "XAI_API_KEY", "value": "multi-x"},
        )
        entries = km_client.get("/settings/keys/audit").json()["entries"]
        key_names = {e["key_name"] for e in entries}
        assert "KRAKEN_API_KEY" in key_names
        assert "XAI_API_KEY" in key_names

    def test_get_audit_filter_unknown_key_returns_empty(self, km_client):
        """Filtering by a key that has no audit entries returns empty list."""
        resp = km_client.get("/settings/keys/audit?key=ALPHA_VANTAGE_API_KEY")
        assert resp.status_code == 200
        assert resp.json()["entries"] == []
