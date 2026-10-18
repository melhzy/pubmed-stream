"""Knowledge graphs for scientific studies.

A study has a topic, the PubMed searches that collect its literature, and
optionally key articles whose evidence neighborhoods (similar, citing and
cited papers) belong in it.  :func:`create_kg` runs all of them and builds
the study's Obsidian knowledge graph in ``./kg_<topic>``::

    from pubmed_stream import create_kg

    result = create_kg(
        "gut microbiome frailty",
        queries=["gut microbiome frailty", "microbiome sarcopenia"],
        seeds=["35803947"],
    )
    print(result)

The graph remembers its study in ``.pubmed-stream/study.json``.  Later calls
with the same topic add to it, and ``refresh=True`` runs every remembered
search and neighborhood again to pick up newly published papers; articles
already downloaded are skipped.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

import requests

from .downloader import MAX_WORKERS, DownloadStats, search_and_download
from .neighborhood import (
    Neighborhood,
    download_neighborhood,
    get_neighborhood,
    save_neighborhood,
)
from .vault import STATE_DIR, VaultStats, _read_json, build_vault, topic_vault_dir

STUDY_FILE = "study.json"

PathLike = Union[str, Path]


@dataclass
class KGResult:
    """Outcome of :func:`create_kg`."""
    topic: str
    kg_dir: Path
    queries: List[str] = field(default_factory=list)  # every search of the study
    seeds: List[str] = field(default_factory=list)  # every neighborhood seed of the study
    downloads: List[DownloadStats] = field(default_factory=list)  # searches run this time
    neighborhoods: List[Neighborhood] = field(default_factory=list)  # fetched this time
    vault: Optional[VaultStats] = None
    errors: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        new_articles = sum(s.successful for s in self.downloads)
        lines = [
            "",
            "=" * 60,
            f"Knowledge graph: {self.topic}",
            "=" * 60,
            f"Folder:            {self.kg_dir}",
            (
                f"Study searches:    {len(self.queries)} ({len(self.downloads)} run now, "
                f"{new_articles} new articles)"
            ),
            f"Study seeds:       {len(self.seeds)} ({len(self.neighborhoods)} fetched now)",
        ]
        lines += [f"[ERROR] {e}" for e in self.errors]
        lines.append("=" * 60)
        text = "\n".join(lines)
        return text + (str(self.vault) if self.vault else "")


def load_study(kg_dir: PathLike) -> Dict[str, Any]:
    """The study recorded in a knowledge graph: ``{"topic", "queries", "seeds"}``."""
    path = Path(kg_dir) / STATE_DIR / STUDY_FILE
    study = (_read_json(path) or {}) if path.is_file() else {}
    return {
        "topic": study.get("topic"),
        "queries": list(study.get("queries") or []),
        "seeds": [str(s) for s in study.get("seeds") or []],
    }


def _save_study(kg_dir: Path, topic: str, queries: List[str], seeds: List[str]) -> None:
    path = kg_dir / STATE_DIR / STUDY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"topic": topic, "queries": queries, "seeds": seeds}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def record_study(
    kg_dir: PathLike,
    topic: Optional[str] = None,
    queries: Iterable[str] = (),
    seeds: Iterable[Union[str, int]] = (),
) -> Dict[str, Any]:
    """Add searches and seeds run elsewhere to a knowledge graph's study.

    Keeps the recorded topic unless *topic* is given; a new study without one
    is named after its folder.  Returns the updated study.
    """
    directory = Path(kg_dir)
    study = load_study(directory)
    topic = topic or study["topic"] or directory.name
    queries = _unique(study["queries"] + [" ".join(q.split()) for q in queries])
    seeds = _unique(study["seeds"] + [str(s).strip() for s in seeds])
    _save_study(directory, topic, queries, seeds)
    return {"topic": topic, "queries": queries, "seeds": seeds}


def _unique(items: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(i for i in items if i))


def create_kg(
    topic: str,
    queries: Optional[Iterable[str]] = None,
    seeds: Optional[Iterable[Union[str, int]]] = None,
    sources: Optional[Iterable[PathLike]] = None,
    refresh: bool = False,
    max_results: int = 100,
    max_per_relation: int = 100,
    download_neighbors: bool = False,
    kg_dir: Optional[PathLike] = None,
    output_dir: Optional[PathLike] = None,
    fmt: str = "text",
    include_text: bool = True,
    use_concurrent: bool = True,
    max_workers: int = MAX_WORKERS,
    fulltext: bool = False,
    offline: bool = False,
    api_key: Optional[str] = None,
    user_agent: Optional[str] = None,
    email: Optional[str] = None,
    rate_limit: Optional[float] = None,
    session: Optional[requests.Session] = None,
) -> KGResult:
    """Collect a study's literature and build its knowledge graph.

    Args:
        topic: The study topic; the graph is ``./kg_<topic>``.
        queries: PubMed searches to download (see :func:`search_and_download`).
        seeds: PMIDs of key articles whose evidence neighborhoods to add
            (see :func:`get_neighborhood`).
        sources: Folders or files downloaded earlier to add.
        refresh: Also run every search and neighborhood the study already has,
            to pick up newly published papers.
        max_results: Articles per search (default 100).
        max_per_relation: Similar, citing and cited articles per seed (default 100).
        download_neighbors: Download PMC full text of neighborhood articles too;
            otherwise they appear as stub notes.
        kg_dir: Graph folder, instead of ``./kg_<topic>``.
        output_dir: Base folder for downloads (default ``./publications``).
        fmt, include_text, use_concurrent, max_workers: Download options, as in
            :func:`search_and_download`.
        fulltext: Put each article's full text into its note.
        offline: Do not fetch MeSH terms from PubMed for the graph.
        api_key, user_agent, email, rate_limit, session: NCBI client settings.

    Returns:
        A :class:`KGResult`.  Searches or neighborhoods that failed are listed
        in ``errors``; the graph is still built from everything else.

    Raises:
        ValueError: The topic is empty, a seed is not a numeric PMID, or the
            study has nothing to build from yet.
        FileNotFoundError: A source does not exist.
    """
    topic = " ".join(str(topic).split())
    if not topic:
        raise ValueError("The study needs a topic")
    new_seeds = [str(s).strip() for s in seeds or []]
    for seed in new_seeds:
        if not re.fullmatch(r"[0-9]+", seed):
            raise ValueError(f"Seed must be a numeric PubMed ID, got {seed!r}")
    new_queries = [" ".join(q.split()) for q in queries or []]

    directory = (Path(kg_dir) if kg_dir else topic_vault_dir(topic)).resolve()
    study = load_study(directory)
    all_queries = _unique(study["queries"] + new_queries)
    all_seeds = _unique(study["seeds"] + new_seeds)
    run_queries = all_queries if refresh else _unique(new_queries)
    run_seeds = all_seeds if refresh else _unique(new_seeds)

    result = KGResult(topic=topic, kg_dir=directory, queries=all_queries, seeds=all_seeds)
    client = {"api_key": api_key, "user_agent": user_agent, "email": email,
              "rate_limit": rate_limit, "session": session}
    base = Path(output_dir) if output_dir else None
    new_sources: List[Path] = [Path(s) for s in sources or []]

    for query in run_queries:
        stats = search_and_download(
            query,
            max_results=max_results,
            fmt=fmt,
            use_concurrent=use_concurrent,
            max_workers=max_workers,
            include_text=include_text,
            output_dir=base,
            **client,
        )
        result.downloads.append(stats)
        if stats.requested:
            new_sources.append(stats.output_dir)
        else:
            result.errors.append(f"Search {query!r}: no PMC articles found, or the search failed")

    for seed in run_seeds:
        try:
            hood = get_neighborhood(seed, max_per_relation=max_per_relation, **client)
        except (ValueError, requests.RequestException) as e:
            result.errors.append(f"Neighborhood of PMID {seed}: {e}")
            continue
        if hood.seed is None:
            result.errors.append(f"Neighborhood of PMID {seed}: not found in PubMed")
            continue
        path = save_neighborhood(hood, base)
        if download_neighbors:
            download_neighborhood(
                hood,
                output_dir=base,
                fmt=fmt,
                use_concurrent=use_concurrent,
                max_workers=max_workers,
                include_text=include_text,
                **client,
            )
        result.neighborhoods.append(hood)
        new_sources.append(path.parent)

    # Remember the study before building, so a failed build can be retried
    _save_study(directory, topic, all_queries, all_seeds)
    try:
        result.vault = build_vault(
            new_sources or None, directory, fulltext=fulltext, offline=offline, **client
        )
    except ValueError:
        if result.errors:
            return result  # everything failed: report why, with no graph yet
        raise ValueError(
            f"Nothing to build for {topic!r} yet: add searches, seeds or download folders"
        ) from None
    return result
