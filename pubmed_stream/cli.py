"""Command-line interface for pubmed-stream.

Installed as the ``pubmed-stream`` console script, or runnable via
``python -m pubmed_stream``.
"""

import argparse
import contextlib
import io
import json
import logging
import sys
import textwrap
from pathlib import Path
import requests

from . import __version__
from .downloader import (
    MAX_WORKERS,
    RATE_LIMIT_WITH_API_KEY,
    RATE_LIMIT_NO_API_KEY,
    search_and_download,
    search_pmc,
)
from .abstracts import count_pubmed, fetch_abstracts
from .corpus import list_articles, most_cited, select, short_id
from .export import FORMATS, export_citations
from .neighborhood import (
    Neighborhood,
    download_neighborhood,
    get_neighborhood,
    save_neighborhood,
)
from .kg import create_kg, record_study
from .vault import build_vault, topic_vault_dir

# --vault given without a folder: name the vault after the run's topic
_AUTO_VAULT = object()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pubmed-stream",
        description="Search PubMed Central, download full-text articles, map the evidence around "
                    "key papers, and build a study's knowledge graph.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""a typical literature search:
  pubmed-stream search '"gut microbiota"[Title] AND frailty[Title/Abstract]'   # size it first
  pubmed-stream download '"gut microbiota"[Title] AND frailty[Title/Abstract]' --max-results 30
  pubmed-stream list publications --abstracts                                 # read compactly
  pubmed-stream kg "gut microbiome frailty" -q '...' --seed 31319564          # link it all

Run 'pubmed-stream <command> --help' for each command's options.""",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    # Options shared by every subcommand that talks to NCBI
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
        "--quiet",
        action="store_true",
        help="Print only results and errors, not progress (useful for scripts and AI assistants)",
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
        "--output-dir",
        "-o",
        help="Base output directory for downloads (default: ./publications)",
    )
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

    # Options for building a knowledge graph (an Obsidian vault)
    vault = argparse.ArgumentParser(add_help=False)
    vault.add_argument(
        "--fulltext",
        action="store_true",
        help="Knowledge graph: put each article's full text into its note (default: abstract only)",
    )
    vault.add_argument(
        "--offline",
        action="store_true",
        help="Knowledge graph: do not fetch MeSH terms from PubMed; use only the cache",
    )
    # How download and neighborhood runs join a study's knowledge graph
    study = argparse.ArgumentParser(add_help=False)
    study.add_argument(
        "--topic",
        help="Add the results to the knowledge graph of this study topic, ./kg_<topic> "
             "(example: --topic 'gut microbiome frailty'; see 'pubmed-stream kg')",
    )
    study.add_argument(
        "--vault",
        metavar="DIR",
        nargs="?",
        const=_AUTO_VAULT,
        help="Add the results to the knowledge graph in DIR, or with no DIR to "
             "./kg_<download folder name>",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser(
        "search",
        parents=[common],
        help="Count a PMC search and list its newest matches, without downloading",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  pubmed-stream search '"gut microbiota"[Title] AND frailty[Title/Abstract]'
  pubmed-stream search 'gut microbiome frailty' --show 0      # size only
  pubmed-stream search '"gut microbiota"[Title]' --json

Check a search's size and read a sample of titles before downloading it.
Exits with 1 when the search finds nothing.""",
    )
    search.add_argument("query", help="PMC search query, with PubMed field tags such as [Title]")
    search.add_argument(
        "--show",
        type=int,
        default=10,
        metavar="N",
        help="How many of the newest matches to list (default: 10; 0 for the count only)",
    )
    search.add_argument("--json", action="store_true", help="Print the result as JSON")

    download = subparsers.add_parser(
        "download",
        parents=[common, fetch, study, vault],
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

    abstracts = subparsers.add_parser(
        "abstracts",
        parents=[common, study, vault],
        help="Search PubMed and save abstracts, including articles whose full text is not free in PMC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  pubmed-stream abstracts '"gut microbiota"[Title] AND frailty[Title/Abstract]' --max-results 200
  pubmed-stream abstracts 'frailty cytokines' --topic 'frailty cytokines'

PMC has the free full text of only part of the literature; PubMed has an
abstract for most of the rest. Abstracts are saved as
<output-dir>/<query>/PMID*.json, next to any full texts 'download' saved for
the same query, and 'list', 'review' and the knowledge graph read both. An
article saved both ways is shown with its full text. The newest matches
come first; re-running skips abstracts already saved.""",
    )
    abstracts.add_argument("query", help="PubMed search query, with field tags such as [Title]")
    abstracts.add_argument("--max-results", type=int, default=100,
                           help="Maximum number of abstracts, newest first (default: 100; at most 9,999)")
    abstracts.add_argument("--output-dir", "-o", help="Base output directory (default: ./publications)")

    listing = subparsers.add_parser(
        "list",
        help="List downloaded articles compactly: identifiers, year, journal, title, abstract",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  pubmed-stream list publications/gut_microbiota_Title_AND_frailty_Title_Abstract
  pubmed-stream list publications --abstracts
  pubmed-stream list publications --json --abstracts > corpus.jsonl
  pubmed-stream list publications --cited               # the works cited most
  pubmed-stream list publications --id 38686220 PMC10841011 --abstracts

Each article appears once, newest first, however many searches found it.
An article's full text is in the "text" field of its file.""",
    )
    listing.add_argument(
        "path",
        nargs="?",
        default="publications",
        help="A download folder, a folder of them, or one PMC*.json file (default: ./publications)",
    )
    listing.add_argument("--abstracts", action="store_true", help="Include each article's abstract")
    listing.add_argument("--limit", type=int, metavar="N", help="List only the newest N articles")
    listing.add_argument(
        "--id",
        nargs="+",
        metavar="ID",
        help="List only these articles, by PubMed ID or PMC ID",
    )
    listing.add_argument(
        "--cited",
        type=int,
        nargs="?",
        const=10,
        metavar="N",
        help="Instead, list the N works the articles cite most (default N: 10): the corpus's "
             "foundations, and good key papers for 'neighborhood' or 'kg --seed'",
    )
    listing.add_argument("--json", action="store_true", help="Print one JSON object per line")

    export = subparsers.add_parser(
        "export",
        help="Export downloaded articles as BibTeX or RIS citations, for Zotero, EndNote or Mendeley",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  pubmed-stream export publications -o review.bib
  pubmed-stream export publications --format ris -o review.ris
  pubmed-stream export publications --id 38686220 41113141 -o chosen.bib

Every reference manager imports BibTeX and RIS: in Zotero, File > Import.
Entries have the title, authors, journal, year, DOI, PubMed and PMC IDs, a
link and the abstract, for full texts and saved abstracts alike. The first
word of each author name is taken as the surname, so check multi-word
surnames such as "van der Berg" after importing.""",
    )
    export.add_argument("path", nargs="?", default="publications",
                        help="A download folder, a folder of them, or one article file (default: ./publications)")
    export.add_argument("--format", choices=FORMATS, default="bibtex", help="Citation format (default: bibtex)")
    export.add_argument("--id", nargs="+", metavar="ID", help="Export only these articles, by PubMed ID or PMC ID")
    export.add_argument("--output", "-o", metavar="FILE", help="Write to FILE instead of printing")

    review_p = subparsers.add_parser(
        "review",
        help="Summarize downloaded abstracts with a local model (Ollama) or an AI assistant (Claude Code, "
             "Codex, Gemini CLI), and check its numbers and citations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  pubmed-stream review "Does FMT help Parkinson's disease?" --id 38686220 41826284 38057970
  pubmed-stream review "What is known about X?" --limit 10 --answer --vault kg_x
  pubmed-stream review "What is known about X?" --limit 10 --model qwen3.5:9b
  pubmed-stream review "What is known about X?" --limit 10 --model claude
  pubmed-stream review "What is known about X?" --limit 10 --model codex

--model chooses who summarizes:
  a local model in Ollama (https://ollama.com): nothing leaves your computer.
    Download it first: ollama pull qwen3.5:9b. The default is Llama 3.2 1B:
    ollama pull hf.co/unsloth/Llama-3.2-1B-Instruct-GGUF:Q4_K_M
  claude, codex or gemini: the AI assistant installed and signed in on this
    computer, with its tools turned off. Larger models, fewer mistakes, but
    the abstracts go to Anthropic, OpenAI or Google. Add the assistant's own
    model after a colon: claude:opus, codex:<model>, gemini:<model>.
The model reads one abstract at a time, without the question; pubmed-stream
attaches each PubMed ID itself and flags numbers a summary adds. Exits with 1
when the answer cites an article that was not read, 2 when the model fails.""",
    )
    review_p.add_argument("question", help="The research question, in plain language")
    review_p.add_argument("--path", default="publications", help="Downloaded articles (default: ./publications)")
    review_p.add_argument("--id", nargs="+", metavar="ID", help="Summarize these articles, by PubMed ID or PMC ID")
    review_p.add_argument("--limit", type=int, default=10, help="Without --id, the newest N articles (default: 10)")
    review_p.add_argument("--model", help="An Ollama model, or claude, codex or gemini (default: the folder's "
                                         "review model from 'init --review-model', else Llama 3.2 1B Instruct, "
                                         "Unsloth's 4-bit GGUF, in Ollama)")
    review_p.add_argument("--answer", action="store_true",
                          help="Also write one answer from all the summaries (experimental with small models)")
    review_p.add_argument("--out", help="Also save the review as this Markdown file")
    review_p.add_argument("--vault", metavar="DIR",
                          help="Also save it as a note in this knowledge graph's reviews folder")
    review_p.add_argument("--num-ctx", type=int, default=8192,
                          help="The model's working memory in tokens (default: 8192)")
    review_p.add_argument("--ollama-host", help="Ollama's address (default: OLLAMA_HOST, or http://127.0.0.1:11434)")

    init = subparsers.add_parser(
        "init",
        help="Prepare a research folder for Claude Code, Codex and Gemini CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Writes AGENTS.md (the instructions; CLAUDE.md and GEMINI.md import it),
.mcp.json (Claude Code), .codex/config.toml (Codex) and .gemini/settings.json
(Gemini CLI), which start pubmed-stream's MCP server. Existing files are kept, and settings are added
to them. Where the pubmed-stream plugin is installed, Claude Code's or Codex's settings get no server,
because the plugin provides it in every folder. While no NCBI API key is configured, init asks for one, which
makes everything about three times faster, and saves it for every folder in ~/.pubmed-stream.json.
Then start your assistant in the folder: claude, codex or gemini.""",
    )
    init.add_argument("folder", nargs="?", default=".", help="The research folder (default: the current folder)")
    init.add_argument("--force", action="store_true", help="Rewrite AGENTS.md with the current instructions")
    init.add_argument("--claude-model", metavar="MODEL",
                      help="Claude Code's model in this folder, such as opus or sonnet (.claude/settings.json)")
    init.add_argument("--review-model", metavar="MODEL",
                      help="The model 'pubmed-stream review' uses in this folder: an Ollama model, or claude, "
                           "codex or gemini (.pubmed-stream.json)")
    init.add_argument("--ncbi-api-key", metavar="KEY",
                      help="Your NCBI API key, saved for every folder in ~/.pubmed-stream.json")

    open_p = subparsers.add_parser(
        "open",
        help="Open a knowledge graph in Obsidian",
        description="Open a knowledge graph's home note in Obsidian. Obsidian must know the folder as a "
                    "vault: add it once with Open folder as vault.",
    )
    open_p.add_argument("kg_dir", nargs="?", help="The kg_<topic> folder (default: the only one here)")

    mcp = subparsers.add_parser(
        "mcp",
        help="Run as an MCP server, so Claude Code, Codex and other AI assistants can call pubmed-stream's tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Started by the AI assistant, not by you. Connect it in one of three ways:
  the plugin, for Claude Code or Codex in every folder (needs uv):
    claude plugin install pubmed-stream --marketplace melhzy/pubmed-stream
    codex plugin marketplace add melhzy/pubmed-stream
    codex plugin add pubmed-stream@pubmed-stream
  'pubmed-stream init', for Claude Code, Codex or Gemini CLI in one research folder
  by hand, for every folder:
    claude mcp add --scope user pubmed-stream -- pubmed-stream mcp
    codex mcp add pubmed-stream -- pubmed-stream mcp

Tools: search_pmc, download, fetch_abstracts, list_articles, most_cited,
read_article, neighborhood, export_citations, build_knowledge_graph.
Messages are JSON-RPC on standard input and output; logs go to standard
error.""",
    )
    mcp.add_argument("--root", help="Folder that relative paths refer to (default: the current folder)")

    neighborhood = subparsers.add_parser(
        "neighborhood",
        parents=[common, fetch, study, vault],
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

    kg = subparsers.add_parser(
        "kg",
        parents=[common, fetch, vault],
        help="Build the knowledge graph of a study: searches, neighborhoods and "
             "downloads linked in an Obsidian vault",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  pubmed-stream kg "gut microbiome frailty" -q "gut microbiome frailty" -q "microbiome sarcopenia"
  pubmed-stream kg "gut microbiome frailty" --seed 35803947 --max-per-relation 30
  pubmed-stream kg "gut microbiome frailty" --add ./publications/old_query
  pubmed-stream kg "gut microbiome frailty" --refresh
  pubmed-stream kg "gut microbiome frailty"

The graph is the folder ./kg_<topic>; open it in Obsidian as a vault. It has
one note per paper, MeSH concept and collection, linked by citations,
similarity and topic. The study's searches and seeds are remembered:
--refresh runs them all again to pick up new papers, and with no options the
graph is rebuilt from what the study already has. Rebuilding keeps anything
written outside the generated %% pubmed-stream %% block.""",
    )
    kg.add_argument(
        "topic",
        help="Study topic (example: 'gut microbiome frailty'); names the graph ./kg_<topic>",
    )
    kg.add_argument(
        "--query",
        "-q",
        action="append",
        default=[],
        metavar="QUERY",
        help="PubMed search to download into the study (repeatable)",
    )
    kg.add_argument(
        "--seed",
        "-s",
        action="append",
        default=[],
        metavar="PMID",
        help="Key article whose evidence neighborhood joins the study (repeatable)",
    )
    kg.add_argument(
        "--add",
        action="append",
        default=[],
        metavar="DIR",
        help="Folder or file downloaded earlier to add to the study (repeatable)",
    )
    kg.add_argument(
        "--refresh",
        action="store_true",
        help="Run every search and neighborhood of the study again to pick up new papers",
    )
    kg.add_argument(
        "--open",
        action="store_true",
        help="Open the knowledge graph in Obsidian afterwards (Obsidian must know it as a vault)",
    )
    kg.add_argument(
        "--max-results",
        type=int,
        default=100,
        help="Maximum articles per search (default: 100)",
    )
    kg.add_argument(
        "--max-per-relation",
        type=int,
        default=100,
        help="Maximum similar, citing and cited articles per seed (default: 100)",
    )
    kg.add_argument(
        "--download-neighbors",
        action="store_true",
        help="Download PMC full text of neighborhood articles too (default: stub notes)",
    )
    kg.add_argument(
        "--abstracts",
        action="store_true",
        help="Also save PubMed abstracts for each search, so articles without free full text join the graph",
    )
    kg.add_argument(
        "--kg-dir",
        metavar="DIR",
        help="Graph folder, instead of ./kg_<topic>",
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


def _update_vault(args: argparse.Namespace, vault_dir: Path, sources, queries=(), seeds=()) -> int:
    """Add a run to the knowledge graph in *vault_dir*; returns an exit code."""
    try:
        # Recorded in the study, so 'kg --refresh' runs them again
        record_study(vault_dir, args.topic, queries=queries, seeds=seeds)
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


def _run_kg(args: argparse.Namespace) -> int:
    try:
        with _progress(args):
            result = create_kg(
                args.topic,
                queries=args.query,
                seeds=args.seed,
                sources=args.add,
                refresh=args.refresh,
                max_results=args.max_results,
                max_per_relation=args.max_per_relation,
                download_neighbors=args.download_neighbors,
                abstracts=args.abstracts,
                kg_dir=args.kg_dir,
                output_dir=args.output_dir,
                fmt=args.format,
                include_text=not args.exclude_text,
                use_concurrent=not args.sequential,
                max_workers=args.workers,
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
        print(f"Error: could not write the knowledge graph: {e}", file=sys.stderr)
        return 2
    print(result)
    if args.open and result.kg_dir is not None:
        _run_open(result.kg_dir)
    return 2 if result.errors else 0


def _progress(args: argparse.Namespace):
    """Hide the download progress the library prints, under --quiet."""
    if getattr(args, "quiet", False):
        return contextlib.redirect_stdout(io.StringIO())
    return contextlib.nullcontext()


def _run_search(args: argparse.Namespace) -> int:
    try:
        result = search_pmc(
            args.query,
            max_results=max(args.show, 0),
            api_key=args.api_key,
            user_agent=args.user_agent,
            email=args.email,
            rate_limit=args.rate_limit,
        )
    except requests.RequestException as e:
        print(f"Error: could not reach NCBI: {e}", file=sys.stderr)
        return 2
    try:
        in_pubmed = count_pubmed(args.query, api_key=args.api_key, rate_limit=args.rate_limit)
    except (requests.RequestException, KeyError, ValueError):
        in_pubmed = None
    if args.json:
        print(json.dumps({"query": result.query, "total_found": result.total_found, "pubmed_total": in_pubmed,
                          "articles": result.articles}, ensure_ascii=False, indent=1))
    else:
        print(result)
        if in_pubmed is not None and in_pubmed > result.total_found:
            print(f"\n{in_pubmed:,} articles in PubMed: 'pubmed-stream abstracts' saves the abstracts of "
                  "those without free full text")
    return 0 if result.total_found or in_pubmed else 1


def _run_abstracts(args: argparse.Namespace) -> int:
    try:
        stats = fetch_abstracts(
            args.query,
            max_results=args.max_results,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            api_key=args.api_key,
            user_agent=args.user_agent,
            email=args.email,
            rate_limit=args.rate_limit,
        )
    except requests.RequestException as e:
        print(f"Error: could not reach NCBI: {e}", file=sys.stderr)
        return 2
    print(stats)
    if not stats.requested:
        return 1
    vault_dir = _vault_dir(args, stats.output_dir.name)
    if vault_dir is not None:
        return _update_vault(args, vault_dir, [stats.output_dir])
    return 0


def _run_list(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        print(f"Error: {path} does not exist", file=sys.stderr)
        return 1
    records = list_articles(path)
    if not records:
        print(f"No downloaded articles in {path}", file=sys.stderr)
        return 1
    if args.cited is not None:
        works = most_cited(path, args.cited)
        if args.json:
            for work in works:
                print(json.dumps(work, ensure_ascii=False))
            return 0
        print(f"Works cited most by the {len(records)} articles in {path}:")
        for w in works:
            ref = f"PMID {w['pmid']}" if w["pmid"] else f"DOI {w['doi']}"
            print(f"  cited by {w['cited_by']:<3} {ref:<14} {w['year'] or 'n.d.'}  {w['title'] or ''}")
        return 0
    if args.id:
        records, missing = select(records, args.id)
        if missing:
            print(f"Not downloaded under {path}: {', '.join(missing)}", file=sys.stderr)
        if not records:
            return 1
    shown = records[:args.limit] if args.limit is not None else records
    if args.json:
        for record in shown:
            if not args.abstracts:
                record = {k: v for k, v in record.items() if k != "abstract"}
            print(json.dumps(record, ensure_ascii=False))
        return 0
    count = f"newest {len(shown)} of {len(records)}" if len(shown) < len(records) else str(len(records))
    print(f"{count} articles in {path}")
    for r in shown:
        pmid = f"PMID {r['pmid']}" if r["pmid"] else "no PMID"
        journal = f" ({r['journal']})" if r["journal"] else ""
        size = f"{r['words']:,} words" if r["full_text"] else "abstract only"
        print(f"{r['year'] or 'n.d.'}  {short_id(r):<12} {pmid:<14} {r['title'] or ''}{journal} [{size}]")
        if args.abstracts and r["abstract"]:
            print(textwrap.fill(r["abstract"], width=100, initial_indent="      ", subsequent_indent="      "))
    return 0


def _run_export(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        print(f"Error: {path} does not exist", file=sys.stderr)
        return 1
    text, count, missing = export_citations(path, args.format, args.id)
    if missing:
        print(f"Not downloaded under {path}: {', '.join(missing)}", file=sys.stderr)
    if not count:
        print(f"No articles to export in {path}", file=sys.stderr)
        return 1
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"Wrote {count} citations to {args.output}")
    else:
        sys.stdout.write(text)
    return 0


def _run_open(kg_dir) -> int:
    from .obsidian import open_vault

    if kg_dir is None:
        found = sorted(p for p in Path.cwd().glob("kg_*") if p.is_dir())
        if len(found) != 1:
            print("Error: name the knowledge graph folder: " + (", ".join(p.name for p in found) or "none here"),
                  file=sys.stderr)
            return 1
        kg_dir = found[0]
    opened, message = open_vault(kg_dir)
    print(message, file=sys.stdout if opened else sys.stderr)
    return 0 if opened else 1


def _run_review(args: argparse.Namespace) -> int:
    from .assistants import review_model
    from .review import DEFAULT_MODEL, ModelError, review, save_to_vault

    try:
        result = review(args.question, path=args.path, ids=args.id, limit=args.limit,
                        model=args.model or review_model() or DEFAULT_MODEL, answer=args.answer, host=args.ollama_host,
                        num_ctx=args.num_ctx)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ModelError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    print(result)
    if args.out:
        Path(args.out).write_text(str(result) + "\n", encoding="utf-8")
        print(f"\nSaved {args.out}", file=sys.stderr)
    if args.vault:
        print(f"Saved {save_to_vault(result, args.vault)}", file=sys.stderr)
    return 1 if result.not_read else 0


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
        with _progress(args):
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
        return _update_vault(args, vault_dir, [path.parent], seeds=[hood.pmid])
    return 0


def _utf8_output() -> None:
    """Write UTF-8 when output is piped or redirected.

    Article titles hold Greek letters and accents that Windows' default
    encoding for pipes cannot represent, which would stop the command.
    """
    for stream in (sys.stdout, sys.stderr):
        if not hasattr(stream, "reconfigure"):
            continue
        if stream.isatty():
            stream.reconfigure(errors="replace")
        else:
            stream.reconfigure(encoding="utf-8")


def _interactive() -> bool:
    """Whether a person is at the terminal, so a command may ask a question."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def main() -> int:
    _utf8_output()
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
    elif getattr(args, "quiet", False):
        logging.getLogger("pubmed_stream").setLevel(logging.ERROR)

    if args.command == "mcp":
        from .mcp_server import serve

        logging.getLogger("pubmed_stream").setLevel(logging.WARNING)
        serve(Path(args.root) if args.root else None)
        return 0

    if args.command == "search":
        return _run_search(args)

    if args.command == "open":
        return _run_open(args.kg_dir)

    if args.command == "init":
        from .assistants import init_folder
        from .downloader import api_key_status, check_api_key, configured_api_key
        from .settings import NCBI_API_KEY_SETTING, read_settings, set_setting, user_settings_file

        key = args.ncbi_api_key
        asked_before = NCBI_API_KEY_SETTING in read_settings(user_settings_file())
        if key is None and not configured_api_key() and not asked_before and _interactive():
            print("A free NCBI API key makes searches and downloads about three times faster. Create one under\n"
                  "API Key Management in the settings of your NCBI account, https://account.ncbi.nlm.nih.gov/settings/,\n"
                  "and paste it here; it is saved for every folder. Or press Enter to skip, and add it later with\n"
                  "pubmed-stream init --ncbi-api-key YOUR-KEY.")
            try:
                key = input("NCBI API key: ").strip() or None
            except EOFError:
                key = None
            if key is None:
                # remember the answer, so that init does not ask again in the next folder
                try:
                    set_setting(user_settings_file(), NCBI_API_KEY_SETTING, "")
                except ValueError as e:
                    print(f"Warning: {e}", file=sys.stderr)
            print()
        if key:
            verdict = check_api_key(key)
            if verdict == "invalid":
                print("NCBI rejected this key (API key invalid), so it was not saved. Check it for missing characters "
                      "in the settings of your NCBI account, and try again.", file=sys.stderr)
                if args.ncbi_api_key:
                    return 1
                key = None
            elif verdict == "ok":
                print("NCBI accepted the key.")
            else:
                print("NCBI could not be reached to check the key; it is saved anyway.")
        try:
            actions = init_folder(args.folder, force=args.force, claude_model=args.claude_model,
                                  review_model=args.review_model, ncbi_api_key=key)
        except ValueError as e:         # a settings file that is not valid JSON
            print(f"Error: {e}. Fix or delete the file, then run init again.", file=sys.stderr)
            return 1
        for name, action in actions:
            print(f"{action:>8}  {Path(args.folder) / name}")
        if any(action == "plugin" for _, action in actions):
            print("\n  plugin: the pubmed-stream plugin gives that assistant the tools in every folder, so this "
                  "file has no pubmed-stream server of its own.")
        notes = [] if dict(actions).get(".mcp.json") == "plugin" else [
            "Claude Code asks once to approve the pubmed-stream server"]
        notes.append("in Codex and Gemini CLI, /mcp lists its tools")
        sentence = "; ".join(notes)
        print(f"\nNCBI API key: {api_key_status()}")
        print(f"\nStart your assistant in this folder: claude, codex or gemini. {sentence[0].upper()}{sentence[1:]}.")
        return 0

    if args.command == "review":
        return _run_review(args)

    if args.command == "list":
        return _run_list(args)

    if args.command == "export":
        return _run_export(args)

    if args.command == "download":
        with _progress(args):
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
        if args.quiet:
            print(stats)
        else:
            from .downloader import api_key_hint

            # failed includes unavailable; with a chosen rate, the hint's arithmetic would not apply
            hint = api_key_hint(stats.successful + stats.failed, stats.duration_seconds)
            if hint and args.rate_limit is None:
                print(f"\n{hint}")

        if stats.successful > 0 or (stats.skipped > 0 and stats.errors == 0):
            vault_dir = _vault_dir(args, stats.output_dir.name)
            if vault_dir is not None:
                return _update_vault(args, vault_dir, [stats.output_dir], queries=[args.keyword])
            return 0
        if stats.requested == 0:
            return 1
        return 2

    if args.command == "abstracts":
        return _run_abstracts(args)

    if args.command == "neighborhood":
        return _run_neighborhood(args)

    if args.command == "kg":
        return _run_kg(args)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
