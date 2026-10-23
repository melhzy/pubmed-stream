# pubmed-stream

Literature searches in PubMed and PubMed Central (PMC), with every claim cited by PubMed ID.

Ask a research question in plain language, such as *Does fecal microbiota transplantation help people with Parkinson's disease? Find the clinical evidence and summarize it, with PMIDs.* The assistant sizes the search before downloading, downloads the free full texts and the abstracts of the rest, reads them compactly, maps the papers around a key paper with retractions flagged, and writes a report that cites only papers it read, says what kind of evidence each is, lists the searches with their counts, and names what it could not read. It can export the papers for Zotero, EndNote or Mendeley, and link a study's searches and key papers into an [Obsidian](https://obsidian.md) knowledge graph.

## Install

Inside Claude Code, or in a terminal with `claude` in front:

```
/plugin install pubmed-stream --marketplace melhzy/pubmed-stream
```

## What the plugin contains

- **Nine MCP tools**: `search_pmc`, `download`, `fetch_abstracts`, `list_articles`, `most_cited`, `read_article`, `neighborhood`, `export_citations` and `build_knowledge_graph`. Each returns compact text, so the assistant scans dozens of papers in a few thousand tokens.
- **One skill**, `literature-search`, with the rules above. In Claude Code type `/pubmed-stream` and choose it; in Cowork type `/` and choose *literature-search*; or simply ask about the literature.

## What it runs, sends and saves

The plugin holds no program of its own. It starts the MCP server of the [pubmed-stream](https://pypi.org/project/pubmed-stream/) Python library with `uvx --from pubmed-stream==<version> pubmed-stream mcp`: [uv](https://docs.astral.sh/uv/getting-started/installation/) downloads that release from PyPI and runs it on your computer, so **uv must be installed**. The first start takes longer while uv downloads it.

The server talks only to NCBI's E-utilities at `eutils.ncbi.nlm.nih.gov`: searches, article records, full texts and citation links. If you give it an NCBI API key, optional and free, the key goes to NCBI with each request, which raises NCBI's limit from 3 to 10 requests a second, and nowhere else. After the first request NCBI accepts with that key, the server also saves it in `~/.pubmed-stream.json`, so the `pubmed-stream` command line can use it. Nothing is sent to the plugin's author or to any other service.

Files are saved in the folder the session starts in: downloaded articles and abstracts under `publications/`, a knowledge graph under `kg_<topic>/`, and a citations file where you ask for one. Running the same search again fetches only new articles.

## Where it works

In Claude Code (terminal, VS Code, JetBrains and the desktop app's Code tab) and in Cowork, which starts the server on your computer when the plugin is on your claude.ai account (**Customize > Plugins > Add > Add marketplace**, then `melhzy/pubmed-stream`). The server runs on your computer, so Claude's chat cannot use it. Codex users install it from the same repository: `codex plugin marketplace add melhzy/pubmed-stream`, then `codex plugin add pubmed-stream@pubmed-stream`.

[Documentation](https://melhzy.github.io/pubmed-stream/) · [Tutorial for medical students and biologists](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/07_ai_assistant.md) · [Source](https://github.com/melhzy/pubmed-stream) · MIT license
