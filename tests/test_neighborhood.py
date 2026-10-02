import json
import logging
import re
import sys
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from pubmed_stream import (
    download_neighborhood,
    extract_metadata_from_pmc_xml,
    get_neighborhood,
    save_neighborhood,
)
from pubmed_stream import cli
from pubmed_stream.neighborhood import _parse_pubmed_articles

API_KEY = "SECRET_KEY_123"

# Fixture articles matched by each PubMed search filter
SEARCH_FLAGS = {
    "review[pt:noexp]": {"201", "401"},
    "retracted publication[pt]": {"202", "301"},
    "nih[gr]": {"100", "202"},
    "pubmed pmc[sb]": {"100", "202", "301"},
}
# Flag counts per relation of the fixture neighborhood
FLAG_COUNTS = {
    "similar": {"reviews": 1, "retracted": 1, "nih_funded": 1, "in_pmc": 1},
    "cited_by": {"reviews": 0, "retracted": 2, "nih_funded": 1, "in_pmc": 2},
    "references": {"reviews": 1, "retracted": 0, "nih_funded": 0, "in_pmc": 0},
}


class FakeHistory:
    """EPost/ESearch stand-in: stores posted ID sets and counts flags within them."""

    def __init__(self):
        self.posted = {}

    def epost(self, request):
        key = str(len(self.posted) + 1)
        self.posted[key] = parse_qs(request.body)["id"][0].split(",")
        return f"<ePostResult><QueryKey>{key}</QueryKey><WebEnv>MCID_test</WebEnv></ePostResult>"

    def esearch(self, request):
        term = parse_qs(urlparse(request.url).query)["term"][0]
        key, search_filter = re.fullmatch(r"#(\d+) AND (.+)", term).groups()
        flagged = next(ids for marker, ids in SEARCH_FLAGS.items() if marker in search_filter)
        return json.dumps({"esearchresult": {"count": str(sum(i in flagged for i in self.posted[key]))}})


@pytest.fixture
def history():
    return FakeHistory()


@pytest.fixture
def ncbi(make_session, elink_json, pubmed_xml, full_xml, history):
    """Session answering ELink, EFetch (PubMed and PMC), EPost and ESearch requests."""
    return make_session(routes={
        "elink.fcgi": elink_json,
        "efetch.fcgi?db=pubmed": pubmed_xml,
        "efetch.fcgi?db=pmc": full_xml,
        "epost.fcgi": history.epost,
        "esearch.fcgi": history.esearch,
    })


def sent(session):
    return session.get_adapter("https://").requests


def neighborhood(session, **kwargs):
    return get_neighborhood("100", session=session, rate_limit=0, **kwargs)


def test_relations_in_elink_order_with_scores(ncbi):
    hood = neighborhood(ncbi)

    assert [(a.pmid, a.score) for a in hood.similar] == [("201", 900), ("202", 800)]
    assert [(a.pmid, a.score) for a in hood.cited_by] == [("301", None), ("202", None)]
    assert [a.pmid for a in hood.references] == ["401", "999"]
    assert hood.seed.title == "The seed article on gut microbiome."
    assert hood.totals == {"similar": 2, "cited_by": 2, "references": 2}
    assert hood.linked_discoveries_url == "https://linkeddiscoveries.ncbi.nlm.nih.gov/100/"


def test_one_elink_and_one_efetch_request(ncbi):
    neighborhood(ncbi)

    elink, efetch = sent(ncbi)
    assert parse_qs(urlparse(elink.url).query)["cmd"] == ["neighbor_score"]
    # Seed first, each PMID once; the alsoviewed link set is ignored
    assert parse_qs(urlparse(efetch.url).query)["id"] == ["100,201,202,301,401,999"]


def test_article_details_and_flags(ncbi):
    articles = {a.pmid: a for a in neighborhood(ncbi).articles()}

    seed = articles["100"]
    assert (seed.year, seed.journal, seed.authors) == ("2018", "Journal of Seeds", ["Smith John A"])
    assert (seed.pmcid, seed.doi) == ("PMC100", "10.1000/seed")
    assert seed.nih_funded  # from the grant list only

    assert articles["201"].is_review and articles["201"].year == "2019"
    assert articles["202"].is_retracted and articles["202"].nih_funded  # publication types
    assert articles["301"].is_retracted  # RetractionIn comment only
    assert articles["301"].authors == ["Microbiome Study Group", "Doe Jane"]
    assert articles["401"].is_review and not articles["401"].nih_funded  # Systematic Review, Wellcome
    assert not any([articles["201"].is_retracted, articles["401"].is_retracted, articles["100"].is_review])


def test_missing_record_keeps_pmid(ncbi):
    missing = neighborhood(ncbi).references[1]

    assert (missing.pmid, missing.title, missing.pmcid) == ("999", None, None)


def test_articles_are_deduplicated(ncbi):
    assert [a.pmid for a in neighborhood(ncbi).articles()] == ["100", "201", "202", "301", "401", "999"]


def test_max_per_relation(ncbi):
    hood = neighborhood(ncbi, max_per_relation=1)

    assert [len(hood.similar), len(hood.cited_by), len(hood.references)] == [1, 1, 1]
    # Totals still count every linked article
    assert hood.totals == {"similar": 2, "cited_by": 2, "references": 2}
    assert parse_qs(urlparse(sent(ncbi)[1].url).query)["id"] == ["100,201,301,401"]


def test_flag_counts_from_fetched_articles(ncbi):
    hood = neighborhood(ncbi)

    assert hood.flag_counts == FLAG_COUNTS
    assert len(sent(ncbi)) == 2  # nothing was cut short, so no search requests


def test_flag_counts_cover_articles_beyond_cap(ncbi, history):
    hood = neighborhood(ncbi, max_per_relation=1)

    # Same counts as without a cap: EPost + ESearch count all linked articles
    assert hood.flag_counts == FLAG_COUNTS
    assert history.posted == {"1": ["201", "202"], "2": ["301", "202"], "3": ["401", "999"]}
    epost = next(r for r in sent(ncbi) if "epost.fcgi" in r.url)
    assert epost.method == "POST" and "id=" not in epost.url
    assert len(sent(ncbi)) == 2 + 3 * 5


def test_scoping_review_is_a_review():
    xml = (
        "<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID><Article>"
        "<ArticleTitle>T</ArticleTitle><PublicationTypeList>"
        "<PublicationType>Scoping Review</PublicationType></PublicationTypeList>"
        "</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"
    )

    assert _parse_pubmed_articles(xml)["1"].is_review


def test_negative_max_per_relation(ncbi):
    with pytest.raises(ValueError):
        neighborhood(ncbi, max_per_relation=-1)


def test_unknown_pmid_has_no_seed(make_session):
    session = make_session(routes={
        "elink.fcgi": json.dumps({"linksets": [{"dbfrom": "pubmed", "ids": ["1"]}]}),
        "efetch.fcgi?db=pubmed": "<PubmedArticleSet></PubmedArticleSet>",
    })
    hood = get_neighborhood("1", session=session, rate_limit=0)

    assert hood.seed is None
    assert hood.articles() == []


@pytest.mark.parametrize("pmid", ["", "PMC123", "12a", "\u00b2"])
def test_invalid_pmid(pmid, make_session):
    session = make_session()

    with pytest.raises(ValueError):
        get_neighborhood(pmid, session=session)
    assert sent(session) == []


def test_pmc_id_gets_a_helpful_error(make_session):
    with pytest.raises(ValueError, match="is a PMC ID; pass the article's PubMed ID"):
        get_neighborhood("PMC5866166", session=make_session())


def test_ncbi_failure_raises_without_api_key(make_session, caplog):
    session = make_session(status=500)

    with caplog.at_level(logging.WARNING), pytest.raises(requests.RequestException) as excinfo:
        get_neighborhood("100", api_key=API_KEY, session=session, rate_limit=0)

    assert len(sent(session)) == 3
    assert API_KEY not in str(excinfo.value)
    assert excinfo.value.__cause__ is None and excinfo.value.__context__ is None
    assert API_KEY not in caplog.text


def test_save_neighborhood(ncbi, tmp_path):
    hood = neighborhood(ncbi)
    path = save_neighborhood(hood, tmp_path)

    assert path == tmp_path / "neighborhood_100" / "neighborhood.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["seed"]["pmid"] == "100"
    assert [a["pmid"] for a in data["similar"]] == ["201", "202"]
    assert data["cited_by"][0]["is_retracted"] is True
    assert data["totals"] == {"similar": 2, "cited_by": 2, "references": 2}
    assert data["flag_counts"] == FLAG_COUNTS


def test_download_neighborhood(ncbi, tmp_path):
    hood = neighborhood(ncbi)
    stats = download_neighborhood(hood, output_dir=tmp_path, session=ncbi, rate_limit=0, use_concurrent=False)

    out_dir = tmp_path / "neighborhood_100"
    assert sorted(p.name for p in out_dir.iterdir()) == ["PMC100.json", "PMC202.json", "PMC301.json"]
    assert (stats.total_found, stats.requested, stats.successful) == (6, 3, 3)
    assert stats.output_dir == out_dir


def test_metadata_links_to_linked_discoveries(full_xml):
    metadata = extract_metadata_from_pmc_xml(full_xml)

    assert metadata["linked_discoveries_url"] == "https://linkeddiscoveries.ncbi.nlm.nih.gov/30000001/"


def test_cli_neighborhood(ncbi, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("pubmed_stream.downloader.create_session", lambda user_agent: ncbi)
    monkeypatch.setattr(sys, "argv", [
        "pubmed-stream", "neighborhood", "100", "-o", str(tmp_path), "--rate-limit", "0",
        "--download", "--sequential",
    ])

    assert cli.main() == 0
    out = capsys.readouterr().out
    assert "Similar         2            (1 reviews, 1 retracted, 1 NIH-funded, 1 in PMC)" in out
    assert "Neighborhood    5 unique articles fetched" in out
    assert "[RETRACTED] PMID 202 (2020) A retracted study." in out
    assert "[RETRACTED] PMID 301 (2023)" in out
    assert "https://linkeddiscoveries.ncbi.nlm.nih.gov/100/" in out
    assert (tmp_path / "neighborhood_100" / "neighborhood.json").exists()
    assert (tmp_path / "neighborhood_100" / "PMC202.json").exists()



def test_cli_neighborhood_shows_totals_when_capped(ncbi, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("pubmed_stream.downloader.create_session", lambda user_agent: ncbi)
    monkeypatch.setattr(sys, "argv", [
        "pubmed-stream", "neighborhood", "100", "-o", str(tmp_path), "--rate-limit", "0",
        "--max-per-relation", "1",
    ])

    assert cli.main() == 0
    out = capsys.readouterr().out
    # Flag counts still cover both articles of each relation
    assert "Similar         1 of 2       (1 reviews, 1 retracted, 1 NIH-funded, 1 in PMC)" in out
    assert "Cited by        1 of 2       (0 reviews, 2 retracted, 1 NIH-funded, 2 in PMC)" in out
    assert "Neighborhood    3 unique articles fetched" in out


def test_cli_neighborhood_not_found(make_session, tmp_path, monkeypatch, capsys):
    session = make_session(routes={
        "elink.fcgi": json.dumps({"linksets": []}),
        "efetch.fcgi?db=pubmed": "<PubmedArticleSet></PubmedArticleSet>",
    })
    monkeypatch.setattr("pubmed_stream.downloader.create_session", lambda user_agent: session)
    monkeypatch.setattr(sys, "argv", ["pubmed-stream", "neighborhood", "1", "-o", str(tmp_path)])

    assert cli.main() == 1
    assert "not found" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []
