"""Measure how a paper spread through the literature: tutorial 8's helpers.

pubmed-stream's neighborhood gives a paper's citing articles (the first hop).
These helpers go further:

- ``citers_of(pmids)`` asks PubMed which articles cite each of many papers at
  once: the citing papers' own citers are the second hop.
- ``count_by_year(pmids)`` and ``count_flags(pmids)`` count tens of thousands
  of articles by year, or as reviews, retracted or NIH-funded, without
  downloading their records.
- ``corrections(pmid)`` lists the retraction notice, errata and comments
  PubMed links to a paper.
- ``citation_contexts(folder, pmid, doi)`` finds the sentences in which each
  downloaded full-text article cites the paper, and ``classify(sentences)``
  sorts them: the citation discusses the paper's retraction or doubts about
  it, names its specific finding, or cites it in general.

The contexts are read from the article XML that PubMed Central publishes, so
download with ``fmt="xml"``.  Classification is by keywords: read a sample of
sentences before you trust the counts.
"""

import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Pattern, Tuple

import requests

from pubmed_stream.downloader import _eutils_request, _prepare_client

CITE = "⟦CITE⟧"   # marks the citation inside a sentence
BATCH = 100                 # papers per ELink request
POST_BATCH = 10000          # PMIDs per EPost request; a search may name at most about 20,000

# Keyword rules, checked in this order; the first that matches a sentence wins
# Words about a paper's integrity or reproducibility.  "Retraction" of dendritic spines and
# "manipulation" of a protein are biology, so those words count only in a publishing sense.
DOUBT = re.compile(r"(?<!spine )(?<!spines )(?<!neurite )(?<!axon )(?<!axonal )(?<!process )\bretract(?:ed|ion)\b|"
                   r"(?:data|image|images|figure|figures|blot|blots)\W+(?:\w+\W+){0,4}manipulat|"
                   r"manipulat\w*\W+(?:\w+\W+){0,4}(?:data|image|images|figure|figures|blot|blots)\b|"
                   r"falsified|fabricat|misconduct|expression of concern|editor(?:'s|ial)? (?:note|notice)|"
                   r"concerns? (?:about|over|regarding|have been raised)|(?:research|scientific|data) integrity|whistleblow|Piller|"
                   r"could not (?:be )?(?:detect|reproduc|replicat|confirm)|"
                   r"(?:fail|unable)(?:ed|ure)? to (?:detect|reproduc|replicat|confirm)|"
                   r"not (?:been )?(?:reproduc|replicat)|irreproduc|(?:serious|major) errors?|sleuth|"
                   r"post-publication (?:peer )?review|self-correct|alleg(?:ed|ations?)\b|scrutini[sz]ed|"
                   r"(?:image|images|data|figure|figures) (?:alteration|irregularit|anomal)", re.I)
# Softer words that may, or may not, question the paper: citations sorted as general or naming the
# finding whose sentence has one of them are worth a second look by a person
REVIEW = re.compile(r"controvers|debat|disput|questionab|questioned|in question|unclear|uncertain|conflicting|"
                    r"inconsisten|discrepan|challeng|caution|skeptic|sceptic|reproducib|"
                    r"not (?:been )?(?:confirmed|observed|detected)", re.I)
# Publishers set the asterisk of Aβ*56 in several characters: ∗ (U+2217), ＊, ⁎ and ✱ all become *
ASTERISKS = str.maketrans({"∗": "*", "＊": "*", "⁎": "*", "✱": "*"})
# Aβ*56, the oligomer the retracted paper reported, as authors write it: Aβ*56, Abeta*56, Aβ56, 56-kDa
SPECIFIC = re.compile(r"A\s?(?:β|beta|-beta|ß|b)\s?\*\s?56|A(?:β|beta|ß)[\s-]?56\b|\b56[ -]?kDa", re.I)
KINDS = ["Discusses the retraction or doubts", "Names Aβ*56", "Cites it in general", "No full text, or citation not found"]


def _client():
    api_key, rate_limiter, session, _ = _prepare_client(None, None, None, None, None)
    return api_key, session, rate_limiter


def citers_of(pmids: Iterable[str]) -> Dict[str, List[str]]:
    """The PubMed IDs of the articles citing each paper in *pmids*."""
    pmids, client = list(pmids), _client()
    citers: Dict[str, List[str]] = {p: [] for p in pmids}
    for start in range(0, len(pmids), BATCH):
        _citers_batch(pmids[start:start + BATCH], citers, client)
    return citers


def _citers_batch(batch: List[str], citers: Dict[str, List[str]], client) -> None:
    """One ELink request; when NCBI keeps failing on it, wait and try each half separately."""
    try:
        resp = _eutils_request("elink.fcgi", {"dbfrom": "pubmed", "db": "pubmed", "retmode": "json",
                                              "linkname": "pubmed_pubmed_citedin", "id": batch},
                               *client, post=True)
    except requests.RequestException:
        if len(batch) == 1:
            raise
        time.sleep(5)
        half = len(batch) // 2
        _citers_batch(batch[:half], citers, client)
        _citers_batch(batch[half:], citers, client)
        return
    for linkset in resp.json().get("linksets", []):
        citers[str(linkset["ids"][0])] = [str(i) for db in linkset.get("linksetdbs", [])
                                           for i in db.get("links", [])]


def corrections(pmid: str) -> List[Dict[str, str]]:
    """The notices PubMed links to *pmid*: retraction, errata, comments, with their PubMed IDs."""
    key, session, limiter = _client()
    root = ET.fromstring(_eutils_request("efetch.fcgi", {"db": "pubmed", "id": pmid, "retmode": "xml"},
                                         key, session, limiter).text)
    return [{"type": " ".join(re.findall(r"[A-Z][a-z]+", c.get("RefType", ""))), "pmid": c.findtext("PMID") or "",
             "source": c.findtext("RefSource") or ""} for c in root.iter("CommentsCorrections")]


def _post(pmids: List[str], key, session, limiter) -> Tuple[str, List[str]]:
    """Upload *pmids* to PubMed's history server, in batches; returns its session and one key per batch."""
    webenv, keys = None, []
    for start in range(0, len(pmids), POST_BATCH):
        params = {"db": "pubmed", "id": ",".join(pmids[start:start + POST_BATCH])}
        if webenv:
            params["WebEnv"] = webenv
        root = ET.fromstring(_eutils_request("epost.fcgi", params, key, session, limiter, post=True).text)
        webenv = root.findtext("WebEnv")
        keys.append(f"#{root.findtext('QueryKey')}")
    return webenv, keys


def _counts(pmids: Iterable[str], filters: Dict[str, str]) -> Dict[str, int]:
    pmids, (key, session, limiter) = sorted(set(pmids)), _client()
    if not pmids:
        return {name: 0 for name in filters}
    # PubMed expands "#1 OR #2" into the IDs themselves, which overflows its query limit,
    # so each batch is counted on its own; batches never share an ID, so the counts add up
    webenv, batches = _post(pmids, key, session, limiter)
    counts = dict.fromkeys(filters, 0)
    for name, search in filters.items():
        for batch in batches:
            for attempt in range(4):
                resp = _eutils_request("esearch.fcgi", {"db": "pubmed", "term": f"{batch} AND {search}",
                                                        "WebEnv": webenv, "usehistory": "y", "retmax": 0,
                                                        "retmode": "json"}, key, session, limiter)
                result = resp.json()["esearchresult"]
                if "count" in result or attempt == 3:
                    break
                time.sleep(2 ** attempt)   # PubMed's search backend sometimes fails for a moment
            if "count" not in result or result.get("errorlist", {}).get("phrasesnotfound"):
                raise ValueError(f"PubMed could not count {search!r}: {result}")
            counts[name] += int(result["count"])
    return counts


def count_by_year(pmids: Iterable[str], first: int, last: int) -> Dict[int, int]:
    """How many of *pmids* PubMed dates to each year from *first* to *last*."""
    counts = _counts(pmids, {str(y): f"{y}[dp]" for y in range(first, last + 1)})
    return {int(y): n for y, n in counts.items()}


def count_flags(pmids: Iterable[str]) -> Dict[str, int]:
    """How many of *pmids* are reviews, retracted, NIH-funded, or in PubMed Central."""
    pmids = list(set(pmids))
    counts = _counts(pmids, {
        "reviews": '(review[pt:noexp] OR "systematic review"[pt:noexp] OR "scoping review"[pt:noexp])',
        "retracted": "retracted publication[pt]",
        "nih_funded": '(nih[gr] OR "research support, n.i.h., extramural"[pt] OR '
                      '"research support, n.i.h., intramural"[pt])',
        "in_pmc": "pubmed pmc[sb]",
    })
    return {"articles": len(pmids), **counts}


def _text(el: ET.Element, targets: set, ranges: set, out: List[str]) -> None:
    """The text of *el*, with CITE where it cites one of *targets* (ref IDs) or starts one of *ranges*."""
    if el.tag == "xref" and el.get("ref-type") == "bibr":
        cites = el in ranges or targets & set((el.get("rid") or "").split())
        out.append(CITE if cites else (el.text or ""))
    elif el.tag in ("table-wrap", "fig", "disp-formula"):
        pass
    else:
        out.append(el.text or "")
        for child in el:
            _text(child, targets, ranges, out)
    if el.tail:
        out.append(el.tail)


def _ranges(body: ET.Element, order: List[str], targets: set) -> set:
    """Citations of a range, such as [10-14], that includes one of *targets*: returns the range's first xref.

    Only the two ends of a range are tagged in the XML, so the paper inside it
    is cited there although its ID appears nowhere.
    """
    index = {rid: i for i, rid in enumerate(order)}
    inside = [index[t] for t in targets if t in index]
    found = set()
    for parent in body.iter():
        kids = list(parent)
        for a, b in zip(kids, kids[1:]):
            if (a.tag == b.tag == "xref" and re.fullmatch(r"\s*[-–—]\s*", a.tail or "")
                    and a.get("rid") in index and b.get("rid") in index
                    and any(index[a.get("rid")] < i < index[b.get("rid")] for i in inside)):
                found.add(a)
    return found


def _sentences(paragraph: str) -> List[str]:
    paragraph = " ".join(paragraph.translate(ASTERISKS).split())
    # A sentence ends at . ! or ?, after any citation numbers set as superscripts ("memory.12,13 The")
    end = re.compile(r"[.!?](?:(?:\d+|" + CITE + r")(?:\s?[,–\-]\s?(?:\d+|" + CITE + r"))*)?\s+(?=[A-Z\[(])")
    parts = end.sub(lambda m: m.group(0).rstrip() + "\0", paragraph).split("\0")
    return [p.strip() for p in parts if CITE in p]


def citation_contexts(folder, pmid: str, doi: Optional[str] = None, title_words: str = "",
                      finding: Pattern = SPECIFIC) -> Dict[str, dict]:
    """The sentences in which each downloaded article cites the paper *pmid*.

    Reads every ``PMC*.json`` under *folder* that holds PMC XML.  The paper is
    found in each reference list by its PubMed ID, its DOI, or the words
    *title_words* in the reference.  Returns, per PMC ID::

        {"pmid", "year", "title", "found": bool, "sentences": [...], "mentions": int}

    where ``mentions`` counts matches of *finding* (default: Aβ*56) anywhere
    in the article's text.
    """
    results = {}
    title_words = title_words.lower()
    for path in sorted(Path(folder).rglob("PMC*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        meta, xml = data.get("metadata") or {}, data.get("xml")
        if not xml:
            continue
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            continue
        refs = root.findall(".//ref-list//ref") or root.findall(".//ref")
        targets = set()
        for ref in refs:
            ids = {(p.get("pub-id-type"), (p.text or "").strip().lower()) for p in ref.iter("pub-id")}
            text = " ".join("".join(ref.itertext()).split()).lower()
            if (("pmid", pmid) in ids or (doi and ("doi", doi.lower()) in ids) or (doi and doi.lower() in text)
                    or (title_words and title_words in text)):
                targets.add(ref.get("id"))
        body = root.find(".//body")
        sentences: List[str] = []
        if targets and body is not None:
            ranges = _ranges(body, [r.get("id") for r in refs], targets)
            for p in body.iter("p"):
                if p.find(".//p") is not None:
                    continue  # read the innermost paragraphs only
                out: List[str] = []
                _text(p, targets, ranges, out)
                sentences += _sentences("".join(out))
        full = " ".join(body.itertext()).translate(ASTERISKS) if body is not None else ""
        results[data.get("pmcid") or path.stem] = {
            "pmid": meta.get("pmid"), "year": meta.get("year"), "title": meta.get("title"),
            "found": bool(targets), "sentences": sentences, "mentions": len(finding.findall(full)),
        }
    return results


def classify(sentences: List[str], finding: Pattern = SPECIFIC) -> str:
    """One of KINDS for an article, from the sentences in which it cites the paper.

    *finding* matches the paper's specific claim; the default matches Aβ*56.
    """
    if not sentences:
        return KINDS[3]
    sentences = [s.translate(ASTERISKS) for s in sentences]
    if any(DOUBT.search(s) for s in sentences):
        return KINDS[0]
    if any(finding.search(s) for s in sentences):
        return KINDS[1]
    return KINDS[2]


def worth_a_look(sentences: List[str], kind: str) -> bool:
    """True for a citation sorted as general or naming the finding whose sentence has a softer doubt word."""
    return kind in (KINDS[1], KINDS[2]) and any(REVIEW.search(s) for s in sentences)


def annotate(kg_dir, properties: Dict[str, Dict[str, object]]) -> int:
    """Add properties to paper notes of a knowledge graph, by PubMed ID; returns the notes changed.

    The properties are not pubmed-stream's own, so rebuilding the graph keeps them.
    """
    from pubmed_stream.vault import _merge_frontmatter, _split_frontmatter

    changed = 0
    for pmid, props in properties.items():
        path = Path(kg_dir) / "papers" / f"PMID{pmid}.md"
        if not path.is_file():
            continue
        old = path.read_text(encoding="utf-8")
        frontmatter, body = _split_frontmatter(old)
        new = f"---\n{_merge_frontmatter(frontmatter, props, props.keys())}\n---\n{body}"
        if new != old:
            path.write_text(new, encoding="utf-8", newline="\n")
            changed += 1
    return changed


def _view(name: str, *conditions: str) -> str:
    rules = "".join(f"        - '{c}'" + chr(10) for c in conditions)
    return f"""  - type: table
    name: {name}
    filters:
      and:
{rules}    order:
      - file.name
      - title
      - year
      - citation_sentence
    sort:
      - property: year
        direction: DESC
"""


def write_base(kg_dir, name: str = "Citation impact") -> Path:
    """An Obsidian Bases table of the citing papers, one view per kind of citation."""
    views = "".join(_view(kind, f'citation_kind == "{kind}"') for kind in KINDS[:3])
    views += _view("Retracted citing papers", "hop == 1", "retracted == true")
    text = ("filters:\n  and:\n    - file.inFolder(\"papers\")\nproperties:\n  file.name:\n    displayName: Paper\n"
            "  note.citation_sentence:\n"
            "    displayName: How it cites the paper\n  note.title:\n    displayName: Title\n"
            "  note.year:\n    displayName: Year\nviews:\n" + views)
    path = Path(kg_dir) / f"{name}.base"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def count_matching(pmids: Iterable[str], searches: Dict[str, str]) -> Dict[str, int]:
    """How many of *pmids* match each PubMed search, such as ``{"AD": "alzheimer disease[mh]"}``."""
    return _counts(pmids, searches)


def pubmed_count(search: str) -> int:
    """How many PubMed records a search finds."""
    key, session, limiter = _client()
    resp = _eutils_request("esearch.fcgi", {"db": "pubmed", "term": search, "retmax": 0, "retmode": "json"},
                           key, session, limiter)
    return int(resp.json()["esearchresult"]["count"])



S2_CITATIONS = "https://api.semanticscholar.org/graph/v1/paper/PMID:{pmid}/citations"


def semantic_scholar_contexts(pmid: str, api_key: Optional[str] = None) -> Dict[str, List[str]]:
    """The citing sentences Semantic Scholar has for the paper *pmid*, by the citing paper's PubMed ID.

    Semantic Scholar (https://www.semanticscholar.org) extracts citing
    sentences from many papers whose full text PubMed Central cannot give,
    so it fills in the papers ``citation_contexts`` cannot read.  Without an
    API key (``api_key`` or the ``S2_API_KEY`` environment variable) it
    answers slowly, so this waits and retries; an empty result means it could
    not be reached.
    """
    import os

    headers = {"x-api-key": api_key or os.environ.get("S2_API_KEY", "")}
    headers = {k: v for k, v in headers.items() if v}
    contexts: Dict[str, List[str]] = {}
    offset = 0
    while offset is not None:
        for attempt in range(8):
            try:
                resp = requests.get(S2_CITATIONS.format(pmid=pmid), headers=headers, timeout=60,
                                    params={"fields": "contexts,externalIds", "limit": 1000, "offset": offset})
            except requests.RequestException:
                resp = None
            if resp is not None and resp.status_code == 200:
                break
            time.sleep(min(5 * 2 ** attempt, 60))   # Semantic Scholar's shared rate limit
        else:
            return contexts
        page = resp.json()
        for row in page.get("data", []):
            citing = (row.get("citingPaper") or {}).get("externalIds") or {}
            if citing.get("PubMed") and row.get("contexts"):
                contexts[str(citing["PubMed"])] = [c.translate(ASTERISKS) for c in row["contexts"]]
        offset = page.get("next")
    return contexts
