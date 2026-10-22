"""Core download engine for pubmed-stream.

Searches NCBI PubMed, resolves PMC full-text links, and downloads articles
concurrently.  Designed to be called from application code::

    from pubmed_stream import search_and_download

    stats = search_and_download("frailty cytokines", max_results=50, fmt="json")

Or from the CLI::

    pubmed-stream download "frailty cytokines" --max-results 50

Configuration is read from environment variables when explicit arguments are
not provided:

- ``NCBI_API_KEY`` – increases NCBI rate limit from 3 to 10 req/s.  When it is
  unset, the key that ``pubmed-stream init --ncbi-api-key`` saved for the user is used.
- ``NCBI_EMAIL``   – included in the User-Agent header per NCBI guidelines.
"""

import hashlib
import html
import logging
import json
import os
import re
import time
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .settings import saved_api_key, user_settings_file
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime

import requests
import xml.etree.ElementTree as ET


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = Path("publications")

# Environment variables for configuration
NCBI_API_KEY_ENV = "NCBI_API_KEY"
# The Claude Code plugin passes the key the user gave it under its own name, so that it never
# overrides the user's variable; it is empty when the user gave none
PLUGIN_API_KEY_ENV = "PUBMED_STREAM_NCBI_API_KEY"
# Longest download folder name; longer search strings are shortened with a hash
MAX_SLUG_LENGTH = 100
NCBI_EMAIL_ENV = "NCBI_EMAIL"
DEFAULT_USER_AGENT = "pubmed-stream/1.0"

# NCBI E-utilities endpoints
EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
# NLM Linked Discoveries (web UI only, no public API)
LINKED_DISCOVERIES_BASE = "https://linkeddiscoveries.ncbi.nlm.nih.gov"

# Rate limiting and retry configuration
RATE_LIMIT_WITH_API_KEY = 0.1  # 10 requests/second with API key
RATE_LIMIT_NO_API_KEY = 0.34   # 3 requests/second without API key
MAX_RETRIES = 3
RETRY_DELAY = 2.0  # seconds
REQUEST_TIMEOUT = 60  # seconds
MAX_WORKERS = 5  # concurrent download threads

logger = logging.getLogger(__name__)


def _redact_api_key(message: object) -> str:
    """Hide the ``api_key`` query value that requests includes in error messages."""
    return re.sub(r"(api_key=)[^&\s'\"]+", r"\1***", str(message))


class RateLimiter:
    """Simple global rate limiter shared across threads."""

    def __init__(self, min_interval: float) -> None:
        self._min_interval = max(0.0, min_interval)
        self._lock = threading.Lock()
        self._last_request = 0.0

    def touch(self) -> None:
        """Count a request made outside ``wait``, so the next one keeps its distance."""
        with self._lock:
            self._last_request = time.monotonic()

    def wait(self) -> None:
        if self._min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            wait_time = (self._last_request + self._min_interval) - now
            if wait_time > 0:
                time.sleep(wait_time)
            self._last_request = time.monotonic()


def build_user_agent(user_agent: Optional[str], email: Optional[str]) -> str:
    if user_agent:
        return user_agent
    email = email or os.getenv(NCBI_EMAIL_ENV)
    if email:
        return f"{DEFAULT_USER_AGENT} (mailto:{email})"
    return DEFAULT_USER_AGENT


def create_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    return session


def linked_discoveries_url(pmid: str) -> str:
    """Link to the NLM Linked Discoveries page (evidence graph) of a PubMed article."""
    return f"{LINKED_DISCOVERIES_BASE}/{pmid}/"


def configured_api_key() -> Optional[str]:
    """The NCBI API key from the environment, else the one saved for the user; None when there is none."""
    return os.getenv(NCBI_API_KEY_ENV) or os.getenv(PLUGIN_API_KEY_ENV) or saved_api_key()


def api_key_status() -> str:
    """One line on the NCBI API key in use: its last characters and where it comes from, or that there is none."""
    sources = (("NCBI_API_KEY", os.getenv(NCBI_API_KEY_ENV)), ("the plugin", os.getenv(PLUGIN_API_KEY_ENV)),
               (str(user_settings_file()), saved_api_key()))
    for source, key in sources:
        if key:
            return f"on (…{key[-4:]}, from {source})"
    return ("off; a free key makes downloads about three times faster: create one in the settings of your NCBI "
            "account and run pubmed-stream init --ncbi-api-key YOUR-KEY")


# NCBI's verdict on each key this process has checked, and when, so that a key is checked once
_checked_keys: Dict[str, Tuple[str, float]] = {}
_warned_keys: set = set()
CHECK_TIMEOUT = 15      # seconds: the check is optional, so it must not hold a command up for long
RECHECK_AFTER = 300.0   # seconds after which an "unknown" verdict (NCBI unreachable) is asked again


def api_key_verdict(api_key: str) -> Optional[str]:
    """NCBI's cached verdict on *api_key* in this process: ok, invalid, unknown, or None when not yet asked."""
    entry = _checked_keys.get(api_key)
    return entry[0] if entry else None


def check_api_key(api_key: str, session: Optional[requests.Session] = None) -> str:
    """Ask NCBI once whether *api_key* is valid: ``ok``, ``invalid``, or ``unknown`` when NCBI could not be reached.

    NCBI answers every request made with an invalid key with ``400 API key invalid``,
    so a mistyped key would otherwise fail every search and download.  An
    ``unknown`` verdict is asked again after ``RECHECK_AFTER`` seconds.
    """
    entry = _checked_keys.get(api_key)
    if entry and (entry[0] != "unknown" or time.monotonic() - entry[1] < RECHECK_AFTER):
        return entry[0]
    owned = session is None
    session = session or create_session(build_user_agent(None, None))
    try:
        resp = session.get(f"{EUTILS_BASE}/esearch.fcgi", timeout=CHECK_TIMEOUT,
                           params={"db": "pubmed", "term": "pubmed-stream", "retmax": 0, "retmode": "json",
                                   "api_key": api_key})
        verdict = "invalid" if resp.status_code == 400 and "API key invalid" in resp.text else \
            "ok" if resp.ok else "unknown"
    except requests.RequestException:
        verdict = "unknown"
    finally:
        if owned:
            session.close()
    _checked_keys[api_key] = (verdict, time.monotonic())
    return verdict


def api_key_hint(requests_made: int, seconds: float) -> Optional[str]:
    """What a free NCBI API key would have saved on a run of *requests_made* requests, when that is 10 s or more.

    None when a key is configured or the saving is small.
    """
    if configured_api_key() or requests_made <= 0:
        return None
    saved = requests_made * (RATE_LIMIT_NO_API_KEY - RATE_LIMIT_WITH_API_KEY)
    if saved < 10:
        return None
    with_key = max(seconds - saved, requests_made * RATE_LIMIT_WITH_API_KEY, 1.0)
    return (f"Without an NCBI API key this took {seconds:.0f} s; with a free one it would take about {with_key:.0f} s. "
            "Create a key in the settings of your NCBI account (https://account.ncbi.nlm.nih.gov/settings/) and save "
            "it with: pubmed-stream init --ncbi-api-key YOUR-KEY")


def _prepare_client(
    api_key: Optional[str],
    rate_limit: Optional[float],
    user_agent: Optional[str],
    email: Optional[str],
    session: Optional[requests.Session],
) -> Tuple[Optional[str], RateLimiter, requests.Session, bool]:
    """Resolve the API key, rate limiter and session for a high-level call.

    Returns ``(api_key, rate_limiter, session, owned_session)``; the caller
    closes the session when *owned_session* is true.
    """
    api_key = api_key or configured_api_key()
    owned_session = session is None
    session = session or create_session(build_user_agent(user_agent, email))

    # A key NCBI rejects would fail every request: continue without it, and say so once
    probed = False
    if api_key:
        probed = api_key_verdict(api_key) is None
        if check_api_key(api_key, session) == "invalid":
            if api_key not in _warned_keys:
                _warned_keys.add(api_key)
                logger.warning("NCBI rejected the API key (API key invalid), so pubmed-stream continues without it, "
                               "at 3 requests a second. Check the key in the settings of your NCBI account and save "
                               "it again with 'pubmed-stream init --ncbi-api-key', or remove it from %s",
                               user_settings_file())
            api_key = None

    # Auto-detect rate limit based on API key presence if not explicitly specified
    if rate_limit is None:
        rate_limit = RATE_LIMIT_WITH_API_KEY if api_key else RATE_LIMIT_NO_API_KEY
        logger.debug("Auto-detected rate limit: %.2fs (%s API key)",
                     rate_limit, "with" if api_key else "without")

    rate_limiter = RateLimiter(rate_limit)
    if probed:
        rate_limiter.touch()        # the check was a request too
    return api_key, rate_limiter, session, owned_session


@dataclass
class DownloadStats:
    """Statistics for a download session."""
    keyword: str
    total_found: int
    requested: int
    successful: int
    failed: int
    skipped: int
    unavailable: int
    errors: int
    duration_seconds: float
    output_dir: Path

    def __str__(self) -> str:
        return (
            f"\n{'='*60}\n"
            f"Download Summary\n"
            f"{'='*60}\n"
            f"Keyword:           {self.keyword}\n"
            f"Total found:       {self.total_found}\n"
            f"Requested:         {self.requested}\n"
            f"[OK] Successful:   {self.successful}\n"
            f"[FAIL] Failed:     {self.failed}\n"
            f"  - Unavailable:   {self.unavailable}\n"
            f"  - Errors:        {self.errors}\n"
            f"[SKIP] Skipped:    {self.skipped}\n"
            f"Duration:          {self.duration_seconds:.1f}s\n"
            f"Output directory:  {self.output_dir}\n"
            f"{'='*60}"
        )

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage.
        
        Counts both newly downloaded (successful) and previously downloaded
        (skipped) files as successful, since both result in available files.
        """
        if self.requested == 0:
            return 0.0
        return ((self.successful + self.skipped) / self.requested) * 100


def esearch_pmc(
    term: str,
    max_results: int,
    api_key: Optional[str],
    session: requests.Session,
    rate_limiter: RateLimiter,
    retries: int = MAX_RETRIES,
) -> Tuple[List[str], int]:
    """Search PMC directly for articles with full-text available.
    
    Strategy: Search PMC database directly instead of PubMed→PMC to ensure
    all results have full-text available.
    
    Args:
        term: Search query string
        max_results: Maximum PMC IDs to return
        api_key: NCBI API key
        retries: Number of retry attempts on failure
    
    Returns:
        Tuple of (pmcid_list, total_count) where total_count is the PMC
        result count for the query.
    """
    search_url = f"{EUTILS_BASE}/esearch.fcgi"
    logger.info("Searching PMC for full-text articles: %s (target: %d articles)", term, max_results)
    
    # Search PMC database directly - all results have full-text by definition
    search_params = {
        "db": "pmc",  # Search PMC directly, not PubMed
        "term": term,
        "retmax": max_results,
        "retmode": "json",
        "retstart": 0,
    }
    if api_key:
        search_params["api_key"] = api_key
    
    for attempt in range(retries):
        try:
            rate_limiter.wait()
            resp = session.get(search_url, params=search_params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            
            data = resp.json()
            result = data.get("esearchresult", {})
            pmcids = result.get("idlist", [])
            total_count = int(result.get("count", len(pmcids)))
            
            logger.info("Found %d PMC IDs (total PMC results: %d)", len(pmcids), total_count)
            return pmcids, total_count
            
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.warning("Search attempt %d/%d failed: %s", attempt + 1, retries, _redact_api_key(e))
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                logger.error("All search attempts failed for: %s", term)
                return [], 0
    
    return [], 0


def _eutils_request(
    endpoint: str,
    params: Dict[str, Any],
    api_key: Optional[str],
    session: requests.Session,
    rate_limiter: RateLimiter,
    retries: int = MAX_RETRIES,
    post: bool = False,
) -> requests.Response:
    """Call an E-utilities endpoint (e.g. ``'elink.fcgi'``), retrying on failure.

    With *post*, parameters go in the request body (for long ID lists).

    Raises:
        requests.RequestException: all attempts failed.  The message has the
            API key redacted.
    """
    params = dict(params)
    if api_key:
        params["api_key"] = api_key
    url = f"{EUTILS_BASE}/{endpoint}"

    error = None
    for attempt in range(retries):
        try:
            rate_limiter.wait()
            if post:
                resp = session.post(url, data=params, timeout=REQUEST_TIMEOUT)
            else:
                resp = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            error = _redact_api_key(e)
            logger.warning("%s attempt %d/%d failed: %s", endpoint, attempt + 1, retries, error)
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))

    if error is None:
        raise ValueError("retries must be at least 1")
    # Raised outside the except block so the original exception, whose
    # message contains the API key, is not chained as __context__
    raise requests.RequestException(f"{endpoint} failed: {error}")


def esummary_pmc(
    pmcids: List[str],
    api_key: Optional[str],
    session: requests.Session,
    rate_limiter: RateLimiter,
    retries: int = MAX_RETRIES,
) -> List[Dict[str, Optional[str]]]:
    """Titles, journals, years and identifiers of PMC articles, without downloading them.

    Accepts PMC IDs with or without the ``PMC`` prefix.  Returns one dict per
    article found, in the order given, with ``pmcid``, ``pmid``, ``doi``,
    ``year``, ``journal``, ``title`` and ``first_author``.

    Raises:
        requests.RequestException: NCBI did not answer after all retries.
    """
    ids = [re.sub(r"^PMC", "", str(i).strip(), flags=re.I) for i in pmcids]
    if not ids:
        return []
    params = {"db": "pmc", "id": ",".join(ids), "retmode": "json"}
    for attempt in range(retries):
        resp = _eutils_request("esummary.fcgi", params, api_key, session, rate_limiter, post=len(ids) > 200)
        try:
            result = resp.json()["result"]
            break
        except (ValueError, KeyError):
            # NCBI answers a burst of requests with HTTP 200 and an error message
            logger.warning("esummary.fcgi attempt %d/%d returned no result", attempt + 1, retries)
            if attempt == retries - 1:
                raise requests.RequestException("esummary.fcgi failed: no result in the response")
            time.sleep(RETRY_DELAY * (attempt + 1))

    articles = []
    for uid in ids:
        record = result.get(uid)
        if not record or "error" in record:
            continue
        idmap = {a.get("idtype"): a.get("value") for a in record.get("articleids", [])}
        date = record.get("pubdate") or record.get("epubdate") or ""
        authors = record.get("authors") or []
        articles.append({
            "pmcid": f"PMC{uid}",
            "pmid": idmap.get("pmid") if idmap.get("pmid") not in (None, "", "0") else None,
            "doi": idmap.get("doi") or None,
            "year": date[:4] if date[:4].isdigit() else None,
            "journal": record.get("fulljournalname") or record.get("source") or None,
            "title": " ".join((record.get("title") or "").split()) or None,
            "first_author": authors[0].get("name") if authors else None,
        })
    return articles


def strip_xml_tags(xml_text: str) -> str:
    """Very simple XML/HTML tag stripper for plain-text export."""

    # Remove tags
    text = re.sub(r"<[^>]+>", " ", xml_text)
    # Decode entities (&lt;, &amp;, &#x003b1;, ...)
    text = html.unescape(text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# JATS elements that start a new line in extracted plain text
_TEXT_BLOCK_TAGS = {
    "title", "p", "sec", "abstract", "caption", "fig", "table-wrap", "tr",
    "list-item", "def-item", "disp-formula", "disp-quote", "boxed-text",
}
# Table cells are separated by spaces
_TEXT_CELL_TAGS = {"td", "th"}
# LaTeX formula sources (full \documentclass preambles in PMC) are noise
_TEXT_SKIP_TAGS = {"tex-math"}


def _append_element_text(el: ET.Element, parts: List[str]) -> None:
    if el.tag in _TEXT_SKIP_TAGS:
        return
    if el.tag in _TEXT_BLOCK_TAGS:
        sep = "\n"
    elif el.tag in _TEXT_CELL_TAGS:
        sep = " "
    else:
        sep = ""
    parts.append(sep)
    # "\n" marks structure only, so whitespace inside the source text is flattened
    if el.text:
        parts.append(re.sub(r"\s+", " ", el.text))
    for child in el:
        _append_element_text(child, parts)
        if child.tail:
            parts.append(re.sub(r"\s+", " ", child.tail))
    parts.append(sep)


def extract_text_from_pmc_xml(xml_text: str) -> str:
    """Extract readable plain text (title, abstracts, body) from PMC XML.

    Journal/article identifiers, references and other back matter are left
    out, entities are decoded, and each title, paragraph, caption and table
    row is put on its own line.  Falls back to :func:`strip_xml_tags` if the
    XML cannot be parsed as a PMC article.
    """

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return strip_xml_tags(xml_text)

    article = root.find("article") if root.tag != "article" else root
    if article is None:
        return strip_xml_tags(xml_text)

    parts: List[str] = []
    for el in (
        article.findall("front/article-meta/title-group/article-title")
        + article.findall("front/article-meta/abstract")
        + article.findall("body")
        + article.findall("floats-group")
    ):
        parts.append("\n")
        _append_element_text(el, parts)

    lines = (re.sub(r" +", " ", line).strip() for line in "".join(parts).split("\n"))
    return "\n".join(line for line in lines if line)


def _find_first(parent: ET.Element, paths: Tuple[str, ...]) -> Optional[ET.Element]:
    """Return the first element matched by *paths*, tried in order."""
    for path in paths:
        el = parent.find(path)
        if el is not None:
            return el
    return None


def extract_metadata_from_pmc_xml(xml_text: str) -> Dict[str, Any]:
    """Extract basic metadata (title, journal, authors, IDs, dates) from PMC XML.

    This is intentionally conservative and resilient; if parsing fails, the
    function returns an empty dictionary and the caller can still use the raw
    XML and plain text representations.
    """

    metadata: Dict[str, Any] = {}

    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return metadata

    # Locate core elements
    article = root.find("article") if root.tag != "article" else root
    if article is None:
        return metadata

    front = article.find("front")
    if front is None:
        return metadata

    journal_meta = front.find("journal-meta")
    article_meta = front.find("article-meta")

    # Journal information
    journal_title = None
    journal_nlm_ta = None
    journal_iso_abbrev = None

    if journal_meta is not None:
        jt_group = journal_meta.find("journal-title-group")
        if jt_group is not None:
            jt = jt_group.find("journal-title")
            if jt is not None:
                journal_title = "".join(jt.itertext()).strip()

        for jid in journal_meta.findall("journal-id"):
            jid_type = jid.get("journal-id-type", "")
            value = (jid.text or "").strip()
            if jid_type == "nlm-ta":
                journal_nlm_ta = value
            elif jid_type == "iso-abbrev":
                journal_iso_abbrev = value

    # Store detailed journal fields and a generic alias used by other tooling
    if journal_title:
        metadata["journal_title"] = journal_title
    if journal_nlm_ta:
        metadata["journal_nlm_ta"] = journal_nlm_ta
    if journal_iso_abbrev:
        metadata["journal_iso_abbrev"] = journal_iso_abbrev

    # Provide a generic "journal" key for compatibility with external tools
    if journal_title:
        metadata["journal"] = journal_title
    elif journal_iso_abbrev:
        metadata["journal"] = journal_iso_abbrev
    elif journal_nlm_ta:
        metadata["journal"] = journal_nlm_ta

    if article_meta is None:
        return metadata

    # Article identifiers
    for aid in article_meta.findall("article-id"):
        id_type = aid.get("pub-id-type", "")
        value = (aid.text or "").strip()
        if id_type == "pmid":
            metadata["pmid"] = value
        elif id_type == "pmcid":
            metadata["pmcid"] = value
        elif id_type == "doi":
            metadata["doi"] = value
    if metadata.get("pmid"):
        metadata["linked_discoveries_url"] = linked_discoveries_url(metadata["pmid"])

    # Title
    title_group = article_meta.find("title-group")
    if title_group is not None:
        at = title_group.find("article-title")
        if at is not None:
            metadata["title"] = "".join(at.itertext()).strip()

    # Publication dates
    # Prefer the electronic publication date (JATS 1.0 pub-type or JATS 1.1+
    # date-type), then print dates, and fall back to the collection year
    pub_date = _find_first(article_meta, (
        "pub-date[@pub-type='epub']",
        "pub-date[@date-type='pub'][@publication-format='electronic']",
        "pub-date[@pub-type='epub-ppub']",
        "pub-date[@pub-type='ppub']",
        "pub-date[@date-type='pub']",
    ))
    pub_year = None
    pub_month = None
    pub_day = None
    if pub_date is not None:
        year_el = pub_date.find("year")
        month_el = pub_date.find("month")
        day_el = pub_date.find("day")
        if year_el is not None:
            pub_year = (year_el.text or "").strip()
        if month_el is not None:
            pub_month = (month_el.text or "").strip()
        if day_el is not None:
            pub_day = (day_el.text or "").strip()
    else:
        coll_date = _find_first(article_meta, (
            "pub-date[@pub-type='collection']",
            "pub-date[@date-type='collection']",
        ))
        if coll_date is not None:
            year_el = coll_date.find("year")
            if year_el is not None:
                pub_year = (year_el.text or "").strip()

    # Store both flat year/month/day (for this project) and a nested
    # pub_date.year structure compatible with external utilities
    if pub_year is not None:
        metadata["year"] = pub_year
    if pub_month is not None:
        metadata["month"] = pub_month
    if pub_day is not None:
        metadata["day"] = pub_day

    if pub_year is not None:
        metadata["pub_date"] = {"year": pub_year}
        if pub_month is not None:
            metadata["pub_date"]["month"] = pub_month
        if pub_day is not None:
            metadata["pub_date"]["day"] = pub_day

    # Authors (simple list of display names)
    authors: List[str] = []
    for contrib in article_meta.findall("contrib-group/contrib"):
        if contrib.get("contrib-type") != "author":
            continue
        name_el = contrib.find("name")
        if name_el is None:
            continue
        surname = (name_el.findtext("surname") or "").strip()
        given = (name_el.findtext("given-names") or "").strip()
        initials = (name_el.get("initials") or "").strip()
        if given:
            full = f"{surname} {given}".strip()
        elif initials:
            full = f"{surname} {initials}".strip()
        else:
            full = surname
        if full:
            authors.append(full)
    if authors:
        metadata["authors"] = authors

    # Abstract (concatenate all abstract sections)
    abstract_el = article_meta.find("abstract")
    if abstract_el is not None:
        metadata["abstract"] = " ".join(list(abstract_el.itertext())).strip()

    # Keywords / MeSH (if present)
    keywords: List[str] = []
    for kwd in article_meta.findall("kwd-group/kwd"):
        text = "".join(kwd.itertext()).strip()
        if text:
            keywords.append(text)
    if keywords:
        metadata["keywords"] = keywords

    references = _extract_references(article)
    if references:
        metadata["references"] = references

    return metadata


def _extract_references(article: ET.Element) -> List[Dict[str, str]]:
    """Return the cited works in *article*'s reference list that carry a PMID or DOI.

    Each entry has ``pmid`` and/or ``doi``, plus ``title`` and ``year`` when
    the citation is structured.  A ``<citation-alternatives>`` element can
    repeat a citation, so each ID is taken once per ``<ref>``.
    """
    references: List[Dict[str, str]] = []
    back = article.find("back")
    if back is None:
        return references
    for ref in back.iter("ref"):
        entry: Dict[str, str] = {}
        for pub_id in ref.iter("pub-id"):
            id_type = pub_id.get("pub-id-type", "")
            value = "".join(pub_id.itertext()).strip()
            if id_type in ("pmid", "doi") and value and id_type not in entry:
                entry[id_type] = value
        if not entry:
            continue
        title_el = next(ref.iter("article-title"), None)
        if title_el is not None:
            title = " ".join("".join(title_el.itertext()).split())
            if title:
                entry["title"] = title
        year_el = next(ref.iter("year"), None)
        if year_el is not None and (year_el.text or "").strip():
            entry["year"] = year_el.text.strip()
        references.append(entry)
    return references


def efetch_pmc(
    pmcid: str,
    out_dir: Path,
    fmt: str,
    api_key: Optional[str],
    session: requests.Session,
    rate_limiter: RateLimiter,
    retries: int = MAX_RETRIES,
    include_text: bool = True,
) -> Tuple[bool, str]:
    """Fetch a single PMC article and save it in the requested format.

    Args:
        pmcid: Numeric PMC database ID (as returned by esearch on db=pmc).
               Do NOT include 'PMC' prefix - use raw ID like '12345678'.
        out_dir: Base directory where files are written.
        fmt: 'xml', 'text', 'both', or legacy 'json'/'txt'.
             'text' (default): JSON with metadata and 'text' field (plain text)
             'xml': JSON with metadata and 'xml' field (raw XML string)
             'both': JSON with metadata and both 'xml' and 'text' fields
        api_key: NCBI API key.
        retries: Number of retry attempts on failure.
        include_text: For JSON format, whether to include the 'text' field
                     (stripped XML). Default True for VS Code search compatibility.

    Returns:
        Tuple of (success: bool, status: str) where status is one of:
        'success', 'unavailable', 'error', 'exists'
    """
    # Use raw numeric ID for efetch (db=pmc expects internal IDs, not PMCIDs)
    pmcid_numeric = str(pmcid).replace("PMC", "") if str(pmcid).startswith("PMC") else str(pmcid)
    
    # Format with PMC prefix for filenames and display only
    pmcid_display = f"PMC{pmcid_numeric}" if not pmcid_numeric.startswith("PMC") else pmcid_numeric

    # Normalize format aliases: 'json' -> 'text', 'txt' -> 'text'
    if fmt == "json" or fmt == "txt":
        fmt = "text"

    # Check if file already exists (all formats save as .json now)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{pmcid_display}.json"
    
    if json_path.exists():
        logger.debug("%s already exists, skipping", json_path.name)
        return True, "exists"

    params = {
        "db": "pmc",
        "id": pmcid_numeric,  # Use raw numeric ID for efetch
        "rettype": "full",
        "retmode": "xml",
    }
    if api_key:
        params["api_key"] = api_key

    url = f"{EUTILS_BASE}/efetch.fcgi"
    
    for attempt in range(retries):
        try:
            logger.debug("Downloading %s (attempt %d/%d)", pmcid_display, attempt + 1, retries)
            rate_limiter.wait()
            resp = session.get(url, params=params, timeout=REQUEST_TIMEOUT)

            if resp.status_code != 200:
                if resp.status_code == 429:
                    if attempt < retries - 1:
                        logger.info("Rate limited (429) for %s, retrying in %ds...", pmcid_display, RETRY_DELAY)
                    else:
                        logger.warning("Rate limit exceeded for %s after %d attempts", pmcid_display, retries)
                else:
                    logger.warning("HTTP %s error for %s%s", resp.status_code, pmcid_display, 
                                   ", retrying..." if attempt < retries - 1 else " (max retries reached)")
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                return False, "error"

            # Detect error responses where the requested PMCID is not available
            try:
                root = ET.fromstring(resp.text)
                # When a PMCID is unavailable, PMC returns <pmc-articleset><error ...>
                if root.tag == "pmc-articleset":
                    error_el = root.find("error")
                    if error_el is not None:
                        logger.info(
                            "%s not available in PMC: %s",
                            pmcid_display,
                            (error_el.text or "").strip(),
                        )
                        return False, "unavailable"
            except ET.ParseError:
                # If parsing fails, the XML might be malformed
                logger.warning("%s returned malformed XML", pmcid_display)
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                return False, "error"

            # Publishers can withhold the XML full text; PMC then returns the
            # front matter only (no <body>), which is not a full-text article
            article = root.find("article") if root.tag != "article" else root
            if article is None or article.find("body") is None:
                logger.info(
                    "%s has no full text in PMC XML (publisher restriction or PDF-only)",
                    pmcid_display,
                )
                return False, "unavailable"

            # Save the article (all formats save as .json)
            # Extract metadata once
            metadata = extract_metadata_from_pmc_xml(resp.text)
            
            # Validate metadata has at least title or pmcid
            if not metadata.get("title") and not metadata.get("pmcid"):
                logger.warning("%s: extracted metadata is empty or invalid", pmcid_display)
            
            # Build payload based on format
            payload = {
                "pmcid": pmcid_display,
                "source": "PMC",
                "download_date": datetime.now().isoformat(),
                "metadata": metadata,
            }
            
            if fmt == "xml":
                # Include raw XML string
                payload["xml"] = resp.text
            elif fmt == "text":
                # Include plain-text version (optionally)
                if include_text:
                    payload["text"] = extract_text_from_pmc_xml(resp.text)
            elif fmt == "both":
                # Include both XML and text
                payload["xml"] = resp.text
                if include_text:
                    payload["text"] = extract_text_from_pmc_xml(resp.text)
            
            # Save as JSON
            json_path = out_dir / f"{pmcid_display}.json"
            json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("[OK] Saved %s", json_path.name)
            
            return True, "success"
            
        except requests.RequestException as e:
            logger.warning("Download attempt %d/%d failed for %s: %s", attempt + 1, retries, pmcid_display,
                           _redact_api_key(e))
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                return False, "error"
        except (IOError, OSError) as e:
            logger.error("Failed to write %s: %s", json_path.name, e)
            return False, "error"
    
    return False, "error"


def _download_pmcids(
    pmcids: List[str],
    out_dir: Path,
    fmt: str,
    api_key: Optional[str],
    session: requests.Session,
    rate_limiter: RateLimiter,
    use_concurrent: bool,
    max_workers: int,
    include_text: bool,
) -> Tuple[int, int, int, int]:
    """Download *pmcids* into *out_dir*.

    Returns:
        Tuple of (successful, unavailable, errors, skipped) counts.
    """
    # Counters
    successful = 0
    unavailable = 0
    errors = 0
    skipped = 0

    if use_concurrent and len(pmcids) > 1:
        # Concurrent download with thread pool
        logger.info("Using concurrent downloads with %d workers", max_workers)
        
        def download_with_delay(pmcid: str) -> Tuple[str, bool, str]:
            """Download with rate limiting."""
            result = efetch_pmc(
                pmcid,
                out_dir,
                fmt=fmt,
                api_key=api_key,
                session=session,
                rate_limiter=rate_limiter,
                include_text=include_text,
            )
            return pmcid, result[0], result[1]
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(download_with_delay, pmcid): pmcid for pmcid in pmcids}
            
            for i, future in enumerate(as_completed(futures), start=1):
                try:
                    pmcid, success, status = future.result()
                    
                    if status == "success":
                        successful += 1
                    elif status == "exists":
                        skipped += 1
                    elif status == "unavailable":
                        unavailable += 1
                    else:  # error
                        errors += 1
                    
                    # Progress indicator
                    if i % 10 == 0 or i == len(pmcids):
                        print(f"Progress: {i}/{len(pmcids)} processed "
                              f"(OK:{successful} | FAIL:{unavailable + errors} | SKIP:{skipped})", 
                              end="\r")
                        
                except Exception as e:
                    pmcid = futures[future]
                    logger.error("Unexpected error downloading %s: %s", pmcid, e)
                    errors += 1
        
        print()  # New line after progress
    else:
        # Sequential download
        logger.info("Using sequential downloads")
        
        for i, pmcid in enumerate(pmcids, start=1):
            try:
                success, status = efetch_pmc(
                    pmcid,
                    out_dir,
                    fmt=fmt,
                    api_key=api_key,
                    session=session,
                    rate_limiter=rate_limiter,
                    include_text=include_text,
                )
                
                if status == "success":
                    successful += 1
                elif status == "exists":
                    skipped += 1
                elif status == "unavailable":
                    unavailable += 1
                else:  # error
                    errors += 1
                
                # Progress indicator
                if i % 5 == 0 or i == len(pmcids):
                    print(f"Progress: {i}/{len(pmcids)} processed", end="\r")
                
            except Exception as e:
                logger.error("Unexpected error downloading %s: %s", pmcid, e)
                errors += 1
        
        print()  # New line after progress

    return successful, unavailable, errors, skipped


QUERY_FILE = "query.json"


def slugify(text: str, default: str = "keyword", max_length: int = MAX_SLUG_LENGTH) -> str:
    """File-system-safe name for *text*, as used for download folders.

    A name longer than *max_length* is cut short and ends with a hash of the
    full text, so it stays unique and keeps paths within the 260 characters
    Windows allows by default.
    """
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip()).strip("_") or default
    if len(slug) > max_length:
        digest = hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:8]
        slug = f"{slug[:max_length - len(digest) - 1].rstrip('_.')}_{digest}"
    return slug


def _write_query_file(out_dir: Path, keyword: str) -> None:
    """Record the search query next to its articles, for tools like the vault builder."""
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        payload = {"query": keyword, "retrieved": datetime.now().isoformat(timespec="seconds")}
        (out_dir / QUERY_FILE).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning("Could not write %s: %s", out_dir / QUERY_FILE, e)


def search_and_download(
    keyword: str,
    max_results: int,
    fmt: str = "text",
    api_key: Optional[str] = None,
    use_concurrent: bool = True,
    max_workers: int = MAX_WORKERS,
    include_text: bool = True,
    output_dir: Optional[Path] = None,
    user_agent: Optional[str] = None,
    email: Optional[str] = None,
    rate_limit: Optional[float] = None,
    session: Optional[requests.Session] = None,
) -> DownloadStats:
    """Search PMC for *keyword* and download up to *max_results* articles.

    All articles are saved as JSON files: ``<output_dir>/<keyword_slug>/PMC*.json``

    Args:
        keyword: PubMed search query.
        max_results: Cap on the number of articles to fetch.
        fmt: Output format – ``'text'`` (default, JSON with metadata+text field), 
             ``'xml'`` (JSON with metadata+xml field), ``'both'`` (JSON with both xml and text fields), or 
             legacy ``'json'``/``'txt'`` (mapped to 'text').
        api_key: NCBI API key.  Falls back to ``NCBI_API_KEY`` env var.
        use_concurrent: Use a thread pool for downloads (default ``True``).
        max_workers: Thread pool size (default 5).
        include_text: Embed a plain-text copy in JSON output (default ``True``).
        output_dir: Base directory for downloads (default ``./publications``).
        user_agent: Custom ``User-Agent`` header.
        email: Contact e-mail sent to NCBI in the ``User-Agent`` header.
        rate_limit: Minimum seconds between HTTP requests. Auto-detected based on
                   API key presence: 0.1s with key (10 req/s), 0.34s without (3 req/s).
        session: Optional ``requests.Session`` to reuse across calls.

    Returns:
        A :class:`DownloadStats` instance with counts and timing.
    """
    start_time = time.time()

    api_key, rate_limiter, session, owned_session = _prepare_client(
        api_key, rate_limit, user_agent, email, session
    )

    output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        pmcids, total_found = esearch_pmc(
            keyword,
            max_results=max_results,
            api_key=api_key,
            session=session,
            rate_limiter=rate_limiter,
        )
    except Exception as e:
        logger.error("Search failed: %s", e)
        if owned_session:
            session.close()
        return DownloadStats(
            keyword=keyword,
            total_found=0,
            requested=0,
            successful=0,
            failed=0,
            skipped=0,
            unavailable=0,
            errors=0,
            duration_seconds=time.time() - start_time,
            output_dir=output_dir
        )

    if not pmcids:
        logger.warning("No PMC articles found for: %s", keyword)
        print(f"No results found for '{keyword}'")
        if owned_session:
            session.close()
        return DownloadStats(
            keyword=keyword,
            total_found=total_found,
            requested=0,
            successful=0,
            failed=0,
            skipped=0,
            unavailable=0,
            errors=0,
            duration_seconds=time.time() - start_time,
            output_dir=output_dir
        )

    # Create keyword-based output directory
    keyword_slug = slugify(keyword)
    out_dir = output_dir / keyword_slug
    _write_query_file(out_dir, keyword)

    print(
        f"\nFound {len(pmcids)} PMC IDs for '{keyword}' "
        f"(total PubMed results: {total_found})\n"
        f"Output directory: {out_dir}\n"
    )

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

    duration = time.time() - start_time
    stats = DownloadStats(
        keyword=keyword,
        total_found=total_found,
        requested=len(pmcids),
        successful=successful,
        failed=unavailable + errors,
        skipped=skipped,
        unavailable=unavailable,
        errors=errors,
        duration_seconds=duration,
        output_dir=out_dir
    )
    
    print(stats)
    
    if successful > 0:
        logger.info("Successfully downloaded %d articles to %s", successful, out_dir)
    if unavailable > 0:
        logger.warning("%d articles were not available in PMC full-text", unavailable)
    if errors > 0:
        logger.error("%d articles failed due to errors", errors)
    
    if owned_session:
        session.close()
    return stats




@dataclass
class SearchResult:
    """The size of a PMC search and its newest matches, without downloading them."""
    query: str
    total_found: int
    articles: List[Dict[str, Optional[str]]]

    def __str__(self) -> str:
        lines = [f"{self.total_found:,} articles in PMC for: {self.query}"]
        if self.articles:
            lines.append(f"Newest {len(self.articles)}:")
        for a in self.articles:
            pmid = f"PMID {a['pmid']}" if a["pmid"] else "no PMID"
            journal = f" ({a['journal']})" if a["journal"] else ""
            lines.append(f"  {a['year'] or 'n.d.'}  {a['pmcid']:<12} {pmid:<14} {a['title'] or ''}{journal}")
        return "\n".join(lines)


def search_pmc(
    query: str,
    max_results: int = 10,
    api_key: Optional[str] = None,
    user_agent: Optional[str] = None,
    email: Optional[str] = None,
    rate_limit: Optional[float] = None,
    session: Optional[requests.Session] = None,
) -> SearchResult:
    """Count a PMC search and list its newest *max_results* matches, without downloading.

    Use it to check a search's size and precision before ``search_and_download``.

    Raises:
        requests.RequestException: NCBI did not answer the summary request.
    """
    api_key, rate_limiter, session, owned_session = _prepare_client(api_key, rate_limit, user_agent, email, session)
    try:
        pmcids, total_found = esearch_pmc(query, max_results, api_key, session, rate_limiter)
        articles = esummary_pmc(pmcids, api_key, session, rate_limiter) if pmcids else []
    finally:
        if owned_session:
            session.close()
    return SearchResult(query=query, total_found=total_found, articles=articles)
