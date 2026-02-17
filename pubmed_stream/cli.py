"""Command-line interface for pubmed-stream.

Installed as the ``pubmed-stream`` console script, or runnable via
``python -m pubmed_stream``.
"""

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .downloader import (
    MAX_WORKERS,
    RATE_LIMIT_WITH_API_KEY,
    RATE_LIMIT_NO_API_KEY,
    search_and_download,
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

    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser(
        "download",
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
    download.add_argument(
        "--format",
        choices=["text", "xml", "both", "json", "txt"],
        default="text",
        help="Output format (all save as .json): 'text' (default, JSON with metadata+text field), "
             "'xml' (JSON with metadata+xml field), 'both' (JSON with both xml and text fields). "
             "Legacy: 'json'/'txt' (mapped to 'text')",
    )
    download.add_argument(
        "--api-key",
        help="Override NCBI API key (otherwise uses NCBI_API_KEY env var)",
    )
    download.add_argument(
        "--sequential",
        action="store_true",
        help="Use sequential downloads instead of concurrent",
    )
    download.add_argument(
        "--workers",
        type=int,
        default=MAX_WORKERS,
        help=f"Number of concurrent worker threads (default: {MAX_WORKERS})",
    )
    download.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )
    download.add_argument(
        "--exclude-text",
        action="store_true",
        help="Exclude plain-text field in JSON output to save space",
    )
    download.add_argument(
        "--output-dir",
        "-o",
        help="Base output directory for downloads (default: ./publications)",
    )
    download.add_argument(
        "--user-agent",
        help="Override HTTP User-Agent header",
    )
    download.add_argument(
        "--email",
        help="Email address for NCBI contact (or NCBI_EMAIL env var)",
    )
    download.add_argument(
        "--rate-limit",
        type=float,
        help=f"Minimum seconds between HTTP requests (auto: {RATE_LIMIT_WITH_API_KEY}s with API key, "
             f"{RATE_LIMIT_NO_API_KEY}s without)",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if getattr(args, "verbose", False) else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

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

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
