"""Evidence neighborhood of a PubMed article.

A programmatic counterpart to NLM's Linked Discoveries web tool
(https://linkeddiscoveries.ncbi.nlm.nih.gov), which has no public API.  It is
built on documented NCBI E-utilities:

- ELink ``pubmed_pubmed``        – similar articles, ranked by similarity score
- ELink ``pubmed_pubmed_citedin`` – articles citing the seed
- ELink ``pubmed_pubmed_refs``    – articles the seed cites
- EFetch (PubMed XML)            – titles, dates, publication types, grants
  and PMC IDs, used to flag reviews, retractions and NIH-funded work

Similarity comes from PubMed's Similar Articles algorithm rather than the
BiomedBERT model behind Linked Discoveries, so the neighbors can differ::

    from pubmed_stream import get_neighborhood

    hood = get_neighborhood("29096998")
    retracted = [a for a in hood.articles() if a.is_retracted]
"""

import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from .downloader import (
    DEFAULT_OUTPUT_DIR,
    MAX_WORKERS,
    DownloadStats,
    RateLimiter,
    _download_pmcids,
    _eutils_request,
    _prepare_client,
    linked_discoveries_url,
)

# ELink link names and the Neighborhood field each one fills
_LINKNAMES = {
    "pubmed_pubmed": "similar",
    "pubmed_pubmed_citedin": "cited_by",
    "pubmed_pubmed_refs": "references",
}
EFETCH_BATCH_SIZE = 200  # PMIDs per EFetch request (GET URL length stays safe)
# PubMed's review[pt] also covers these child publication types
_REVIEW_TYPES = {"Review", "Systematic Review", "Scoping Review"}
# PubMed search filters equivalent to the RelatedArticle flags, used to count
# flags across relations that max_per_relation cut short
_FLAG_FILTERS = {
    "reviews": "(review[pt] OR systematic review[pt] OR scoping review[pt])",
    "retracted": "retracted publication[pt]",
    "nih_funded": '(nih[gr] OR "research support, n.i.h., extramural"[pt]'
                  ' OR "research support, n.i.h., intramural"[pt])',
    "in_pmc": "pubmed pmc[sb]",
}

logger = logging.getLogger(__name__)


@dataclass
class RelatedArticle:
    """A PubMed article in a neighborhood, with the flags Linked Discoveries shows."""
    pmid: str
    title: Optional[str] = None
    journal: Optional[str] = None
    year: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    pub_types: List[str] = field(default_factory=list)
    is_review: bool = False
    is_retracted: bool = False
    nih_funded: bool = False
    pmcid: Optional[str] = None
    doi: Optional[str] = None
    score: Optional[int] = None  # PubMed similarity score (similar articles only)


@dataclass
class Neighborhood:
    """Similar, citing and cited articles around a seed PubMed article.

    ``totals`` counts every article PubMed links per relation (``'similar'``,
    ``'cited_by'``, ``'references'``), including those beyond
    ``max_per_relation`` that are not in the lists.  ``flag_counts`` counts
    ``reviews``, ``retracted``, ``nih_funded`` and ``in_pmc`` across all of
    them, too.
    """
    pmid: str
    seed: Optional[RelatedArticle]
    similar: List[RelatedArticle]
    cited_by: List[RelatedArticle]
    references: List[RelatedArticle]
    totals: Dict[str, int]
    flag_counts: Dict[str, Dict[str, int]]
    linked_discoveries_url: str
    retrieved: str

    def articles(self) -> List[RelatedArticle]:
        """Seed plus all neighbors, without duplicates, in that order."""
        seen = set()
        result = []
        seed = [self.seed] if self.seed else []
        for article in seed + self.similar + self.cited_by + self.references:
            if article.pmid not in seen:
                seen.add(article.pmid)
                result.append(article)
        return result

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _pubmed_year(article: ET.Element) -> Optional[str]:
    year = article.findtext("Journal/JournalIssue/PubDate/Year")
    if year:
        return year.strip()
    # e.g. <MedlineDate>1998 Dec-1999 Jan</MedlineDate>
    match = re.search(r"\d{4}", article.findtext("Journal/JournalIssue/PubDate/MedlineDate") or "")
    if match:
        return match.group(0)
    year = article.findtext("ArticleDate/Year")
    return year.strip() if year else None


def _parse_pubmed_article(record: ET.Element) -> Optional[RelatedArticle]:
    citation = record.find("MedlineCitation")
    article = citation.find("Article") if citation is not None else None
    if article is None:
        return None
    pmid = (citation.findtext("PMID") or "").strip()

    title_el = article.find("ArticleTitle")
    title = "".join(title_el.itertext()).strip() if title_el is not None else ""

    authors: List[str] = []
    for author in article.findall("AuthorList/Author"):
        surname = (author.findtext("LastName") or "").strip()
        given = (author.findtext("ForeName") or "").strip()
        name = f"{surname} {given}".strip() if surname else (author.findtext("CollectiveName") or "").strip()
        if name:
            authors.append(name)

    pub_types = [(pt.text or "").strip() for pt in article.findall("PublicationTypeList/PublicationType")]
    agencies = [g.findtext("Agency") or "" for g in article.findall("GrantList/Grant")]
    retraction_notice = citation.find("CommentsCorrectionsList/CommentsCorrections[@RefType='RetractionIn']")
    ids = {
        aid.get("IdType"): (aid.text or "").strip()
        for aid in record.findall("PubmedData/ArticleIdList/ArticleId")
    }

    return RelatedArticle(
        pmid=pmid,
        title=title or None,
        journal=(article.findtext("Journal/Title") or "").strip() or None,
        year=_pubmed_year(article),
        authors=authors,
        pub_types=pub_types,
        is_review=any(pt in _REVIEW_TYPES for pt in pub_types),
        is_retracted="Retracted Publication" in pub_types or retraction_notice is not None,
        # Publication types miss recent grants, so the grant list is checked too
        nih_funded=(
            any(pt.startswith("Research Support, N.I.H.") for pt in pub_types)
            or any(re.search(r"\bNIH\b", agency) for agency in agencies)
        ),
        pmcid=ids.get("pmc") or None,
        doi=ids.get("doi") or None,
    )


def _parse_pubmed_articles(xml_text: str) -> Dict[str, RelatedArticle]:
    """Parse EFetch PubMed XML into :class:`RelatedArticle` records keyed by PMID."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ValueError(f"Unparseable PubMed XML from EFetch: {e}") from None

    articles = {}
    for record in root.findall("PubmedArticle"):
        article = _parse_pubmed_article(record)
        if article is not None:
            articles[article.pmid] = article
    return articles


def _elink_neighbors(
    pmid: str,
    api_key: Optional[str],
    session: requests.Session,
    rate_limiter: RateLimiter,
) -> Dict[str, List[Tuple[str, Optional[int]]]]:
    """Return ``(pmid, score)`` pairs per relation, in ELink order."""
    # Without a linkname, one ELink call returns all pubmed->pubmed link sets
    resp = _eutils_request(
        "elink.fcgi",
        {"dbfrom": "pubmed", "db": "pubmed", "id": pmid, "cmd": "neighbor_score", "retmode": "json"},
        api_key,
        session,
        rate_limiter,
    )
    links: Dict[str, List[Tuple[str, Optional[int]]]] = {name: [] for name in _LINKNAMES.values()}
    for linkset in resp.json().get("linksets", []):
        for linksetdb in linkset.get("linksetdbs", []):
            name = _LINKNAMES.get(linksetdb.get("linkname"))
            if name is None:
                continue
            for link in linksetdb.get("links", []):
                if isinstance(link, dict):
                    score = link.get("score")
                    links[name].append((str(link["id"]), int(score) if score not in (None, "") else None))
                else:
                    links[name].append((str(link), None))
    return links


def _efetch_pubmed(
    pmids: List[str],
    api_key: Optional[str],
    session: requests.Session,
    rate_limiter: RateLimiter,
) -> Dict[str, RelatedArticle]:
    details: Dict[str, RelatedArticle] = {}
    for start in range(0, len(pmids), EFETCH_BATCH_SIZE):
        batch = pmids[start:start + EFETCH_BATCH_SIZE]
        resp = _eutils_request(
            "efetch.fcgi",
            {"db": "pubmed", "id": ",".join(batch), "retmode": "xml"},
            api_key,
            session,
            rate_limiter,
        )
        details.update(_parse_pubmed_articles(resp.text))
    return details


def _count_flags(articles: List[RelatedArticle]) -> Dict[str, int]:
    return {
        "reviews": sum(a.is_review for a in articles),
        "retracted": sum(a.is_retracted for a in articles),
        "nih_funded": sum(a.nih_funded for a in articles),
        "in_pmc": sum(a.pmcid is not None for a in articles),
    }


def _search_flag_counts(
    pmids: List[str],
    api_key: Optional[str],
    session: requests.Session,
    rate_limiter: RateLimiter,
) -> Dict[str, int]:
    """Count flags across *pmids* with PubMed search instead of fetching every record."""
    # POST keeps long ID lists out of the URL
    resp = _eutils_request(
        "epost.fcgi", {"db": "pubmed", "id": ",".join(pmids)}, api_key, session, rate_limiter, post=True
    )
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        raise ValueError(f"Unparseable EPost response: {e}") from None
    webenv, query_key = root.findtext("WebEnv"), root.findtext("QueryKey")
    if not webenv or not query_key:
        raise ValueError(f"EPost failed: {root.findtext('ERROR') or 'no WebEnv returned'}")

    counts = {}
    for flag, search_filter in _FLAG_FILTERS.items():
        resp = _eutils_request(
            "esearch.fcgi",
            {
                "db": "pubmed",
                "term": f"#{query_key} AND {search_filter}",
                "WebEnv": webenv,
                "usehistory": "y",
                "retmax": 0,
                "retmode": "json",
            },
            api_key,
            session,
            rate_limiter,
        )
        result = resp.json().get("esearchresult", {})
        if "count" not in result:
            raise ValueError(f"ESearch returned no count: {result.get('ERROR') or 'unknown error'}")
        counts[flag] = int(result["count"])
    return counts


def get_neighborhood(
    pmid: str,
    max_per_relation: int = 100,
    api_key: Optional[str] = None,
    user_agent: Optional[str] = None,
    email: Optional[str] = None,
    rate_limit: Optional[float] = None,
    session: Optional[requests.Session] = None,
) -> Neighborhood:
    """Fetch the evidence neighborhood of the PubMed article *pmid*.

    Args:
        pmid: PubMed ID of the seed article.
        max_per_relation: Cap on similar, citing and cited articles each
            (default 100).  PubMed returns at most 100 similar articles;
            citing articles come newest first.  Flags of a relation cut
            short are still counted across all its articles, with five
            extra requests (EPost plus four ESearch counts).
        api_key: NCBI API key.  Falls back to ``NCBI_API_KEY`` env var.
        user_agent: Custom ``User-Agent`` header.
        email: Contact e-mail sent to NCBI in the ``User-Agent`` header.
        rate_limit: Minimum seconds between HTTP requests (auto-detected).
        session: Optional ``requests.Session`` to reuse across calls.

    Returns:
        A :class:`Neighborhood`.  Its ``seed`` is ``None`` if PubMed has no
        record for *pmid*; ``totals`` has the uncapped count per relation.

    Raises:
        ValueError: *pmid* is not numeric, or NCBI returned unparseable data.
        requests.RequestException: NCBI could not be reached after retries.
    """
    pmid = str(pmid).strip()
    if not re.fullmatch(r"[0-9]+", pmid):
        raise ValueError(f"PMID must be numeric, got {pmid!r}")
    if max_per_relation < 0:
        raise ValueError(f"max_per_relation must be >= 0, got {max_per_relation}")

    api_key, rate_limiter, session, owned_session = _prepare_client(
        api_key, rate_limit, user_agent, email, session
    )
    try:
        all_links = _elink_neighbors(pmid, api_key, session, rate_limiter)
        links = {name: pairs[:max_per_relation] for name, pairs in all_links.items()}
        pmids = list(dict.fromkeys([pmid] + [i for pairs in links.values() for i, _ in pairs]))
        details = _efetch_pubmed(pmids, api_key, session, rate_limiter)
        search_counts = {
            name: _search_flag_counts([i for i, _ in pairs], api_key, session, rate_limiter)
            for name, pairs in all_links.items()
            if len(pairs) > len(links[name])
        }
    finally:
        if owned_session:
            session.close()

    def related(pairs: List[Tuple[str, Optional[int]]]) -> List[RelatedArticle]:
        # Deleted or unindexed records keep their PMID but no details
        return [replace(details.get(i) or RelatedArticle(pmid=i), score=score) for i, score in pairs]

    relations = {name: related(pairs) for name, pairs in links.items()}
    return Neighborhood(
        pmid=pmid,
        seed=details.get(pmid),
        similar=relations["similar"],
        cited_by=relations["cited_by"],
        references=relations["references"],
        totals={name: len(pairs) for name, pairs in all_links.items()},
        flag_counts={
            name: search_counts[name] if name in search_counts else _count_flags(articles)
            for name, articles in relations.items()
        },
        linked_discoveries_url=linked_discoveries_url(pmid),
        retrieved=datetime.now().isoformat(timespec="seconds"),
    )


def _neighborhood_dir(pmid: str, output_dir: Optional[Path]) -> Path:
    base = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    return base / f"neighborhood_{pmid}"


def save_neighborhood(neighborhood: Neighborhood, output_dir: Optional[Path] = None) -> Path:
    """Write ``<output_dir>/neighborhood_<pmid>/neighborhood.json`` and return its path."""
    out_dir = _neighborhood_dir(neighborhood.pmid, output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "neighborhood.json"
    path.write_text(json.dumps(neighborhood.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def download_neighborhood(
    neighborhood: Neighborhood,
    output_dir: Optional[Path] = None,
    fmt: str = "text",
    api_key: Optional[str] = None,
    use_concurrent: bool = True,
    max_workers: int = MAX_WORKERS,
    include_text: bool = True,
    user_agent: Optional[str] = None,
    email: Optional[str] = None,
    rate_limit: Optional[float] = None,
    session: Optional[requests.Session] = None,
) -> DownloadStats:
    """Download PMC full text for the seed and every neighbor with a PMC ID.

    Articles are saved as ``<output_dir>/neighborhood_<pmid>/PMC*.json`` in
    the same format as :func:`search_and_download`; see it for the arguments.
    """
    start_time = time.time()
    articles = neighborhood.articles()
    pmcids = list(dict.fromkeys(a.pmcid for a in articles if a.pmcid))
    out_dir = _neighborhood_dir(neighborhood.pmid, output_dir)

    successful = unavailable = errors = skipped = 0
    if pmcids:
        api_key, rate_limiter, session, owned_session = _prepare_client(
            api_key, rate_limit, user_agent, email, session
        )
        try:
            successful, unavailable, errors, skipped = _download_pmcids(
                pmcids,
                out_dir,
                fmt=fmt,
                api_key=api_key,
                session=session,
                rate_limiter=rate_limiter,
                use_concurrent=use_concurrent,
                max_workers=max_workers,
                include_text=include_text,
            )
        finally:
            if owned_session:
                session.close()

    return DownloadStats(
        keyword=f"neighborhood of PMID {neighborhood.pmid}",
        total_found=len(articles),
        requested=len(pmcids),
        successful=successful,
        failed=unavailable + errors,
        skipped=skipped,
        unavailable=unavailable,
        errors=errors,
        duration_seconds=time.time() - start_time,
        output_dir=out_dir,
    )
