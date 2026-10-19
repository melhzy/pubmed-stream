"""Export downloaded articles as citations, for Zotero, EndNote, Mendeley or LaTeX.

``export_citations`` reads the articles under a folder, full texts and
abstracts alike, and writes them as BibTeX or RIS, the two formats every
reference manager imports.  Each entry has the title, authors, journal,
year, DOI, PubMed and PMC IDs, a link and the abstract.

Author names are stored as "Surname Given names", so the surname is taken
to be the first word.  Multi-word surnames, such as "van der Berg", come
out split; check them after importing.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from .corpus import list_articles, select

PathLike = Union[str, Path]

FORMATS = ("bibtex", "ris")

_BIBTEX_SPECIAL = re.compile(r"([&%$#_])")


def _authors(record: Dict[str, Any]) -> List[str]:
    """The record's authors, read from its file, as "Surname, Given names"."""
    try:
        meta = json.loads(Path(record["file"]).read_text(encoding="utf-8")).get("metadata") or {}
    except (OSError, ValueError):
        meta = {}
    names = meta.get("authors") or ([record["first_author"]] if record.get("first_author") else [])
    return [", ".join(name.split(" ", 1)) for name in names if name]


def _title(record: Dict[str, Any]) -> str:
    """The title without PubMed's closing full stop, which citation styles add themselves."""
    title = " ".join((record.get("title") or "").split())
    return title[:-1] if title.endswith(".") and not title.endswith("..") else title


def _url(record: Dict[str, Any]) -> Optional[str]:
    if record.get("pmid"):
        return f"https://pubmed.ncbi.nlm.nih.gov/{record['pmid']}/"
    if record.get("pmcid"):
        return f"https://pmc.ncbi.nlm.nih.gov/articles/{record['pmcid']}/"
    return None


def _bibtex_value(text: Any) -> str:
    text = " ".join(str(text).split()).replace("{", "(").replace("}", ")")
    return _BIBTEX_SPECIAL.sub(r"\\\1", text)


def _bibtex_key(record: Dict[str, Any], authors: List[str], used: Dict[str, int]) -> str:
    surname = re.sub(r"\W", "", authors[0].split(",")[0]) if authors else "Anon"
    word = next((re.sub(r"\W", "", w) for w in (record.get("title") or "").split() if re.sub(r"\W", "", w)),
                "Untitled")
    key = f"{surname or 'Anon'}{record.get('year') or ''}{word}"
    used[key] = used.get(key, 0) + 1
    # A second article with the same key gets a letter: Smith2020Gut, Smith2020Guta, ...
    return key if used[key] == 1 else f"{key}{chr(ord('a') + used[key] - 2)}"


def to_bibtex(records: Iterable[Dict[str, Any]]) -> str:
    """BibTeX entries (``@article``) for *records* from :func:`list_articles`."""
    entries, used = [], {}
    for record in records:
        authors = _authors(record)
        fields = {
            "title": _title(record),
            "author": " and ".join(authors),
            "journal": record.get("journal"),
            "year": record.get("year"),
            "doi": record.get("doi"),
            "pmid": record.get("pmid"),
            "pmcid": record.get("pmcid"),
            "url": _url(record),
            "abstract": record.get("abstract"),
        }
        body = ",\n".join(f"  {name} = {{{_bibtex_value(value)}}}" for name, value in fields.items() if value)
        entries.append(f"@article{{{_bibtex_key(record, authors, used)},\n{body}\n}}")
    return "\n\n".join(entries) + "\n" if entries else ""


def to_ris(records: Iterable[Dict[str, Any]]) -> str:
    """RIS records (type ``JOUR``) for *records* from :func:`list_articles`."""
    entries = []
    for record in records:
        lines = ["TY  - JOUR", f"TI  - {_title(record)}"]
        lines += [f"AU  - {name}" for name in _authors(record)]
        for tag, value in (("JO", record.get("journal")), ("PY", record.get("year")), ("DO", record.get("doi")),
                           ("AN", f"PMID:{record['pmid']}" if record.get("pmid") else None),
                           ("UR", _url(record)), ("AB", " ".join((record.get("abstract") or "").split()))):
            if value:
                lines.append(f"{tag}  - {value}")
        if record.get("pmcid"):
            lines.append(f"N1  - PMCID: {record['pmcid']}")
        entries.append("\n".join(lines + ["ER  - "]))
    return "\n\n".join(entries) + "\n" if entries else ""


def export_citations(
    path: PathLike = "publications",
    fmt: str = "bibtex",
    ids: Optional[Iterable[Any]] = None,
) -> Tuple[str, int, List[str]]:
    """Citations for the articles under *path*, as BibTeX or RIS.

    *ids* chooses articles by PubMed or PMC ID; without it, every article
    is exported, newest first.  Returns ``(text, count, missing)``, where
    *missing* lists the IDs not found.

    Raises:
        ValueError: *fmt* is not ``"bibtex"`` or ``"ris"``.
    """
    if fmt not in FORMATS:
        raise ValueError(f"Format must be one of {', '.join(FORMATS)}, not {fmt!r}")
    records, missing = list_articles(path), []
    if ids:
        records, missing = select(records, ids)
    text = to_bibtex(records) if fmt == "bibtex" else to_ris(records)
    return text, len(records), missing
