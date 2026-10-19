"""Offline tests of PubMed abstracts: saving them, listing them with full texts, and the vault."""

import json
import sys
from urllib.parse import parse_qs, urlparse

from pubmed_stream import cli
from pubmed_stream.abstracts import fetch_abstracts
from pubmed_stream.corpus import list_articles, select, short_id
from pubmed_stream.vault import build_vault

ESEARCH = json.dumps({"esearchresult": {"count": "1200", "idlist": ["100", "201"]}})


def pubmed(make_session, pubmed_xml):
    return make_session(routes={"esearch.fcgi": ESEARCH, "efetch.fcgi?db=pubmed": pubmed_xml})


def test_fetch_abstracts_saves_records_and_skips_them_next_time(make_session, pubmed_xml, tmp_path):
    session = pubmed(make_session, pubmed_xml)

    stats = fetch_abstracts("gut frailty", max_results=2, output_dir=tmp_path, session=session)

    folder = tmp_path / "gut_frailty"
    assert stats.output_dir == folder and stats.total_found == 1200
    assert (stats.requested, stats.saved, stats.skipped, stats.without_abstract, stats.in_pmc) == (2, 2, 0, 1, 1)
    record = json.loads((folder / "PMID100.json").read_text(encoding="utf-8"))
    assert record["source"] == "pubmed" and record["pmid"] == "100"
    assert record["metadata"]["abstract"] == "BACKGROUND: Gut microbes matter. RESULTS: It worked."
    assert record["metadata"]["mesh_terms"][0]["name"] == "Gastrointestinal Microbiome"
    assert json.loads((folder / "query.json").read_text(encoding="utf-8"))["query"] == "gut frailty"
    search = parse_qs(urlparse(session.get_adapter("https://").requests[0].url).query)
    assert search["db"] == ["pubmed"] and search["sort"] == ["pub_date"] and search["retmax"] == ["2"]

    again = fetch_abstracts("gut frailty", max_results=2, output_dir=tmp_path, session=session)
    assert (again.saved, again.skipped) == (0, 2)
    # Articles already saved are not fetched again
    assert sum("efetch" in r.url for r in session.get_adapter("https://").requests) == 1


def write_full_text(folder, pmcid, pmid, title):
    folder.mkdir(parents=True, exist_ok=True)
    data = {"pmcid": pmcid, "metadata": {"pmid": pmid, "pmcid": pmcid, "year": "2020", "title": title,
                                         "abstract": "From PMC."}, "text": "one two three"}
    (folder / f"{pmcid}.json").write_text(json.dumps(data), encoding="utf-8")


def test_list_articles_prefers_the_full_text_of_an_article_saved_both_ways(make_session, pubmed_xml, tmp_path):
    fetch_abstracts("gut frailty", output_dir=tmp_path, session=pubmed(make_session, pubmed_xml))
    write_full_text(tmp_path / "other_search", "PMC100", "100", "The seed, in full")

    records = list_articles(tmp_path)

    assert len(records) == 2
    seed = next(r for r in records if r["pmid"] == "100")
    assert seed["full_text"] and seed["title"] == "The seed, in full" and seed["words"] == 3
    assert sorted(seed["folders"]) == ["gut_frailty", "other_search"]
    review = next(r for r in records if r["pmid"] == "201")
    assert not review["full_text"] and review["pmcid"] is None and short_id(review) == "abstract"
    chosen, missing = select(records, ["201", "pmc100", "999"])
    assert sorted(r["pmid"] for r in chosen) == ["100", "201"] and missing == ["999"]


def test_vault_notes_for_abstracts_carry_the_pubmed_record(make_session, pubmed_xml, tmp_path):
    stats = fetch_abstracts("gut frailty", output_dir=tmp_path, session=pubmed(make_session, pubmed_xml))

    vault = build_vault([stats.output_dir], tmp_path / "kg", offline=True)

    assert (vault.papers, vault.full_text, vault.abstracts, vault.stubs) == (2, 0, 2, 0)
    note = (tmp_path / "kg" / "papers" / "PMID100.md").read_text(encoding="utf-8")
    assert 'status: "abstract"' in note and '"pubmed/abstract-only"' in note
    assert '"Gastrointestinal Microbiome"' in note and "> [!note] Abstract only" in note
    assert "BACKGROUND: Gut microbes matter." in note
    assert "| Papers with abstract only | 2 |" in (tmp_path / "kg" / "PubMed Stream.md").read_text(encoding="utf-8")


def test_cli_list_marks_abstracts(make_session, pubmed_xml, tmp_path, monkeypatch, capsys):
    fetch_abstracts("gut frailty", output_dir=tmp_path, session=pubmed(make_session, pubmed_xml))
    monkeypatch.setattr(sys, "argv", ["pubmed-stream", "list", str(tmp_path)])

    assert cli.main() == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == f"2 articles in {tmp_path}"
    assert all(line.endswith("[abstract only]") for line in lines[1:])
    assert any(line.split()[1:4] == ["abstract", "PMID", "201"] for line in lines[1:])
