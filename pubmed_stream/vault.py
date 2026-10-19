"""Obsidian knowledge-graph vault built from downloaded articles.

Turns the JSON files written by ``pubmed-stream download`` and
``pubmed-stream neighborhood`` into a folder of linked Markdown notes that
Obsidian opens as a vault::

    from pubmed_stream import build_vault

    stats = build_vault(["publications"], "vault")

The vault holds one note per paper (``papers/PMID<id>.md``), one per MeSH
concept (``concepts/``), one per search query or neighborhood
(``collections/``) and a ``PubMed Stream.md`` home note.  Papers link to the
papers they cite, cite them, or resemble them, and to their MeSH concepts, so
Obsidian's graph view shows the citation network and its topics.

Rebuilding is safe: each note keeps generated content between two
``%% pubmed-stream %%`` markers and rewrites only that block and the
frontmatter keys it owns.  Text written outside the block, and frontmatter
keys or tags added in Obsidian, survive.  The vault remembers its sources in
``.pubmed-stream/sources.json``, so later builds from new downloads keep the
papers of earlier ones.

MeSH terms and publication types come from PubMed, which is queried once per
200 papers and cached in ``.pubmed-stream/pubmed_records.json``.  Pass
``offline=True`` to use only the cache.
"""

import json
import logging
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

import requests

from .downloader import (
    QUERY_FILE,
    _prepare_client,
    extract_metadata_from_pmc_xml,
    extract_text_from_pmc_xml,
    slugify,
)
from .neighborhood import _efetch_pubmed

logger = logging.getLogger(__name__)

VAULT_PREFIX = "kg_"
STATE_DIR = ".pubmed-stream"
SOURCES_FILE = "sources.json"
CACHE_FILE = "pubmed_records.json"
PAPERS_DIR = "papers"
CONCEPTS_DIR = "concepts"
COLLECTIONS_DIR = "collections"
HOME_NOTE = "PubMed Stream"
PAPERS_BASE = "Papers.base"

# Obsidian property types for the keys the notes use, written to
# .obsidian/types.json for keys the vault has no type for yet
PROPERTY_TYPES = {
    "year": "number", "retracted": "checkbox", "authors": "multitext", "publication_types": "multitext",
    "mesh": "multitext", "keywords": "multitext", "pmid": "text", "pmcid": "text", "doi": "text",
    "journal": "text", "status": "text", "url": "text", "papers": "multitext",
}

# An Obsidian Bases table of the papers, written once; the user may edit it
PAPERS_BASE_TEXT = """filters:
  and:
    - file.inFolder("papers")
properties:
  file.name:
    displayName: Note
  note.title:
    displayName: Title
  note.year:
    displayName: Year
  note.journal:
    displayName: Journal
  note.status:
    displayName: Status
  note.publication_types:
    displayName: Publication type
views:
  - type: table
    name: All papers
    order:
      - file.name
      - title
      - year
      - journal
      - status
      - publication_types
    sort:
      - property: year
        direction: DESC
  - type: table
    name: Full text
    filters:
      and:
        - 'status == "full-text"'
    order:
      - file.name
      - title
      - year
      - journal
    sort:
      - property: year
        direction: DESC
  - type: table
    name: Reviews
    filters:
      and:
        - file.hasTag("pubmed/review")
    order:
      - file.name
      - title
      - year
      - journal
    sort:
      - property: year
        direction: DESC
  - type: table
    name: Retracted
    filters:
      and:
        - retracted == true
    order:
      - file.name
      - title
      - year
      - journal
  - type: table
    name: Reading list
    filters:
      and:
        - file.hasTag("to-read")
    order:
      - file.name
      - title
      - year
      - journal
    sort:
      - property: year
        direction: DESC
"""
TAG_PREFIX = "pubmed/"

BLOCK_START = "%% pubmed-stream:start - generated; edits inside this block are overwritten %%"
BLOCK_END = "%% pubmed-stream:end %%"
_BLOCK_START_PREFIX = "%% pubmed-stream:start"

# MeSH check tags describe the study population, not its topic.  As concept
# notes they would link nearly every paper, so they stay in frontmatter only.
MESH_CHECK_TAGS = frozenset({
    "Humans", "Animals", "Male", "Female", "Pregnancy", "Infant", "Infant, Newborn",
    "Child", "Child, Preschool", "Adolescent", "Young Adult", "Adult", "Middle Aged",
    "Aged", "Aged, 80 and over", "Mice", "Rats", "Cattle", "Dogs", "Cats", "Swine",
    "Sheep", "Rabbits", "Guinea Pigs", "Cricetinae", "Chick Embryo",
})

MAX_AUTHORS_SHOWN = 10
MAX_LABEL_LENGTH = 100
TOP_CONCEPTS = 10

# Frontmatter keys each note type writes.  On a rebuild these are replaced or
# removed; any other key is the user's and is kept as written.
_PAPER_KEYS = (
    "type", "title", "aliases", "pmid", "pmcid", "doi", "year", "journal", "authors",
    "publication_types", "mesh", "keywords", "status", "retracted", "url", "tags",
)
_CONCEPT_KEYS = ("type", "vocabulary", "mesh_ui", "url", "tags")
_COLLECTION_KEYS = ("type", "kind", "query", "seed", "source", "tags")
_HOME_KEYS = ("type", "tags")
# List keys merged with the user's own entries instead of replaced
_MERGED_LIST_KEYS = ("tags", "aliases")

# Obsidian graph-view colour groups, written only when the vault has none
_GRAPH_COLOR_GROUPS = [
    ("tag:#pubmed/retracted", 0xE5484D),
    ("path:collections", 0x8E4EC6),
    ("path:concepts", 0x12A594),
    ("tag:#pubmed/stub", 0x8B8D98),
    ("tag:#pubmed/review", 0xF76B15),
]

PathLike = Union[str, Path]


# ---------------------------------------------------------------------------
# Graph model
# ---------------------------------------------------------------------------

@dataclass
class Paper:
    """A paper in the vault, merged from every source that mentions it."""
    key: str  # note name: "PMID<id>", or the PMC ID when there is no PMID
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    doi: Optional[str] = None
    title: Optional[str] = None
    journal: Optional[str] = None
    year: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    abstract: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    pub_types: List[str] = field(default_factory=list)
    mesh_terms: List[Dict[str, Any]] = field(default_factory=list)
    is_review: bool = False
    is_retracted: bool = False
    nih_funded: bool = False
    downloaded: bool = False  # full text was downloaded from PMC
    full_text: Optional[str] = None
    # Raw reference-list entries ({"pmid", "doi", "title", "year"}), resolved later
    raw_references: List[Dict[str, str]] = field(default_factory=list)
    cites: Dict[str, Dict[str, str]] = field(default_factory=dict)  # key -> label hints
    other_references: List[Dict[str, str]] = field(default_factory=list)  # DOI-only, not in vault
    similar: Dict[str, Optional[int]] = field(default_factory=dict)  # key -> similarity score
    collections: List[str] = field(default_factory=list)

    @property
    def has_note(self) -> bool:
        """Papers get a note when downloaded or when their title is known."""
        return self.downloaded or bool(self.title)


@dataclass
class Collection:
    """A search query or evidence neighborhood the papers were collected from."""
    name: str  # note name
    kind: str  # "search", "neighborhood" or "folder"
    source: str
    query: Optional[str] = None
    seed: Optional[str] = None  # paper key of a neighborhood's seed
    papers: List[str] = field(default_factory=list)

    def add(self, key: str) -> None:
        if key not in self.papers:
            self.papers.append(key)


@dataclass
class VaultStats:
    """Summary of a :func:`build_vault` run."""
    vault_dir: Path
    sources: List[Path]
    papers: int = 0
    full_text: int = 0
    stubs: int = 0
    concepts: int = 0
    collections: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    pubmed_fetched: int = 0
    pubmed_missing: int = 0  # papers that still lack PubMed details

    def __str__(self) -> str:
        lines = [
            "",
            "=" * 60,
            "Obsidian vault",
            "=" * 60,
            f"Vault:             {self.vault_dir}",
            f"Sources:           {len(self.sources)}",
            f"Papers:            {self.papers} ({self.full_text} full text, {self.stubs} stubs)",
            f"MeSH concepts:     {self.concepts}",
            f"Collections:       {self.collections}",
            (
                f"Notes:             {self.created} created, {self.updated} updated, "
                f"{self.unchanged} unchanged"
            ),
            f"PubMed records:    {self.pubmed_fetched} fetched",
        ]
        if self.pubmed_missing:
            lines.append(
                f"  - Without MeSH:  {self.pubmed_missing} (offline, too new, or a journal outside MEDLINE)"
            )
        lines.append("=" * 60)
        return "\n".join(lines)


class _Graph:
    def __init__(self) -> None:
        self.papers: Dict[str, Paper] = {}
        self.collections: Dict[str, Collection] = {}
        self._by_pmid: Dict[str, str] = {}
        self._by_pmcid: Dict[str, str] = {}
        self._by_doi: Dict[str, str] = {}
        self.folders: Dict[Path, Collection] = {}  # download folder -> its collection

    def resolve(
        self, pmid: Optional[str] = None, pmcid: Optional[str] = None, doi: Optional[str] = None
    ) -> Optional[str]:
        if pmid and pmid in self._by_pmid:
            return self._by_pmid[pmid]
        if pmcid and pmcid in self._by_pmcid:
            return self._by_pmcid[pmcid]
        if doi and doi.lower() in self._by_doi:
            return self._by_doi[doi.lower()]
        return None

    def upsert(self, **fields: Any) -> Paper:
        """Add or merge a paper; known values win over missing ones, flags are OR-ed."""
        pmid = fields.get("pmid") or None
        pmcid = _normalize_pmcid(fields.get("pmcid"))
        doi = fields.get("doi") or None
        key = self.resolve(pmid, pmcid, doi) or (f"PMID{pmid}" if pmid else pmcid)
        if key is None:
            raise ValueError("a paper needs a PMID or PMC ID")
        paper = self.papers.get(key)
        if paper is None:
            paper = self.papers[key] = Paper(key=key)
        fields["pmcid"] = pmcid
        for name, value in fields.items():
            if value in (None, "", []):
                continue
            current = getattr(paper, name)
            if isinstance(current, bool):
                setattr(paper, name, current or bool(value))
            elif current in (None, "", []):
                setattr(paper, name, value)
        if paper.pmid:
            self._by_pmid[paper.pmid] = key
        if paper.pmcid:
            self._by_pmcid[paper.pmcid] = key
        if paper.doi:
            self._by_doi[paper.doi.lower()] = key
        return paper

    def collection(self, name: str, **fields: Any) -> Collection:
        if name not in self.collections:
            self.collections[name] = Collection(name=name, **fields)
        return self.collections[name]

    def join(self, paper: Paper, collection: Collection) -> None:
        collection.add(paper.key)
        if collection.name not in paper.collections:
            paper.collections.append(collection.name)

    def resolve_references(self) -> None:
        """Turn reference-list entries into citation links, once every paper is known."""
        for paper in self.papers.values():
            for ref in paper.raw_references:
                target = self.resolve(ref.get("pmid"), None, ref.get("doi"))
                if target is None and ref.get("pmid"):
                    target = f"PMID{ref['pmid']}"  # unresolved link; Obsidian can create it
                if target == paper.key:
                    continue
                if target is not None:
                    paper.cites.setdefault(target, {k: v for k, v in ref.items() if k in ("title", "year")})
                elif ref.get("doi"):
                    paper.other_references.append(ref)

    def cited_by(self) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = defaultdict(list)
        for paper in self.papers.values():
            for target in paper.cites:
                result[target].append(paper.key)
        return result


def _normalize_pmcid(pmcid: Optional[str]) -> Optional[str]:
    if not pmcid:
        return None
    pmcid = str(pmcid).strip()
    return pmcid if pmcid.upper().startswith("PMC") else f"PMC{pmcid}"


# ---------------------------------------------------------------------------
# Loading sources
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        logger.warning("Skipping unreadable %s: %s", path, e)
        return None
    return data if isinstance(data, dict) else None


def _folder_collection(graph: _Graph, folder: Path) -> Collection:
    """The collection of a download folder: its neighborhood, search query, or name."""
    if folder not in graph.folders:
        graph.folders[folder] = _new_folder_collection(graph, folder)
    return graph.folders[folder]


def _new_folder_collection(graph: _Graph, folder: Path) -> Collection:
    hood = folder / "neighborhood.json"
    if hood.is_file():
        data = _read_json(hood) or {}
        pmid = str(data.get("pmid") or folder.name.replace("neighborhood_", ""))
        return graph.collection(
            f"Neighborhood - PMID {pmid}", kind="neighborhood", source=str(folder), seed=f"PMID{pmid}"
        )
    query_file = folder / QUERY_FILE
    query = (_read_json(query_file) or {}).get("query") if query_file.is_file() else None
    if query:
        return graph.collection(f"Search - {_safe_name(query)}", kind="search", source=str(folder), query=query)
    return graph.collection(f"Folder - {_safe_name(folder.name)}", kind="folder", source=str(folder))


def _load_article(graph: _Graph, path: Path, fulltext: bool) -> None:
    data = _read_json(path)
    if data is None:
        return
    meta = data.get("metadata") or {}
    xml = data.get("xml")
    references = meta.get("references")
    if references is None and xml:
        # Downloads from before reference extraction still carry the raw XML
        references = extract_metadata_from_pmc_xml(xml).get("references", [])
    text = None
    if fulltext:
        text = data.get("text") or (extract_text_from_pmc_xml(xml) if xml else None)
    try:
        paper = graph.upsert(
            pmid=meta.get("pmid"),
            pmcid=meta.get("pmcid") or data.get("pmcid"),
            doi=meta.get("doi"),
            title=_clean(meta.get("title")),
            journal=meta.get("journal"),
            year=meta.get("year"),
            authors=meta.get("authors") or [],
            abstract=_clean(meta.get("abstract")),
            keywords=meta.get("keywords") or [],
            downloaded=True,
            full_text=text,
        )
    except ValueError:
        logger.warning("Skipping %s: no PMID or PMC ID", path)
        return
    if references and not paper.raw_references:
        paper.raw_references = references
    graph.join(paper, _folder_collection(graph, path.parent))


def _related_fields(article: Dict[str, Any]) -> Dict[str, Any]:
    """Map a saved RelatedArticle (neighborhood.json or the PubMed cache) to Paper fields."""
    return {
        "pmid": article.get("pmid"),
        "pmcid": article.get("pmcid"),
        "doi": article.get("doi"),
        "title": _clean(article.get("title")),
        "journal": article.get("journal"),
        "year": article.get("year"),
        "authors": article.get("authors") or [],
        "pub_types": article.get("pub_types") or [],
        "mesh_terms": article.get("mesh_terms") or [],
        "is_review": article.get("is_review", False),
        "is_retracted": article.get("is_retracted", False),
        "nih_funded": article.get("nih_funded", False),
    }


def _load_neighborhood(graph: _Graph, path: Path) -> None:
    data = _read_json(path)
    if data is None or not data.get("pmid"):
        return
    collection = _folder_collection(graph, path.parent)
    seed = graph.upsert(**_related_fields(data.get("seed") or {"pmid": data["pmid"]}))
    collection.seed = seed.key
    graph.join(seed, collection)

    for article in data.get("similar") or []:
        paper = graph.upsert(**_related_fields(article))
        seed.similar.setdefault(paper.key, article.get("score"))
        graph.join(paper, collection)
    for article in data.get("cited_by") or []:
        paper = graph.upsert(**_related_fields(article))
        paper.cites.setdefault(seed.key, {})
        graph.join(paper, collection)
    for article in data.get("references") or []:
        paper = graph.upsert(**_related_fields(article))
        seed.cites.setdefault(paper.key, {})
        graph.join(paper, collection)


def _load_sources(graph: _Graph, sources: List[Path], fulltext: bool) -> None:
    articles: List[Path] = []
    neighborhoods: List[Path] = []
    for source in sources:
        if source.is_file():
            (neighborhoods if source.name == "neighborhood.json" else articles).append(source)
        else:
            articles.extend(sorted(source.rglob("PMC*.json")))
            neighborhoods.extend(sorted(source.rglob("neighborhood.json")))
    # Articles first: their PMC metadata (titles in original case, abstracts)
    # wins over the PubMed summaries in neighborhoods
    for path in dict.fromkeys(articles):
        _load_article(graph, path, fulltext)
    for path in dict.fromkeys(neighborhoods):
        _load_neighborhood(graph, path)
    graph.resolve_references()


# ---------------------------------------------------------------------------
# PubMed enrichment (MeSH terms, publication types, flags)
# ---------------------------------------------------------------------------

def _enrich_from_pubmed(
    graph: _Graph,
    cache_path: Path,
    offline: bool,
    client: Dict[str, Any],
) -> Tuple[int, int]:
    """Fill MeSH terms and flags from PubMed records; returns (fetched, still missing)."""
    cache: Dict[str, Any] = (_read_json(cache_path) or {}) if cache_path.is_file() else {}
    wanted = [
        p.pmid for p in graph.papers.values()
        if p.pmid and p.has_note and not p.mesh_terms and p.pmid not in cache
    ]
    fetched = 0
    if wanted and not offline:
        api_key, rate_limiter, session, owned = _prepare_client(
            client.get("api_key"), client.get("rate_limit"), client.get("user_agent"),
            client.get("email"), client.get("session"),
        )
        try:
            records = _efetch_pubmed(wanted, api_key, session, rate_limiter)
        except (requests.RequestException, ValueError) as e:
            logger.warning("Could not fetch MeSH terms from PubMed, continuing without: %s", e)
            records = {}
        else:
            # Remember PMIDs PubMed has no record for, so they are not asked again
            for pmid in wanted:
                cache[pmid] = asdict(records[pmid]) if pmid in records else {"pmid": pmid}
            fetched = sum(pmid in records for pmid in wanted)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        finally:
            if owned:
                session.close()

    for paper in list(graph.papers.values()):
        record = cache.get(paper.pmid or "")
        if record and record.get("title") is not None:
            graph.upsert(**_related_fields(record))
    missing = sum(1 for p in graph.papers.values() if p.has_note and p.pmid and not p.mesh_terms)
    return fetched, missing


# ---------------------------------------------------------------------------
# Markdown and YAML helpers
# ---------------------------------------------------------------------------

_ILLEGAL_NAME_CHARS = re.compile(r'[\\/:*?<>|#^]')
_NAME_REPLACEMENTS = str.maketrans({'"': "", "[": "(", "]": ")"})


def _clean(text: Optional[str]) -> Optional[str]:
    return " ".join(text.split()) if text else text


def _safe_name(name: str, max_length: int = 120) -> str:
    """A note name Obsidian accepts as a file name and inside a wikilink."""
    name = _ILLEGAL_NAME_CHARS.sub("-", name.translate(_NAME_REPLACEMENTS))
    name = " ".join(name.split()).strip(" .-")
    return name[:max_length].rstrip(" .") or "untitled"


def _shorten(text: str, max_length: int = MAX_LABEL_LENGTH) -> str:
    return text if len(text) <= max_length else text[:max_length - 3].rstrip() + "..."


def _link(target: str, label: Optional[str] = None) -> str:
    if label:
        label = label.replace("|", "-").replace("[", "(").replace("]", ")")
    return f"[[{target}|{label}]]" if label and label != target else f"[[{target}]]"


def _escape(text: str) -> str:
    """Keep article text from creating Obsidian tags, links or comment markers."""
    text = text.replace("%%", "% %")
    text = text.replace("[[", "\\[\\[").replace("]]", "\\]\\]")
    return re.sub(r"(^|\s)#(?=[^\s#])", r"\1\\#", text)


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _tag(name: str) -> str:
    return TAG_PREFIX + name


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    # JSON strings are valid YAML double-quoted scalars
    return json.dumps(str(value), ensure_ascii=False)


def _yaml_entry(key: str, value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return "\n".join([f"{key}:"] + [f"  - {_yaml_scalar(v)}" for v in value])
    return f"{key}: {_yaml_scalar(value)}"


def _split_frontmatter(text: str) -> Tuple[Optional[str], str]:
    if text.startswith("---\n"):
        end = text.find("\n---", 3)
        if end != -1 and text[end + 4:end + 5] in ("\n", ""):
            return text[4:end + 1], text[end + 5:]
    return None, text


def _frontmatter_chunks(frontmatter: str) -> List[Tuple[Optional[str], str]]:
    """Split YAML frontmatter into top-level entries, keeping each entry's exact text."""
    chunks: List[Tuple[Optional[str], List[str]]] = []
    for line in frontmatter.splitlines():
        match = re.match(r"([^\s#:][^:]*):(\s|$)", line)
        if match:
            chunks.append((match.group(1).strip(), [line]))
        elif chunks:
            chunks[-1][1].append(line)
        else:
            chunks.append((None, [line]))
    return [(key, "\n".join(lines)) for key, lines in chunks]


def _parse_yaml_list(chunk: str) -> List[str]:
    """Read a simple YAML list or scalar, as Obsidian writes tags and aliases."""
    head, _, rest = chunk.partition(":")
    lines = rest.split("\n")
    first = lines[0].strip()
    if first.startswith("[") and first.endswith("]"):
        items = [i.strip() for i in first[1:-1].split(",")]
    elif first:
        items = [first]
    else:
        items = [ln.strip()[1:].strip() for ln in lines[1:] if ln.strip().startswith("-")]
    result = []
    for item in items:
        if len(item) >= 2 and item[0] == item[-1] and item[0] in "\"'":
            try:
                item = json.loads(item) if item[0] == '"' else item[1:-1]
            except ValueError:
                item = item[1:-1]
        if item:
            result.append(item.lstrip("#") if head.strip() == "tags" else item)
    return result


def _merge_frontmatter(existing: Optional[str], new: Dict[str, Any], owned: Iterable[str]) -> str:
    owned = set(owned)
    entries: List[str] = []
    written: Set[str] = set()
    for key, chunk in _frontmatter_chunks(existing or ""):
        if key not in owned:
            entries.append(chunk)  # the user's entry
            continue
        if key in written or key not in new:
            continue
        value = new[key]
        if key in _MERGED_LIST_KEYS:
            user_items = _parse_yaml_list(chunk)
            if key == "tags":
                user_items = [t for t in user_items if not t.startswith(TAG_PREFIX)]
            value = list(dict.fromkeys(list(value) + user_items))
        entries.append(_yaml_entry(key, value))
        written.add(key)
    for key, value in new.items():
        if key not in written:
            entries.append(_yaml_entry(key, value))
    return "\n".join(entries)


def _merge_body(existing: str, block: str) -> str:
    start = existing.find(_BLOCK_START_PREFIX)
    end = existing.find(BLOCK_END, start) if start != -1 else -1
    if start != -1 and end != -1:
        return existing[:start] + block + existing[end + len(BLOCK_END):]
    # Markers removed by hand: put the generated block back on top
    return block + "\n\n" + existing.lstrip("\n")


def _write_note(path: Path, frontmatter: Dict[str, Any], body: str, owned: Iterable[str]) -> str:
    """Create or update a note; returns 'created', 'updated' or 'unchanged'."""
    frontmatter = {k: v for k, v in frontmatter.items() if v not in (None, "", [], False)}
    block = f"{BLOCK_START}\n{body.strip()}\n{BLOCK_END}"
    if path.is_file():
        old = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        old_frontmatter, old_body = _split_frontmatter(old)
        content = (
            f"---\n{_merge_frontmatter(old_frontmatter, frontmatter, owned)}\n---\n"
            f"{_merge_body(old_body, block)}"
        )
        if content == old:
            return "unchanged"
        status = "updated"
    else:
        content = f"---\n{_merge_frontmatter(None, frontmatter, owned)}\n---\n{block}\n\n## Notes\n\n"
        status = "created"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    return status


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _paper_label(graph: _Graph, key: str, hint: Optional[Dict[str, str]] = None) -> Optional[str]:
    paper = graph.papers.get(key)
    title = (paper.title if paper else None) or (hint or {}).get("title")
    year = (paper.year if paper else None) or (hint or {}).get("year")
    if not title:
        return None
    title = _shorten(title)
    return f"{title} ({year})" if year else title


def _concept_name(term: Dict[str, Any]) -> str:
    return _safe_name(term["name"])


def _concept_terms(paper: Paper) -> List[Dict[str, Any]]:
    """The paper's MeSH terms that get concept notes."""
    return [t for t in paper.mesh_terms if t["name"] not in MESH_CHECK_TAGS]


def _year_sort(graph: _Graph, keys: Iterable[str]) -> List[str]:
    """Newest first, then by title."""
    def sort_key(key: str) -> Tuple[int, str]:
        paper = graph.papers.get(key)
        year = paper.year if paper and paper.year and paper.year.isdigit() else "0"
        return (-int(year), (paper.title or key).lower() if paper else key)
    return sorted(keys, key=sort_key)


def _paper_list(graph: _Graph, keys: Iterable[str], hints: Optional[Dict[str, Dict]] = None) -> List[str]:
    return [f"- {_link(k, _paper_label(graph, k, (hints or {}).get(k)))}" for k in keys]


def _render_paper(graph: _Graph, paper: Paper, cited_by: List[str]) -> Tuple[Dict[str, Any], str]:
    tags = [_tag("paper")]
    if paper.is_review:
        tags.append(_tag("review"))
    if paper.is_retracted:
        tags.append(_tag("retracted"))
    if paper.nih_funded:
        tags.append(_tag("nih-funded"))
    if not paper.downloaded:
        tags.append(_tag("stub"))
    pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{paper.pmid}/" if paper.pmid else None

    frontmatter = {
        "type": "paper",
        "title": paper.title,
        "aliases": [paper.title] if paper.title else [],
        "pmid": paper.pmid,
        "pmcid": paper.pmcid,
        "doi": paper.doi,
        "year": int(paper.year) if paper.year and paper.year.isdigit() else paper.year,
        "journal": paper.journal,
        "authors": paper.authors,
        "publication_types": paper.pub_types,
        "mesh": [t["name"] for t in paper.mesh_terms],
        "keywords": paper.keywords,
        "status": "full-text" if paper.downloaded else "stub",
        "retracted": paper.is_retracted,
        "url": pubmed_url,
        "tags": tags,
    }

    lines = [f"# {_escape(paper.title or paper.key)}", ""]
    if paper.is_retracted:
        lines += [
            "> [!warning] Retracted publication",
            "> PubMed marks this article as retracted or links a retraction notice. Check it before citing.",
            "",
        ]
    if not paper.downloaded:
        lines += [
            "> [!note] Stub",
            "> Known from an evidence neighborhood; its full text has not been downloaded.",
            "",
        ]
    if paper.authors:
        shown = ", ".join(paper.authors[:MAX_AUTHORS_SHOWN])
        more = f", et al. ({len(paper.authors)} authors)" if len(paper.authors) > MAX_AUTHORS_SHOWN else ""
        lines.append(f"**Authors:** {_escape(shown)}{more}")
    published = [f"*{_escape(paper.journal)}*" if paper.journal else None, paper.year]
    links = [
        f"[PubMed]({pubmed_url})" if pubmed_url else None,
        f"[PMC](https://pmc.ncbi.nlm.nih.gov/articles/{paper.pmcid}/)" if paper.pmcid else None,
        f"[DOI](https://doi.org/{paper.doi})" if paper.doi else None,
    ]
    published_line = " · ".join(p for p in published + links if p)
    if published_line:
        lines.append(f"**Published:** {published_line}")
    if paper.pub_types:
        lines.append(f"**Publication type:** {', '.join(paper.pub_types)}")
    if paper.collections:
        lines.append("**Collections:** " + ", ".join(_link(c) for c in paper.collections))

    if paper.abstract:
        lines += ["", "## Abstract", "", _escape(paper.abstract)]
    concepts = _concept_terms(paper)
    if concepts:
        lines += ["", "## MeSH concepts", ""]
        lines += [
            f"- {_link(_concept_name(t), t['name'])}" + (" (major topic)" if t.get("major") else "")
            for t in concepts
        ]
    if paper.keywords:
        lines += ["", "## Keywords", "", _escape(", ".join(paper.keywords))]
    if paper.cites:
        lines += ["", f"## Cites ({len(paper.cites)})", ""] + _paper_list(graph, paper.cites, paper.cites)
    if cited_by:
        lines += ["", f"## Cited by ({len(cited_by)})", ""] + _paper_list(graph, _year_sort(graph, cited_by))
    if paper.similar:
        ranked = sorted(paper.similar.items(), key=lambda item: -(item[1] or 0))
        lines += ["", f"## Similar articles ({len(ranked)})", ""]
        lines += [
            f"- {_link(k, _paper_label(graph, k))}" + (f" · score {s}" if s is not None else "")
            for k, s in ranked
        ]
    if paper.other_references:
        lines += ["", f"## Other references ({len(paper.other_references)})", ""]
        lines += [
            f"- [{_escape(ref.get('title') or ref['doi'])}](https://doi.org/{ref['doi']})"
            for ref in paper.other_references
        ]
    if paper.full_text:
        lines += ["", "## Full text", "", _escape(paper.full_text)]
    return frontmatter, "\n".join(lines)


def _render_concept(
    graph: _Graph, term: Dict[str, Any], papers: List[Tuple[str, bool]]
) -> Tuple[Dict[str, Any], str]:
    ui = term.get("ui") or None
    url = f"https://meshb.nlm.nih.gov/record/ui?ui={ui}" if ui else None
    frontmatter = {
        "type": "concept",
        "vocabulary": "MeSH",
        "mesh_ui": ui,
        "url": url,
        "tags": [_tag("concept")],
    }
    major = {key for key, is_major in papers if is_major}
    lines = [f"# {term['name']}", ""]
    if url:
        lines += [f"MeSH descriptor {ui} · [MeSH Browser]({url})", ""]
    lines += [f"## Papers ({len(papers)})", ""]
    lines += [
        f"- {_link(k, _paper_label(graph, k))}" + (" (major topic)" if k in major else "")
        for k in _year_sort(graph, [k for k, _ in papers])
    ]
    return frontmatter, "\n".join(lines)


def _top_concepts(graph: _Graph, keys: Iterable[str], limit: int) -> List[Tuple[Dict[str, Any], int]]:
    counts: Counter = Counter()
    terms: Dict[str, Dict[str, Any]] = {}
    for key in keys:
        paper = graph.papers.get(key)
        for term in (_concept_terms(paper) if paper else []):
            counts[term["name"]] += 1
            terms[term["name"]] = term
    return [(terms[name], n) for name, n in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def _render_collection(graph: _Graph, collection: Collection) -> Tuple[Dict[str, Any], str]:
    keys = [k for k in collection.papers if graph.papers[k].has_note]
    frontmatter = {
        "type": "collection",
        "kind": collection.kind,
        "query": collection.query,
        "seed": collection.seed,
        "source": collection.source,
        "tags": [_tag("collection")],
    }
    if collection.kind == "search":
        heading = f"Search: {_escape(collection.query or '')}"
    elif collection.kind == "neighborhood":
        seed = graph.papers.get(collection.seed or "")
        heading = f"Evidence neighborhood of PMID {seed.pmid if seed and seed.pmid else collection.seed}"
    else:
        heading = f"Folder: {collection.name}"
    full = sum(graph.papers[k].downloaded for k in keys)
    lines = [f"# {heading}", "", f"{_count(len(keys), 'paper')}, {full} with full text.", ""]
    if collection.seed:
        lines += [f"**Seed:** {_link(collection.seed, _paper_label(graph, collection.seed))}", ""]
    top = _top_concepts(graph, keys, TOP_CONCEPTS)
    if top:
        lines += ["## Top MeSH concepts", ""]
        lines += [f"- {_link(_concept_name(t), t['name'])} ({n})" for t, n in top]
        lines.append("")
    lines += [f"## Papers ({len(keys)})", ""] + _paper_list(graph, _year_sort(graph, keys))
    return frontmatter, "\n".join(lines)


def _render_home(graph: _Graph, concept_papers: Dict[str, List[Tuple[str, bool]]], terms: Dict[str, Dict],
                 vault: Optional[Path] = None) -> str:
    noted = [p for p in graph.papers.values() if p.has_note]
    lines = [
        "# PubMed Stream",
        "",
        "Knowledge graph of the papers downloaded with pubmed-stream. Open the graph view to explore it.",
        "",
        "| Notes | Count |",
        "|---|---|",
        f"| Papers with full text | {sum(p.downloaded for p in noted)} |",
        f"| Stub papers | {sum(not p.downloaded for p in noted)} |",
        f"| MeSH concepts | {len(concept_papers)} |",
        f"| Collections | {len(graph.collections)} |",
        "",
        "## Collections",
        "",
    ]
    for collection in sorted(graph.collections.values(), key=lambda c: c.name.lower()):
        count = sum(graph.papers[k].has_note for k in collection.papers)
        lines.append(f"- {_link(collection.name)} ({_count(count, 'paper')})")
    ranked = sorted(concept_papers.items(), key=lambda item: (-len(item[1]), item[0]))[:20]
    if ranked:
        lines += ["", "## Most connected concepts", ""]
        lines += [f"- {_link(name, terms[name]['name'])} ({_count(len(papers), 'paper')})" for name, papers in ranked]
    retracted = [p.key for p in noted if p.is_retracted]
    if retracted:
        lines += ["", f"## Retracted papers ({len(retracted)})", ""] + _paper_list(graph, _year_sort(graph, retracted))
    if vault is not None and (vault / PAPERS_BASE).exists():
        lines += ["", "## All papers", "",
                  "A table of every paper. Switch views at its top left: full text, reviews, retracted papers, "
                  "and your reading list, the papers you tag `#to-read`.", "", f"![[{PAPERS_BASE}]]"]
    if vault is not None and (vault / "reviews").is_dir():
        reviews = sorted(p.stem for p in (vault / "reviews").glob("*.md"))
        if reviews:
            lines += ["", "## Reviews by a local model", ""] + [f"- {_link(name)}" for name in reviews]
    return "\n".join(lines)


def _write_obsidian_files(vault: Path) -> None:
    """Property types, and the Papers base, without overwriting the user's own."""
    types_path = vault / ".obsidian" / "types.json"
    try:
        current = json.loads(types_path.read_text(encoding="utf-8")) if types_path.exists() else {}
        types = current.setdefault("types", {})
        missing = {k: v for k, v in PROPERTY_TYPES.items() if k not in types}
        if missing:
            types.update(missing)
            types_path.parent.mkdir(parents=True, exist_ok=True)
            types_path.write_text(json.dumps(current, indent=2), encoding="utf-8")
        base_path = vault / PAPERS_BASE
        if not base_path.exists():
            base_path.write_text(PAPERS_BASE_TEXT, encoding="utf-8")
    except (OSError, ValueError) as e:
        logger.warning("Could not write Obsidian settings in %s: %s", vault, e)


def _write_graph_settings(vault: Path) -> None:
    """Colour retracted papers, stubs, reviews, concepts and collections in the graph view."""
    path = vault / ".obsidian" / "graph.json"
    if path.exists():
        return
    settings = {
        "colorGroups": [
            {"query": query, "color": {"a": 1, "rgb": rgb}} for query, rgb in _GRAPH_COLOR_GROUPS
        ],
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning("Could not write %s: %s", path, e)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def topic_vault_dir(topic: str, parent: PathLike = ".") -> Path:
    """The vault folder of a study topic: ``<parent>/kg_<topic slug>``.

    The slug follows download folder names, so the topic
    ``"gut microbiome"`` gives ``kg_gut_microbiome`` next to
    ``publications/gut_microbiome``.
    """
    slug = slugify(topic, default="topic")
    if slug.lower().startswith(VAULT_PREFIX):
        slug = slug[len(VAULT_PREFIX):] or "topic"
    return Path(parent) / f"{VAULT_PREFIX}{slug}"


def _registered_sources(vault: Path, sources: Optional[Iterable[PathLike]]) -> List[Path]:
    registry = vault / STATE_DIR / SOURCES_FILE
    known = [Path(p) for p in ((_read_json(registry) or {}).get("sources", []) if registry.is_file() else [])]
    added = [Path(p).resolve() for p in (sources or [])]
    for path in added:
        if not path.exists():
            raise FileNotFoundError(f"Source not found: {path}")
    result = []
    for path in dict.fromkeys(known + added):
        if path.exists():
            result.append(path)
        else:
            logger.warning("Dropping source that no longer exists: %s", path)
    if not result:
        raise ValueError("No sources: pass a download folder (for example ./publications)")
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(json.dumps({"sources": [str(p) for p in result]}, indent=2), encoding="utf-8")
    return result


def build_vault(
    sources: Optional[Iterable[PathLike]],
    vault_dir: PathLike,
    fulltext: bool = False,
    offline: bool = False,
    api_key: Optional[str] = None,
    user_agent: Optional[str] = None,
    email: Optional[str] = None,
    rate_limit: Optional[float] = None,
    session: Optional[requests.Session] = None,
) -> VaultStats:
    """Build or update an Obsidian vault from downloaded articles.

    Args:
        sources: Download folders or files (``PMC*.json``, ``neighborhood.json``)
            to add.  Folders are searched recursively.  Sources of earlier builds
            are remembered and always included; pass ``None`` to rebuild from them.
        vault_dir: The vault folder; created if missing.  Use
            :func:`topic_vault_dir` for the ``kg_<topic>`` naming convention.
        fulltext: Put each article's full text into its note (default: abstract only).
        offline: Do not query PubMed; use only cached MeSH terms.
        api_key, user_agent, email, rate_limit, session: NCBI client settings,
            as in :func:`pubmed_stream.search_and_download`.

    Returns:
        A :class:`VaultStats` summary.

    Raises:
        FileNotFoundError: A source does not exist.
        ValueError: There are no sources to build from.
    """
    vault = Path(vault_dir).absolute().resolve()
    vault.mkdir(parents=True, exist_ok=True)
    source_paths = _registered_sources(vault, sources)

    graph = _Graph()
    _load_sources(graph, source_paths, fulltext)
    fetched, missing = _enrich_from_pubmed(
        graph,
        vault / STATE_DIR / CACHE_FILE,
        offline,
        {"api_key": api_key, "user_agent": user_agent, "email": email,
         "rate_limit": rate_limit, "session": session},
    )

    stats = VaultStats(vault_dir=vault, sources=source_paths, pubmed_fetched=fetched, pubmed_missing=missing)
    outcomes: Counter = Counter()
    cited_by = graph.cited_by()
    concept_papers: Dict[str, List[Tuple[str, bool]]] = defaultdict(list)
    concept_terms: Dict[str, Dict[str, Any]] = {}

    for paper in graph.papers.values():
        if not paper.has_note:
            continue
        frontmatter, body = _render_paper(graph, paper, cited_by.get(paper.key, []))
        outcomes[_write_note(vault / PAPERS_DIR / f"{paper.key}.md", frontmatter, body, _PAPER_KEYS)] += 1
        stats.papers += 1
        stats.full_text += paper.downloaded
        stats.stubs += not paper.downloaded
        for term in _concept_terms(paper):
            name = _concept_name(term)
            concept_terms.setdefault(name, term)
            if all(k != paper.key for k, _ in concept_papers[name]):
                concept_papers[name].append((paper.key, bool(term.get("major"))))

    for name, papers in concept_papers.items():
        frontmatter, body = _render_concept(graph, concept_terms[name], papers)
        outcomes[_write_note(vault / CONCEPTS_DIR / f"{name}.md", frontmatter, body, _CONCEPT_KEYS)] += 1
    for collection in graph.collections.values():
        frontmatter, body = _render_collection(graph, collection)
        path = vault / COLLECTIONS_DIR / f"{collection.name}.md"
        outcomes[_write_note(path, frontmatter, body, _COLLECTION_KEYS)] += 1
    _write_obsidian_files(vault)
    outcomes[_write_note(
        vault / f"{HOME_NOTE}.md",
        {"type": "home", "tags": [_tag("home")]},
        _render_home(graph, concept_papers, concept_terms, vault),
        _HOME_KEYS,
    )] += 1
    _write_graph_settings(vault)

    stats.concepts = len(concept_papers)
    stats.collections = len(graph.collections)
    stats.created, stats.updated, stats.unchanged = (
        outcomes["created"], outcomes["updated"], outcomes["unchanged"]
    )
    return stats
