# pubmed-stream

[![PyPI version](https://badge.fury.io/py/pubmed-stream.svg)](https://pypi.org/project/pubmed-stream/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**From a PubMed search to a knowledge graph of the literature.** pubmed-stream downloads full-text articles from PubMed Central, maps the evidence around key papers, and links everything a study collects into an [Obsidian](https://obsidian.md) knowledge graph, where papers connect through citations, similarity and MeSH topics. It is built on NCBI's official E-utilities, works from the command line or Python, and needs nothing beyond `requests`.

> **New to programming?** Start with [tutorial 0](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/00_new_topic.ipynb), which takes a research question to a map of its literature in an afternoon. Click [Open in Colab](https://colab.research.google.com/github/melhzy/pubmed-stream/blob/main/tutorials/00_new_topic.ipynb) to run it in your web browser, with nothing to install; you only type your question into one settings cell.

```mermaid
flowchart LR
    S["PubMed searches"] -->|"download"| D["Full-text articles<br/>metadata, references, text"]
    K["Key papers"] -->|"neighborhood"| N["Similar, citing and cited papers<br/>flagged reviews, retractions, NIH funding"]
    D --> G["Knowledge graph<br/>kg_topic, an Obsidian vault"]
    N --> G
    G --> O["Explore, write, refresh"]
```

## Contents

- [Quick start](#quick-start)
- [Tutorials](#tutorials)
- [Installation and configuration](#installation-and-configuration)
- [1. Download full-text articles](#1-download-full-text-articles)
- [2. Write searches that find the right papers](#2-write-searches-that-find-the-right-papers)
- [3. Map the evidence around a paper](#3-map-the-evidence-around-a-paper)
- [4. Build the knowledge graph of a study](#4-build-the-knowledge-graph-of-a-study)
- [5. Work with AI assistants, local models and Obsidian](#5-work-with-ai-assistants-local-models-and-obsidian)
- [Python API](#python-api)
- [Troubleshooting](#troubleshooting)
- [How it works](#how-it-works)
- [Contributing](#contributing)
- [FAQ](#faq)
- [Citation, acknowledgments and license](#citation-acknowledgments-and-license)

## Quick start

```bash
pip install pubmed-stream

# Size a search and preview its newest titles, without downloading
pubmed-stream search '"gut microbiota"[Title] AND frailty[Title/Abstract]'

# Download the full text of up to 50 articles, then read them compactly
pubmed-stream download '"gut microbiota"[Title] AND frailty[Title/Abstract]' --max-results 50
pubmed-stream list publications --abstracts

# Map the evidence around one paper: similar, citing and cited papers, with retractions flagged
pubmed-stream neighborhood 31319564

# Build a study's knowledge graph in ./kg_gut_microbiome_frailty, then open it in Obsidian
pubmed-stream kg "gut microbiome frailty" -q '"gut microbiota"[Title] AND frailty[Title/Abstract]' --seed 31319564
pubmed-stream open kg_gut_microbiome_frailty

# Let Claude Code, Codex or Gemini CLI do all of this: set up a folder, then start the assistant there
pubmed-stream init
```

The same in Python:

```python
from pubmed_stream import create_kg, get_neighborhood, search_and_download

stats = search_and_download('"gut microbiota"[Title] AND frailty[Title/Abstract]', max_results=50)
hood = get_neighborhood("31319564")
result = create_kg("gut microbiome frailty", queries=['"gut microbiota"[Title] AND frailty[Title/Abstract]'],
                   seeds=["31319564"])
print(stats.successful, hood.totals, result.kg_dir)
```

## Tutorials

The notebooks in [`tutorials/`](https://github.com/melhzy/pubmed-stream/tree/main/tutorials) are written for researchers, not programmers. Each follows a real research question. The notebooks have a single **Your settings** cell for your own question, run in Google Colab with nothing to install, and are saved with their results so you can read them on GitHub first; tutorial 7 happens in a terminal, with an AI assistant.

| # | Tutorial | Use case |
|---|----------|----------|
| 0 | [**Start here: a new research topic in an afternoon**](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/00_new_topic.ipynb) | From a question to a map of its literature: size the field, find the paper everyone cites, build a knowledge graph, read its themes, evidence and gaps, export a reading list |
| 1 | [Getting started](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/01_getting_started.ipynb) | Download a search, read the files, choose a format, resume, fetch one known article, rescue a search that finds nothing, read downloads compactly |
| 2 | [Designing searches](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/02_search_strategies.ipynb) | Measure the size, precision and availability of five versions of one search, and combine words with MeSH headings |
| 3 | [A literature-review corpus](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/03_literature_review.ipynb) | Run a keyword list, deduplicate, screen by theme, export to CSV and BibTeX |
| 4 | [The evidence around one paper](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/04_evidence_neighborhood.ipynb) | Map a paper's neighborhood and screen it for retractions |
| 5 | [The knowledge graph of a study](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/05_knowledge_graph.ipynb) | Build a graph and explain it with twelve charts and tables |
| 6 | [Text mining and RAG preparation](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/06_text_mining.ipynb) | Split articles into sections and chunk them for embeddings |
| 7 | [Your literature search with an AI assistant](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/07_ai_assistant.md) | For medical students and biologists: install Claude Code or Codex, choose a model, ask in plain English, check the evidence, keep it in Obsidian, or use a local model through Ollama |

Five short guides support them:

| Guide | For |
|---|---|
| [How to run the tutorials](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/guides/setup.md) | Colab, installing Python on Windows or Mac, running a notebook, a free NCBI API key |
| [Reading a knowledge graph in Obsidian](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/guides/obsidian.md) | Opening, exploring, searching and writing in a graph |
| [Glossary](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/guides/glossary.md) | MeSH, PMC, stub, seed and every other term, in plain language |
| [What pubmed-stream can and cannot do](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/guides/limitations.md) | Coverage, blind spots, and why it is not a systematic review |
| [Troubleshooting for beginners](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/guides/troubleshooting.md) | Setup, notebook, Colab and Obsidian problems |

The [tutorials README](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/README.md) lists everything, including how programmers can run the notebooks locally.

## Installation and configuration

```bash
pip install pubmed-stream                  # the library and the pubmed-stream command
pip install "pubmed-stream[tutorials]"     # plus jupyter, matplotlib, networkx and pandas for the tutorials
```

The AI-assistant, local-model and Obsidian features of [section 5](#5-work-with-ai-assistants-local-models-and-obsidian) need version 0.3.0 or later: `pubmed-stream --version` shows yours, and `pip install --upgrade pubmed-stream` updates it. From a clone, `pip install -e ".[dev]"` installs it in editable mode with pytest and ruff. pubmed-stream needs Python 3.8 or later; its only runtime dependency is [requests](https://pypi.org/project/requests/).

**Set an NCBI API key.** NCBI allows 3 requests per second without a key and 10 with one, so a key makes everything about three times faster. Keys are free: create one in the settings of an [NCBI account](https://www.ncbi.nlm.nih.gov/account/). pubmed-stream reads it, and an optional contact email, from the environment:

```bash
export NCBI_API_KEY="your-key"        # PowerShell: $env:NCBI_API_KEY = "your-key"
export NCBI_EMAIL="you@example.org"   # PowerShell: $env:NCBI_EMAIL = "you@example.org"
```

Every command also accepts `--api-key` and `--email`. pubmed-stream sets its request rate from the key automatically, retries failed requests three times with back-off, and never writes the key to its logs. `--rate-limit SECONDS` slows it down further if needed.

## 1. Download full-text articles

`pubmed-stream download` searches PubMed Central directly, so every result is an article with a PMC record, then fetches each one's full-text XML in parallel and saves it as one JSON file. Some publishers do not allow their articles to be downloaded as XML; those are reported as **unavailable** and skipped, rather than saved half-empty.

```bash
pubmed-stream download "gut microbiome" --max-results 50
```

```python
from pubmed_stream import search_and_download

stats = search_and_download("gut microbiome", max_results=50)
print(f"{stats.successful} saved, {stats.skipped} already there, {stats.unavailable} unavailable "
      f"of {stats.total_found} matches, in {stats.duration_seconds:.0f} s")
```

Each search gets its own folder, named after the query; a name longer than 100 characters is shortened and ends with a short hash of the query. Running a search again skips the files that already exist, so an interrupted download resumes and a repeated search only fetches what is new.

To see what you downloaded without opening every file, `list` prints one line per article, newest first, and each article once however many searches found it:

```bash
pubmed-stream list publications                       # identifiers, year, title, journal, length
pubmed-stream list publications --id 31319564 --abstracts   # the abstracts of chosen articles
pubmed-stream list publications --cited               # the works the downloads cite most
pubmed-stream list publications --json --abstracts > corpus.jsonl
```

```
publications/
└── gut_microbiome/
    ├── query.json          the original search, recorded for later tools
    ├── PMC12345678.json
    └── PMC12345679.json
```

Every article file has the same shape. `metadata.references` lists the cited works that have a PubMed ID or DOI; those become citation links in a knowledge graph.

```json
{
  "pmcid": "PMC13279599",
  "source": "PMC",
  "download_date": "2026-10-18T13:20:45",
  "metadata": {
    "pmid": "42060019",
    "pmcid": "PMC13279599",
    "doi": "10.1007/s40520-026-03403-6",
    "title": "Association between gut microbiota and sarcopenia in older adults: ...",
    "journal": "Aging Clinical and Experimental Research",
    "year": "2026", "month": "4", "day": "30",
    "authors": ["Ramezani Kashal Fatemeh", "Sharifi Farshad", "..."],
    "abstract": "Introduction Investigating gut microbiota has emerged as a novel approach ...",
    "keywords": ["Sarcopenia", "Gut microbiota", "Aging", "Muscle metabolism"],
    "references": [
      {"pmid": "32033882", "doi": "10.1016/j.jamda.2019.12.012",
       "title": "Asian Working Group for Sarcopenia: 2019 Consensus Update ...", "year": "2020"}
    ],
    "linked_discoveries_url": "https://linkeddiscoveries.ncbi.nlm.nih.gov/42060019/"
  },
  "text": "Association between gut microbiota and sarcopenia ...\nAbstract\nIntroduction ..."
}
```

The format decides what is kept beside the metadata:

| `--format` | Adds | Best for |
|------------|------|----------|
| `text` (default) | `text`: title, abstract and body, one paragraph per line | Reading, search, embeddings, most NLP |
| `xml` | `xml`: the raw JATS XML | Section-level parsing, tables, figures |
| `both` | `text` and `xml` | Keeping every option open |

| Option | Meaning | Default |
|--------|---------|---------|
| `QUERY` | PubMed search; field tags such as `[Title]` work | required |
| `--max-results N` | Articles to download, newest first | 100 |
| `--format` | `text`, `xml` or `both` | `text` |
| `--exclude-text` | Leave out the `text` field to save space | included |
| `--output-dir`, `-o` | Base folder | `./publications` |
| `--workers N`, `--sequential` | Parallel downloads, or one at a time for unstable networks | 5 workers |
| `--topic`, `--vault` | Also add the results to a knowledge graph, see [section 4](#4-build-the-knowledge-graph-of-a-study) | off |
| `--api-key`, `--email`, `--rate-limit`, `--user-agent`, `-v` | NCBI settings and verbose logging | environment |
| `--quiet` | Print only the summary, without progress | progress shown |

`download` exits with 0 when articles were saved or already present, 1 when the search found nothing, and 2 when every download failed.

## 2. Write searches that find the right papers

PMC searches the **full text** of every article, including its reference list, so a plain search such as `gut microbiome frailty` matches thousands of articles that only mention the words in passing. Field tags fix this. In [tutorial 2](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/02_search_strategies.ipynb), five versions of one question range from 7,587 matches with almost no relevant recent results to 66 matches where most are on topic.

| Technique | Example | Effect |
|-----------|---------|--------|
| Put the core concept in the title | `"gut microbiota"[Title]` | The largest gain in precision |
| Restrict the rest to title and abstract | `frailty[Title/Abstract]` | Drops passing mentions in the body |
| Quote multi-word terms, and cover synonyms with `OR` | `("gut microbiome" OR "gut microbiota")` | Keeps phrases together without losing recall |
| Restrict to open access | `AND "open access"[filter]` | Every result can be downloaded |
| Limit the years | `AND 2020:2026[pdat]` | Reaches past the newest results, or focuses on them |

PMC returns the newest matches first, so `--max-results` takes the most recent articles. Check a search before downloading: `pubmed-stream search QUERY` prints its size and newest titles without downloading anything, and `--show 0` prints the count only.

```
$ pubmed-stream search '"gut microbiota"[Title] AND sarcopenia[Title/Abstract]' --show 2
80 articles in PMC for: "gut microbiota"[Title] AND sarcopenia[Title/Abstract]
Newest 2:
  2026  PMC13668947  PMID 42875678  Correspondence for the article: "Association between gut microbiota and sarcopenia ...
  2026  PMC13641649  PMID 41879259  Alterations in the Gut Microbiota of Cirrhotic Patients With Sarcopenia and PH After TIPS. ...
```

## 3. Map the evidence around a paper

A search finds papers by their words. An **evidence neighborhood** starts from one key paper and follows PubMed's links instead: the papers PubMed rates as similar, the papers citing it, and the papers it cites. Each is flagged as a review, retracted or NIH-funded. NLM's [Linked Discoveries](https://linkeddiscoveries.ncbi.nlm.nih.gov/userguide/) web tool shows the same kind of neighborhood but has no API; pubmed-stream builds one from documented E-utilities.

```bash
pubmed-stream neighborhood 9500320
```

```
Seed: PMID 9500320 (1998) Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and ...
Similar       100            (4 reviews, 0 retracted, 0 NIH-funded, 18 in PMC)
Cited by      100 of 489     (145 reviews, 0 retracted, 52 NIH-funded, 421 in PMC)
References      0            (0 reviews, 0 retracted, 0 NIH-funded, 0 in PMC)
Neighborhood  200 unique articles fetched
[RETRACTED] PMID 9500320 (1998) Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and ...
Saved: publications/neighborhood_9500320/neighborhood.json
Explore the graph: https://linkeddiscoveries.ncbi.nlm.nih.gov/9500320/
```

`100 of 489` means 489 PubMed articles cite the seed and the newest 100 were fetched in detail; `--max-per-relation` changes that cap. The counts in brackets always cover all 489, counted with PubMed searches rather than by downloading every record. `[RETRACTED]` lists every retracted article among those fetched, so check them before citing or building on them.

| Flag | Meaning |
|------|---------|
| review | Publication type Review, Systematic Review or Scoping Review; narrower than PubMed's Review filter, which also counts guidelines and meta-analyses |
| retracted | Publication type Retracted Publication, or a linked retraction notice |
| NIH-funded | An NIH grant in the grant list, or an N.I.H. research-support publication type |
| in PMC | The article has a PMC ID, so its full text may be downloadable |

The neighborhood is saved as `publications/neighborhood_<PMID>/neighborhood.json`. `--download` also saves the PMC full text of the seed and every neighbor that has one, beside it. In Python:

```python
from pubmed_stream import get_neighborhood, save_neighborhood, download_neighborhood

hood = get_neighborhood("31319564", max_per_relation=50)
print(hood.totals)                      # {"similar": 384, "cited_by": 239, "references": 139}
print(hood.flag_counts["cited_by"])     # reviews, retracted, NIH-funded and in-PMC counts across all of them

retracted = [a for a in hood.articles() if a.is_retracted]          # seed and neighbors
cites_retracted = [a for a in hood.references if a.is_retracted]    # does the paper cite retracted work?

save_neighborhood(hood)                 # publications/neighborhood_31319564/neighborhood.json
download_neighborhood(hood)             # PMC full text of the seed and its neighbors
```

Each neighbor is a `RelatedArticle` with `pmid`, `title`, `journal`, `year`, `authors`, `pub_types`, `is_review`, `is_retracted`, `nih_funded`, `pmcid`, `doi`, `mesh_terms`, and, for similar articles, a similarity `score`. A neighborhood costs two requests for up to 200 articles, plus five for each relation cut short by the cap.

Compared with Linked Discoveries: similarity comes from PubMed's Similar Articles algorithm rather than a BiomedBERT model, so the neighbors can differ; there are no condition, gene or chemical filters; and citation links exist only where reference lists were deposited, mostly for PMC articles. Like the web tool, the flags describe connections; they do not judge whether a study is sound. [Tutorial 4](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/04_evidence_neighborhood.ipynb) charts a neighborhood and walks through retraction screening.

`neighborhood` exits with 0 on success, 1 when the PMID is invalid or not in PubMed, and 2 when NCBI could not be reached. It takes a PubMed ID, the number in a `pubmed.ncbi.nlm.nih.gov/<PMID>/` link or a downloaded article's `metadata.pmid`, not a PMC ID.

## 4. Build the knowledge graph of a study

Downloads and neighborhoods come together in a **knowledge graph**. A study has a topic, the searches that collect its literature, and optionally key papers whose neighborhoods belong in it. `pubmed-stream kg` runs them all and links the results in an Obsidian vault named `kg_<topic>`: a folder of Markdown notes, one per paper, MeSH concept and collection. Open it in Obsidian with **Open folder as vault**, and the graph view shows which papers cite each other and which topics they share.

```bash
pubmed-stream kg "gut microbiome frailty" \
    -q '"gut microbiota"[Title] AND frailty[Title/Abstract]' \
    -q '"gut microbiota"[Title] AND sarcopenia[Title/Abstract]' \
    --seed 31319564 --max-results 25 --max-per-relation 30
```

That study gives a graph of 127 papers, 42 with full text and 85 from the seed's neighborhood, linked to 309 MeSH concepts: 440 notes in all. The study is remembered, so it keeps growing and stays current with only its topic:

```bash
pubmed-stream kg "gut microbiome frailty" -q "microbiome inflammaging"   # add a search
pubmed-stream kg "gut microbiome frailty" --add ./publications/old_query # add earlier downloads
pubmed-stream kg "gut microbiome frailty" --refresh                      # rerun everything, add new papers
pubmed-stream kg "gut microbiome frailty"                                # rebuild the notes only
```

`download` and `neighborhood` can join a study too: with `--topic "gut microbiome frailty"`, their search or seed is recorded like one made with `kg`. A bare `--vault` names the graph after the query or the neighborhood instead, and `--vault DIR` or `--kg-dir DIR` picks any folder. Obsidian links notes only inside one vault, so give every search of a study the same topic.

### What the graph contains

| Note | Location | Links to |
|------|----------|----------|
| Paper | `papers/PMID<id>.md` | Papers it cites, papers citing it, similar papers, its MeSH concepts and collections |
| Concept | `concepts/<MeSH heading>.md` | Papers indexed with that heading |
| Collection | `collections/Search - <query>.md`, `collections/Neighborhood - PMID <id>.md` | Its papers and top concepts |
| Home | `PubMed Stream.md` | Collections, most connected concepts, retracted papers |

Here is a slice of the example study's graph. Every link in it is real: two 2026 studies from different searches cite the same 2021 study, which PubMed also rates as similar to the seed review. Connections like this are what a list of search results hides.

```mermaid
flowchart LR
    C1["Search -<br/>gut microbiota AND sarcopenia"] --> P1["PMID 42060019<br/>gut microbiota and sarcopenia<br/>in older adults, 2026"]
    C2["Search -<br/>gut microbiota AND frailty"] --> P4["PMID 41601864<br/>gut microbiota and<br/>cognitive frailty, 2026"]
    C3["Neighborhood -<br/>PMID 31319564"] --> P2["PMID 31319564<br/>seed review, 2019"]
    C3 --> P3["PMID 33633246<br/>microbiota in patients<br/>with sarcopenia, 2021"]
    P1 -->|cites| P3
    P4 -->|cites| P3
    P2 -.->|similar| P3
    P1 --> M1(["Sarcopenia"])
    P1 --> M2(["Gastrointestinal Microbiome"])
    P3 --> M1
    P3 --> M2
    P2 --> M1
    classDef collection fill:#8E4EC6,stroke:#8E4EC6,color:#fff
    classDef stub fill:#8B8D98,stroke:#8B8D98,color:#fff
    classDef concept fill:#12A594,stroke:#12A594,color:#fff
    class C1,C2,C3 collection
    class P2,P3 stub
    class M1,M2 concept
```

Where the links come from:

- **Citations** come from the reference lists of downloaded articles, for references with a PMID, and from neighborhood citing and cited papers. References with only a DOI are listed under *Other references*.
- **Similarity** comes from neighborhood similar articles, with PubMed's score.
- **Concepts** are MeSH headings fetched from PubMed, once per 200 papers, and cached in the graph. Check tags such as *Humans* or *Aged* stay in the paper's properties but get no note, because they would link almost every paper.
- **Stubs** are neighborhood papers that were not downloaded. Their notes carry PubMed details and links, and are tagged `pubmed/stub`.

A paper note holds Obsidian properties, then a generated block, then space for your own notes:

```markdown
---
type: "paper"
title: "Association between gut microbiota and sarcopenia in older adults: ..."
pmid: "42060019"
year: 2026
journal: "Aging Clinical and Experimental Research"
mesh:
  - "Sarcopenia"
  - "Gastrointestinal Microbiome"
status: "full-text"
tags:
  - "pubmed/paper"
---
%% pubmed-stream:start - generated; edits inside this block are overwritten %%
# Association between gut microbiota and sarcopenia in older adults: ...

**Published:** *Aging Clinical and Experimental Research* · 2026 · [PubMed](...) · [PMC](...) · [DOI](...)

## Abstract
## MeSH concepts
- [[Sarcopenia]] (major topic)
## Cites (39)
- [[PMID33633246|Alterations in intestinal microbiota diversity, composition, and function in patients with sarcop... (2021)]]
## Cited by (1)
%% pubmed-stream:end %%

## Notes

Your own notes go here and survive every rebuild.
```

**Rebuilding is safe.** A rebuild replaces only the generated block and the properties the tool owns. Text outside the block, and properties, tags and aliases you add in Obsidian, are kept; unchanged notes are not rewritten. Do not rename or move generated notes, or a rebuild will recreate them. Properties work in Obsidian search, Bases and the Dataview plugin, and on the first build the graph view gets colours for retracted papers, reviews, stubs, concepts and collections.

[Tutorial 5](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/05_knowledge_graph.ipynb) builds this study and explains the graph with charts: where the papers came from, which concepts travel together, which papers the study relies on most, and which ones bridge its parts.

| `kg` option | Meaning | Default |
|-------------|---------|---------|
| `TOPIC` | Study topic; the graph is `./kg_<topic>` | required |
| `--query`, `-q` | Search to download into the study; repeatable | none |
| `--seed`, `-s` | PMID whose neighborhood joins the study; repeatable | none |
| `--add DIR` | Folder or file downloaded earlier; repeatable | none |
| `--refresh` | Run every remembered search and seed again | only new ones |
| `--max-results`, `--max-per-relation` | Articles per search; neighbors per relation | 100, 100 |
| `--download-neighbors` | Download neighbors' full text instead of stub notes | stubs |
| `--fulltext` | Put each article's full text into its note | abstract only |
| `--offline` | Use cached MeSH terms only | fetch missing ones |
| `--kg-dir DIR` | Graph folder instead of `./kg_<topic>` | `./kg_<topic>` |

`kg` exits with 0 when everything worked, 1 when there is nothing to build or an option is invalid, and 2 when a search or neighborhood failed; the graph is still built from everything else.

Limitations to know about:

- **Some papers lack MeSH terms.** Indexing takes months, and papers in journals outside MEDLINE are never indexed, so such papers have no concept links. Rebuild later to pick up newly indexed papers; the others stay unlinked to concepts but keep their citation links.
- **Downloads from pubmed-stream 0.1.1 or earlier have no reference lists**, unless saved with `--format xml` or `both`. Download them again to add citation links.
- **Many references have no PMID.** Conference papers, preprints and books appear under *Other references*, not in the graph.
- **Notes are never deleted.** Removing a source leaves its notes in the graph.

## 5. Work with AI assistants, local models and Obsidian

pubmed-stream connects to the tools researchers now work with: AI assistants that run in a terminal, local models that keep everything on your computer, and Obsidian, where the knowledge graph lives.

```mermaid
flowchart LR
    A["Claude Code, Codex,<br/>Gemini CLI"] -->|"MCP tools"| P["pubmed-stream"]
    P --> K["kg_topic<br/>Obsidian vault"]
    P -->|"pubmed-stream review"| O["Ollama<br/>local model"]
    O -->|"review notes"| K
    A -->|"obsidian CLI"| K
```

**AI assistants.** In a research folder, `pubmed-stream init` writes the instructions and settings for Claude Code, Codex and Gemini CLI. The assistant then calls pubmed-stream directly through its **MCP server**, as the tools `search_pmc`, `download`, `list_articles`, `most_cited`, `read_article`, `neighborhood` and `build_knowledge_graph`. Ask it a research question in plain language:

```bash
pubmed-stream init
claude        # or: codex, gemini
```

> *Does fecal microbiota transplantation help people with Parkinson's disease? Find the clinical evidence and summarize it, with PMIDs.*

The instructions make the assistant size searches before downloading, cite only papers it downloaded and read in the session, say what kind of evidence each is, report its searches with their counts, and name what it could not read. Every tool returns compact text, so the assistant can scan 64 papers in about 3,000 tokens instead of reading 4.3 MB of full text. `init --claude-model opus` and `init --review-model <ollama model>` also choose the models for the folder. To give an assistant the tools in every folder, register the server once instead: `claude mcp add pubmed-stream -- pubmed-stream mcp`, or the same with `codex mcp add`.

**Local models.** `pubmed-stream review` has a model running in [Ollama](https://ollama.com) on your own computer summarize the abstracts you chose, one at a time, at temperature 0. pubmed-stream attaches each PubMed ID itself and flags numbers and citations the abstracts do not support:

```bash
ollama pull hf.co/unsloth/Llama-3.2-1B-Instruct-GGUF:Q4_K_M
pubmed-stream review "Does FMT help people with Parkinson's disease?" --id 38686220 41826284 41113141 --vault kg_fmt_parkinson
```

**Obsidian.** Every knowledge graph has property types for Obsidian and `Papers.base`, a Bases table of all papers with views for full texts, reviews, retracted papers and your `#to-read` list. `pubmed-stream open kg_<topic>` opens it, and with Obsidian's [command line](https://obsidian.md/help/cli) switched on, an assistant can query it: `obsidian vault=kg_<topic> base:query path=Papers.base view="Reading list"`.

[Tutorial 7](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/07_ai_assistant.md) walks through real sessions: an assistant going from 4,863 search results to a cited report, Claude Code and Codex using the MCP tools, and what a 1-billion-parameter local model gets right and wrong. A model that small summarizes well but cannot run the searches itself.

## Python API

Everything the commands do is available from `pubmed_stream`:

| Function | Purpose | Returns |
|----------|---------|---------|
| `search_and_download(query, max_results, fmt="text", ...)` | Search PMC and download full text | `DownloadStats` |
| `get_neighborhood(pmid, max_per_relation=100, ...)` | Similar, citing and cited papers with flags | `Neighborhood` |
| `save_neighborhood(hood, output_dir=None)` | Write `neighborhood.json` | path |
| `download_neighborhood(hood, ...)` | Full text of the seed and neighbors | `DownloadStats` |
| `create_kg(topic, queries, seeds, sources, refresh=False, ...)` | Run a study and build its knowledge graph | `KGResult` |
| `load_study(kg_dir)`, `record_study(kg_dir, topic, queries, seeds)` | Read, or add to, a graph's recorded study | dict |
| `build_vault(sources, vault_dir, ...)` | Build graph notes from download folders only | `VaultStats` |
| `topic_vault_dir(topic)` | The `kg_<topic>` folder of a topic | path |
| `search_pmc(query, max_results=10, ...)` | Count a search and list its newest matches, without downloading | `SearchResult` |
| `list_articles(path)` | Compact records of downloaded articles, newest first, each once | list of dicts |
| `most_cited(path, n=10)` | The works the downloaded articles cite most | list of dicts |
| `review(question, path, ids, model, answer=False, ...)` | Summaries by a local model through Ollama, with checks | `Review` |
| `init_folder(folder)` | Instructions and MCP settings for Claude Code, Codex and Gemini CLI | list of actions |
| `open_vault(kg_dir)` | Open a knowledge graph in Obsidian | `(opened, message)` |
| `esearch_pmc(term, max_results, api_key, session, rate_limiter)` | One PMC search: IDs and total count | `(ids, total)` |
| `esummary_pmc(pmcids, api_key, session, rate_limiter)` | Titles, journals, years and identifiers of PMC articles | list of dicts |
| `efetch_pmc(pmcid, out_dir, fmt, api_key, session, rate_limiter)` | Download one article | `(ok, status)` |
| `extract_metadata_from_pmc_xml(xml)`, `extract_text_from_pmc_xml(xml)` | Parse JATS XML you already have | dict, str |
| `create_session(user_agent)`, `RateLimiter(seconds)` | Building blocks for the low-level functions | |

Functions that call NCBI accept `api_key`, `email`, `user_agent`, `rate_limit` and a `session` to reuse, and fall back to the environment variables. The low-level functions take an explicit session and rate limiter:

```python
from pathlib import Path
from pubmed_stream import RateLimiter, create_session, efetch_pmc, esearch_pmc

session, limiter = create_session("my-project/1.0"), RateLimiter(0.34)
ids, total = esearch_pmc('"gut microbiota"[Title] AND frailty[Title/Abstract]', 20, None, session, limiter)
for pmc_id in ids:
    ok, status = efetch_pmc(pmc_id, Path("downloads"), "both", None, session, limiter)   # success, unavailable, exists or error
```

## Troubleshooting

| Symptom | Cause and fix |
|---------|---------------|
| A quoted phrase is ignored on Windows | Windows PowerShell 5.1 drops inner double quotes, and Command Prompt does not understand single quotes. In PowerShell write `'\"gut microbiota\"[Title] AND frailty[Title/Abstract]'`; in Command Prompt, `"\"gut microbiota\"[Title] AND frailty[Title/Abstract]"`. PowerShell 7.3 and later, macOS and Linux take the examples as written |
| `0` saved but many matches | The files already exist and were skipped, which counts as success; `stats.skipped` shows them |
| Many *unavailable* articles | Their publishers do not allow XML download. Add `AND "open access"[filter]` to the search |
| HTTP 429, *Too Many Requests* | Requests are retried automatically. Set `NCBI_API_KEY`, or slow down with `--rate-limit 0.5` |
| Timeouts or a flaky network | Use `--sequential`, or fewer `--workers` |
| Results unrelated to the question | The search matched text anywhere in the article; see [section 2](#2-write-searches-that-find-the-right-papers) |
| `'PMC…' is a PMC ID` | `neighborhood` and `--seed` need the PubMed ID, which downloaded files have in `metadata.pmid` |
| Few references or citations in a neighborhood | NCBI has citation links only where reference lists were deposited, mostly for PMC articles |
| Papers without concept links in a graph | PubMed has not indexed them with MeSH yet; rebuild later |

Problems with installing Python, Jupyter, Colab or Obsidian are covered in the [troubleshooting guide for beginners](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/guides/troubleshooting.md).

For details, add `-v` to any command, or enable debug logging for this package only, since the HTTP library's debug output would log request URLs with your API key:

```python
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("pubmed_stream").setLevel(logging.DEBUG)
```

## How it works

pubmed-stream is a stack of five small modules. Each one uses only those below it, from the command line down to the HTTP client:

| Module | Role |
|--------|------|
| `cli.py` | The `pubmed-stream` command: `init`, `search`, `download`, `list`, `neighborhood`, `kg`, `review`, `open` and `mcp` |
| `corpus.py` | Reads downloaded articles back as compact records, and finds the works they cite most |
| `mcp_server.py` | The MCP server that gives AI assistants pubmed-stream's tools |
| `review.py` | Summaries by a local model through Ollama, with number and citation checks |
| `obsidian.py`, `assistants.py` | Opening graphs in Obsidian; setting up folders for AI assistants |
| `kg.py` | Studies: run searches and seeds, record them, refresh them |
| `vault.py` | Knowledge-graph notes: merge every source, render notes, rebuild safely |
| `neighborhood.py` | Similar, citing and cited papers, with flags and MeSH terms |
| `downloader.py` | The E-utilities client, PMC search and download, JATS parsing |

The [architecture guide](https://github.com/melhzy/pubmed-stream/blob/main/docs/ARCHITECTURE.md) explains the whole repository with diagrams, tables and figures: every NCBI request, the request flows, how knowledge graphs are merged and safely rebuilt, the data model, and where to extend the code.

```
pubmed-stream/
├── pubmed_stream/      the package
├── tests/              117 offline tests; NCBI is faked with canned responses
├── tutorials/          seven notebooks, the AI assistant tutorial and instructions, guides, kg_study.py, keyword lists, tools
├── docs/               the architecture guide and its figures
├── pyproject.toml      package metadata and dependencies
├── CHANGELOG.md        changes in each version
├── CITATION.cff        how to cite pubmed-stream
└── LICENSE             MIT
```

## Contributing

Contributions are welcome. Fork the repository, create a feature branch, and open a pull request. Add tests for new behaviour, and make sure `pytest` and `ruff check .` pass. The tests run offline in a few seconds:

```bash
pip install -e ".[dev]"
pytest
```

Ideas on the roadmap: PubMed abstracts for articles outside PMC, a search query builder, progress bars, and export to BibTeX or RIS from the command line.

### Releasing to PyPI

Maintainers publish new versions by hand. Replace `X.Y.Z` with the new version.

1. **Bump the version** in `pyproject.toml` (`version = "X.Y.Z"`), `pubmed_stream/__init__.py` (`__version__ = "X.Y.Z"`) and `CITATION.cff` (`version` and `date-released`), keeping them identical, and turn the changelog's *Unreleased* heading into `X.Y.Z - YYYY-MM-DD`.
2. **Run the tests**: `pytest`.
3. **Build and check the distributions**; `dist/` is git-ignored:

   ```bash
   pip install --upgrade build twine
   rm -rf dist build *.egg-info
   python -m build
   python -m twine check dist/*
   ```

4. **Upload to PyPI** with an API token from <https://pypi.org/manage/account/token/>, scoped to the `pubmed-stream` project. The username is literally `__token__`; a PyPI password will not work. A `403 Forbidden` means the token is wrong, expired or not scoped to this project. PyPI never accepts the same version twice, so fix a broken release with a new patch version.

   ```bash
   python -m twine upload -u __token__ -p pypi-... dist/*
   ```

5. **Commit, tag and push** the release:

   ```bash
   git commit -am "chore: Release X.Y.Z"
   git tag X.Y.Z
   git push origin main X.Y.Z
   ```

   If the tag already exists on the wrong commit, move it and force-push only that tag, never `main`: `git tag -f X.Y.Z <commit>`, then `git push --force origin refs/tags/X.Y.Z`.

6. **Create the GitHub release.** In the web interface, open `https://github.com/melhzy/pubmed-stream/releases/new?tag=X.Y.Z`, set the title to `X.Y.Z`, paste the version's section of `CHANGELOG.md` as the description, attach the two files from `dist/`, and publish. With the [GitHub CLI](https://cli.github.com/), after a one-time `gh auth login`: `gh release create X.Y.Z --title "X.Y.Z" --notes "<the changelog section>" dist/*`.
7. **Verify**: `pip install --upgrade pubmed-stream`, then `pubmed-stream --version`.

## FAQ

**What is the difference between PubMed and PMC?** PubMed indexes the citations and abstracts of over 35 million articles. PubMed Central (PMC) is NCBI's archive of full-text articles, a subset of them. pubmed-stream downloads full text from PMC and uses PubMed for neighborhoods and MeSH terms.

**Does it comply with NCBI's terms?** Yes. It uses the official E-utilities, keeps within NCBI's rate limits, identifies itself with a User-Agent, and sends your contact email when you set one.

**Why one JSON file per article?** One file keeps an article's metadata, references and text together, in every format, and makes corpora easy to filter, merge and resume.

**Can I resume an interrupted download?** Yes. Run the same command again; existing files are skipped.

**Can I use it for a systematic review?** For the first steps: scoping the field, testing and recording searches, and finding key papers. A systematic review also needs other databases, screening by two reviewers and risk-of-bias assessment; see [what pubmed-stream can and cannot do](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/guides/limitations.md).

**Why are some important papers missing?** Full text comes only from PMC, and searches return the newest matches first. Older and subscription-only papers enter a knowledge graph through key papers' neighborhoods, as stubs, or as links from the papers that cite them.

**Do I need Obsidian?** Only to explore a knowledge graph visually. The notes are plain Markdown, and [tutorial 5](https://github.com/melhzy/pubmed-stream/blob/main/tutorials/05_knowledge_graph.ipynb) analyses one in Python.

**Can I use it commercially?** Yes, under the MIT license, while respecting NCBI's usage policies.

## Citation, acknowledgments and license

pubmed-stream was developed to support biomedical research at the **University of Massachusetts** by the **Haran Lab**, the **Bucci Lab** and the **Microbiology & Microbiome Dynamics AI HUB**. Thanks to NCBI for the E-utilities and open access to PubMed Central. If you use it in your research, please cite it. GitHub's **Cite this repository** button, on the repository's main page, gives the citation in APA and BibTeX from [`CITATION.cff`](https://github.com/melhzy/pubmed-stream/blob/main/CITATION.cff):

```bibtex
@software{pubmed_stream_2026,
  title = {pubmed-stream: From PubMed Searches to Knowledge Graphs of the Biomedical Literature},
  author = {Haran Lab and Bucci Lab and Microbiology \& Microbiome Dynamics AI HUB},
  organization = {University of Massachusetts},
  year = {2026},
  url = {https://github.com/melhzy/pubmed-stream},
  note = {Built on NCBI E-utilities}
}
```

pubmed-stream is free software under the [MIT License](https://github.com/melhzy/pubmed-stream/blob/main/LICENSE). Changes in each version are listed in the [changelog](https://github.com/melhzy/pubmed-stream/blob/main/CHANGELOG.md).

Questions and bug reports: [open an issue](https://github.com/melhzy/pubmed-stream/issues). Package: [pypi.org/project/pubmed-stream](https://pypi.org/project/pubmed-stream/).
