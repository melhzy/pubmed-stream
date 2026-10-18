# Glossary

The words used in pubmed-stream's tutorials and output, in plain language.

**Abstract.** The summary at the start of a paper. Paper notes include it for downloaded papers.

**AI assistant.** Here, an AI that can run commands in a terminal, such as Claude Code, Codex or Gemini CLI. It can drive pubmed-stream for you; see [tutorial 7](../07_ai_assistant.md).

**API key.** A free personal code from NCBI that raises its speed limit from 3 to 10 requests per second. See [getting a key](setup.md#getting-a-free-ncbi-api-key).

**Bases.** An Obsidian core plugin that shows notes as a table, filtered and sorted by their properties. Every knowledge graph has one, `Papers.base`; see the [Obsidian guide](obsidian.md#a-table-of-all-papers).

**Boolean operators.** `AND`, `OR` and `NOT`, written in capitals, combine search terms. `A AND B` needs both, `A OR B` either, `A NOT B` excludes B. Brackets group them: `(A OR B) AND C`.

**Bridge paper.** A paper that links parts of a knowledge graph that are otherwise far apart, such as two lines of research. Measured by *betweenness centrality*. Bridge papers are good early reads.

**Cell.** One box of a notebook. Text cells explain; code cells run and show their results underneath.

**Chunk.** A passage of a few hundred words cut from a paper, the unit that embedding models and RAG systems work on. Tutorial 6 makes them.

**Collection.** In a knowledge graph, a note for one search or one evidence neighborhood, listing the papers it brought in.

**Colab.** Google Colaboratory, a free service that runs notebooks in the web browser. See [option 1](setup.md#option-1-google-colab-nothing-to-install).

**Concept note.** In a knowledge graph, a note for one MeSH heading, listing every paper indexed with it.

**Corpus.** The set of papers a study works with, such as all the downloads of a literature review.

**DOI.** Digital Object Identifier, a permanent ID for a paper, such as `10.3390/nu11071633`. `https://doi.org/` followed by the DOI opens the paper at its publisher.

**Embedding.** A list of numbers that represents the meaning of a passage, so a computer can find passages with similar meaning. Used for semantic search and RAG.

**E-utilities.** NCBI's public programming interface to PubMed and PMC. pubmed-stream uses it to search, download and follow links.

**Evidence neighborhood.** The papers linked to one key paper: the ones PubMed rates as **similar**, the ones that **cite** it (*cited by*) and the ones it cites (*references*). Tutorial 4 explores one.

**Field tag.** A label in square brackets that limits a search term to part of a record: `[Title]`, `[Title/Abstract]`, `[mh]` for MeSH, `[pdat]` for publication date. `frailty[Title]` finds papers with *frailty* in the title.

**Full text.** The whole paper, not only its abstract. pubmed-stream downloads full text from PMC when the publisher allows it.

**Graph view.** Obsidian's map of a vault: every note a dot, every link a line. See the [Obsidian guide](obsidian.md#the-graph-view).

**Instructions file.** A text file, such as `AGENTS.md` or `CLAUDE.md`, that an AI assistant reads when it starts in a folder. pubmed-stream's tells it how to search and to cite only papers it has read.

**JATS XML.** The standard format in which PMC stores papers, with every section, figure caption and reference marked up. pubmed-stream can keep it for text mining (`fmt="both"`).

**JSON.** A plain-text file format for structured data. pubmed-stream saves each paper as one JSON file, `PMC<number>.json`, readable by any programming language.

**Key paper, or seed.** A paper whose evidence neighborhood you add to a study, usually a landmark review or discovery. Tutorial 0 finds one automatically: the paper your downloads cite most.

**Knowledge graph.** A network of linked facts. Here, an Obsidian vault in which papers, MeSH concepts and searches are notes, linked by citation, similarity and topic. pubmed-stream names it `kg_<topic>`.

**Local model.** An AI model that runs on your own computer, so nothing you give it leaves the machine. [Ollama](https://ollama.com) runs them; small ones summarize text but cannot run commands reliably. See [tutorial 7](../07_ai_assistant.md#8-private-questions-a-model-on-your-own-computer).

**Major topic.** A MeSH heading that NLM's indexers mark as a main point of a paper, as opposed to one that is only discussed. Search for it with `[majr]`.

**MCP.** The Model Context Protocol, an open standard by which AI assistants such as Claude Code and Codex call tools directly. `pubmed-stream mcp` is pubmed-stream's MCP server; `pubmed-stream init` sets it up. See [tutorial 7](../07_ai_assistant.md#3-set-up-a-folder-for-your-question).

**MeSH.** Medical Subject Headings, NLM's controlled vocabulary of about 30,000 biomedical concepts. Indexers tag each paper in **MEDLINE**, PubMed's curated core of journals, with MeSH **headings**, so a MeSH search finds papers about a concept whatever words the authors used. Look up headings in the [MeSH browser](https://www.ncbi.nlm.nih.gov/mesh); search with `[mh]`. New papers take weeks to months to be indexed, and papers in journals outside MEDLINE never are.

**Model.** The AI that an assistant runs on. Each assistant offers several, from fast to most capable; see [choosing a model](../07_ai_assistant.md#4-choose-a-model).

**Metadata.** Information about a paper rather than its text: title, authors, journal, year, identifiers, keywords and references.

**NCBI.** The National Center for Biotechnology Information, part of the US National Library of Medicine (NLM). It runs PubMed and PMC.

**Notebook.** A document that mixes explanations, code and results, such as the tutorials. Jupyter and Colab run them.

**Obsidian.** A free note-taking app that shows linked notes as a graph. See the [Obsidian guide](obsidian.md).

**Ollama.** A free program that runs AI models on your own computer. `pubmed-stream review` uses it to summarize abstracts locally.

**Open access.** Papers whose license allows free reading and reuse. In PMC, `"open access"[filter]` keeps only papers that pubmed-stream can always download.

**PMC.** PubMed Central, NCBI's free archive of full-text papers. pubmed-stream searches PMC and downloads full text from it.

**PMCID.** A paper's ID in PMC, such as `PMC6683074`.

**PMID.** A paper's ID in PubMed, such as `31319564`. Knowledge-graph notes are named after it: `PMID31319564`.

**Precision.** The share of a search's results that are really about the question. Tutorial 2 measures it.

**Property.** A labelled detail at the top of an Obsidian note, such as `year: 2019`. Obsidian can search and sort by properties.

**PubMed.** NCBI's database of more than 35 million biomedical paper records: titles, abstracts, MeSH headings and links, but mostly not full text.

**Publication type.** PubMed's label for what kind of paper a record is: *Journal Article*, *Review*, *Systematic Review*, *Meta-Analysis*, *Randomized Controlled Trial* and more.

**Query.** A search, written in PubMed's search language, such as `"gut microbiota"[Title] AND frailty[Title/Abstract]`.

**RAG.** Retrieval-augmented generation: an AI system that answers questions by first finding relevant passages, such as chunks of papers, and then writing an answer from them, so the answer can cite its sources.

**Rate limit.** The maximum number of requests NCBI accepts per second. pubmed-stream stays within it automatically; an occasional *429 Too Many Requests* message means it waited and retried.

**Recall.** The share of all relevant papers that a search finds. Stricter searches gain precision but can lose recall; combining word and MeSH searches with `OR` recovers it.

**Reference manager.** Software that stores and formats citations, such as Zotero, EndNote or Mendeley. Tutorials 0 and 3 export files they can import.

**Retraction.** The withdrawal of a published paper, for error or misconduct. PubMed marks retracted papers; pubmed-stream flags them, and Obsidian's graph view colours them red.

**Similar articles.** PubMed's list of papers with similar words and MeSH headings, scored by its own algorithm. Scores compare within one paper's list, not across lists.

**Stub.** A paper note without full text, for a paper in a key paper's evidence neighborhood that was not downloaded. It has PubMed's details and links, but no abstract.

**Terminal.** A window for typing commands: *Terminal* or *Command Prompt* on Windows, *Terminal* on a Mac.

**Vault.** Obsidian's name for a folder of notes. A pubmed-stream knowledge graph is a vault.

**Wikilink.** A link between Obsidian notes, written `[[note name]]`.
