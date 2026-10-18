# Changelog

Notable changes to pubmed-stream. Versions follow [semantic versioning](https://semver.org/).

## Unreleased

### Added

- A `tutorials/` folder for researchers without programming experience, replacing `examples/`. Tutorial 0 takes a research question to a knowledge graph, a reading list and a list of gaps in one afternoon; tutorials 1 to 6 cover each step in depth. Every notebook has one settings cell and runs in Google Colab.
- Guides: setting up from zero, reading a knowledge graph in Obsidian, a glossary, what pubmed-stream can and cannot do, and troubleshooting.
- The `tutorials` install extra: `pip install "pubmed-stream[tutorials]"`.
- `LICENSE`, `CITATION.cff` and this changelog.
- `pubmed-stream search` counts a search and lists its newest matches without downloading (`search_pmc`, `esummary_pmc`).
- `pubmed-stream list` prints downloaded articles compactly, each once, with `--abstracts`, `--id`, `--limit` and `--json`; `--cited` lists the works they cite most (`list_articles`, `most_cited`).
- `--quiet` prints only results and errors, not progress.
- `pubmed-stream mcp`, an MCP server that gives Claude Code, Codex and other AI assistants seven tools: `search_pmc`, `download`, `list_articles`, `most_cited`, `read_article`, `neighborhood` and `build_knowledge_graph`.
- `pubmed-stream init` prepares a research folder for Claude Code, Codex and Gemini CLI: instructions in `AGENTS.md`, imported by `CLAUDE.md` and `GEMINI.md`, and MCP settings in `.mcp.json` and `.codex/config.toml` (`init_folder`). `--claude-model` and `--review-model` choose Claude Code's model and the local review model for the folder; `review` uses the folder's model when `--model` is not given.
- `pubmed-stream review` summarizes chosen abstracts with a local model through Ollama, at temperature 0, attaches each PubMed ID itself, flags numbers the abstracts do not contain and citations of articles not read, and can save the review as a note in a knowledge graph (`review`, `save_to_vault`).
- Knowledge graphs get Obsidian property types (`.obsidian/types.json`) and `Papers.base`, a Bases table with views for all papers, full texts, reviews, retracted papers and the `#to-read` list, embedded in the home note. Existing types and an edited base are kept.
- `pubmed-stream open`, and `kg --open`, open a knowledge graph in Obsidian (`open_vault`).
- `tutorials/tools/session_figures.py` charts a research folder's session: its searches, papers by year, most cited works, kinds of evidence and the key paper's neighborhood.
- Tutorial 7, a step-by-step guide for medical students and biologists who have never programmed: installing Claude Code or Codex, choosing a model, asking questions, checking the evidence, Obsidian and private local models, built on real sessions with Claude Code, Codex and a local Llama 3.2 1B model.

### Changed

- The README is rewritten as one guide, from downloading to building a knowledge graph.

### Fixed

- Commands no longer stop with a `UnicodeEncodeError` on Windows when their output is piped or redirected: they write UTF-8.
- Download folder names longer than 100 characters are shortened and end with a hash of the search, so paths stay within Windows' default limit. A search that long downloads into a new folder the next time it runs.

### Removed

- `test_download.ipynb` and `check_files.py` from the repository root. Tutorials 1 and 2 cover what they demonstrated, and `tutorials/tools/manage_text_field.py check` replaces the file check.

## 0.2.0 - 2026-10-18

### Added

- Knowledge graphs of a study: `create_kg` and `pubmed-stream kg TOPIC` collect searches and key papers into an Obsidian vault, `kg_<topic>`, with linked notes for papers, MeSH concepts and collections.
- Studies are recorded in the vault, so `--refresh` reruns every search and key paper and adds new papers. `load_study` and `record_study` read and write the record.
- `build_vault` and `topic_vault_dir`, and `--vault` and `--topic` options on `download` and `neighborhood`.
- Downloaded articles keep their reference lists in `metadata.references`, and each download folder records its search in `query.json`.
- Neighborhood articles carry their MeSH headings, with major topics marked.
- An architecture guide in `docs/`.

## 0.1.1 - 2026-10-18

### Added

- Evidence neighborhoods of a paper, like NLM's Linked Discoveries: `get_neighborhood`, `save_neighborhood`, `download_neighborhood` and `pubmed-stream neighborhood`. They list similar, citing and cited papers, flag reviews, retractions and NIH funding, and count all linked papers beyond the fetch limit.
- PyPI release instructions in the README.

### Fixed

- Articles whose publisher withholds the full text are reported as unavailable, instead of being saved without text.
- The `text` field is built from the title, abstract and body, one paragraph per line, with entities decoded and references left out. `extract_text_from_pmc_xml` is now public.
- API keys are removed from logged request errors.
- Neighborhood review counts match the per-article review flag; PubMed's broader review filter also counted guidelines and most meta-analyses.

## 0.1.0 - 2026-02-17

First release on PyPI: search PubMed Central and download full-text articles as JSON, in `text`, `xml` or `both` formats, with concurrent downloads within NCBI's rate limits, from Python or the command line.
