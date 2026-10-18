# pubmed-stream tutorials

These tutorials teach you to use pubmed-stream to get into a new research topic quickly: find the literature, see how it connects, and decide what to read. No programming is needed. Each notebook has one **Your settings** cell where you type your own question, and runs in your web browser with Google Colab or on your own computer.

## Start here

| | |
|---|---|
| **[Tutorial 0: a new research topic in an afternoon](00_new_topic.ipynb)** [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/melhzy/pubmed-stream/blob/main/tutorials/00_new_topic.ipynb) | From a question to a map of its literature in one notebook: size the field, collect the core papers, find the paper everyone cites, build a knowledge graph, read its growth, themes, evidence and gaps, and export a reading list for Zotero. |

Click **Open in Colab** to run it in your browser, with nothing to install. To run it on your own computer instead, follow [how to run the tutorials](guides/setup.md).

## Guides

| Guide | Read it when |
|---|---|
| [How to run the tutorials](guides/setup.md) | You are starting: Colab, installing on Windows or Mac, running a notebook, getting a free NCBI API key |
| [Reading a knowledge graph in Obsidian](guides/obsidian.md) | You have built a graph and want to explore it, search it and write in it |
| [Glossary](guides/glossary.md) | A word such as MeSH, PMC, stub or seed is unfamiliar |
| [What pubmed-stream can and cannot do](guides/limitations.md) | Before you rely on the results, or describe them in a paper |
| [Troubleshooting](guides/troubleshooting.md) | Something does not work |

## Learn each step in depth

Tutorial 0 uses every part of pubmed-stream once. These six tutorials take one step each, with more detail and more charts. They are saved with their results, so you can also just read them on GitHub.

| # | Tutorial | You will learn to | Run |
|---|----------|-------------------|-----|
| 1 | [Getting started](01_getting_started.ipynb) | Download a search, see what each file holds, choose a format, update a download, fetch one article by its PMC ID, rescue a search that finds nothing | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/melhzy/pubmed-stream/blob/main/tutorials/01_getting_started.ipynb) |
| 2 | [Designing searches](02_search_strategies.ipynb) | Turn a loose search into a precise one, use MeSH headings, and check a search before downloading | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/melhzy/pubmed-stream/blob/main/tutorials/02_search_strategies.ipynb) |
| 3 | [A literature-review corpus](03_literature_review.ipynb) | Run a keyword list, merge and deduplicate, screen by theme, export to Excel and a reference manager | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/melhzy/pubmed-stream/blob/main/tutorials/03_literature_review.ipynb) |
| 4 | [The evidence around one paper](04_evidence_neighborhood.ipynb) | Map the papers similar to, citing and cited by a key paper; screen for retractions | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/melhzy/pubmed-stream/blob/main/tutorials/04_evidence_neighborhood.ipynb) |
| 5 | [The knowledge graph of a study](05_knowledge_graph.ipynb) | Build a knowledge graph and explain it in twelve views: composition, sources, years, network, concepts, co-occurrence, most cited and bridge papers, journals, evidence types | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/melhzy/pubmed-stream/blob/main/tutorials/05_knowledge_graph.ipynb) |
| 6 | [Text mining and RAG preparation](06_text_mining.ipynb) | Split full text into sections, see where topics are discussed, prepare passages for AI search tools (RAG) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/melhzy/pubmed-stream/blob/main/tutorials/06_text_mining.ipynb) |

The examples follow real research questions: the gut microbiome in Parkinson's disease, in frailty and sarcopenia, and the oral and gut microbiomes in Alzheimer's disease. Each notebook takes one to five minutes. Results change over time, because new papers keep appearing; the saved results show one run.

## For programmers

```bash
git clone https://github.com/melhzy/pubmed-stream.git
cd pubmed-stream
pip install -e ".[tutorials]"     # pubmed-stream plus jupyter, matplotlib, networkx, pandas
jupyter notebook tutorials
```

Setting the `NCBI_API_KEY` environment variable makes every notebook about three times faster. Everything they download or build goes to `tutorials/workspace/`, which git ignores; delete it to start fresh.

| File | What it is |
|------|------------|
| [`kg_study.py`](kg_study.py) | Tutorial 5's study as a short script to copy and adapt; run it again with `--refresh` to add new papers |
| [`tutorial_utils.py`](tutorial_utils.py) | Helpers the notebooks share: chart style and colours, `read_kg`, which reads a knowledge graph's notes into Python, and Colab support |
| [`keywords/`](keywords/) | Keyword lists from real projects, with categories, priorities and rationales; tutorial 3 uses one |
| [`tools/manage_text_field.py`](tools/manage_text_field.py) | Add, remove or check the `text` field of downloaded files, to save space or restore it from the XML |

The charts share one colour code: **blue** for papers with full text, **grey** for stub papers, **aqua** for MeSH concepts and **orange** for collections. The palette was checked for colour-blind readers, and every chart labels its values directly. Obsidian's graph view uses its own colours, which the [Obsidian guide](guides/obsidian.md#the-graph-view) lists.
