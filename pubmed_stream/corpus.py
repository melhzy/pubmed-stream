"""Read downloaded articles back as compact records.

A downloaded article file holds the full text, typically 50 to 100 KB.  To
scan a corpus, a person or an AI assistant needs only each article's
identifiers, title, journal, year and abstract: ``list_articles`` returns
those, one record per article, however many searches found it.  Abstracts
saved from PubMed (``PMID*.json``, see ``fetch_abstracts``) are read too;
an article saved both ways is listed once, with its full text.
``most_cited`` finds the works the corpus cites most, its foundations.
"""

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Tuple, Union

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]


def _is_abstract(data: Dict[str, Any]) -> bool:
    """A record saved from PubMed, with the abstract but not the full text."""
    return data.get("source") == "pubmed"


def _articles(path: PathLike) -> Iterator[Tuple[Path, Dict[str, Any], List[str]]]:
    """Each downloaded article under *path* once, with the folders it is in.

    Full texts are read before abstracts, so an article saved both ways is
    represented by its full text.
    """
    path = Path(path)
    files = [path] if path.is_file() else sorted(path.rglob("PMC*.json")) + sorted(path.rglob("PMID*.json"))
    seen: Dict[str, Tuple[Path, Dict[str, Any], List[str]]] = {}
    keys: Dict[str, str] = {}  # PubMed ID or PMC ID -> the key of the article it belongs to
    for file in files:
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            logger.warning("Skipping %s: %s", file, e)
            continue
        if not isinstance(data, dict):
            continue
        meta = data.get("metadata") or {}
        ids = [str(i) for i in (meta.get("pmid"), data.get("pmcid") or meta.get("pmcid")) if i]
        key = next((keys[i] for i in ids if i in keys), None) or (ids[0] if ids else file.stem)
        if key in seen:
            if file.parent.name not in seen[key][2]:
                seen[key][2].append(file.parent.name)
        else:
            seen[key] = (file, data, [file.parent.name])
        keys.update((i, key) for i in ids)
    return iter(seen.values())


def list_articles(path: PathLike) -> List[Dict[str, Any]]:
    """Compact records of the articles downloaded under *path*, newest first.

    *path* is one article file or a folder, searched recursively, such as
    one search's download folder or the whole ``publications`` folder.
    Each record has ``pmcid`` (``None`` for an abstract of an article not in
    PMC), ``pmid``, ``doi``, ``year``, ``journal``, ``title``,
    ``first_author``, ``abstract``, ``full_text`` (whether the full text was
    downloaded, rather than only the abstract), ``words`` (the length of the
    full text), ``file`` and ``folders`` (the download folders it is in).
    An article in several folders, or saved both ways, appears once.
    """
    records = []
    for file, data, folders in _articles(path):
        meta = data.get("metadata") or {}
        authors = meta.get("authors") or []
        abstract_only = _is_abstract(data)
        records.append({
            "pmcid": data.get("pmcid") or meta.get("pmcid") or (None if abstract_only else file.stem),
            "pmid": meta.get("pmid"),
            "doi": meta.get("doi"),
            "year": meta.get("year"),
            "journal": meta.get("journal") or meta.get("journal_title"),
            "title": " ".join((meta.get("title") or "").split()) or None,   # some titles hold line breaks
            "first_author": authors[0] if authors else None,
            "abstract": meta.get("abstract") or "",
            "full_text": not abstract_only,
            "words": len((data.get("text") or "").split()),
            "file": str(file),
            "folders": folders,
        })
    return sorted(records, key=lambda r: (str(r["year"] or ""), r["pmcid"] or "", r["pmid"] or ""), reverse=True)


def select(records: List[Dict[str, Any]], ids: Iterable[Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """The records with the given PubMed or PMC IDs, and the IDs not found among them."""
    wanted = {str(i).strip().upper() for i in ids}
    chosen = [r for r in records if str(r["pmid"]) in wanted or (r["pmcid"] or "").upper() in wanted]
    found = {str(r["pmid"]) for r in chosen} | {(r["pmcid"] or "").upper() for r in chosen}
    return chosen, sorted(wanted - found)


def short_id(record: Dict[str, Any]) -> str:
    """The record's PMC ID, or "abstract" for an abstract saved from PubMed."""
    return record["pmcid"] or "abstract"


def most_cited(path: PathLike, n: int = 10) -> List[Dict[str, Any]]:
    """The *n* works cited by the most articles downloaded under *path*.

    These are the corpus's foundations, usually landmark reviews and
    discoveries, and good key papers for an evidence neighborhood.  Each
    record has ``pmid``, ``doi``, ``title``, ``year`` and ``cited_by``, the
    number of downloaded articles that cite it.  References are matched by
    PubMed ID, or by DOI when they have none.
    """
    counts: Counter = Counter()
    details: Dict[str, Dict[str, Any]] = {}
    for _, data, _ in _articles(path):
        cited: Dict[str, None] = {}   # ordered, so ties keep the order works are first cited
        for ref in (data.get("metadata") or {}).get("references") or []:
            key = ref.get("pmid") or (ref.get("doi") or "").lower()
            if not key:
                continue
            cited[key] = None
            known = details.setdefault(key, {"pmid": ref.get("pmid"), "doi": ref.get("doi"),
                                             "title": ref.get("title"), "year": ref.get("year")})
            for field in ("doi", "title", "year"):
                known[field] = known[field] or ref.get(field)
        counts.update(cited.keys())
    return [{**details[key], "cited_by": count} for key, count in counts.most_common(n)]
