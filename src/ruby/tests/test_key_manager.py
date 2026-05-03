"""
Unit tests for lib.core.key_manager

Covers:
  - _mask(): string masking logic
  - _get_fernet(): cipher initialization with/without the env secret
  - _encrypt() / _decrypt(): round-trip and error/edge cases
  - get_key(): resolution chain (DB → env → None)
  - list_keys(): metadata listing with source/configured/db_stored flags
  - DB operations (set_key, delete_key, get_audit_log, _db_get_all) via SQLite
  - validate_key(): validator dispatch including deferred and unknown key names
  - set_key() / delete_key(): guard clauses that reject bad input early
"""

from __future__ import annotations

import sqlite3

import pytest

import lib.core.key_manager as km

# ---------------------------------------------------------------------------
# Shared SQLite fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def sqlite_km(monkeypatch, tmp_path):
    """Patch key_manager to use a temp-file SQLite DB and a fresh Fernet key.

    Returns the (already-imported) km module with all DB helpers swapped out.
    The Fernet secret is injected via monkeypatch so _get_fernet() picks it
    up automatically; the global _fernet cache is also reset so there is no
    stale state from an earlier test.
    """
    from cryptography.fernet import Fernet

    test_key = Fernet.generate_key().decode()
    monkeypatch.setenv("API_KEY_ENCRYPTION_SECRET", test_key)
    monkeypatch.setenv("DATABASE_URL", "")  # force the SQLite branch

    db_path = tmp_path / "test_keys.db"

    def _make_conn():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_dict_impl(row):
        return dict(row)

    monkeypatch.setattr(km, "_get_conn", _make_conn)
    monkeypatch.setattr(km, "_row_to_dict", _row_to_dict_impl)
    monkeypatch.setattr(km, "_is_postgres", lambda: False)
    monkeypatch.setattr(km, "_fernet", None)  # reset singleton

    km.ensure_tables_exist()
    return km


# ---------------------------------------------------------------------------
# TestMask
# ---------------------------------------------------------------------------


class TestMask:
    """Tests for the _mask() string-masking helper."""

    def test_short_value_all_stars(self):
        """Values shorter than 4 chars → all stars, length preserved."""
        assert km._mask("abc") == "***"

    def test_exactly_four_chars_all_stars(self):
        """Exactly 4 chars → all stars (****)."""
        assert km._mask("abcd") == "****"

    def test_five_chars_one_star_plus_last_four(self):
        """5-char value → one star prepended to the last 4 chars."""
        assert km._mask("hello") == "*ello"

    def test_longer_value_stars_plus_last_four(self):
        """Values longer than 4 chars → stars replace all but last 4."""
        value = "supersecretkey"
        result = km._mask(value)
        assert result.endswith("tkey")
        assert all(c == "*" for c in result[:-4])

    def test_long_api_key(self):
        """Long 26-char string → 22 stars + last 4 chars."""
        value = "abcdefghijklmnopqrstuvwxyz"
        result = km._mask(value)
        assert result == "*" * 22 + "wxyz"

    def test_single_char(self):
        """Single char → single star."""
        assert km._mask("x") == "*"

    def test_two_chars(self):
        """Two chars → two stars."""
        assert km._mask("xy") == "**"

    def test_empty_string(self):
        """Empty string edge case → empty string (zero stars)."""
        assert km._mask("") == ""


# ---------------------------------------------------------------------------
# TestFernet
# ---------------------------------------------------------------------------


class TestFernet:
    """Tests for _get_fernet() cipher initialization."""

    def test_returns_none_when_env_absent(self, monkeypatch):
        """Returns None when API_KEY_ENCRYPTION_SECRET is not set at all."""
        monkeypatch.delenv("API_KEY_ENCRYPTION_SECRET", raising=False)
        result = km._get_fernet()
        assert result is None

    def test_returns_none_when_env_empty_string(self, monkeypatch):
        """Returns None when the secret env var is set to an empty string."""
        monkeypatch.setenv("API_KEY_ENCRYPTION_SECRET", "")
        result = km._get_fernet()
        assert result is None

    def test_returns_none_when_env_whitespace_only(self, monkeypatch):
        """Returns None when the secret env var contains only whitespace."""
        monkeypatch.setenv("API_KEY_ENCRYPTION_SECRET", "   ")
        result = km._get_fernet()
        assert result is None

    def test_returns_fernet_with_proper_44_char_key(self, monkeypatch):
        """Returns a Fernet instance when a proper 44-char base64 key is set."""
        from cryptography.fernet import Fernet

        test_key = Fernet.generate_key().decode()
        assert len(test_key) == 44  # confirm our key really is 44 chars
        monkeypatch.setenv("API_KEY_ENCRYPTION_SECRET", test_key)
        result = km._get_fernet()
        assert result is not None
        assert isinstance(result, Fernet)

    def test_works_with_arbitrary_non_standard_string(self, monkeypatch):
        """A non-standard passphrase goes through the SHA-256 derivation path."""
        monkeypatch.setenv("API_KEY_ENCRYPTION_SECRET", "my-arbitrary-passphrase!")
        result = km._get_fernet()
        assert result is not None
        # Verify the derived instance is actually usable
        ciphertext = result.encrypt(b"round-trip-test")
        assert result.decrypt(ciphertext) == b"round-trip-test"

    def test_repeated_calls_produce_compatible_instances(self, monkeypatch):
        """Two successive calls with the same key can cross-decrypt each other."""
        from cryptography.fernet import Fernet

        test_key = Fernet.generate_key().decode()
        monkeypatch.setenv("API_KEY_ENCRYPTION_SECRET", test_key)

        f1 = km._get_fernet()
        f2 = km._get_fernet()

        assert f1 is not None
        assert f2 is not None

        ct = f1.encrypt(b"hello from f1")
        assert f2.decrypt(ct) == b"hello from f1"

    def test_instance_is_usable_for_encrypt_decrypt(self, monkeypatch):
        """The returned instance encrypts and decrypts bytes correctly."""
        from cryptography.fernet import Fernet

        test_key = Fernet.generate_key().decode()
        monkeypatch.setenv("API_KEY_ENCRYPTION_SECRET", test_key)

        f = km._get_fernet()
        assert f is not None
        ct = f.encrypt(b"secret payload")
        assert f.decrypt(ct) == b"secret payload"


# ---------------------------------------------------------------------------
# TestEncryptDecrypt
# ---------------------------------------------------------------------------


class TestEncryptDecrypt:
    """Tests for _encrypt() / _decrypt() round-trip and error paths."""

    def test_round_trip_returns_original_plaintext(self, monkeypatch):
        """Encrypting then decrypting yields the original string."""
        from cryptography.fernet import Fernet

        test_key = Fernet.generate_key().decode()
        monkeypatch.setenv("API_KEY_ENCRYPTION_SECRET", test_key)

        plaintext = "my-super-secret-api-key-99"
        ciphertext = km._encrypt(plaintext)

        assert ciphertext is not None
        assert ciphertext != plaintext  # sanity: output is not the input

        recovered = km._decrypt(ciphertext)
        assert recovered == plaintext

    def test_encrypt_returns_none_without_secret(self, monkeypatch):
        """_encrypt() returns None when API_KEY_ENCRYPTION_SECRET is absent."""
        monkeypatch.delenv("API_KEY_ENCRYPTION_SECRET", raising=False)
        result = km._encrypt("some-value")
        assert result is None

    def test_decrypt_returns_none_without_secret(self, monkeypatch):
        """_decrypt() returns None when API_KEY_ENCRYPTION_SECRET is absent."""
        monkeypatch.delenv("API_KEY_ENCRYPTION_SECRET", raising=False)
        result = km._decrypt("gAAAAA_not_real_ciphertext==")
        assert result is None

    def test_decrypt_with_wrong_key_returns_none_not_raises(self, monkeypatch):
        """Decrypting with a different key returns None — no exception escapes."""
        from cryptography.fernet import Fernet

        key_a = Fernet.generate_key().decode()
        key_b = Fernet.generate_key().decode()

        # Encrypt under key A
        monkeypatch.setenv("API_KEY_ENCRYPTION_SECRET", key_a)
        ciphertext = km._encrypt("sensitive-data")
        assert ciphertext is not None

        # Try to decrypt with key B
        monkeypatch.setenv("API_KEY_ENCRYPTION_SECRET", key_b)
        result = km._decrypt(ciphertext)
        assert result is None

    def test_decrypt_corrupt_data_returns_none_not_raises(self, monkeypatch):
        """Decrypting random garbage data returns None — no exception escapes."""
        from cryptography.fernet import Fernet

        test_key = Fernet.generate_key().decode()
        monkeypatch.setenv("API_KEY_ENCRYPTION_SECRET", test_key)

        result = km._decrypt("this-is-definitely-not-valid-fernet-data-xyz")
        assert result is None

    def test_encrypt_produces_different_ciphertext_each_time(self, monkeypatch):
        """Fernet uses random IVs so the same plaintext encrypts differently."""
        from cryptography.fernet import Fernet

        test_key = Fernet.generate_key().decode()
        monkeypatch.setenv("API_KEY_ENCRYPTION_SECRET", test_key)

        ct1 = km._encrypt("same-value")
        ct2 = km._encrypt("same-value")

        assert ct1 is not None
        assert ct2 is not None
        # Fernet tokens include a random IV — they should differ
        assert ct1 != ct2

    def test_round_trip_with_non_standard_derivation_key(self, monkeypatch):
        """Round-trip works with an arbitrary passphrase (SHA-256 derivation path)."""
        monkeypatch.setenv("API_KEY_ENCRYPTION_SECRET", "just-a-passphrase")

        plaintext = "xai-super-secret-1234"
        ciphertext = km._encrypt(plaintext)
        assert ciphertext is not None
        assert km._decrypt(ciphertext) == plaintext


# ---------------------------------------------------------------------------
# TestResolutionChain
# ---------------------------------------------------------------------------


class TestResolutionChain:
    """Tests for get_key() DB → env → None resolution chain."""

    def test_env_fallback_when_db_returns_none(self, monkeypatch):
        """Returns the env var value when the DB has no entry."""
        monkeypatch.setenv("KRAKEN_API_KEY", "my-env-kraken-key")
        monkeypatch.setattr(km, "_db_get", lambda _: None)

        result = km.get_key("KRAKEN_API_KEY")
        assert result == "my-env-kraken-key"

    def test_returns_none_when_neither_db_nor_env_has_key(self, monkeypatch):
        """Returns None when neither the DB nor the env has the key."""
        monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
        monkeypatch.setattr(km, "_db_get", lambda _: None)

        result = km.get_key("KRAKEN_API_KEY")
        assert result is None

    def test_db_takes_priority_over_env_var(self, monkeypatch):
        """DB value shadows an env var with the same name."""
        monkeypatch.setenv("KRAKEN_API_KEY", "env-value")
        monkeypatch.setattr(km, "_db_get", lambda _: "db-value")

        result = km.get_key("KRAKEN_API_KEY")
        assert result == "db-value"

    def test_env_used_when_db_lookup_fails(self, monkeypatch):
        """Falls back to env var when DB lookup silently returns None (error path)."""
        monkeypatch.setenv("XAI_API_KEY", "xai-env-fallback")
        monkeypatch.setattr(km, "_db_get", lambda _: None)

        result = km.get_key("XAI_API_KEY")
        assert result == "xai-env-fallback"

    def test_env_value_whitespace_is_stripped(self, monkeypatch):
        """Leading / trailing whitespace in an env var is stripped."""
        monkeypatch.setenv("FINNHUB_API_KEY", "   trimmed-key   ")
        monkeypatch.setattr(km, "_db_get", lambda _: None)

        result = km.get_key("FINNHUB_API_KEY")
        assert result == "trimmed-key"

    def test_empty_env_value_treated_as_not_configured(self, monkeypatch):
        """An env var set to an empty string is treated as absent."""
        monkeypatch.setenv("MASSIVE_API_KEY", "")
        monkeypatch.setattr(km, "_db_get", lambda _: None)

        result = km.get_key("MASSIVE_API_KEY")
        assert result is None

    def test_whitespace_only_env_treated_as_not_configured(self, monkeypatch):
        """An env var containing only spaces is treated as absent."""
        monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "   ")
        monkeypatch.setattr(km, "_db_get", lambda _: None)

        result = km.get_key("ALPHA_VANTAGE_API_KEY")
        assert result is None


# ---------------------------------------------------------------------------
# TestDatabaseOperations
# ---------------------------------------------------------------------------


class TestDatabaseOperations:
    """Tests for DB-backed operations using a temp SQLite database."""

    def test_set_key_returns_true(self, sqlite_km, monkeypatch):
        """set_key() stores the value and returns True."""
        monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
        result = sqlite_km.set_key("KRAKEN_API_KEY", "test-kraken-key", by="admin", ip="127.0.0.1")
        assert result is True

    def test_get_key_retrieves_value_after_set(self, sqlite_km, monkeypatch):
        """get_key() retrieves the exact plaintext value stored by set_key()."""
        monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
        sqlite_km.set_key("KRAKEN_API_KEY", "retrieve-me-correctly", by="admin", ip="127.0.0.1")
        result = sqlite_km.get_key("KRAKEN_API_KEY")
        assert result == "retrieve-me-correctly"

    def test_delete_key_removes_value(self, sqlite_km, monkeypatch):
        """delete_key() removes the key so get_key() returns None afterwards."""
        monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
        sqlite_km.set_key("KRAKEN_API_KEY", "to-be-deleted", by="admin", ip="127.0.0.1")
        assert sqlite_km.get_key("KRAKEN_API_KEY") == "to-be-deleted"

        sqlite_km.delete_key("KRAKEN_API_KEY", by="admin", ip="127.0.0.1")
        assert sqlite_km.get_key("KRAKEN_API_KEY") is None

    def test_delete_key_falls_back_to_env(self, sqlite_km, monkeypatch):
        """After deletion, get_key() falls back to the env var if present."""
        monkeypatch.setenv("KRAKEN_API_KEY", "env-fallback-value")
        sqlite_km.set_key("KRAKEN_API_KEY", "db-override-value", by="admin", ip="127.0.0.1")
        sqlite_km.delete_key("KRAKEN_API_KEY", by="admin", ip="127.0.0.1")
        assert sqlite_km.get_key("KRAKEN_API_KEY") == "env-fallback-value"

    def test_overwrite_existing_key_returns_new_value(self, sqlite_km, monkeypatch):
        """Calling set_key() twice on the same key overwrites the first value."""
        monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
        sqlite_km.set_key("MASSIVE_API_KEY", "old-value", by="sys", ip="")
        sqlite_km.set_key("MASSIVE_API_KEY", "new-value", by="sys", ip="")
        assert sqlite_km.get_key("MASSIVE_API_KEY") == "new-value"

    def test_get_audit_log_has_entry_after_set(self, sqlite_km, monkeypatch):
        """get_audit_log() returns at least one entry after set_key()."""
        monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
        sqlite_km.set_key("KRAKEN_API_KEY", "audit-test-key", by="tester", ip="10.0.0.1")
        entries = sqlite_km.get_audit_log(key_name="KRAKEN_API_KEY")
        assert len(entries) >= 1

    def test_audit_log_set_entry_fields(self, sqlite_km, monkeypatch):
        """A set-operation audit entry records the correct actor and IP."""
        monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
        sqlite_km.set_key("KRAKEN_API_KEY", "audit-key", by="tester", ip="10.0.0.1")
        entries = sqlite_km.get_audit_log(key_name="KRAKEN_API_KEY")
        assert len(entries) >= 1
        entry = entries[0]
        assert entry["key_name"] == "KRAKEN_API_KEY"
        assert entry["action"] == "set"
        assert entry["performed_by"] == "tester"
        assert entry["ip_address"] == "10.0.0.1"

    def test_audit_log_records_delete_action(self, sqlite_km, monkeypatch):
        """get_audit_log() contains both 'set' and 'delete' entries after both ops."""
        monkeypatch.delenv("XAI_API_KEY", raising=False)
        sqlite_km.set_key("XAI_API_KEY", "some-key", by="user1", ip="192.168.1.1")
        sqlite_km.delete_key("XAI_API_KEY", by="user1", ip="192.168.1.1")
        entries = sqlite_km.get_audit_log(key_name="XAI_API_KEY")
        actions = {e["action"] for e in entries}
        assert "set" in actions
        assert "delete" in actions

    def test_audit_entry_has_all_required_fields(self, sqlite_km, monkeypatch):
        """Every audit entry contains the five expected metadata fields."""
        monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
        sqlite_km.set_key("FINNHUB_API_KEY", "fh-key", by="ops", ip="10.1.2.3")
        entries = sqlite_km.get_audit_log(key_name="FINNHUB_API_KEY")
        assert len(entries) >= 1
        required = {"key_name", "action", "performed_at", "performed_by", "ip_address"}
        assert required.issubset(set(entries[0].keys()))

    def test_db_get_all_returns_all_stored_keys(self, sqlite_km, monkeypatch):
        """_db_get_all() returns a dict of all decrypted key→value pairs."""
        monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
        monkeypatch.delenv("XAI_API_KEY", raising=False)

        sqlite_km.set_key("KRAKEN_API_KEY", "kraken-val", by="sys", ip="")
        sqlite_km.set_key("XAI_API_KEY", "xai-val", by="sys", ip="")

        all_keys = sqlite_km._db_get_all()
        assert "KRAKEN_API_KEY" in all_keys
        assert all_keys["KRAKEN_API_KEY"] == "kraken-val"
        assert "XAI_API_KEY" in all_keys
        assert all_keys["XAI_API_KEY"] == "xai-val"

    def test_db_get_all_empty_when_no_keys_set(self, sqlite_km):
        """_db_get_all() returns an empty dict when no keys have been stored."""
        all_keys = sqlite_km._db_get_all()
        assert isinstance(all_keys, dict)
        assert len(all_keys) == 0

    def test_ensure_tables_exist_is_idempotent(self, sqlite_km):
        """ensure_tables_exist() can be called multiple times without error."""
        sqlite_km.ensure_tables_exist()
        sqlite_km.ensure_tables_exist()
        sqlite_km.ensure_tables_exist()

    def test_get_audit_log_without_filter_returns_all_keys(self, sqlite_km, monkeypatch):
        """get_audit_log() with no key_name filter returns entries for all keys."""
        monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
        monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
        sqlite_km.set_key("KRAKEN_API_KEY", "k1", by="sys", ip="")
        sqlite_km.set_key("FINNHUB_API_KEY", "f1", by="sys", ip="")
        entries = sqlite_km.get_audit_log()
        key_names = {e["key_name"] for e in entries}
        assert "KRAKEN_API_KEY" in key_names
        assert "FINNHUB_API_KEY" in key_names

    def test_multiple_keys_stored_independently(self, sqlite_km, monkeypatch):
        """Different keys stored in the DB are retrieved independently."""
        monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
        monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
        sqlite_km.set_key("REDDIT_CLIENT_ID", "client-id-abc", by="sys", ip="")
        sqlite_km.set_key("REDDIT_CLIENT_SECRET", "client-secret-xyz", by="sys", ip="")
        assert sqlite_km.get_key("REDDIT_CLIENT_ID") == "client-id-abc"
        assert sqlite_km.get_key("REDDIT_CLIENT_SECRET") == "client-secret-xyz"

    def test_delete_nonexistent_key_returns_bool(self, sqlite_km):
        """delete_key() on a key that was never stored completes without error."""
        result = sqlite_km.delete_key("RITHMIC_USER", by="sys", ip="")
        assert isinstance(result, bool)

    def test_audit_log_limit_is_respected(self, sqlite_km, monkeypatch):
        """get_audit_log() respects the limit parameter."""
        monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
        for i in range(10):
            sqlite_km.set_key("KRAKEN_API_KEY", f"value-{i}", by="sys", ip="")
        entries = sqlite_km.get_audit_log(key_name="KRAKEN_API_KEY", limit=3)
        assert len(entries) <= 3


# ---------------------------------------------------------------------------
# TestListKeys
# ---------------------------------------------------------------------------


class TestListKeys:
    """Tests for list_keys() metadata listing."""

    def test_returns_entry_for_every_known_key(self, monkeypatch):
        """list_keys() returns exactly one entry per KNOWN_KEYS entry."""
        monkeypatch.setattr(km, "_db_get_all", lambda: {})
        for k in km.KNOWN_KEYS:
            monkeypatch.delenv(k, raising=False)
        result = km.list_keys()
        assert len(result) == len(km.KNOWN_KEYS)

    def test_each_entry_has_all_required_fields(self, monkeypatch):
        """Every entry in list_keys() has the nine required metadata fields."""
        monkeypatch.setattr(km, "_db_get_all", lambda: {})
        for k in km.KNOWN_KEYS:
            monkeypatch.delenv(k, raising=False)
        result = km.list_keys()
        required = {
            "name",
            "label",
            "description",
            "url",
            "group",
            "source",
            "masked_value",
            "configured",
            "db_stored",
        }
        for entry in result:
            assert required.issubset(set(entry.keys())), (
                f"Entry '{entry.get('name')}' is missing fields: {required - set(entry.keys())}"
            )

    def test_env_key_source_is_env(self, monkeypatch):
        """An env-set key has source='env'."""
        monkeypatch.setattr(km, "_db_get_all", lambda: {})
        for k in km.KNOWN_KEYS:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("KRAKEN_API_KEY", "my-kraken-key-12345")
        result = km.list_keys()
        entry = next(e for e in result if e["name"] == "KRAKEN_API_KEY")
        assert entry["source"] == "env"

    def test_env_key_configured_is_true(self, monkeypatch):
        """An env-set key has configured=True."""
        monkeypatch.setattr(km, "_db_get_all", lambda: {})
        for k in km.KNOWN_KEYS:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("KRAKEN_API_KEY", "my-kraken-key-12345")
        result = km.list_keys()
        entry = next(e for e in result if e["name"] == "KRAKEN_API_KEY")
        assert entry["configured"] is True

    def test_env_key_db_stored_is_false(self, monkeypatch):
        """An env-only key has db_stored=False."""
        monkeypatch.setattr(km, "_db_get_all", lambda: {})
        for k in km.KNOWN_KEYS:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("KRAKEN_API_KEY", "my-kraken-key-12345")
        result = km.list_keys()
        entry = next(e for e in result if e["name"] == "KRAKEN_API_KEY")
        assert entry["db_stored"] is False

    def test_missing_key_source_is_missing(self, monkeypatch):
        """Keys that are set nowhere have source='missing'."""
        monkeypatch.setattr(km, "_db_get_all", lambda: {})
        for k in km.KNOWN_KEYS:
            monkeypatch.delenv(k, raising=False)
        result = km.list_keys()
        for entry in result:
            assert entry["source"] == "missing"

    def test_missing_key_configured_is_false(self, monkeypatch):
        """Keys that are set nowhere have configured=False."""
        monkeypatch.setattr(km, "_db_get_all", lambda: {})
        for k in km.KNOWN_KEYS:
            monkeypatch.delenv(k, raising=False)
        result = km.list_keys()
        for entry in result:
            assert entry["configured"] is False

    def test_missing_key_masked_value_is_empty(self, monkeypatch):
        """Keys that are set nowhere have an empty masked_value."""
        monkeypatch.setattr(km, "_db_get_all", lambda: {})
        for k in km.KNOWN_KEYS:
            monkeypatch.delenv(k, raising=False)
        result = km.list_keys()
        for entry in result:
            assert entry["masked_value"] == ""

    def test_env_key_masked_value_shows_last_four(self, monkeypatch):
        """masked_value for an env-set key ends with the last 4 chars of the value."""
        monkeypatch.setattr(km, "_db_get_all", lambda: {})
        for k in km.KNOWN_KEYS:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("KRAKEN_API_KEY", "abcdefghijklmnop")
        result = km.list_keys()
        entry = next(e for e in result if e["name"] == "KRAKEN_API_KEY")
        assert entry["masked_value"] == km._mask("abcdefghijklmnop")
        assert entry["masked_value"].endswith("mnop")

    def test_env_key_masked_value_has_star_prefix(self, monkeypatch):
        """masked_value's non-suffix characters are all stars."""
        monkeypatch.setattr(km, "_db_get_all", lambda: {})
        for k in km.KNOWN_KEYS:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("FINNHUB_API_KEY", "pk_live_abcdefghijkl")
        result = km.list_keys()
        entry = next(e for e in result if e["name"] == "FINNHUB_API_KEY")
        mv = entry["masked_value"]
        # All chars except the last 4 should be stars
        assert all(c == "*" for c in mv[:-4])

    def test_db_key_source_is_database(self, monkeypatch):
        """A DB-stored key has source='database'."""
        monkeypatch.setattr(km, "_db_get_all", lambda: {"XAI_API_KEY": "db-xai-secret"})
        for k in km.KNOWN_KEYS:
            monkeypatch.delenv(k, raising=False)
        result = km.list_keys()
        entry = next(e for e in result if e["name"] == "XAI_API_KEY")
        assert entry["source"] == "database"

    def test_db_key_db_stored_is_true(self, monkeypatch):
        """A DB-stored key has db_stored=True."""
        monkeypatch.setattr(km, "_db_get_all", lambda: {"XAI_API_KEY": "db-xai-secret"})
        for k in km.KNOWN_KEYS:
            monkeypatch.delenv(k, raising=False)
        result = km.list_keys()
        entry = next(e for e in result if e["name"] == "XAI_API_KEY")
        assert entry["db_stored"] is True

    def test_db_key_takes_priority_over_env(self, monkeypatch):
        """When a key exists in both DB and env, source should be 'database'."""
        monkeypatch.setattr(km, "_db_get_all", lambda: {"XAI_API_KEY": "db-value"})
        for k in km.KNOWN_KEYS:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("XAI_API_KEY", "env-value")
        result = km.list_keys()
        entry = next(e for e in result if e["name"] == "XAI_API_KEY")
        assert entry["source"] == "database"
        assert entry["db_stored"] is True

    def test_result_contains_label_and_description(self, monkeypatch):
        """Each entry's label and description come from KNOWN_KEYS registry."""
        monkeypatch.setattr(km, "_db_get_all", lambda: {})
        for k in km.KNOWN_KEYS:
            monkeypatch.delenv(k, raising=False)
        result = km.list_keys()
        for entry in result:
            meta = km.KNOWN_KEYS[entry["name"]]
            assert entry["label"] == meta["label"]
            assert entry["description"] == meta["description"]


# ---------------------------------------------------------------------------
# TestValidateKey
# ---------------------------------------------------------------------------


class TestValidateKey:
    """Tests for validate_key() validator dispatch."""

    def test_kraken_api_key_returns_ok_true(self):
        """KRAKEN_API_KEY validator returns ok=True (deferred, no network)."""
        result = km.validate_key("KRAKEN_API_KEY", "some-key-value")
        assert result["ok"] is True

    def test_kraken_api_key_detail_is_deferred(self):
        """KRAKEN_API_KEY validator returns detail='deferred'."""
        result = km.validate_key("KRAKEN_API_KEY", "some-key-value")
        assert result["detail"] == "deferred"

    def test_rithmic_user_returns_ok_true(self):
        """RITHMIC_USER validator returns ok=True (deferred, no network)."""
        result = km.validate_key("RITHMIC_USER", "my-rithmic-user")
        assert result["ok"] is True

    def test_rithmic_user_detail_is_deferred(self):
        """RITHMIC_USER validator returns detail='deferred'."""
        result = km.validate_key("RITHMIC_USER", "my-rithmic-user")
        assert result["detail"] == "deferred"

    def test_rithmic_password_returns_ok_true(self):
        """RITHMIC_PASSWORD validator returns ok=True (deferred, no network)."""
        result = km.validate_key("RITHMIC_PASSWORD", "my-rithmic-pass")
        assert result["ok"] is True

    def test_reddit_client_id_returns_ok_true(self):
        """REDDIT_CLIENT_ID validator returns ok=True (deferred, no network)."""
        result = km.validate_key("REDDIT_CLIENT_ID", "some-reddit-id")
        assert result["ok"] is True

    def test_reddit_client_secret_returns_ok_true(self):
        """REDDIT_CLIENT_SECRET validator returns ok=True (deferred, no network)."""
        result = km.validate_key("REDDIT_CLIENT_SECRET", "some-reddit-secret")
        assert result["ok"] is True

    def test_unknown_key_returns_ok_true(self):
        """An unknown key name returns ok=True (skipped)."""
        result = km.validate_key("NONEXISTENT_KEY_XYZ_99", "any-value")
        assert result["ok"] is True

    def test_unknown_key_detail_is_skipped(self):
        """An unknown key name returns detail='skipped'."""
        result = km.validate_key("NONEXISTENT_KEY_XYZ_99", "any-value")
        assert result["detail"] == "skipped"

    def test_validate_key_result_always_has_ok_field(self):
        """validate_key() result always contains an 'ok' key."""
        for key_name in ["KRAKEN_API_KEY", "RITHMIC_USER", "UNKNOWN_KEY_123"]:
            result = km.validate_key(key_name, "dummy")
            assert "ok" in result, f"Missing 'ok' field for key {key_name!r}"

    def test_validate_key_result_always_has_message_field(self):
        """validate_key() result always contains a 'message' key."""
        for key_name in ["KRAKEN_API_KEY", "RITHMIC_USER", "UNKNOWN_KEY_123"]:
            result = km.validate_key(key_name, "dummy")
            assert "message" in result, f"Missing 'message' field for key {key_name!r}"

    def test_validate_key_result_always_has_detail_field(self):
        """validate_key() result always contains a 'detail' key."""
        for key_name in ["KRAKEN_API_KEY", "RITHMIC_USER", "UNKNOWN_KEY_123"]:
            result = km.validate_key(key_name, "dummy")
            assert "detail" in result, f"Missing 'detail' field for key {key_name!r}"

    def test_validate_key_never_raises_on_internal_exception(self, monkeypatch):
        """validate_key() catches internal validator exceptions and returns ok=False."""

        def always_raises(value):
            raise RuntimeError("Deliberate test exception")

        monkeypatch.setitem(km._VALIDATORS, "KRAKEN_API_KEY", always_raises)
        result = km.validate_key("KRAKEN_API_KEY", "test-value")
        assert isinstance(result, dict)
        assert result["ok"] is False
        assert "detail" in result

    def test_validate_key_exception_message_in_result(self, monkeypatch):
        """When the validator raises, the exception message appears in the result."""

        def always_raises(value):
            raise ValueError("specific-error-message-here")

        monkeypatch.setitem(km._VALIDATORS, "RITHMIC_USER", always_raises)
        result = km.validate_key("RITHMIC_USER", "test-value")
        assert result["ok"] is False
        # Either the message or detail should reference the exception
        combined = (result.get("message", "") + result.get("detail", "")).lower()
        assert "specific-error-message-here" in combined or "exception" in combined


# ---------------------------------------------------------------------------
# TestGuards
# ---------------------------------------------------------------------------


class TestGuards:
    """Tests for guard clauses in set_key() and delete_key()."""

    def test_set_key_rejects_unknown_key_name(self):
        """set_key() returns False for a name not in KNOWN_KEYS."""
        result = km.set_key("NOT_A_REAL_KEY_AT_ALL", "some-value")
        assert result is False

    def test_set_key_rejects_empty_value(self):
        """set_key() returns False when value is an empty string."""
        result = km.set_key("KRAKEN_API_KEY", "")
        assert result is False

    def test_set_key_unknown_key_false_regardless_of_db(self, monkeypatch):
        """Unknown key rejection is a pure guard — no DB connection is needed."""
        # We can verify this by confirming it returns False even without any DB patches
        result = km.set_key("COMPLETELY_BOGUS_KEY_XYZ", "value")
        assert result is False

    def test_set_key_empty_value_false_regardless_of_db(self):
        """Empty value rejection is a pure guard — no DB connection is needed."""
        result = km.set_key("KRAKEN_API_KEY", "")
        assert result is False

    def test_set_key_returns_false_for_every_unknown_name(self):
        """Any name not in KNOWN_KEYS is rejected regardless of which name."""
        bogus_names = [
            "RANDOM_KEY",
            "kraken_api_key",  # wrong case
            "KRAKEN_API_KEY_TYPO",
            "",  # empty name
            "123",
        ]
        for name in bogus_names:
            result = km.set_key(name, "valid-value")
            assert result is False, f"Expected False for unknown key name {name!r}"

    def test_set_key_empty_value_for_all_known_keys(self):
        """Empty value is rejected for every key name in KNOWN_KEYS."""
        for key_name in km.KNOWN_KEYS:
            result = km.set_key(key_name, "")
            assert result is False, f"Expected False for empty value with key {key_name!r}"

    def test_delete_key_for_nonexistent_key_returns_bool(self, sqlite_km):
        """delete_key() on a key never stored completes without raising."""
        result = sqlite_km.delete_key("RITHMIC_USER", by="sys", ip="")
        assert isinstance(result, bool)

    def test_set_key_valid_known_key_but_no_encryption_returns_false(self, monkeypatch):
        """set_key() returns False when the Fernet key is absent (no DB storage possible)."""
        monkeypatch.delenv("API_KEY_ENCRYPTION_SECRET", raising=False)
        # The guard passes (name is known, value is non-empty) but _db_set should fail
        result = km.set_key("KRAKEN_API_KEY", "some-valid-value")
        assert result is False
