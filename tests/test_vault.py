import json
import sys
from pathlib import Path

import pytest
import requests

from pubmed_stream import build_vault, cli, topic_vault_dir
from pubmed_stream.vault import BLOCK_END, _merge_frontmatter, _safe_name


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def article(pmid, title, year, **metadata):
    return {"pmcid": f"PMC{pmid}0", "metadata": {
        "pmid": pmid, "pmcid": f"PMC{pmid}0", "title": title, "year": year, **metadata
    }}


@pytest.fixture
def search_dir(tmp_path):
    """A search download: paper 1 cites paper 2, an outside paper and a DOI-only work."""
    folder = tmp_path / "downloads" / "gut_microbiome"
    write_json(folder / "query.json", {"query": "gut microbiome"})
    write_json(folder / "PMC10.json", {
        **article(
            "1", "Paper One", "2020",
            authors=["Smith John"],
            journal="Journal of Tests",
            doi="10.1/one",
            abstract="Uses #hashtag, [[link]] and %% marker.",
            references=[
                {"pmid": "2", "title": "Paper Two", "year": "2019"},
                {"pmid": "900", "title": "Outside paper", "year": "2001"},
                {"doi": "10.1/x", "title": "DOI only work"},
                {"doi": "10.1/one"},  # self-citation is dropped
            ],
        ),
        "text": "Full text body.",
    })
    write_json(folder / "PMC20.json", article("2", "Paper Two", "2019"))
    return folder


@pytest.fixture
def hood_dir(tmp_path):
    """A neighborhood of paper 1 with PubMed summaries and MeSH terms."""
    folder = tmp_path / "downloads" / "neighborhood_1"
    write_json(folder / "neighborhood.json", {
        "pmid": "1",
        "seed": {"pmid": "1", "title": "PAPER ONE.", "year": "2020", "pub_types": ["Journal Article"],
                 "mesh_terms": [{"ui": "D1", "name": "Gastrointestinal Microbiome", "major": True},
                                {"ui": "D006801", "name": "Humans", "major": False}]},
        "similar": [{"pmid": "3", "title": "Paper Three", "year": "2018", "score": 50,
                     "is_retracted": True,
                     "mesh_terms": [{"ui": "D1", "name": "Gastrointestinal Microbiome", "major": False}]}],
        "cited_by": [{"pmid": "4", "title": "Paper Four", "year": "2023", "is_review": True}],
        "references": [{"pmid": "2", "title": "Paper Two.", "year": "2019"}, {"pmid": "999"}],
    })
    return folder


def note(vault, name):
    return (vault / f"{name}.md").read_text(encoding="utf-8")


def build(sources, vault, **kwargs):
    return build_vault(sources, vault, offline=True, **kwargs)


def test_paper_notes_link_citations_both_ways(search_dir, hood_dir, tmp_path):
    vault = tmp_path / "vault"
    stats = build([search_dir, hood_dir], vault)

    one = note(vault, "papers/PMID1")
    assert 'title: "Paper One"' in one  # PMC metadata wins over the PubMed summary
    assert 'status: "full-text"' in one
    assert "[[PMID2|Paper Two (2019)]]" in one
    assert "[[PMID900|Outside paper (2001)]]" in one  # unresolved link, no note
    assert "[DOI only work](https://doi.org/10.1/x)" in one
    # 2 and 900 from the reference list, 999 from the neighborhood; 2 only once
    assert "## Cites (3)" in one and "- [[PMID999]]" in one
    assert "[[PMID3|Paper Three (2018)]] · score 50" in one
    assert "## Cited by (1)" in one and "[[PMID4|Paper Four (2023)]]" in one

    assert "## Cited by (1)" in note(vault, "papers/PMID2")
    assert not (vault / "papers" / "PMID900.md").exists()
    assert not (vault / "papers" / "PMID999.md").exists()  # no details, no note
    assert (stats.papers, stats.full_text, stats.stubs) == (4, 2, 2)


def test_stubs_flags_and_escaping(search_dir, hood_dir, tmp_path):
    vault = tmp_path / "vault"
    build([search_dir, hood_dir], vault)

    three = note(vault, "papers/PMID3")
    assert '"pubmed/stub"' in three and '"pubmed/retracted"' in three
    assert "> [!warning] Retracted publication" in three
    assert "retracted: true" in three
    assert '"pubmed/review"' in note(vault, "papers/PMID4")

    one = note(vault, "papers/PMID1")
    assert "Uses \\#hashtag, \\[\\[link\\]\\] and % % marker." in one
    assert "## Full text" not in one


def test_concepts_collections_and_home(search_dir, hood_dir, tmp_path):
    vault = tmp_path / "vault"
    stats = build([search_dir, hood_dir], vault)

    concept = note(vault, "concepts/Gastrointestinal Microbiome")
    assert 'mesh_ui: "D1"' in concept
    assert "[[PMID1|Paper One (2020)]] (major topic)" in concept
    assert "[[PMID3|Paper Three (2018)]]" in concept
    # Check tags stay in frontmatter but get no concept note
    assert not (vault / "concepts" / "Humans.md").exists()
    assert '  - "Humans"' in note(vault, "papers/PMID1")
    assert stats.concepts == 1

    search = note(vault, "collections/Search - gut microbiome")
    assert 'query: "gut microbiome"' in search and "## Papers (2)" in search
    hood = note(vault, "collections/Neighborhood - PMID 1")
    assert "**Seed:** [[PMID1|Paper One (2020)]]" in hood
    assert "- [[Gastrointestinal Microbiome]] (2)" in hood

    home = note(vault, "PubMed Stream")
    assert "[[Search - gut microbiome]] (2 papers)" in home
    assert "## Retracted papers (1)" in home
    graph = json.loads((vault / ".obsidian" / "graph.json").read_text(encoding="utf-8"))
    assert graph["colorGroups"][0]["query"] == "tag:#pubmed/retracted"


def test_fulltext_option(search_dir, tmp_path):
    vault = tmp_path / "vault"
    build([search_dir], vault, fulltext=True)

    assert "## Full text\n\nFull text body." in note(vault, "papers/PMID1")


def test_rebuild_is_unchanged_and_keeps_user_edits(search_dir, hood_dir, tmp_path):
    vault = tmp_path / "vault"
    build([search_dir, hood_dir], vault)
    assert build(None, vault).updated == 0

    path = vault / "papers" / "PMID2.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("tags:\n", "rating: 5\ntags:\n  - to-read\n", 1)
    text = text.replace("## Notes\n", "## Notes\n\nMy own summary.\n")
    text = text.replace("# Paper Two", "# I edited the generated title")
    path.write_text(text, encoding="utf-8")

    # A new paper citing paper 2 changes its generated block
    write_json(search_dir / "PMC50.json", article("5", "Paper Five", "2024", references=[{"pmid": "2"}]))
    stats = build(None, vault)

    two = path.read_text(encoding="utf-8")
    assert stats.updated >= 1
    assert "rating: 5" in two
    assert '  - "to-read"' in two and '  - "pubmed/paper"' in two
    assert "My own summary." in two.split(BLOCK_END)[1]
    assert "# Paper Two" in two and "I edited" not in two
    assert "## Cited by (2)" in two


def test_sources_are_remembered(search_dir, hood_dir, tmp_path):
    vault = tmp_path / "vault"
    build([search_dir], vault)
    stats = build([hood_dir], vault)

    assert stats.sources == [search_dir.resolve(), hood_dir.resolve()]
    assert stats.collections == 2
    assert "## Papers (2)" in note(vault, "collections/Search - gut microbiome")


def test_missing_source_and_no_sources(tmp_path):
    with pytest.raises(FileNotFoundError):
        build([tmp_path / "nope"], tmp_path / "vault")
    with pytest.raises(ValueError):
        build(None, tmp_path / "vault")


def test_mesh_terms_fetched_once_and_cached(make_session, pubmed_xml, tmp_path):
    folder = tmp_path / "downloads" / "seed"
    write_json(folder / "PMC1000.json", article("100", "The seed article", "2018"))
    vault = tmp_path / "vault"
    session = make_session(routes={"efetch.fcgi?db=pubmed": pubmed_xml})

    stats = build_vault([folder], vault, session=session, rate_limit=0)

    assert stats.pubmed_fetched == 1
    concept = note(vault, "concepts/Gastrointestinal Microbiome")
    assert "[[PMID100|The seed article (2018)]] (major topic)" in concept
    seed = note(vault, "papers/PMID100")
    assert '"pubmed/nih-funded"' in seed and "Journal of Seeds" in seed

    # Cached: a failing network is never asked
    failing = make_session(error=requests.ConnectionError("offline"))
    again = build_vault(None, vault, session=failing, rate_limit=0)
    assert failing.get_adapter("https://").requests == []
    assert again.updated == 0 and again.pubmed_missing == 0


def test_pubmed_failure_still_builds(make_session, tmp_path, caplog):
    folder = tmp_path / "downloads" / "seed"
    write_json(folder / "PMC1000.json", article("100", "The seed article", "2018"))
    session = make_session(error=requests.ConnectionError("offline"))

    stats = build_vault([folder], tmp_path / "vault", session=session, rate_limit=0)

    assert stats.papers == 1 and stats.pubmed_missing == 1
    assert "Could not fetch MeSH terms" in caplog.text


def test_references_read_from_saved_xml(full_xml, tmp_path):
    folder = tmp_path / "downloads" / "xml"
    xml = full_xml.replace(
        "<mixed-citation>Roe R. An unrelated reference. 2020.</mixed-citation>",
        '<mixed-citation>Roe R. <pub-id pub-id-type="pmid">77</pub-id></mixed-citation>',
    )
    write_json(folder / "PMC1000001.json", {"pmcid": "PMC1000001", "metadata": {
        "pmid": "30000001", "pmcid": "PMC1000001", "title": "Old download"}, "xml": xml})

    build([folder], tmp_path / "vault")

    assert "[[PMID77]]" in note(tmp_path / "vault", "papers/PMID30000001")


def test_merge_frontmatter_flow_lists():
    existing = 'tags: [to-read, "pubmed/stub"]\naliases: [Nickname]\nmine: yes'
    merged = _merge_frontmatter(existing, {"tags": ["pubmed/paper"], "aliases": ["Title"]}, ("tags", "aliases"))

    assert merged == 'tags:\n  - "pubmed/paper"\n  - "to-read"\naliases:\n  - "Title"\n  - "Nickname"\nmine: yes'


@pytest.mark.parametrize("name, expected", [
    ('"knowledge graph"[Title/Abstract]', "knowledge graph(Title-Abstract)"),
    ("Antibodies, Monoclonal", "Antibodies, Monoclonal"),
    ("a/b: c?", "a-b- c"),
    ("...", "untitled"),
])
def test_safe_name(name, expected):
    assert _safe_name(name) == expected


def test_cli_graph(search_dir, tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    monkeypatch.setattr(sys, "argv", [
        "pubmed-stream", "graph", str(search_dir), "--vault", str(vault), "--offline",
    ])

    assert cli.main() == 0
    assert (vault / "papers" / "PMID1.md").exists()
    assert "Obsidian vault" in capsys.readouterr().out

    # With no SOURCE the vault's remembered sources are used
    monkeypatch.setattr(sys, "argv", ["pubmed-stream", "graph", "--vault", str(vault), "--offline"])
    assert cli.main() == 0


def test_cli_graph_missing_source(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [
        "pubmed-stream", "graph", str(tmp_path / "nope"), "--vault", str(tmp_path / "vault"),
    ])

    assert cli.main() == 1
    assert "Source not found" in capsys.readouterr().err


@pytest.mark.parametrize("topic, expected", [
    ("gut microbiome", "kg_gut_microbiome"),
    ('"knowledge graph"[Title]', "kg_knowledge_graph_Title"),
    ("kg_frailty", "kg_frailty"),  # no kg_kg_ prefix
    ("???", "kg_topic"),
])
def test_topic_vault_dir(topic, expected, tmp_path):
    assert topic_vault_dir(topic) == Path(expected)
    assert topic_vault_dir(topic, tmp_path) == tmp_path / expected


def test_cli_graph_names_vault_after_single_source(search_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["pubmed-stream", "graph", str(search_dir), "--offline"])

    assert cli.main() == 0
    assert (tmp_path / "kg_gut_microbiome" / "papers" / "PMID1.md").exists()


def test_cli_graph_topic_for_several_sources(search_dir, hood_dir, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["pubmed-stream", "graph", str(search_dir), str(hood_dir), "--offline"])
    assert cli.main() == 1
    assert "--topic" in capsys.readouterr().err

    monkeypatch.setattr(sys, "argv", [
        "pubmed-stream", "graph", str(search_dir), str(hood_dir), "--topic", "gut microbiome study", "--offline",
    ])
    assert cli.main() == 0
    assert (tmp_path / "kg_gut_microbiome_study" / "collections" / "Neighborhood - PMID 1.md").exists()

    # The topic alone rebuilds from the remembered sources
    monkeypatch.setattr(sys, "argv", ["pubmed-stream", "graph", "--topic", "gut microbiome study", "--offline"])
    assert cli.main() == 0


@pytest.mark.parametrize("argv, expected", [
    ([], None),  # no vault requested
    (["--vault"], Path("kg_gut_microbiome")),
    (["--vault", "my_vault"], Path("my_vault")),
    (["--topic", "frailty"], Path("kg_frailty")),
    (["--vault", "--topic", "frailty"], Path("kg_frailty")),
    (["--vault", "my_vault", "--topic", "frailty"], Path("my_vault")),
])
def test_download_vault_naming(argv, expected):
    args = cli.build_parser().parse_args(["download", "gut microbiome"] + argv)

    assert cli._vault_dir(args, "gut_microbiome") == expected
