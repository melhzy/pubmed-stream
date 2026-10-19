"""Save PubMed abstracts, for articles whose full text is not free in PMC.

PMC holds the free full text of only part of the literature: for most
topics, PubMed finds several times as many articles as PMC.  The rest
still have a PubMed record, usually with an abstract.  ``fetch_abstracts``
searches PubMed and saves each article's record as ``PMID<id>.json``, in
the same folder ``search_and_download`` uses for the same search, so the
articles are listed, reviewed and put into a knowledge graph with the full
texts.  Where an article has both, its full text is used.
"""

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from .downloader import (
    DEFAULT_OUTPUT_DIR,
    RateLimiter,
    _eutils_request,
    _prepare_client,
    _write_query_file,
    slugify,
)
from .neighborhood import RelatedArticle, _efetch_pubmed

logger = logging.getLogger(__name__)

MAX_ABSTRACTS = 9999  # ESearch returns at most 9,999 IDs without the history server
SOURCE = "pubmed"     # the "source" of a saved record, to tell it from a PMC download


@dataclass
class AbstractStats:
    """What ``fetch_abstracts`` found and saved."""
    query: str
    total_found: int
    requested: int
    saved: int
    skipped: int           # already saved by an earlier run
    without_abstract: int  # saved, but PubMed has no abstract (letters, editorials, some older articles)
    in_pmc: int            # also free in PMC: ``download`` gets their full text
    duration_seconds: float
    output_dir: Path

    def __str__(self) -> str:
        return (
            f"\n{'=' * 60}\nPubMed abstracts\n{'=' * 60}\n"
            f"Query:             {self.query}\n"
            f"Total in PubMed:   {self.total_found}\n"
            f"Requested:         {self.requested}\n"
            f"[OK] Saved:        {self.saved}\n"
            f"  - No abstract:   {self.without_abstract}\n"
            f"[SKIP] Skipped:    {self.skipped}\n"
            f"Also free in PMC:  {self.in_pmc} (pubmed-stream download gets their full text)\n"
            f"Duration:          {self.duration_seconds:.1f}s\n"
            f"Output directory:  {self.output_dir}\n"
            f"{'=' * 60}"
        )


def esearch_pubmed(
    term: str,
    max_results: int,
    api_key: Optional[str],
    session: requests.Session,
    rate_limiter: RateLimiter,
) -> Tuple[List[str], int]:
    """PubMed IDs for *term*, newest first, and the total number of matches.

    Raises:
        requests.RequestException: NCBI did not answer.
    """
    params = {"db": "pubmed", "term": term, "retmax": min(max_results, MAX_ABSTRACTS),
              "sort": "pub_date", "retmode": "json"}
    result = _eutils_request("esearch.fcgi", params, api_key, session, rate_limiter).json()["esearchresult"]
    return list(result.get("idlist", [])), int(result.get("count", 0))


def count_pubmed(
    term: str,
    api_key: Optional[str] = None,
    session: Optional[requests.Session] = None,
    rate_limit: Optional[float] = None,
) -> int:
    """The number of PubMed articles matching *term*."""
    api_key, rate_limiter, session, owned = _prepare_client(api_key, rate_limit, None, None, session)
    try:
        return esearch_pubmed(term, 0, api_key, session, rate_limiter)[1]
    finally:
        if owned:
            session.close()


def _record(article: RelatedArticle) -> Dict[str, Any]:
    """A saved abstract, shaped like a PMC download so the corpus and vault read both."""
    metadata = asdict(article)
    metadata.pop("score", None)
    return {"pmid": article.pmid, "source": SOURCE,
            "retrieved": datetime.now().isoformat(timespec="seconds"), "metadata": metadata}


def fetch_abstracts(
    query: str,
    max_results: int = 100,
    output_dir: Optional[Path] = None,
    api_key: Optional[str] = None,
    user_agent: Optional[str] = None,
    email: Optional[str] = None,
    rate_limit: Optional[float] = None,
    session: Optional[requests.Session] = None,
) -> AbstractStats:
    """Search PubMed for *query* and save the newest *max_results* articles' abstracts.

    Articles are saved as ``<output_dir>/<query_slug>/PMID<id>.json``, next
    to any full texts ``search_and_download`` saved for the same query.
    Articles saved before are skipped.  The query uses PubMed's syntax,
    which PMC shares, so the same query works for both.

    Raises:
        requests.RequestException: NCBI did not answer.
    """
    start = time.time()
    api_key, rate_limiter, session, owned = _prepare_client(api_key, rate_limit, user_agent, email, session)
    out_dir = Path(output_dir or DEFAULT_OUTPUT_DIR) / slugify(query)
    try:
        pmids, total = esearch_pubmed(query, max_results, api_key, session, rate_limiter)
        wanted = [p for p in pmids if not (out_dir / f"PMID{p}.json").exists()]
        articles = _efetch_pubmed(wanted, api_key, session, rate_limiter) if wanted else {}
    finally:
        if owned:
            session.close()

    if pmids:
        _write_query_file(out_dir, query)
    for pmid in wanted:
        if pmid in articles:
            path = out_dir / f"PMID{pmid}.json"
            path.write_text(json.dumps(_record(articles[pmid]), ensure_ascii=False, indent=1), encoding="utf-8")
    saved = [articles[p] for p in wanted if p in articles]
    stats = AbstractStats(
        query=query, total_found=total, requested=len(pmids), saved=len(saved),
        skipped=len(pmids) - len(wanted), without_abstract=sum(not a.abstract for a in saved),
        in_pmc=sum(bool(a.pmcid) for a in saved), duration_seconds=time.time() - start, output_dir=out_dir,
    )
    logger.info("Saved %d PubMed abstracts to %s", stats.saved, out_dir)
    return stats
