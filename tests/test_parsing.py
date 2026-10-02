import pytest

from pubmed_stream import (
    extract_metadata_from_pmc_xml,
    extract_text_from_pmc_xml,
    strip_xml_tags,
)


def article_with_dates(pub_dates: str) -> str:
    return (
        "<pmc-articleset><article><front><article-meta>"
        f"{pub_dates}"
        "</article-meta></front></article></pmc-articleset>"
    )


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def test_metadata_fields(full_xml):
    metadata = extract_metadata_from_pmc_xml(full_xml)

    assert metadata["title"] == "Gut microbiome & frailty"
    assert metadata["journal"] == "Journal of Testing"
    assert metadata["pmcid"] == "PMC1000001"
    assert metadata["pmid"] == "30000001"
    assert metadata["doi"] == "10.1000/test.1"
    assert metadata["authors"] == ["Smith John A", "Doe Jane"]
    assert metadata["keywords"] == ["microbiome", "frailty"]


def test_epub_date_preferred_over_collection(full_xml):
    metadata = extract_metadata_from_pmc_xml(full_xml)

    assert (metadata["year"], metadata["month"], metadata["day"]) == ("2024", "3", "5")
    assert metadata["pub_date"] == {"year": "2024", "month": "3", "day": "5"}


def test_jats_1_1_date_type_pub():
    xml = article_with_dates(
        '<pub-date publication-format="print" date-type="pub"><year>2025</year></pub-date>'
        '<pub-date publication-format="electronic" date-type="pub" iso-8601-date="2026-09-14">'
        "<day>14</day><month>9</month><year>2026</year></pub-date>"
        '<pub-date publication-format="electronic" date-type="collection"><year>2027</year></pub-date>'
    )
    metadata = extract_metadata_from_pmc_xml(xml)

    assert (metadata["year"], metadata["month"], metadata["day"]) == ("2026", "9", "14")


def test_print_date_when_no_electronic_date():
    xml = article_with_dates(
        '<pub-date pub-type="ppub"><month>6</month><year>1998</year></pub-date>'
    )
    metadata = extract_metadata_from_pmc_xml(xml)

    assert metadata["pub_date"] == {"year": "1998", "month": "6"}


@pytest.mark.parametrize("attr", ["pub-type", "date-type"])
def test_collection_year_fallback(attr):
    xml = article_with_dates(
        f'<pub-date {attr}="collection"><month>1</month><year>2022</year></pub-date>'
    )
    metadata = extract_metadata_from_pmc_xml(xml)

    assert metadata["year"] == "2022"
    assert "month" not in metadata


def test_metadata_unparseable_xml_returns_empty():
    assert extract_metadata_from_pmc_xml("not xml <") == {}


# ---------------------------------------------------------------------------
# Plain text
# ---------------------------------------------------------------------------

def test_text_is_readable_lines(full_xml):
    assert extract_text_from_pmc_xml(full_xml).split("\n") == [
        "Gut microbiome & frailty",
        "Background",
        "Frailty is common in older adults.",
        "Results",
        "Diversity was lower (p < 0.01).",
        "Introduction",
        "Levels of H2O were significant (p < 0.05) in the α group [1].",
        "A second paragraph with an x inline formula.",
        "Table 1",
        "Cohort summary",
        "Group n",
        "Frail 12",
    ]


def test_text_excludes_front_and_back_matter(full_xml):
    text = extract_text_from_pmc_xml(full_xml)

    for noise in ["Test J", "9999", "1234-5678", "PMC1000001", "funders", "unrelated reference", "documentclass"]:
        assert noise not in text


def test_text_falls_back_to_tag_stripping():
    assert extract_text_from_pmc_xml("<p>broken &amp; unclosed") == "broken & unclosed"


def test_strip_xml_tags_decodes_entities():
    assert strip_xml_tags("<p>p &lt; 0.05 &amp; &#x003b1;</p>") == "p < 0.05 & α"
