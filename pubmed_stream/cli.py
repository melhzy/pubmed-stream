"""Command-line interface for pubmed-stream.

Installed as the ``pubmed-stream`` console script, or runnable via
``python -m pubmed_stream``.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List

import requests

from . import __version__
from .downloader import (
    MAX_WORKERS,
    RATE_LIMIT_WITH_API_KEY,
    RATE_LIMIT_NO_API_KEY,
    search_and_download,
)
from .neighborhood import (
    RelatedArticle,
    download_neighborhood,
    get_neighborhood,
    save_neighborhood,
)


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

    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser(
        "download",
        parents=[common, fetch],
        help="Search PMC and download full-text articles",
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
        parents=[common, fetch],
        help="Show similar, citing and cited articles of a PubMed article "
             "(like NLM Linked Discoveries)",
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

    return parser


def _relation_summary(label: str, articles: List[RelatedArticle], total: int) -> str:
    # "10 of 489" when --max-per-relation cut the list short
    count = f"{len(articles):>5}" + (f" of {total:<6}" if total > len(articles) else " " * 10)
    return (
        f"{label:<12}{count}  ("
        f"{sum(a.is_review for a in articles)} reviews, "
        f"{sum(a.is_retracted for a in articles)} retracted, "
        f"{sum(a.nih_funded for a in articles)} NIH-funded, "
        f"{sum(a.pmcid is not None for a in articles)} in PMC)"
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
    print(_relation_summary("Similar", hood.similar, hood.totals["similar"]))
    print(_relation_summary("Cited by", hood.cited_by, hood.totals["cited_by"]))
    print(_relation_summary("References", hood.references, hood.totals["references"]))
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

        if stats.successful > 0:
            return 0
        if stats.skipped > 0 and stats.errors == 0:
            return 0
        if stats.requested == 0:
            return 1
        return 2

    if args.command == "neighborhood":
        return _run_neighborhood(args)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
