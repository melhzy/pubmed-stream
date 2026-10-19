# Changelog

Notable changes to pubmed-stream. Versions follow [semantic versioning](https://semver.org/).

## 0.4.1 - 2026-10-19

### Added

- `pubmed-stream review --model claude`, `codex` or `gemini` has Claude Code, Codex or Gemini CLI summarize instead of a model in Ollama, optionally with its own model, as in `claude:opus`. The assistant runs in an empty folder with its tools turned off, up to four abstracts at once; everything else is as with Ollama, and the note records which assistant wrote it and which company received the abstracts. `init --review-model` accepts them too.

### Changed

- Review notes in a knowledge graph are named after the question, the date and the model, so reviews of one question by several models no longer replace each other. Notes by an assistant are tagged `pubmed/assistant-review`; the graph's home note lists all of them under "Reviews".
- `review` exits with 2 when any model fails, not only Ollama; `ModelError` is the common base of `OllamaError` and the new `AssistantError`.

## 0.4.0 - 2026-10-19

### Added

- PubMed abstracts for articles whose full text is not free in PMC: `pubmed-stream abstracts`, `fetch_abstracts()` and the MCP tool `fetch_abstracts` save each match's PubMed record as `PMID*.json`, next to the full texts of the same search. `list`, `review`, the MCP tools and the knowledge graph read both, and an article saved both ways is shown with its full text. `list` marks abstracts `[abstract only]`; in a knowledge graph their notes have the status `abstract`, with PubMed's MeSH terms and publication types. `kg --abstracts` saves them for each search of a study.
- `pubmed-stream search` and the MCP tool `search_pmc` also report how many articles PubMed has, so you can see how much the PMC full texts leave out (`count_pubmed()`).
- Citation export: `pubmed-stream export`, `export_citations()` and the MCP tool `export_citations` write the downloaded articles and abstracts as BibTeX or RIS, for Zotero, EndNote, Mendeley or LaTeX.
- Stub notes in a knowledge graph show the paper's abstract, from PubMed.

### Changed

- pubmed-stream needs Python 3.9 or later. Python 3.8 no longer receives security updates, and pubmed-stream could not be installed from source on it.
- The instructions `pubmed-stream init` writes tell assistants to save abstracts when PubMed has many more articles than PMC, and to say which articles they read only as abstracts.

## 0.3.3 - 2026-10-19

### Added

- The README's quick start shows how to install Claude Code, Codex or Gemini CLI, set up a research folder and ask a first question.

### Fixed

- `pubmed-stream init` did not give Gemini CLI pubmed-stream's tools: it wrote Gemini's instructions but not its MCP settings. It now writes `.gemini/settings.json` too.

## 0.3.2 - 2026-10-19

### Added

- A GitHub Actions workflow that runs the tests on Python 3.8 to 3.13, on Linux and Windows, and the linter on every push and pull request. The linter's rules are now set in `pyproject.toml`, so `ruff check .` checks the same rules everywhere.
- The README explains how to use any Ollama model with `pubmed-stream review`, with suggested models for each size of computer, and its quick start includes a local review.

### Changed

- `pubmed-stream review` no longer shows the question to the model while it summarizes each abstract. Given the question, small models opened summaries with it restated as a finding ("The gut microbiota is linked to frailty.") even for papers that did not test it. Summaries now start with the kind of study and what it studied. The question is still used for `--answer`.
- Tutorial 7 reports how the local model did with the new summaries, with a new screenshot, and that its summaries can change after Ollama reloads the model.

### Fixed

- On Windows with Python 3.8 or 3.9, `pubmed-stream kg` and `pubmed-stream vault` given a folder that did not exist yet kept a relative path for it.
- Tutorial 8's helpers failed on Python 3.8 and 3.9 when writing notes and the table of citing papers.
- `pubmed-stream review` with a model that thinks before answering, such as Qwen3, spent the summary's length limit on thinking and cut the summary short. Thinking is now turned off.
- A summary cut at its length limit was flagged for the number in its own "[cut at 300 tokens]" note.
- Removed unused imports from tutorials 3 and 6.

## 0.3.1 - 2026-10-19

### Added

- A documentation site, https://melhzy.github.io/pubmed-stream/, built from the README, the tutorials, the guides and the changelog, with the notebooks shown with their results. GitHub Actions publishes it on every push to `main`.
- A Documentation link on the PyPI page.
- Tutorial 8, measuring the impact of a retracted paper: the 2006 *Nature* paper on Aβ\*56, retracted in 2024, followed through the papers citing it and the papers citing those, with the sentence in which each citing paper cites it, read from the full text or, where publishers withhold it, from Semantic Scholar, a list of citations worth a second look, a table of every citation since the retraction, and a knowledge graph with a table of the citing papers by kind of citation. Its helpers are in `tutorials/citation_impact.py` and its charts in `tutorials/impact_charts.py`, and the graph from the saved run is in `tutorials/knowledge_graphs/`, ready to open in Obsidian.

## 0.3.0 - 2026-10-18

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
