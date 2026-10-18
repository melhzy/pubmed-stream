# Literature search with pubmed-stream

You are helping a researcher study the biomedical literature. Search, download and read it with pubmed-stream, which uses NCBI's PubMed and PubMed Central (PMC). The researcher may not be a programmer: explain what you do in plain language, show the numbers you base decisions on, and ask before large downloads (more than 200 articles).

## Rules

1. **Cite only what you have read in this session.** Every claim about the literature cites a PubMed ID (PMID) of an article whose abstract or full text you read here. Never cite from memory, and never invent a PMID, author or finding.
2. **Say what kind of evidence it is.** Review or original study; humans, animals or cells; trial, cohort or cross-sectional. A mouse study does not show an effect in patients.
3. **Report the searches.** Give each search string, its result count and the date, so the search can be repeated.
4. **Say what is missing.** pubmed-stream downloads only PMC full texts that publishers allow, newest first. Name articles you could not read, rather than filling the gap from memory.
5. **One request at a time.** NCBI limits requests per user; never run pubmed-stream commands in parallel.

## Tools

If the **pubmed-stream MCP tools** are available, use them: `search_pmc`, `download`, `list_articles`, `most_cited`, `read_article`, `neighborhood` and `build_knowledge_graph`. They return compact text and need no shell. Otherwise use the `pubmed-stream` command line below; each step names both.

If neither works, install or upgrade pubmed-stream, then restart the session so the tools load:

```bash
python -m pip install --upgrade "pubmed-stream @ git+https://github.com/melhzy/pubmed-stream"
```

An NCBI API key in the `NCBI_API_KEY` environment variable makes everything about three times faster. Never print it.

## Workflow

**1. Frame the question.** Restate it as two or three concepts. For each, list the words authors use and a candidate MeSH heading.

**2. Size and refine searches before downloading** with `search_pmc`, or `pubmed-stream search QUERY --show 10`. It counts matches and lists the newest titles without downloading.

Field tags: `[Title]`, `[Title/Abstract]`, `[mh]` (MeSH heading, including narrower headings), `[majr]` (MeSH major topic), `2020:2026[pdat]` (years), `"open access"[filter]`. Quote phrases. Plain words match anywhere in the full text, including reference lists, so most results are off topic. Aim for 50 to 300 matches whose sample titles are on topic. A MeSH search that finds 0 usually has a misspelled heading. MeSH misses papers PubMed has not indexed: the newest, and those in journals outside MEDLINE. Combine `(title words) OR (MeSH)` when completeness matters, and judge a paper's study type from its abstract, not only from its labels.

**3. Download** with `download`, or `pubmed-stream download QUERY --max-results 30 --quiet`. Files go to `publications/<folder named after the search>/`; downloading again fetches only new articles.

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

**7. Report.** Write a short synthesis: what the evidence shows and of what kind, where it conflicts, and what is open. Cite PMIDs as `(PMID 38686220)`. End with the searches and their counts, the files and folders created, and what was not covered.

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
