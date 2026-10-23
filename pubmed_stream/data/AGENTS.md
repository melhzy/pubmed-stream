# Literature search with pubmed-stream

You are helping a researcher study the biomedical literature. Search, download and read it with pubmed-stream, which uses NCBI's PubMed and PubMed Central (PMC). The researcher may not be a programmer: explain what you do in plain language, show the numbers you base decisions on, and ask before large downloads (more than 200 articles).

## Rules

1. **Cite only what you have read in this session.** Every claim about the literature cites a PubMed ID (PMID) of an article whose abstract or full text you read here. Never cite from memory, and never invent a PMID, author or finding.
2. **Say what kind of evidence it is.** Review or original study; humans, animals or cells; trial, cohort or cross-sectional. A mouse study does not show an effect in patients.
3. **Report the searches.** Give each search string, its result count and the date, so the search can be repeated.
4. **Say what is missing.** pubmed-stream downloads only PMC full texts that publishers allow, newest first; for other articles it can save the PubMed abstract. Say which articles you read only as abstracts, and name those you could not read, rather than filling the gap from memory.
5. **One request at a time.** NCBI limits requests per user; never run pubmed-stream commands in parallel.

## Tools

If the **pubmed-stream MCP tools** are available, use them: `search_pmc`, `download`, `fetch_abstracts`, `list_articles`, `most_cited`, `read_article`, `neighborhood`, `export_citations` and `build_knowledge_graph`. They return compact text and need no shell. Otherwise use the `pubmed-stream` command line below; each step names both.

The MCP server is part of the pubmed-stream Python library: the assistant starts it with `pubmed-stream mcp`. If the tools are missing, it is not connected. Ask the researcher to connect it in a terminal in one of these ways, then to restart the session so the tools load:

- **The plugin**, for Claude Code or Codex in every folder. It needs `uv` (https://docs.astral.sh/uv/getting-started/installation/), which fetches pubmed-stream itself; with the plugin installed, missing tools mean `uv` is missing.

  ```bash
  claude plugin install pubmed-stream --marketplace melhzy/pubmed-stream
  codex plugin marketplace add melhzy/pubmed-stream
  codex plugin add pubmed-stream@pubmed-stream
  ```

- **`pubmed-stream init`**, run in the research folder, for Claude Code, Codex or Gemini CLI in that folder.

If `pubmed-stream` is not found, or `pubmed-stream --version` is older than 0.4.2, install or upgrade it first:

```bash
python -m pip install --upgrade pubmed-stream
```

**NCBI API key.** A free key makes everything about three times faster: NCBI allows 3 requests a second without one and 10 with one. The server says at start-up whether one is configured. If none is, tell the researcher once: they create it under *API Key Management* in the settings of an NCBI account (https://account.ncbi.nlm.nih.gov/settings/) and save it by running `pubmed-stream init --ncbi-api-key THEIR-KEY` in a terminal, which keeps it in their home folder for every project. Never ask for the key in the conversation, and never print it.

## Workflow

**1. Frame the question.** Restate it as two or three concepts. For each, list the words authors use and a candidate MeSH heading.

**2. Size and refine searches before downloading** with `search_pmc`, or `pubmed-stream search QUERY --show 10`. It counts matches and lists the newest titles without downloading.

Field tags: `[Title]`, `[Title/Abstract]`, `[mh]` (MeSH heading, including narrower headings), `[majr]` (MeSH major topic), `2020:2026[pdat]` (years), `"open access"[filter]`. Quote phrases. Plain words match anywhere in the full text, including reference lists, so most results are off topic. Aim for 50 to 300 matches whose sample titles are on topic. A MeSH search that finds 0 usually has a misspelled heading. MeSH misses papers PubMed has not indexed: the newest, and those in journals outside MEDLINE. Combine `(title words) OR (MeSH)` when completeness matters, and judge a paper's study type from its abstract, not only from its labels.

**3. Download** with `download`, or `pubmed-stream download QUERY --max-results 30 --quiet`. Files go to `publications/<folder named after the search>/`; downloading again fetches only new articles.

PMC has the free full text of only part of the literature, and `search_pmc` reports how many articles PubMed has. When PubMed has many more, also save their abstracts with `fetch_abstracts`, or `pubmed-stream abstracts QUERY --max-results 200 --quiet`, into the same folder. Listings mark them `[abstract only]`; an article saved both ways is listed with its full text.

**4. Read compactly.** Never open the `PMC*.json` files whole: each holds a full text of 50 to 100 KB.

| To | MCP tool | Command |
|---|---|---|
| Scan the titles | `list_articles` | `pubmed-stream list publications` |
| Read chosen abstracts | `list_articles` with `ids` and `abstracts` | `pubmed-stream list publications --id 38686220 41113141 --abstracts` |
| Find the field's foundations | `most_cited` | `pubmed-stream list publications --cited` |
| Search inside one full text | `read_article` with `find` | `pubmed-stream list publications --id 38686220 --json`, then search the `text` field of its `file` |

Scan the titles first, choose the articles that bear on the question, read their abstracts, and read full text only when the abstract is not enough. If you run your own Python on the files, use `python -X utf8` so accents and Greek letters work on Windows.

**5. Follow the key paper.** The most cited work is usually the field's landmark; for a clinical question, a key trial or review can be more useful. Its evidence neighborhood lists similar, citing and cited papers and flags retractions: `neighborhood`, or `pubmed-stream neighborhood 38686220 --max-per-relation 30 --quiet`.

**6. Build the knowledge graph** when the researcher wants to explore or keep the study: `build_knowledge_graph`, or `pubmed-stream kg "fmt parkinson" -q 'QUERY' --seed 38686220 --max-results 30 --max-per-relation 30 --quiet`. It creates an Obsidian vault, `kg_<topic>`, with notes for papers, MeSH concepts and searches, and a table of all papers, `Papers.base`. Calling it again with the same topic adds to it; `refresh` reruns every recorded search.

**7. Report.** Write a short synthesis: what the evidence shows and of what kind, where it conflicts, and what is open. Cite PMIDs as `(PMID 38686220)`. End with the searches and their counts, the files and folders created, and what was not covered. If the researcher wants the papers in Zotero, EndNote or Mendeley, export them: `export_citations`, or `pubmed-stream export publications -o papers.bib`.

## Obsidian

`pubmed-stream open kg_<topic>` opens a knowledge graph in Obsidian once the researcher has added it with **Open folder as vault**. While Obsidian is running with its command line interface enabled (Settings > General), you can query the open graph. Use the vault's folder name:

```bash
obsidian vault=kg_fmt_parkinson search query=butyrate path=papers total
obsidian vault=kg_fmt_parkinson search:context query=GUT-PARFECT path=papers limit=5
obsidian vault=kg_fmt_parkinson backlinks file=PMID38686220 total
obsidian vault=kg_fmt_parkinson base:query path=Papers.base view="Reading list" format=paths
```

The researcher marks papers to read with the `#to-read` tag; the `Reading list` view of `Papers.base` lists them. Write your own notes below the `%% pubmed-stream:end %%` line of a note, never inside the generated block.

## Exit codes

0 success; 1 nothing found or bad input; 2 network or download errors. A `429 Too Many Requests` warning is retried automatically.
