"""Offline tests of tutorial 8's helpers, tutorials/citation_impact.py."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tutorials"))

import citation_impact as ci  # noqa: E402

ARTICLE = """<article><front><article-meta><article-id pub-id-type="pmcid">PMC1</article-id></article-meta></front>
<body>
<p>Soluble oligomers impair memory [<xref ref-type="bibr" rid="R1">1</xref>].
Aβ*56 was isolated from mice.<xref ref-type="bibr" rid="R2">2</xref> Plaques are not toxic.</p>
<p>Many species have been described [<xref ref-type="bibr" rid="R1">1</xref>–<xref ref-type="bibr" rid="R3">3</xref>].</p>
<p>The 2006 study was retracted [<xref ref-type="bibr" rid="R2">2</xref>].</p>
<p>Dendritic spine retraction follows exposure [<xref ref-type="bibr" rid="R1">1</xref>].</p>
</body>
<back><ref-list>
<ref id="R1"><mixed-citation>Other paper. <pub-id pub-id-type="pmid">111</pub-id></mixed-citation></ref>
<ref id="R2"><mixed-citation>Lesne S. A specific amyloid-beta protein assembly. Nature 2006.
<pub-id pub-id-type="doi">10.1038/nature04533</pub-id></mixed-citation></ref>
<ref id="R3"><mixed-citation>Third paper.</mixed-citation></ref>
</ref-list></back></article>"""


def write_article(folder, xml=ARTICLE, pmcid="PMC1"):
    folder.mkdir(parents=True, exist_ok=True)
    data = {"pmcid": pmcid, "metadata": {"pmid": "999", "year": "2024", "title": "A citing paper"}, "xml": xml}
    (folder / f"{pmcid}.json").write_text(json.dumps(data), encoding="utf-8")


def test_citation_contexts_finds_direct_superscript_and_range_citations(tmp_path):
    write_article(tmp_path)
    result = ci.citation_contexts(tmp_path, "16541076", "10.1038/nature04533")["PMC1"]
    assert result["found"] and result["pmid"] == "999"
    sentences = result["sentences"]
    # Cited after a superscript-style sentence end: the citation stays with its sentence
    assert any(s.startswith("Aβ*56 was isolated") and s.endswith(ci.CITE) for s in sentences)
    assert not any("Plaques are not toxic" in s for s in sentences)
    # Cited inside the range [1–3], although only refs 1 and 3 are tagged
    assert any(s.startswith("Many species") for s in sentences)
    assert any("retracted" in s for s in sentences)
    # Sentences that cite only other papers are left out
    assert not any("Dendritic" in s or "Soluble oligomers" in s for s in sentences)
    assert result["mentions"] == 1


def test_citation_contexts_matches_title_words_and_skips_articles_without_xml(tmp_path):
    write_article(tmp_path, ARTICLE.replace("10.1038/nature04533", "10.9/other"))
    (tmp_path / "PMC2.json").write_text(json.dumps({"pmcid": "PMC2", "metadata": {}, "text": "no xml"}),
                                        encoding="utf-8")
    assert not ci.citation_contexts(tmp_path, "16541076", "10.1038/nature04533")["PMC1"]["found"]
    result = ci.citation_contexts(tmp_path, "16541076", title_words="specific amyloid")
    assert result["PMC1"]["found"] and "PMC2" not in result


def test_classify_orders_kinds_and_ignores_biological_retraction():
    assert ci.classify([]) == ci.KINDS[3]
    assert ci.classify(["Aβ*56 impairs memory ⟦CITE⟧.", "The study was retracted ⟦CITE⟧."]) == ci.KINDS[0]
    assert ci.classify(["Aβ*56 impairs memory ⟦CITE⟧."]) == ci.KINDS[1]
    assert ci.classify(["Dendritic spine retraction follows exposure ⟦CITE⟧."]) == ci.KINDS[2]
    assert ci.classify(["Oligomers disrupt synaptic integrity ⟦CITE⟧."]) == ci.KINDS[2]
    assert ci.classify(["Figures in the paper were manipulated ⟦CITE⟧."]) == ci.KINDS[0]


def test_annotate_adds_properties_and_keeps_the_note(tmp_path):
    note = tmp_path / "papers" / "PMID999.md"
    note.parent.mkdir()
    note.write_text('---\ntitle: "A citing paper"\nyear: 2024\n---\nBody\n', encoding="utf-8")
    props = {"999": {"hop": 1, "citation_kind": ci.KINDS[1]}, "123": {"hop": 2}}
    assert ci.annotate(tmp_path, props) == 1
    text = note.read_text(encoding="utf-8")
    assert text.startswith('---\ntitle: "A citing paper"\nyear: 2024\nhop: 1\ncitation_kind: "Names Aβ*56"\n---\n')
    assert text.endswith("Body\n")
    assert ci.annotate(tmp_path, props) == 0


def test_write_base_has_a_view_per_kind(tmp_path):
    text = ci.write_base(tmp_path).read_text(encoding="utf-8")
    for kind in ci.KINDS[:3]:
        assert f"citation_kind == \"{kind}\"" in text
    assert "        - 'hop == 1'\n        - 'retracted == true'\n" in text
