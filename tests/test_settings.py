"""The user's settings file, and where the NCBI API key comes from."""

import time

import pytest
import requests

from pubmed_stream import downloader
from pubmed_stream.settings import NCBI_API_KEY_SETTING, read_settings, saved_api_key, set_setting, user_settings_file


def test_set_setting_keeps_the_other_keys(tmp_path):
    path = tmp_path / "settings.json"

    assert set_setting(path, "a", 1) == "created"
    assert set_setting(path, "b", "x") == "updated"
    assert set_setting(path, "b", "x") == "kept"
    assert read_settings(path) == {"a": 1, "b": "x"}

    assert read_settings(tmp_path / "missing.json") == {}
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    assert read_settings(tmp_path / "bad.json") == {}
    with pytest.raises(ValueError, match="bad.json is not valid JSON"):    # never replaces a file it cannot parse
        set_setting(tmp_path / "bad.json", "a", 1)
    (tmp_path / "list.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="does not hold a JSON object"):
        set_setting(tmp_path / "list.json", "a", 1)


def test_api_key_comes_from_the_environment_then_the_saved_setting(home, monkeypatch):
    monkeypatch.delenv(downloader.NCBI_API_KEY_ENV, raising=False)
    monkeypatch.delenv(downloader.PLUGIN_API_KEY_ENV, raising=False)
    assert downloader.configured_api_key() is None

    assert user_settings_file() == home / ".pubmed-stream.json"
    set_setting(user_settings_file(), NCBI_API_KEY_SETTING, "saved-key")
    assert saved_api_key() == "saved-key"
    assert downloader.configured_api_key() == "saved-key"

    monkeypatch.setenv(downloader.PLUGIN_API_KEY_ENV, "")         # the plugin's option, left unset
    assert downloader.configured_api_key() == "saved-key"
    monkeypatch.setenv(downloader.PLUGIN_API_KEY_ENV, "plugin-key")
    assert downloader.configured_api_key() == "plugin-key"
    monkeypatch.setenv(downloader.NCBI_API_KEY_ENV, "env-key")      # the user's own variable wins
    assert downloader.configured_api_key() == "env-key"

    monkeypatch.setattr(downloader, "check_api_key", lambda key, session=None: "ok")
    api_key, _, session, owned = downloader._prepare_client(None, None, None, None, None)
    session.close()
    assert (api_key, owned) == ("env-key", True)
    assert downloader._prepare_client("given", None, None, None, session)[0] == "given"


def test_check_api_key_asks_ncbi_once(make_session, monkeypatch):
    monkeypatch.setattr(downloader, "_checked_keys", {})
    rejected = '{"error":"API key invalid","api-key":"bad","type":"invalid"}'
    assert downloader.check_api_key("bad", make_session(status=400, body=rejected)) == "invalid"
    assert downloader.check_api_key("bad", make_session(status=200, body="{}")) == "invalid"     # remembered
    good = make_session(status=200, body='{"esearchresult": {"count": "1"}}')
    assert downloader.check_api_key("good", good) == "ok"
    assert downloader.check_api_key("good", good) == "ok"
    assert len(good.get_adapter("https://eutils.ncbi.nlm.nih.gov").requests) == 1
    assert downloader.check_api_key("new", make_session(error=requests.ConnectionError("offline"))) == "unknown"
    assert downloader.api_key_verdict("new") == "unknown" and downloader.api_key_verdict("never") is None
    later = make_session(status=200, body="{}")
    assert downloader.check_api_key("new", later) == "unknown"                       # not asked again at once
    assert len(later.get_adapter("https://eutils.ncbi.nlm.nih.gov").requests) == 0
    downloader._checked_keys["new"] = ("unknown", time.monotonic() - downloader.RECHECK_AFTER - 1)
    assert downloader.check_api_key("new", later) == "ok"                            # but after a while


def test_a_rejected_key_is_dropped_with_a_warning(make_session, monkeypatch, caplog):
    monkeypatch.setattr(downloader, "_checked_keys", {})
    monkeypatch.setattr(downloader, "_warned_keys", set())
    session = make_session(status=400, body='{"error":"API key invalid"}')
    with caplog.at_level("WARNING", logger="pubmed_stream.downloader"):
        api_key, limiter, _, _ = downloader._prepare_client("bad", None, None, None, session)
        downloader._prepare_client("bad", None, None, None, session)
    assert api_key is None and limiter._min_interval == downloader.RATE_LIMIT_NO_API_KEY
    assert caplog.text.count("NCBI rejected the API key") == 1


def test_api_key_hint_and_status(home, monkeypatch):
    assert downloader.api_key_hint(20, 7.0) is None                     # would save under 10 s
    hint = downloader.api_key_hint(300, 102.0)
    assert "took 102 s" in hint and "about 30 s" in hint and "init --ncbi-api-key" in hint
    assert downloader.api_key_status().startswith("off;")
    set_setting(user_settings_file(), NCBI_API_KEY_SETTING, "saved-key-1234")
    assert downloader.api_key_hint(300, 102.0) is None
    assert downloader.api_key_status() == f"on (…1234, from {home / '.pubmed-stream.json'})"
    monkeypatch.setenv(downloader.NCBI_API_KEY_ENV, "env-key-5678")
    assert downloader.api_key_status() == "on (…5678, from NCBI_API_KEY)"
