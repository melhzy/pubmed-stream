import json
import sys

import pytest
import requests

from pubmed_stream import RateLimiter, cli, esummary_pmc, list_articles, most_cited, search_pmc
from pubmed_stream.downloader import DownloadStats, SearchResult

SUMMARY = json.dumps({"result": {
    "uids": ["2", "1"],
    "1": {
        "uid": "1", "title": "Gut microbiota in frailty.", "fulljournalname": "Nutrients",
        "pubdate": "2019 Jul 17", "authors": [{"name": "Ticinesi A"}],
        "articleids": [{"idtype": "pmid", "value": "31319564"}, {"idtype": "doi", "value": "10.3390/nu11071633"}],
    },
    "2": {
        "uid": "2", "title": "A preprint without a PMID", "source": "bioRxiv",
        "pubdate": "", "epubdate": "2026 Jan 5", "authors": [],
        "articleids": [{"idtype": "pmid", "value": "0"}],
    },
}})


def test_esummary_reads_titles_and_ids_in_the_order_given(make_session):
    articles = esummary_pmc(["PMC1", "2", "3"], None, make_session(body=SUMMARY), RateLimiter(0))

    assert [a["pmcid"] for a in articles] == ["PMC1", "PMC2"]
    assert articles[0] == {
        "pmcid": "PMC1", "pmid": "31319564", "doi": "10.3390/nu11071633", "year": "2019",
        "journal": "Nutrients", "title": "Gut microbiota in frailty.", "first_author": "Ticinesi A",
    }
    # PMID 0 means none; a missing print date falls back to the electronic date
    assert (articles[1]["pmid"], articles[1]["year"], articles[1]["journal"]) == (None, "2026", "bioRxiv")


def test_esummary_retries_a_response_without_result(make_session):
    answers = iter([json.dumps({"error": "API rate limit exceeded"}), SUMMARY])
    session = make_session(routes={"esummary.fcgi": lambda request: next(answers)})

    assert len(esummary_pmc(["1"], None, session, RateLimiter(0))) == 1


def test_esummary_gives_up_after_retries(make_session):
    session = make_session(body=json.dumps({"error": "API rate limit exceeded"}))

    with pytest.raises(requests.RequestException):
        esummary_pmc(["1"], None, session, RateLimiter(0), retries=2)


def test_search_pmc_counts_and_lists_without_downloading(make_session, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    search = json.dumps({"esearchresult": {"count": "80", "idlist": ["1", "2"]}})
    session = make_session(routes={"esearch.fcgi": search, "esummary.fcgi": SUMMARY})

    result = search_pmc("gut microbiota frailty", 2, session=session, rate_limit=0)

    assert (result.total_found, [a["pmcid"] for a in result.articles]) == (80, ["PMC1", "PMC2"])
    assert "80 articles in PMC for: gut microbiota frailty" in str(result)
    assert list(tmp_path.iterdir()) == []


def write_article(folder, pmcid, year, title, text="one two three", abstract="An abstract.", references=()):
    folder.mkdir(parents=True, exist_ok=True)
    data = {"pmcid": pmcid, "metadata": {"pmid": pmcid[3:], "year": year, "journal": "Nutrients",
                                         "title": title, "authors": ["Ticinesi Andrea"], "abstract": abstract,
                                         "references": list(references)},
            "text": text}
    (folder / f"{pmcid}.json").write_text(json.dumps(data), encoding="utf-8")


def test_list_articles_merges_searches_newest_first(tmp_path):
    write_article(tmp_path / "frailty", "PMC1", "2019", "Older review")
    write_article(tmp_path / "frailty", "PMC2", "2026", "Newer\n  study")
    write_article(tmp_path / "sarcopenia", "PMC1", "2019", "Older review")
    (tmp_path / "sarcopenia" / "PMC9.json").write_text("not json", encoding="utf-8")

    records = list_articles(tmp_path)

    assert [r["pmcid"] for r in records] == ["PMC2", "PMC1"]
    assert records[0]["title"] == "Newer study"
    assert records[1]["folders"] == ["frailty", "sarcopenia"]
    assert (records[1]["words"], records[1]["first_author"]) == (3, "Ticinesi Andrea")


def test_most_cited_counts_each_citing_article_once(tmp_path):
    landmark = {"pmid": "27912057", "title": "Gut microbiota regulate motor deficits", "year": "2016"}
    by_doi = {"doi": "10.1/ABC", "title": "A reference without a PMID"}
    write_article(tmp_path / "a", "PMC1", "2025", "One", references=[landmark, landmark, by_doi])
    write_article(tmp_path / "a", "PMC2", "2026", "Two", references=[landmark, {"doi": "10.1/abc"}])
    write_article(tmp_path / "b", "PMC2", "2026", "Two", references=[landmark])   # the same article again

    works = most_cited(tmp_path, 5)

    assert [(w["pmid"] or w["doi"], w["cited_by"]) for w in works] == [("27912057", 2), ("10.1/ABC", 2)]
    assert works[0]["title"] == "Gut microbiota regulate motor deficits"


def run_cli(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["pubmed-stream", *argv])
    return cli.main()


def test_cli_search(monkeypatch, capsys):
    article = {"pmcid": "PMC1", "pmid": "31319564", "doi": None, "year": "2019",
               "journal": "Nutrients", "title": "Gut microbiota in frailty.", "first_author": None}
    monkeypatch.setattr(cli, "search_pmc", lambda query, **kwargs: SearchResult(query, 80, [article]))

    assert run_cli(monkeypatch, "search", "frailty") == 0
    out = capsys.readouterr().out
    assert "80 articles in PMC for: frailty" in out and "PMID 31319564" in out

    assert run_cli(monkeypatch, "search", "frailty", "--json") == 0
    assert json.loads(capsys.readouterr().out)["articles"] == [article]


def test_cli_search_that_finds_nothing_exits_1(monkeypatch, capsys):
    monkeypatch.setattr(cli, "search_pmc", lambda query, **kwargs: SearchResult(query, 0, []))

    assert run_cli(monkeypatch, "search", "xyzzy") == 1


def test_cli_list(tmp_path, monkeypatch, capsys):
    write_article(tmp_path / "frailty", "PMC1", "2019", "Older review")
    write_article(tmp_path / "frailty", "PMC2", "2026", "Newer study")

    assert run_cli(monkeypatch, "list", str(tmp_path), "--limit", "1") == 0
    out = capsys.readouterr().out
    assert out.startswith("newest 1 of 2 articles") and "Newer study" in out and "Older review" not in out

    assert run_cli(monkeypatch, "list", str(tmp_path), "--json") == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [r["pmcid"] for r in lines] == ["PMC2", "PMC1"] and "abstract" not in lines[0]

    assert run_cli(monkeypatch, "list", str(tmp_path), "--json", "--abstracts") == 0
    assert json.loads(capsys.readouterr().out.splitlines()[0])["abstract"] == "An abstract."


def test_cli_list_selected_articles(tmp_path, monkeypatch, capsys):
    write_article(tmp_path, "PMC1", "2019", "Older review")
    write_article(tmp_path, "PMC2", "2026", "Newer study")

    assert run_cli(monkeypatch, "list", str(tmp_path), "--id", "1", "pmc2", "999", "--abstracts") == 0
    captured = capsys.readouterr()
    assert "Older review" in captured.out and "Newer study" in captured.out and "An abstract." in captured.out
    assert "Not downloaded under" in captured.err and "999" in captured.err

    assert run_cli(monkeypatch, "list", str(tmp_path), "--id", "999") == 1


def test_cli_list_cited(tmp_path, monkeypatch, capsys):
    landmark = {"pmid": "27912057", "title": "Gut microbiota regulate motor deficits", "year": "2016"}
    write_article(tmp_path, "PMC1", "2025", "One", references=[landmark])

    assert run_cli(monkeypatch, "list", str(tmp_path), "--cited") == 0
    out = capsys.readouterr().out
    assert "Works cited most by the 1 articles" in out and "PMID 27912057" in out

    assert run_cli(monkeypatch, "list", str(tmp_path), "--cited", "1", "--json") == 0
    assert json.loads(capsys.readouterr().out)["cited_by"] == 1


def test_cli_list_without_articles_exits_1(tmp_path, monkeypatch, capsys):
    assert run_cli(monkeypatch, "list", str(tmp_path / "missing")) == 1
    assert run_cli(monkeypatch, "list", str(tmp_path)) == 1
    assert "No downloaded articles" in capsys.readouterr().err


def test_cli_download_quiet_prints_only_the_summary(tmp_path, monkeypatch, capsys):
    def fake_download(**kwargs):
        print("Progress: 1/1 processed")
        stats = DownloadStats("frailty", 1, 1, 1, 0, 0, 0, 0, 0.1, output_dir=tmp_path)
        print(stats)
        return stats
    monkeypatch.setattr(cli, "search_and_download", fake_download)

    assert run_cli(monkeypatch, "download", "frailty", "--quiet") == 0
    out = capsys.readouterr().out
    assert "Progress" not in out and out.count("Download Summary") == 1


def test_piped_output_is_utf8(monkeypatch):
    class Stream:
        def __init__(self, tty):
            self.tty, self.settings = tty, None

        def isatty(self):
            return self.tty

        def reconfigure(self, **settings):
            self.settings = settings

    pipe, terminal = Stream(False), Stream(True)
    monkeypatch.setattr(sys, "stdout", pipe)
    monkeypatch.setattr(sys, "stderr", terminal)

    cli._utf8_output()

    assert pipe.settings == {"encoding": "utf-8"} and terminal.settings == {"errors": "replace"}
