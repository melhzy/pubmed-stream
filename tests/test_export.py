"""Offline tests of citation export (BibTeX and RIS)."""

import json
import sys

import pytest

from pubmed_stream import cli
from pubmed_stream.export import export_citations


def write(folder, name, data):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def corpus(tmp_path):
    write(tmp_path / "search", "PMC1.json", {"pmcid": "PMC1", "text": "full text", "metadata": {
        "pmid": "111", "pmcid": "PMC1", "doi": "10.1/a", "year": "2024", "journal": "Gut Microbes",
        "title": "Gut & brain: 50% {better}", "authors": ["Smith John A", "van der Berg Anna"],
        "abstract": "It worked."}})
    write(tmp_path / "search", "PMID222.json", {"pmid": "222", "source": "pubmed", "metadata": {
        "pmid": "222", "year": "2024", "journal": "Brain", "title": "Gut feelings.",
        "authors": ["Smith Jane"], "abstract": None}})
    return tmp_path


def test_bibtex_escapes_and_keeps_keys_unique(corpus):
    text, count, missing = export_citations(corpus, "bibtex")

    assert (count, missing) == (2, [])
    first, second = text.strip().split("\n\n")
    assert first.startswith("@article{Smith2024Gut,\n") and second.startswith("@article{Smith2024Guta,\n")
    assert "title = {Gut \\& brain: 50\\% (better)}" in first
    assert "author = {Smith, John A and van, der Berg Anna}" in first
    assert "pmcid = {PMC1}" in first and "url = {https://pubmed.ncbi.nlm.nih.gov/111/}" in first
    assert "title = {Gut feelings}" in second and "abstract" not in second and "pmcid" not in second


def test_ris_records_and_chosen_ids(corpus):
    text, count, missing = export_citations(corpus, "ris", ids=["222", "999"])

    assert (count, missing) == (1, ["999"])
    assert text == ("TY  - JOUR\nTI  - Gut feelings\nAU  - Smith, Jane\nJO  - Brain\nPY  - 2024\n"
                    "AN  - PMID:222\nUR  - https://pubmed.ncbi.nlm.nih.gov/222/\nER  - \n")
    with pytest.raises(ValueError):
        export_citations(corpus, "endnote")


def test_cli_export_writes_a_file(corpus, monkeypatch, capsys):
    target = corpus / "out.bib"
    monkeypatch.setattr(sys, "argv", ["pubmed-stream", "export", str(corpus), "-o", str(target)])

    assert cli.main() == 0
    assert capsys.readouterr().out.strip() == f"Wrote 2 citations to {target}"
    assert target.read_text(encoding="utf-8").count("@article{") == 2
