"""Command-line interface for pubmed-stream.

Installed as the ``pubmed-stream`` console script, or runnable via
``python -m pubmed_stream``.
"""

import argparse
import logging
import sys
from pathlib import Path
import requests

from . import __version__
from .downloader import (
    MAX_WORKERS,
    RATE_LIMIT_WITH_API_KEY,
    RATE_LIMIT_NO_API_KEY,
    search_and_download,
)
from .neighborhood import (
    Neighborhood,
    download_neighborhood,
    get_neighborhood,
    save_neighborhood,
)
from .vault import build_vault, topic_vault_dir

# --vault given without a folder: name the vault after the run's topic
_AUTO_VAULT = object()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pubmed-stream",
        description="Download PubMed Central full-text articles.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    # Options shared by all subcommands
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--api-key",
        help="Override NCBI API key (otherwise uses NCBI_API_KEY env var)",
    )
    common.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )
    common.add_argument(
        "--output-dir",
        "-o",
        help="Base output directory for downloads (default: ./publications)",
    )
    common.add_argument(
        "--user-agent",
        help="Override HTTP User-Agent header",
    )
    common.add_argument(
        "--email",
        help="Email address for NCBI contact (or NCBI_EMAIL env var)",
    )
    common.add_argument(
        "--rate-limit",
        type=float,
        help=f"Minimum seconds between HTTP requests (auto: {RATE_LIMIT_WITH_API_KEY}s with API key, "
             f"{RATE_LIMIT_NO_API_KEY}s without)",
    )

    # Options controlling how full-text articles are downloaded and saved
    fetch = argparse.ArgumentParser(add_help=False)
    fetch.add_argument(
        "--format",
        choices=["text", "xml", "both", "json", "txt"],
        default="text",
        help="Output format (all save as .json): 'text' (default, JSON with metadata+text field), "
             "'xml' (JSON with metadata+xml field), 'both' (JSON with both xml and text fields). "
             "Legacy: 'json'/'txt' (mapped to 'text')",
    )
    fetch.add_argument(
        "--sequential",
        action="store_true",
        help="Use sequential downloads instead of concurrent",
    )
    fetch.add_argument(
        "--workers",
        type=int,
        default=MAX_WORKERS,
        help=f"Number of concurrent worker threads (default: {MAX_WORKERS})",
    )
    fetch.add_argument(
        "--exclude-text",
        action="store_true",
        help="Exclude plain-text field in JSON output to save space",
    )

    # Options for building an Obsidian vault
    vault = argparse.ArgumentParser(add_help=False)
    vault.add_argument(
        "--topic",
        help="Study topic; its knowledge graph is the vault ./kg_<topic> "
             "(example: --topic 'gut microbiome frailty')",
    )
    vault.add_argument(
        "--fulltext",
        action="store_true",
        help="Vault: put each article's full text into its note (default: abstract only)",
    )
    vault.add_argument(
        "--offline",
        action="store_true",
        help="Vault: do not fetch MeSH terms from PubMed; use only the vault's cache",
    )
    vault_dir = argparse.ArgumentParser(add_help=False)
    vault_dir.add_argument(
        "--vault",
        metavar="DIR",
        nargs="?",
        const=_AUTO_VAULT,
        help="Also add the results to an Obsidian knowledge-graph vault: DIR, the "
             "--topic vault, or with no DIR ./kg_<download folder name> "
             "(see 'pubmed-stream graph')",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser(
        "download",
        parents=[common, fetch, vault_dir, vault],
        help="Search PMC and download full-text articles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  pubmed-stream download "gut microbiome" --max-results 50
  pubmed-stream download "frailty cytokines" --format both -o ./papers

Articles are saved as <output-dir>/<query>/PMC*.json; re-running skips
files that already exist.""",
    )
    download.add_argument(
        "keyword",
        help="PubMed search query (example: 'frailty cytokines')",
    )
    download.add_argument(
        "--max-results",
        type=int,
        default=100,
        help="Maximum number of articles to download (default: 100)",
    )

    neighborhood = subparsers.add_parser(
        "neighborhood",
        parents=[common, fetch, vault_dir, vault],
        help="Show similar, citing and cited articles of a PubMed article "
             "(like NLM Linked Discoveries)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  pubmed-stream neighborhood 29096998
  pubmed-stream neighborhood 29096998 --max-per-relation 20 --download

The PMID is the number in a PubMed URL (pubmed.ncbi.nlm.nih.gov/<PMID>/),
not a PMC ID. Results are saved as <output-dir>/neighborhood_<PMID>/
neighborhood.json; --download adds PMC*.json full-text files there.
"100 of 489" means 100 of 489 linked articles were fetched in detail;
the review/retracted/NIH-funded/PMC counts always cover all 489.""",
    )
    neighborhood.add_argument(
        "pmid",
        help="PubMed ID of the seed article (example: 29096998)",
    )
    neighborhood.add_argument(
        "--max-per-relation",
        type=int,
        default=100,
        help="Maximum similar, citing and cited articles each (default: 100)",
    )
    neighborhood.add_argument(
        "--download",
        action="store_true",
        help="Also download PMC full text of the seed and its neighbors",
    )

    graph = subparsers.add_parser(
        "graph",
        parents=[common, vault],
        help="Build an Obsidian knowledge-graph vault from downloaded articles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  pubmed-stream graph ./publications/gut_microbiome
  pubmed-stream graph ./publications/gut_microbiome ./publications/frailty --topic "gut microbiome frailty"
  pubmed-stream graph --topic "gut microbiome frailty" --offline

Each study topic gets its own vault, ./kg_<topic>. With one SOURCE the topic
is the source folder's name (kg_gut_microbiome); with several, name the study
with --topic, or pick any folder with --vault DIR.

Writes one note per paper, MeSH concept and collection, linked by citations,
similarity and topic; open the vault folder in Obsidian. The vault remembers
its sources, so with no SOURCE it rebuilds from them. Rebuilding keeps
anything written outside the generated %% pubmed-stream %% block.""",
    )
    graph.add_argument(
        "sources",
        nargs="*",
        metavar="SOURCE",
        help="Download folders or files to add (default: the vault's remembered sources)",
    )
    graph.add_argument(
        "--vault",
        metavar="DIR",
        help="Vault folder, overriding the kg_<topic> name",
    )

    return parser


def _vault_dir(args: argparse.Namespace, default_topic: str):
    """The vault a download or neighborhood run adds to, or None for no vault."""
    if args.vault is not None and args.vault is not _AUTO_VAULT:
        return Path(args.vault)
    if args.topic:
        return topic_vault_dir(args.topic)
    if args.vault is _AUTO_VAULT:
        return topic_vault_dir(default_topic)
    return None


def _update_vault(args: argparse.Namespace, vault_dir: Path, sources) -> int:
    """Build the vault in *vault_dir* from *sources*; returns an exit code."""
    try:
        stats = build_vault(
            sources,
            vault_dir,
            fulltext=args.fulltext,
            offline=args.offline,
            api_key=args.api_key,
            user_agent=args.user_agent,
            email=args.email,
            rate_limit=args.rate_limit,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Error: could not write the vault: {e}", file=sys.stderr)
        return 2
    print(stats)
    return 0


def _run_graph(args: argparse.Namespace) -> int:
    sources = args.sources or None
    if args.vault:
        vault_dir = Path(args.vault)
    elif args.topic:
        vault_dir = topic_vault_dir(args.topic)
    elif sources and len(sources) == 1:
        # One download folder: its name is the topic (a file's folder for a file)
        source = Path(sources[0])
        vault_dir = topic_vault_dir((source.parent if source.is_file() else source).resolve().name)
    else:
        print(
            "Error: name the study with --topic (its vault is ./kg_<topic>), or pass --vault DIR"
            + (" when combining several sources" if sources else ""),
            file=sys.stderr,
        )
        return 1
    return _update_vault(args, vault_dir, sources)


def _relation_summary(label: str, hood: Neighborhood, relation: str) -> str:
    fetched, total = len(getattr(hood, relation)), hood.totals[relation]
    flags = hood.flag_counts[relation]
    # "100 of 489" when --max-per-relation cut the list short; flags cover all 489
    count = f"{fetched:>5}" + (f" of {total:<6}" if total > fetched else " " * 10)
    return (
        f"{label:<12}{count}  ("
        f"{flags['reviews']} reviews, {flags['retracted']} retracted, "
        f"{flags['nih_funded']} NIH-funded, {flags['in_pmc']} in PMC)"
    )


def _run_neighborhood(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir) if args.output_dir else None
    try:
        hood = get_neighborhood(
            args.pmid,
            max_per_relation=args.max_per_relation,
            api_key=args.api_key,
            user_agent=args.user_agent,
            email=args.email,
            rate_limit=args.rate_limit,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except requests.RequestException as e:
        print(f"Error: could not reach NCBI: {e}", file=sys.stderr)
        return 2

    if hood.seed is None:
        print(f"Error: PMID {hood.pmid} not found in PubMed", file=sys.stderr)
        return 1

    path = save_neighborhood(hood, output_dir)
    print(f"\nSeed: PMID {hood.pmid} ({hood.seed.year or 'n.d.'}) {hood.seed.title or ''}")
    print(_relation_summary("Similar", hood, "similar"))
    print(_relation_summary("Cited by", hood, "cited_by"))
    print(_relation_summary("References", hood, "references"))
    # The seed is always first in articles(); ELink never lists it as its own neighbor
    print(f"{'Neighborhood':<12}{len(hood.articles()) - 1:>5} unique articles fetched")
    for article in hood.articles():
        if article.is_retracted:
            print(f"[RETRACTED] PMID {article.pmid} ({article.year or 'n.d.'}) {article.title or ''}")
    print(f"Saved: {path}")
    print(f"Explore the graph: {hood.linked_discoveries_url}")

    if args.download:
        stats = download_neighborhood(
            hood,
            output_dir=output_dir,
            fmt=args.format,
            api_key=args.api_key,
            use_concurrent=not args.sequential,
            max_workers=args.workers,
            include_text=not args.exclude_text,
            user_agent=args.user_agent,
            email=args.email,
            rate_limit=args.rate_limit,
        )
        print(stats)

    vault_dir = _vault_dir(args, path.parent.name)
    if vault_dir is not None:
        return _update_vault(args, vault_dir, [path.parent])
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Configure logging.  --verbose enables DEBUG for this package only:
    # urllib3's DEBUG output includes request URLs, and with them the API key.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    if getattr(args, "verbose", False):
        logging.getLogger("pubmed_stream").setLevel(logging.DEBUG)

    if args.command == "download":
        stats = search_and_download(
            keyword=args.keyword,
            max_results=args.max_results,
            fmt=args.format,
            api_key=args.api_key,
            use_concurrent=not args.sequential,
            max_workers=args.workers,
            include_text=not args.exclude_text,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            user_agent=args.user_agent,
            email=args.email,
            rate_limit=args.rate_limit,
        )

        if stats.successful > 0 or (stats.skipped > 0 and stats.errors == 0):
            vault_dir = _vault_dir(args, stats.output_dir.name)
            if vault_dir is not None:
                return _update_vault(args, vault_dir, [stats.output_dir])
            return 0
        if stats.requested == 0:
            return 1
        return 2

    if args.command == "neighborhood":
        return _run_neighborhood(args)

    if args.command == "graph":
        return _run_graph(args)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
