import json
import logging

import requests

from pubmed_stream import RateLimiter, efetch_pmc, esearch_pmc, search_and_download

API_KEY = "SECRET_KEY_123"


def fetch(session, tmp_path, fmt="text", api_key=None):
    return efetch_pmc(
        "1000001",
        tmp_path,
        fmt=fmt,
        api_key=api_key,
        session=session,
        rate_limiter=RateLimiter(0),
    )


def test_efetch_saves_full_text_article(make_session, tmp_path, full_xml):
    result = fetch(make_session(body=full_xml), tmp_path, fmt="both")

    assert result == (True, "success")
    payload = json.loads((tmp_path / "PMC1000001.json").read_text(encoding="utf-8"))
    assert payload["pmcid"] == "PMC1000001"
    assert payload["metadata"]["year"] == "2024"
    assert payload["xml"] == full_xml
    assert "(p < 0.05)" in payload["text"]


def test_efetch_skips_existing_file(make_session, tmp_path, full_xml):
    (tmp_path / "PMC1000001.json").write_text("{}", encoding="utf-8")
    session = make_session(body=full_xml)

    assert fetch(session, tmp_path) == (True, "exists")
    assert session.get_adapter("https://").requests == []


def test_efetch_article_without_body_is_unavailable(make_session, tmp_path, no_body_xml):
    result = fetch(make_session(body=no_body_xml), tmp_path)

    assert result == (False, "unavailable")
    assert list(tmp_path.iterdir()) == []


def test_efetch_pmc_error_response_is_unavailable(make_session, tmp_path):
    body = '<pmc-articleset><error id="1000001">The following PMCID is not available</error></pmc-articleset>'

    assert fetch(make_session(body=body), tmp_path) == (False, "unavailable")
    assert list(tmp_path.iterdir()) == []


def test_efetch_http_error(make_session, tmp_path):
    session = make_session(status=500)

    assert fetch(session, tmp_path) == (False, "error")
    assert len(session.get_adapter("https://").requests) == 3


def test_efetch_does_not_log_api_key(make_session, tmp_path, caplog):
    error = requests.ConnectionError(
        f"Max retries exceeded with url: /entrez/eutils/efetch.fcgi?db=pmc&id=1000001&api_key={API_KEY}"
    )
    with caplog.at_level(logging.WARNING):
        result = fetch(make_session(error=error), tmp_path, api_key=API_KEY)

    assert result == (False, "error")
    assert "api_key=***" in caplog.text
    assert API_KEY not in caplog.text


def test_esearch_does_not_log_api_key(make_session, caplog):
    session = make_session(status=429, body="{}")
    with caplog.at_level(logging.WARNING):
        result = esearch_pmc("microbiome", 5, API_KEY, session, RateLimiter(0))

    assert result == ([], 0)
    assert "api_key=***" in caplog.text
    assert API_KEY not in caplog.text


def test_esearch_returns_ids_and_count(make_session):
    body = json.dumps({"esearchresult": {"count": "42", "idlist": ["1", "2"]}})

    assert esearch_pmc("microbiome", 2, None, make_session(body=body), RateLimiter(0)) == (["1", "2"], 42)


def test_search_and_download(make_session, tmp_path, full_xml, no_body_xml):
    search = json.dumps({"esearchresult": {"count": "3", "idlist": ["1", "2", "3"]}})
    session = make_session(routes={
        "esearch.fcgi": search,
        "db=pmc&id=1&": full_xml,
        "db=pmc&id=2&": no_body_xml,
        "db=pmc&id=3&": full_xml,
    })
    (tmp_path / "gut_microbiome").mkdir()
    (tmp_path / "gut_microbiome" / "PMC3.json").write_text("{}", encoding="utf-8")

    stats = search_and_download("gut microbiome", 3, output_dir=tmp_path, session=session, rate_limit=0)

    assert (stats.total_found, stats.requested) == (3, 3)
    assert (stats.successful, stats.unavailable, stats.skipped, stats.errors) == (1, 1, 1, 0)
    assert stats.output_dir == tmp_path / "gut_microbiome"
