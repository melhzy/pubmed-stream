import json
import sys

import pytest
import requests

from pubmed_stream import cli, create_kg, load_study, record_study

TOPIC = "gut microbiome study"


def search_json(ids):
    return json.dumps({"esearchresult": {"count": str(len(ids)), "idlist": ids}})


@pytest.fixture
def ncbi(make_session, full_xml, elink_json, pubmed_xml):
    """Answers a PMC search finding one article, and a neighborhood of PMID 100."""
    def factory(search_ids=("1",), elink=True):
        routes = {
            "esearch.fcgi?db=pmc": search_json(list(search_ids)),
            "efetch.fcgi?db=pmc": full_xml,
            "efetch.fcgi?db=pubmed": pubmed_xml,
        }
        if elink:
            routes["elink.fcgi"] = elink_json
        return make_session(routes=routes)
    return factory


@pytest.fixture
def study(tmp_path, monkeypatch):
    """Run create_kg in tmp_path with fake NCBI, offline graph builds by default."""
    monkeypatch.chdir(tmp_path)

    def run(session, topic=TOPIC, **kwargs):
        kwargs.setdefault("offline", True)
        return create_kg(topic, output_dir=tmp_path / "publications", session=session, rate_limit=0, **kwargs)
    return run


def sent(session):
    return session.get_adapter("https://").requests


def test_searches_and_seeds_build_one_graph(ncbi, study, tmp_path):
    result = study(ncbi(), queries=["gut microbiome"], seeds=["100"])

    kg = tmp_path / "kg_gut_microbiome_study"
    assert result.kg_dir == kg
    assert [s.successful for s in result.downloads] == [1]
    assert [h.pmid for h in result.neighborhoods] == ["100"]
    assert result.errors == []
    assert result.vault.collections == 2
    assert (kg / "papers" / "PMID30000001.md").exists()  # downloaded article
    assert (kg / "papers" / "PMID100.md").exists()  # neighborhood seed
    assert (kg / "collections" / "Search - gut microbiome.md").exists()
    assert (kg / "collections" / "Neighborhood - PMID 100.md").exists()
    assert load_study(kg) == {"topic": TOPIC, "queries": ["gut microbiome"], "seeds": ["100"]}
    assert "Knowledge graph: gut microbiome study" in str(result)


def test_later_runs_add_to_the_study(ncbi, study, tmp_path):
    study(ncbi(), queries=["gut microbiome"])
    result = study(ncbi(), seeds=[100])

    assert result.queries == ["gut microbiome"] and result.seeds == ["100"]
    assert len(result.downloads) == 0  # the earlier search is not repeated
    assert result.vault.collections == 2


def test_refresh_reruns_every_search_and_seed(ncbi, study):
    study(ncbi(), queries=["gut microbiome"], seeds=["100"])
    session = ncbi()

    result = study(session, refresh=True)

    assert [(s.successful, s.skipped) for s in result.downloads] == [(0, 1)]  # already downloaded
    assert [h.pmid for h in result.neighborhoods] == ["100"]
    assert any("esearch.fcgi" in r.url for r in sent(session))


def test_rebuild_without_network(ncbi, study, make_session):
    study(ncbi(), queries=["gut microbiome"])
    failing = make_session(error=requests.ConnectionError("offline"))

    result = study(failing)

    assert sent(failing) == []
    assert result.vault.updated == 0 and result.vault.unchanged > 0


def test_failures_are_reported_and_the_rest_is_built(ncbi, study):
    result = study(ncbi(search_ids=(), elink=False), queries=["nothing here", "nothing here"], seeds=["100"],
                   sources=[], kg_dir="kg_failures")

    # The duplicate query runs once; the failed seed and empty search are reported
    assert len(result.downloads) == 1
    assert result.errors[0].startswith("Search 'nothing here'")
    assert result.errors[1].startswith("Neighborhood of PMID 100")
    assert result.vault is None  # nothing could be collected, so no graph yet


def test_failed_neighborhood_alongside_a_search(ncbi, study):
    result = study(ncbi(elink=False), queries=["gut microbiome"], seeds=["100"])

    assert [e.split(":")[0] for e in result.errors] == ["Neighborhood of PMID 100"]
    assert result.vault.papers == 1
    assert load_study(result.kg_dir)["seeds"] == ["100"]  # kept, so a refresh retries it


@pytest.mark.parametrize("kwargs, message", [
    ({"topic": "  "}, "needs a topic"),
    ({"seeds": ["PMC123"]}, "numeric PubMed ID"),
    ({}, "Nothing to build"),
])
def test_invalid_studies(make_session, study, kwargs, message):
    session = make_session()
    with pytest.raises(ValueError, match=message):
        study(session, **kwargs)
    assert sent(session) == []


def test_kg_dir_and_sources(study, tmp_path, make_session):
    folder = tmp_path / "old" / "frailty"
    folder.mkdir(parents=True)
    (folder / "PMC70.json").write_text(json.dumps(
        {"metadata": {"pmid": "7", "pmcid": "PMC70", "title": "Older download", "year": "2015"}}
    ), encoding="utf-8")

    result = study(make_session(), sources=[folder], kg_dir=tmp_path / "custom")

    assert result.kg_dir == tmp_path / "custom"
    assert (tmp_path / "custom" / "papers" / "PMID7.md").exists()
    assert load_study(tmp_path / "custom")["topic"] == TOPIC
    assert "(1 paper)" in (tmp_path / "custom" / "PubMed Stream.md").read_text(encoding="utf-8")


def test_record_study_merges(tmp_path):
    record_study(tmp_path / "kg_x", "Topic X", queries=["a"], seeds=["1"])
    study = record_study(tmp_path / "kg_x", queries=["a", "b"], seeds=[2])

    assert study == {"topic": "Topic X", "queries": ["a", "b"], "seeds": ["1", "2"]}
    assert record_study(tmp_path / "kg_new")["topic"] == "kg_new"


def article_folder(tmp_path):
    folder = tmp_path / "publications" / "frailty"
    folder.mkdir(parents=True)
    (folder / "PMC70.json").write_text(json.dumps(
        {"metadata": {"pmid": "7", "pmcid": "PMC70", "title": "Older download", "year": "2015"}}
    ), encoding="utf-8")
    return folder


def test_cli_kg(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    folder = article_folder(tmp_path)
    monkeypatch.setattr(sys, "argv", ["pubmed-stream", "kg", "frailty study", "--add", str(folder), "--offline"])

    assert cli.main() == 0
    assert (tmp_path / "kg_frailty_study" / "papers" / "PMID7.md").exists()
    assert "Knowledge graph: frailty study" in capsys.readouterr().out


def test_cli_kg_nothing_to_build(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["pubmed-stream", "kg", "empty study", "--offline"])

    assert cli.main() == 1
    assert "Nothing to build" in capsys.readouterr().err


def test_download_with_topic_joins_the_study(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    folder = article_folder(tmp_path)
    args = cli.build_parser().parse_args(["download", "frailty", "--topic", "frailty study", "--offline"])

    assert cli._update_vault(args, cli._vault_dir(args, folder.name), [folder], queries=[args.keyword]) == 0
    assert load_study(tmp_path / "kg_frailty_study") == {
        "topic": "frailty study", "queries": ["frailty"], "seeds": []
    }
