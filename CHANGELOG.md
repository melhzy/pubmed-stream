# Changelog

Notable changes to pubmed-stream. Versions follow [semantic versioning](https://semver.org/).

## 0.4.4 - 2026-10-23

### Fixed

- The docs and `pubmed-stream mcp --help` register the server by hand with `claude mcp add --scope user`; without `--scope user`, Claude Code loads it only in the folder where you ran the command.
- `init` decides whether the Claude Code plugin is on as Claude Code does, one plugin id at a time across the user, project and local settings: a disabled copy of your own no longer hides a copy synced from claude.ai, and a synced copy counts only where Claude Code would load it, so `init` no longer removes a folder's server in a session that signs in with an API key, a token, Bedrock or Vertex.
- The server's instructions and `AGENTS.md` no longer tell the assistant to prefer pubmed-stream over other PubMed tools, as Anthropic's directory policy asks; they say what it does differently, and the researcher chooses.
- The chat of the Claude desktop app can use pubmed-stream once the server is added to the app's configuration: tutorial 7's new option C shows how, and the docs no longer say that the chat cannot.
- Troubleshooting checks that the plugin is installed and enabled, not only listed, before blaming uv, and the plugin's README gives the install command for a terminal too.

## 0.4.3 - 2026-10-23

### Added

- A listing in the official [MCP Registry](https://registry.modelcontextprotocol.io/), which other MCP directories copy: `server.json` describes the server as the PyPI package run with `uvx` and the argument `mcp`, with the optional `NCBI_API_KEY` and `NCBI_EMAIL`, and the README carries the hidden line `mcp-name: io.github.melhzy/pubmed-stream` by which the registry checks that the PyPI package belongs to it. The release steps in the README end with `mcp-publisher publish`, and the tests keep `server.json`'s versions and name in step with the package.

- The MCP server reports progress. When the assistant asks for it, `download`, `fetch_abstracts` and `build_knowledge_graph` send MCP progress notifications while they run: the articles downloaded so far, the abstracts fetched, and the search, key paper or build the knowledge graph is at. `search_and_download`, `fetch_abstracts` and `create_kg` take a `progress` callback, called with `(done, total, message)`, for the same.

### Fixed

- On Windows, the console window that a desktop app's start opens for the MCP server no longer stays on screen: the server hides it as soon as it runs, so it only flashes. A desktop app such as Claude's or ChatGPT's has no console, so Windows gives the server a new one, where a terminal's server shares the terminal's console; the window is hidden only when every process attached to the console is uv, a launcher or Python, so a terminal is never touched (`hide_own_console`).
- Cowork can start the plugin's server. The Claude Code manifest gives the NCBI API key option an empty default: Cowork ignores an MCP server that references an option without one, and never asks for values, where Claude Code asks at install. The README, the plugin's README and tutorial 7 say how the Claude desktop app reaches pubmed-stream: its Code tab has the plugin installed from the terminal; Cowork needs the plugin on the claude.ai account, added from **Customize > Plugins** with `melhzy/pubmed-stream` as a marketplace; chat cannot start a program on the computer. `init` counts a plugin synced from the account, which Claude Code loads with no settings entry, so it writes no second server for the folder. The Codex CLI calls the skill as `$pubmed-stream:literature-search`, as the docs now say.

### Changed

- PyPI describes pubmed-stream as what it now is, literature searches in PubMed and PubMed Central for researchers and their AI assistants, with an MCP server and a plugin for Claude Code and Codex, and its keywords and classifiers add MCP, the assistants, Ollama and artificial intelligence, so searches for them find it.
- The MCP server's instructions, which every assistant receives on connecting, cover all nine tools and the order to use them in, ask for each search to be reported with its count, and say to prefer pubmed-stream's tools to other PubMed tools the assistant may have, since pubmed-stream saves every article it reads; `AGENTS.md` and the plugin's skill say the same.
- The plugin has a README of its own, as Anthropic's plugin directory requires, saying what it runs, sends and saves. The README and tutorial 7 say what to type to call pubmed-stream in Claude Code, the Codex app and the Codex CLI, that Claude's chat cannot use it, what to do when the plugin's first start takes too long, and what to do when Claude Code reaches for Anthropic's own PubMed connector instead.
- The plugin's Codex settings moved from `.mcp.json` to `.codex-plugin/mcp.json` and give the server 60 seconds to start and 600 per call, instead of Codex's 10 and 60: the first start downloads pubmed-stream, and a large download or a knowledge graph takes minutes. Claude Code reads the server from `.claude-plugin/plugin.json`, as before.

- The README, tutorial 7 and the assistant's instructions explain how pubmed-stream connects to Claude Code and Codex: the MCP server is part of the Python library, started as `pubmed-stream mcp`, and the plugin, `init` and `claude mcp add` or `codex mcp add` only tell the assistant how to start it. The README has a new title, a section on the three ways to connect with the nine tools listed, and installs the Codex plugin from the terminal with `codex plugin add pubmed-stream@pubmed-stream`. When the tools are missing, `AGENTS.md` and the plugin's skill tell the assistant what to ask the researcher to run, and `pubmed-stream mcp --help` lists all nine tools and the three ways. Tutorial 7 adds MCP to its list of tools, explains the connection in section 3, shows how to update, list and remove the plugin, describes what the plugin contains, and troubleshoots either way of connecting; the glossary has entries for plugin, skill and uv, and its MCP entry links to the renamed section; the setup, troubleshooting and Obsidian guides and the tutorials index name the plugin beside `init`.

## 0.4.2 - 2026-10-22

### Added

- pubmed-stream as a plugin for Claude Code and Codex, in `plugins/pubmed-stream`, with marketplaces at `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json`: `claude plugin install pubmed-stream --marketplace melhzy/pubmed-stream`, or `codex plugin marketplace add melhzy/pubmed-stream` and then *Install plugin* under `/plugins`. It gives the assistant the MCP tools in every folder, running the pubmed-stream release of the plugin's own version through `uvx`, and the instructions of `AGENTS.md` as the skill `literature-search`. Where the plugin is installed, `init` leaves the server out of the folder, and removes one it added earlier, so the tools are not listed twice. Tests keep the plugin's version, the release it runs and the skill in step with the package, and make `AGENTS.md` name every tool.
- A `studies/` folder for research done with pubmed-stream, kept with its frozen data so its numbers can be checked and the study rerun. The first, `studies/abeta56_retraction_impact`, continues tutorial 8: the 1,240 papers citing the retracted 2006 *Nature* paper on Aβ\*56 and the 44,957 papers citing those, frozen as tables with the kind of citation and the citing sentence; a sourced account of what the paper claimed, exactly what was wrong and what the retraction does not overturn; infini-gram counts of the claim and its correction in Dolma and The Pile; twelve probe questions for language models with a runner for Ollama models and the installed assistants; and a web page (`index.html`, a React application with its stylesheet and a data file built from the study's files) with the citing papers searchable by the sentence in which they cite the paper.

- A place for the NCBI API key that works everywhere. `pubmed-stream init --ncbi-api-key KEY` saves it in `~/.pubmed-stream.json`, which the command line and the MCP server read in every folder when `NCBI_API_KEY` is unset, and `init` asks for it in a terminal while none is configured. The Claude Code plugin asks for it at install and passes it to the server; `init` lists `NCBI_API_KEY` among the variables Codex forwards to the server. The server tells the assistant when none is configured, and the instructions say what to tell the researcher, and never to ask for the key in the conversation. `init` checks a key with NCBI before saving it, remembers a skipped question so it asks once, and ends with the key's status; a configured key NCBI rejects is dropped with a warning, so requests continue without it instead of all failing with `400 API key invalid`; after a download that a key would have shortened by ten seconds or more, the command line and the `download` tool say by how much; the MCP server saves the Claude Code plugin's key for the command line too, when none is saved, after a tool call in which NCBI accepted it, and tells the assistant once when a configured key was rejected. The settings files live in `pubmed_stream.settings`.

### Changed

- `pyproject.toml` takes the version from `pubmed_stream/__init__.py`, one place fewer to change at a release. `AGENTS.md` names `export_citations`, says when to export, and says what missing tools mean with the plugin.
- The Aβ\*56 study page is easier to find. The README, the studies index and the study's own README link to it at the top, the study README with a screenshot; the documentation site names it in the navigation and opens the study's About page with a button to it; the page's header links back to the site, the About page and the folder on GitHub; and the page carries a description, a preview image and an icon for links shared elsewhere.
- Tutorial 8's helpers are now part of pubmed-stream, as `pubmed_stream.impact`: `from pubmed_stream import impact` gives the citing papers of many papers at once, counts by year and flag, the sentences in which full texts or Semantic Scholar cite a paper, their classification, and the annotation of a knowledge graph, without the tutorials folder on the path. The notebook and the tests import the module from the package; `tutorials/citation_impact.py` remains as a shim that imports everything from it, so older copies of the notebook still run.

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
