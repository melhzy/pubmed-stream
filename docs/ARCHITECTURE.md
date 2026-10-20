# How pubmed-stream works

This guide explains the repository: what each part does, how data moves from NCBI to your disk and into a knowledge graph, and how the pieces are tested. It combines diagrams, tables, code and figures drawn from a real example study. For day-to-day usage, the [README](../README.md) is the reference.

**Contents**

1. [At a glance](#1-at-a-glance)
2. [Repository map](#2-repository-map)
3. [Talking to NCBI](#3-talking-to-ncbi)
4. [Downloading full text](#4-downloading-full-text)
5. [Evidence neighborhoods](#5-evidence-neighborhoods)
6. [Knowledge graphs](#6-knowledge-graphs)
7. [AI assistants, local models and Obsidian](#7-ai-assistants-local-models-and-obsidian)
8. [The example study in figures](#8-the-example-study-in-figures)
9. [Data model](#9-data-model)
10. [Testing](#10-testing)
11. [Extending pubmed-stream](#11-extending-pubmed-stream)

---

## 1. At a glance

pubmed-stream does three jobs. Each one builds on the one before it, and all three connect to AI assistants, local models and Obsidian ([section 7](#7-ai-assistants-local-models-and-obsidian)).

| Job | Command | Python | NCBI services | Writes |
|-----|---------|--------|---------------|--------|
| **Download** full-text articles for a search | `pubmed-stream download QUERY` | `search_and_download()` | PMC ESearch, PMC EFetch | `publications/<query>/PMC*.json` |
| **Map the evidence** around one article | `pubmed-stream neighborhood PMID` | `get_neighborhood()` | PubMed ELink, EFetch, EPost, ESearch | `publications/neighborhood_<PMID>/neighborhood.json` |
| **Build a study's knowledge graph** | `pubmed-stream kg TOPIC -q ... -s ...` | `create_kg()` | All of the above, plus PubMed EFetch for MeSH terms | `kg_<topic>/`, an Obsidian vault |

```mermaid
flowchart LR
    U(["Researcher"]) -->|"topic, searches, key articles"| PS["pubmed-stream<br/>CLI or Python"]
    PS <-->|"E-utilities over HTTPS"| NCBI[("NCBI<br/>PubMed and PMC")]
    PS -->|"JSON per article"| PUB["publications/"]
    PS -->|"Markdown notes"| KG["kg_topic/"]
    KG -->|"Open folder as vault"| OBS["Obsidian<br/>graph view, Bases, search"]
    PUB -->|"read when building"| PS
    AI(["AI assistant"]) <-->|"MCP tools"| PS
    PS <-->|"review"| OL["Ollama<br/>local model"]
```

The only runtime dependency is `requests`. Everything else, including the XML parsing, the YAML frontmatter and the Markdown rendering, uses the Python standard library.

---

## 2. Repository map

```
pubmed-stream/
├── pubmed_stream/
│   ├── __init__.py        public API: everything importable from pubmed_stream
│   ├── __main__.py        python -m pubmed_stream
│   ├── cli.py             argparse front end: init, search, download, list, neighborhood, kg, review, open, mcp
│   ├── corpus.py          compact records of downloaded articles, most-cited works
│   ├── mcp_server.py      MCP server: pubmed-stream's tools for AI assistants
│   ├── review.py          summaries by a local model through Ollama, with checks
│   ├── obsidian.py        opening knowledge graphs in Obsidian
│   ├── assistants.py      init: instructions and MCP settings for Claude Code, Codex, Gemini CLI
│   ├── data/AGENTS.md     the instructions for AI assistants
│   ├── downloader.py      E-utilities client, PMC search and download, JATS parsing
│   ├── neighborhood.py    similar, citing and cited articles of a PubMed article
│   ├── vault.py           Obsidian notes: graph model, merging, rendering, safe rewrites
│   ├── impact.py          how a paper spread: citers of many papers, counts, citing sentences and their kinds
│   └── kg.py              studies: topic, searches and seeds, refresh
├── tests/                 117 offline tests; NCBI and Ollama are faked with canned responses
├── tutorials/             seven notebooks, the AI assistant tutorial, guides, kg_study.py, keyword lists, tools
├── studies/               research done with pubmed-stream, one folder per study with its frozen data, scripts and write-up
├── docs/                  this guide and its figures
├── pyproject.toml         package metadata, dependencies and the tutorials extra
├── CHANGELOG.md           changes in each version
├── CITATION.cff           citation metadata for GitHub's Cite this repository
└── LICENSE                MIT
```

| Module | Lines | Responsibility | Main public functions |
|--------|------:|----------------|-----------------------|
| `downloader.py` | 1109 | HTTP client with rate limiting and retries; PMC search and summaries; full-text download; metadata, reference and text extraction from JATS XML | `search_and_download`, `search_pmc`, `esearch_pmc`, `esummary_pmc`, `efetch_pmc`, `extract_metadata_from_pmc_xml` |
| `neighborhood.py` | 457 | ELink relations, PubMed records with flags and MeSH terms, flag counts beyond the cap | `get_neighborhood`, `save_neighborhood`, `download_neighborhood` |
| `vault.py` | 1099 | Merges every source into one graph of papers, concepts and collections, then writes notes without losing user edits, with Obsidian property types and a Bases table | `build_vault`, `topic_vault_dir` |
| `kg.py` | 247 | The study layer: runs searches and seeds, records them, refreshes them | `create_kg`, `load_study`, `record_study` |
| `impact.py` | 383 | How a paper spread: the citers of many papers at once, counts by year and flag through PubMed's history server, the sentences in which full texts or Semantic Scholar cite it and their kind, and the annotation of a knowledge graph; used by tutorial 8 | `citers_of`, `count_by_year`, `count_flags`, `citation_contexts`, `classify`, `semantic_scholar_contexts`, `annotate` |
| `corpus.py` | 95 | Reads downloaded articles back as compact records, each once; counts the works they cite | `list_articles`, `most_cited` |
| `review.py` | 249 | Summaries by a local model through Ollama's API, at temperature 0, with number and citation checks | `review`, `save_to_vault` |
| `mcp_server.py` | 357 | The Model Context Protocol over standard input and output, with seven tools; library output kept off the protocol | `serve` |
| `obsidian.py`, `assistants.py` | 166 | Opening graphs through Obsidian URIs; writing instructions and MCP settings into a research folder | `open_vault`, `init_folder` |
| `cli.py` | 767 | Parses arguments and maps them onto the functions above; sets exit codes; writes UTF-8 to pipes | `main` |

The modules form a strict stack. Each one imports only from the modules below it, so the download layer never knows about vaults, and the vault never calls the CLI. Nothing in the package imports `impact.py`; tutorial 8 does:

```mermaid
flowchart TB
    M["mcp_server.py<br/>tools for AI assistants"] --> C
    M --> KG
    M --> V
    M --> N
    M --> D
    CLI["cli.py<br/>init / search / download / list /<br/>neighborhood / kg / review / open / mcp"] --> KG["kg.py<br/>create_kg, studies"]
    CLI --> M
    CLI --> RV["review.py<br/>Ollama summaries"]
    RV --> C
    RV --> V
    CLI --> C["corpus.py<br/>list_articles, most_cited"]
    CLI --> V
    CLI --> N
    CLI --> D
    KG --> V["vault.py<br/>build_vault"]
    KG --> N["neighborhood.py<br/>get_neighborhood"]
    KG --> D["downloader.py<br/>search_and_download"]
    I["impact.py<br/>citers_of, citation_contexts"] --> V
    I --> D
    V --> N
    V --> D
    N --> D
    D --> R(["requests"])
```

---

## 3. Talking to NCBI

Every request goes through one of two paths in `downloader.py`. Both share a thread-safe `RateLimiter`, so concurrent downloads never exceed NCBI's limits.

| Endpoint | Database | Used for | Called by |
|----------|----------|----------|-----------|
| `esearch.fcgi` | `pmc` | Find PMC articles for a search, up to `max_results` | `esearch_pmc` |
| `esummary.fcgi` | `pmc` | Titles, journals, years and identifiers, to preview a search without downloading | `esummary_pmc`, `search_pmc` |
| `efetch.fcgi` | `pmc` | Full-text JATS XML, one article per request | `efetch_pmc` |
| `elink.fcgi` | `pubmed` | Similar, citing and cited articles, in one call with `cmd=neighbor_score` | `get_neighborhood` |
| `efetch.fcgi` | `pubmed` | PubMed records: titles, publication types, grants, MeSH terms; 200 PMIDs per request | `get_neighborhood`, `build_vault` |
| `epost.fcgi` + `esearch.fcgi` | `pubmed` | Count reviews, retractions, NIH funding and PMC coverage across links beyond the cap | `get_neighborhood` |
| Ollama `/api/generate` | local | One summary per abstract, at temperature 0 with a length cap; not NCBI, and only when you run `review` | `review` |

| Setting | Value | Why |
|---------|-------|-----|
| Requests per second | 10 with `NCBI_API_KEY`, 3 without | NCBI's published limits; detected automatically |
| Retries | 3 attempts, waiting 2 s, then 4 s | Rides out rate-limit replies (HTTP 429) and network blips |
| Timeout | 60 s per request | Large full-text articles |
| Download threads | 5 by default, `--workers` to change | Full text is fetched one article per request |
| API key in logs | Always redacted | Error messages from `requests` contain the full URL |

The shared request helper is short enough to read in full. This is its core:

```python
for attempt in range(retries):
    try:
        rate_limiter.wait()                      # shared across threads
        resp = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        error = _redact_api_key(e)               # never log the API key
        logger.warning("%s attempt %d/%d failed: %s", endpoint, attempt + 1, retries, error)
        if attempt < retries - 1:
            time.sleep(RETRY_DELAY * (attempt + 1))
raise requests.RequestException(f"{endpoint} failed: {error}")
```

---

## 4. Downloading full text

```mermaid
sequenceDiagram
    participant U as You
    participant D as search_and_download
    participant N as NCBI E-utilities
    participant F as publications/query/
    U->>D: query, max_results
    D->>N: ESearch db=pmc
    N-->>D: PMC IDs and total count
    D->>F: query.json, the original search
    par up to 5 threads
        D->>N: EFetch db=pmc, one article
        N-->>D: JATS XML
        D->>D: no body? unavailable, publisher withholds XML
        D->>D: extract metadata, references, text
        D->>F: PMCxxxx.json
    end
    D-->>U: DownloadStats
```

Re-running a search skips files that already exist, so a refresh only downloads new articles. Each article becomes one JSON file:

```json
{
  "pmcid": "PMC13279599",
  "source": "PMC",
  "download_date": "2026-10-18T13:20:45",
  "metadata": {
    "pmid": "42060019",
    "doi": "10.1007/s40520-026-03403-6",
    "title": "Association between gut microbiota and sarcopenia in older adults: ...",
    "journal": "Aging Clinical and Experimental Research",
    "year": "2026",
    "authors": ["Ramezani Kashal Fatemeh", "..."],
    "abstract": "Introduction Investigating gut microbiota has emerged ...",
    "keywords": ["Sarcopenia", "Gut microbiota", "Aging", "Muscle metabolism"],
    "references": [
      {"pmid": "32033882", "title": "Asian Working Group for Sarcopenia: 2019 Consensus Update ...", "year": "2020"}
    ]
  },
  "text": "Introduction\nInvestigating gut microbiota ..."
}
```

| Extracted from the JATS XML | Field | Notes |
|-----------------------------|-------|-------|
| Article IDs | `pmid`, `pmcid`, `doi` | From `article-id` elements |
| Title, journal, dates | `title`, `journal`, `year`, `month`, `day` | Electronic publication date preferred |
| Authors | `authors` | "Surname Given names" |
| Abstract and keywords | `abstract`, `keywords` | All abstract sections joined |
| Reference list | `references` | Cited works with a PMID or DOI; these become citation links in the knowledge graph |
| Body text | `text` | Title, abstract and body, one paragraph per line; omitted with `--exclude-text` |

---

## 5. Evidence neighborhoods

A neighborhood is the programmatic counterpart of NLM's Linked Discoveries page for one article. It costs two requests for up to 200 articles, plus five more for each relation that `max_per_relation` cuts short.

```mermaid
sequenceDiagram
    participant U as You
    participant G as get_neighborhood
    participant N as NCBI E-utilities
    U->>G: PMID, max_per_relation
    G->>N: ELink pubmed, cmd=neighbor_score
    N-->>G: similar with scores, cited by, references
    G->>N: EFetch pubmed, seed and neighbors, 200 per request
    N-->>G: titles, publication types, grants, MeSH terms
    opt a relation was cut by max_per_relation
        G->>N: EPost all its PMIDs
        G->>N: ESearch x4, reviews, retracted, NIH, in PMC
        N-->>G: flag counts over every linked article
    end
    G-->>U: Neighborhood
```

| Flag on each article | How it is decided |
|----------------------|-------------------|
| `is_review` | Publication type is Review, Systematic Review or Scoping Review |
| `is_retracted` | Publication type Retracted Publication, or a RetractionIn notice |
| `nih_funded` | An N.I.H. support publication type, or a grant whose agency names NIH |
| `pmcid` | The article has a PMC ID, so its full text may be downloadable |
| `mesh_terms` | MeSH descriptors, each with its ID and a major-topic flag |

---

## 6. Knowledge graphs

### 6.1 A study from start to finish

`create_kg` is the study layer. It runs what is new, or everything with `refresh=True`, then hands the folders to `build_vault`:

```mermaid
sequenceDiagram
    participant U as You
    participant K as create_kg
    participant S as study.json
    participant D as search_and_download
    participant H as get_neighborhood
    participant V as build_vault
    U->>K: topic, queries, seeds, refresh
    K->>S: read earlier searches and seeds
    loop each search to run
        K->>D: query
        D-->>K: download folder, or an error to report
    end
    loop each seed to run
        K->>H: PMID
        H-->>K: neighborhood folder, or an error to report
    end
    K->>S: save every search and seed
    K->>V: new folders
    V-->>K: VaultStats
    K-->>U: KGResult with errors listed
```

A failed search or seed never stops the study. It is listed in `KGResult.errors`, kept in `study.json` so a refresh retries it, and the graph is built from everything else.

### 6.2 How notes are built

```mermaid
flowchart TB
    A["Sources<br/>remembered + new folders"] --> B["Load articles<br/>PMC*.json"]
    B --> C["Load neighborhoods<br/>neighborhood.json"]
    C --> D["Resolve reference lists<br/>PMID, else DOI, to papers"]
    D --> E{"Paper lacks<br/>MeSH terms?"}
    E -->|"yes, and online"| F["EFetch PubMed<br/>200 per request, cached"]
    E -->|"no, or offline"| G["Render notes"]
    F --> G
    G --> H["papers/"]
    G --> I["concepts/"]
    G --> J["collections/"]
    G --> K["PubMed Stream.md"]
```

Papers from different sources are merged into one record, so a paper found by two searches and one neighborhood still has one note.

| Rule | Behaviour |
|------|-----------|
| Identity | A paper is matched by PMID, then PMC ID, then DOI. Its note is named `PMID<id>`, or by PMC ID when there is no PMID |
| First known value wins | Full-text metadata loads first, so PMC titles and abstracts win over PubMed summaries |
| Flags | Review, retracted and NIH-funded are OR-ed across sources |
| Full text | A paper becomes full text when any source downloaded it; otherwise it is a stub |
| Notes | Only papers with a known title, or with full text, get a note; others stay as unresolved links |
| Concepts | Every MeSH heading becomes a concept note, except check tags such as Humans, Male or Aged |
| Citations | Reference-list entries with a PMID, plus neighborhood cites and cited-by links. DOI-only references are listed but not linked |

### 6.3 Safe rebuilds

Users write in these notes, so a rebuild must never destroy their work. Each note has a generated block between two markers, and the tool owns a fixed list of frontmatter keys:

```mermaid
flowchart TB
    S["Render the note"] --> X{"File exists?"}
    X -->|"no"| W["Write frontmatter, block<br/>and an empty Notes heading"]
    X -->|"yes"| M["Merge frontmatter:<br/>replace owned keys, keep the user's,<br/>union tags and aliases"]
    M --> R["Replace only the text between<br/>the pubmed-stream markers"]
    R --> Q{"Content changed?"}
    Q -->|"no"| U["Leave the file untouched"]
    Q -->|"yes"| W2["Write the file"]
```

| Part of a note | Owned by | On rebuild |
|----------------|----------|------------|
| Owned frontmatter keys, such as `title`, `pmid`, `mesh` and `status` | pubmed-stream | Replaced |
| `tags` and `aliases` | Both | The tool's `pubmed/...` tags are replaced; the user's entries are kept |
| Any other frontmatter key | The user | Kept as written |
| Text between `%% pubmed-stream:start %%` and `%% pubmed-stream:end %%` | pubmed-stream | Replaced |
| Everything else, such as the `## Notes` section | The user | Kept as written |

### 6.4 On disk

```
publications/                                 downloads, shared by every study
├── gut_microbiota_Title_AND_frailty_Title_Abstract/
│   ├── query.json                            the original search
│   └── PMC13279599.json ...
└── neighborhood_31319564/
    └── neighborhood.json
kg_gut_microbiome_frailty/                    one study = one Obsidian vault
├── PubMed Stream.md                          home note
├── papers/PMID42060019.md ...                one note per paper
├── concepts/Sarcopenia.md ...                one note per MeSH heading
├── collections/Search - ... .md              one note per search or neighborhood
├── reviews/<question> (date).md ...         summaries by a local model, from 'review --vault'
├── Papers.base                              a Bases table of the papers, first build only
├── .obsidian/graph.json                      graph-view colour groups, first build only
├── .obsidian/types.json                      property types, added for missing keys only
└── .pubmed-stream/
    ├── study.json                            topic, searches, seeds
    ├── sources.json                          download folders the graph is built from
    └── pubmed_records.json                   cached PubMed records with MeSH terms
```

---

## 7. AI assistants, local models and Obsidian

The three jobs above are also reachable from the tools researchers work in. None of these adds a dependency: they use the standard library, `requests`, and programs the researcher installs separately.

| Connection | Module | Talks to | How |
|------------|--------|----------|-----|
| AI assistants call pubmed-stream's tools | `mcp_server.py` | Claude Code, Codex and other MCP clients | JSON-RPC over standard input and output |
| A research folder is set up for them | `assistants.py` | Claude Code, Codex, Gemini CLI | Instruction and settings files |
| A local model summarizes abstracts | `review.py` | Ollama | HTTP to `127.0.0.1:11434` |
| A graph opens in Obsidian | `obsidian.py` | Obsidian | The `obsidian://` URI scheme |

### 7.1 The MCP server

`pubmed-stream mcp` implements the Model Context Protocol's tool features directly: `initialize`, `ping`, `tools/list` and `tools/call`, one JSON object per line. It answers the protocol versions from 2024-11-05 to 2025-11-25. Messages are handled one at a time, so an assistant that calls tools in parallel still sends NCBI one request at a time.

```mermaid
sequenceDiagram
    participant A as AI assistant
    participant M as pubmed-stream mcp
    participant L as pubmed-stream library
    participant N as NCBI
    A->>M: initialize
    M-->>A: tools capability and instructions
    A->>M: tools/list
    M-->>A: seven tools with JSON schemas
    A->>M: tools/call search_pmc
    M->>L: search_pmc(query)
    L->>N: ESearch, ESummary
    N-->>L: count, titles
    Note over M,L: progress printed by the library is captured,<br/>so standard output carries only the protocol
    L-->>M: SearchResult
    M-->>A: compact text result
```

| Tool | Read-only | Wraps |
|------|:---------:|-------|
| `search_pmc` | yes | `search_pmc` |
| `download` | no | `search_and_download` |
| `list_articles` | yes | `list_articles`, filtered by IDs |
| `most_cited` | yes | `most_cited` |
| `read_article` | yes | The `text` field of one download, or only its paragraphs that contain a term |
| `neighborhood` | no | `get_neighborhood` and `save_neighborhood` |
| `build_knowledge_graph` | no | `create_kg` |

Each tool is marked read-only or not, so clients can run read-only tools without asking; Codex does. Problems a user can fix, such as a missing folder or NCBI being unreachable, come back as tool results with `isError` set, so the assistant reads and explains them; only unknown tools and methods are protocol errors. Paths are relative to the folder the server starts in, which assistants set to the project folder, or to `--root`.

### 7.2 Setting up a folder

`pubmed-stream init` writes what each assistant reads when it starts in a folder:

| File | Read by | Contents |
|------|---------|----------|
| `AGENTS.md` | Codex, and through imports the others | The instructions, shipped in the package as `pubmed_stream/data/AGENTS.md` |
| `CLAUDE.md`, `GEMINI.md` | Claude Code, Gemini CLI | `@AGENTS.md`, which imports the instructions |
| `.mcp.json` | Claude Code | The MCP server, started with the Python that has pubmed-stream installed |
| `.codex/config.toml` | Codex | The same server, with start-up and call timeouts |
| `.claude/settings.json` | Claude Code | The folder's model, with `--claude-model` |
| `.pubmed-stream.json` | `pubmed-stream review` | The folder's local model, with `--review-model` |

Files that exist are kept: the import line and the server entries are added to them if missing, and `AGENTS.md` is rewritten only with `--force`. There is no Codex model option: Codex 0.163 reads a folder's MCP servers but ignores its `model`, as tested, so Codex's model is chosen with `codex -m` or `/model`.

### 7.3 Local reviews

A 1-billion-parameter model cannot design searches or call tools reliably, so `review` keeps it to reading, and keeps everything it cannot be trusted with in code:

```mermaid
flowchart TB
    R["Downloaded articles<br/>chosen by ID"] --> S["One prompt per abstract"]
    S --> O["Ollama<br/>temperature 0, capped length"]
    O --> T["Summary"]
    T --> ID["PMID attached by pubmed-stream"]
    T --> NUM{"Every number<br/>in the abstract?"}
    NUM -->|no| FLAG["Flagged under the summary"]
    ID --> ANS["Optional answer from all summaries"]
    ANS --> CIT{"Every cited PMID<br/>among those read?"}
    CIT -->|no| FLAG2["Listed in bold"]
```

| Choice | Why |
|--------|-----|
| One abstract per request | Fits the model's working memory, and a summary cannot mix two papers |
| Temperature 0 | The same articles give the same summaries |
| `num_predict` 300, or 500 for the answer, and a repeat penalty | At temperature 0 a small model can repeat itself until its context is full; a capped reply is marked as cut |
| `num_ctx` 8192, with a warning when a prompt fills it | `ollama run` uses 4,096 tokens and drops the overflow silently |
| Numbers checked as digits and as words below 100 | Abstracts write "Seventy-two patients"; summaries write "72" |

### 7.4 Obsidian

`build_vault` writes three files for Obsidian, each without overwriting the user's version:

| File | Written | Purpose |
|------|---------|---------|
| `.obsidian/graph.json` | Once, if missing | Colour groups for the graph view |
| `.obsidian/types.json` | Missing keys only | Property types: `year` a number, `retracted` a checkbox, `authors`, `mesh` and `keywords` lists |
| `Papers.base` | Once, if missing | A Bases table of `papers/`, with views for all papers, full text, reviews, retracted papers and `#to-read` |

The home note embeds `Papers.base` and lists the notes in `reviews/`. `open_vault` opens the home note with `obsidian://open?path=...`, but only for folders listed as vaults in Obsidian's own settings file, since Obsidian ignores the URI for folders it does not know.

---

## 8. The example study in figures

The figures below are drawn from the notes of the study in [`tutorials/kg_study.py`](../tutorials/kg_study.py): two searches on the gut microbiome with frailty and with sarcopenia, plus the neighborhood of a 2019 review, PMID 31319564. [`docs/figures/make_figures.py`](figures/make_figures.py) regenerates them from any knowledge graph.

| Part of the graph | Count |
|-------------------|------:|
| Papers with full text, from the two searches | 42 |
| Stub papers, from the seed's neighborhood | 85 |
| MeSH concept notes | 309 |
| Collections | 3 |
| Citation links between papers in the graph | 115 |
| Similar-article links between papers in the graph | 30 |
| Notes in total, with the home note | 440 |

![The example study's knowledge graph](figures/study_graph.png)

*The knowledge graph as a network.* The seed review sits at the center, ringed by its neighborhood of stub papers. Papers from the two searches attach to it through citations. Twelve MeSH concepts, those linked by ten or more papers, sit on the outer ring with the three collections. Papers with no citation inside the graph stay close to the search that found them. Obsidian's graph view shows the same structure, interactively.

![Most connected MeSH concepts](figures/top_concepts.png)

*The concepts that tie the study together.* Gastrointestinal Microbiome links 75 papers and Sarcopenia 50. These hubs are where papers from different searches meet.

![Papers by publication year](figures/papers_by_year.png)

*Searches and neighborhoods complement each other.* The full-text papers from the searches are all from 2025 and 2026, because PMC returns the newest matches first. The seed's neighborhood adds the older literature, peaking in 2019, the seed's own year, through the papers it cites and those PubMed rates as similar.

| Year | 2013 | 2015 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|
| Full text | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 16 | 26 |
| Stub | 1 | 1 | 2 | 9 | 25 | 4 | 7 | 4 | 4 | 2 | 0 | 26 |

---

## 9. Data model

```mermaid
classDiagram
    class DownloadStats {
        keyword
        total_found
        requested
        successful
        skipped
        unavailable
        errors
        output_dir
    }
    class RelatedArticle {
        pmid
        pmcid
        doi
        title
        year
        pub_types
        is_review
        is_retracted
        nih_funded
        score
        mesh_terms
    }
    class Neighborhood {
        pmid
        seed
        similar
        cited_by
        references
        totals
        flag_counts
        articles()
    }
    class VaultStats {
        vault_dir
        sources
        papers
        full_text
        stubs
        concepts
        collections
        created
        updated
        unchanged
    }
    class KGResult {
        topic
        kg_dir
        queries
        seeds
        downloads
        neighborhoods
        vault
        errors
    }
    Neighborhood "1" o-- "*" RelatedArticle : seed, similar, cited_by, references
    KGResult "1" o-- "*" DownloadStats : downloads
    KGResult "1" o-- "*" Neighborhood : neighborhoods
    KGResult "1" o-- "0..1" VaultStats : vault
```

| Class | Returned by | Meaning |
|-------|-------------|---------|
| `DownloadStats` | `search_and_download`, `download_neighborhood` | One download run: found, requested, saved, skipped, unavailable |
| `RelatedArticle` | inside `Neighborhood` | One PubMed article with its flags and MeSH terms |
| `Neighborhood` | `get_neighborhood` | A seed and its three relations, with uncapped totals and flag counts |
| `VaultStats` | `build_vault` | One build of the notes: counts of papers, concepts and changed files |
| `KGResult` | `create_kg` | One run of a study: what ran, what failed, and the build |

---

## 10. Testing

All tests run offline in about two seconds. NCBI is replaced by a fake HTTP adapter that answers by URL, so tests exercise the real request and parsing code:

```python
session = make_session(routes={
    "esearch.fcgi?db=pmc": search_json(["1"]),     # a PMC search finding one article
    "efetch.fcgi?db=pmc": full_xml,                # its JATS full text
    "elink.fcgi": elink_json,                      # a neighborhood
    "efetch.fcgi?db=pubmed": pubmed_xml,           # PubMed records with MeSH terms
})
result = create_kg("gut microbiome study", queries=["gut microbiome"], seeds=["100"],
                   session=session, rate_limit=0, offline=True)
```

| Test file | Tests | Covers |
|-----------|------:|--------|
| `test_parsing.py` | 13 | JATS metadata, dates, references and text extraction |
| `test_download.py` | 12 | Search, download, skipping, unavailable articles, API key redaction, query files, folder names |
| `test_integrations.py` | 15 | MCP protocol and tools, keeping output off the protocol, Ollama reviews and their checks, vault notes, Obsidian property types and the papers base, opening vaults, init |
| `test_search_list.py` | 14 | Search previews, summaries and retries, listing and deduplication, most-cited works, CLI output, quiet mode, UTF-8 pipes |
| `test_neighborhood.py` | 24 | Relations, flags, MeSH terms, capped counts, saving, CLI |
| `test_vault.py` | 25 | Citation links, stubs, concepts, escaping, safe rebuilds, sources, MeSH cache, naming |
| `test_kg.py` | 14 | Studies, refresh, failure reporting, validation, CLI |

```bash
pip install -e ".[dev]"
pytest
```

---

## 11. Extending pubmed-stream

| To add | Change | Keep in mind |
|--------|--------|--------------|
| A new field from the full text | `extract_metadata_from_pmc_xml` in `downloader.py` | Old downloads lack it; read it with a fallback |
| A new flag on neighbors | `_parse_pubmed_article`, and `_FLAG_FILTERS` for uncapped counts, in `neighborhood.py` | Add the matching PubMed search filter |
| A new link type in the graph | `_Graph` loading and `_render_paper` in `vault.py` | Links must point at note names, such as `PMID123` |
| A new note type, such as authors | A renderer and its owned keys in `vault.py` | Add its keys to an owned-keys tuple, or rebuilds will treat them as the user's |
| A Logseq or other output format | A second renderer over the same `_Graph` | The graph model is format-independent; only rendering is Obsidian-specific |
| A new study option | `create_kg` in `kg.py`, then the `kg` parser in `cli.py` | Record anything a refresh must repeat in `study.json` |
