# pubmed-stream tutorials

Six notebooks, each a complete use case built on real NCBI data. They are saved with their outputs, so you can read them on GitHub without running anything. Run them in order the first time: later tutorials reuse what earlier ones downloaded.

| # | Tutorial | You will learn to | Charts and outputs |
|---|----------|-------------------|--------------------|
| 1 | [Getting started](01_getting_started.ipynb) | Download a search, read the JSON files, choose a format, resume a download | Article length, linkable references, file size by format |
| 2 | [Designing searches](02_search_strategies.ipynb) | Turn a loose search into a precise one, and check it before downloading | Size and precision of five search versions, download availability |
| 3 | [A literature-review corpus](03_literature_review.ipynb) | Run a keyword list, merge and deduplicate, screen by theme, export to CSV and BibTeX | Search sizes and overlap, years, journals, themes |
| 4 | [The evidence around one paper](04_evidence_neighborhood.ipynb) | Map similar, citing and cited papers; screen for retractions | Relation sizes, flags by relation, timeline, a retracted paper's citations |
| 5 | [The knowledge graph of a study](05_knowledge_graph.ipynb) | Build an Obsidian knowledge graph and explain what it contains | Twelve views: composition, sources, years, the network, concepts, co-occurrence, most cited and bridge papers, journals, evidence types |
| 6 | [Text mining and RAG preparation](06_text_mining.ipynb) | Split full text into sections, compare topics by section, chunk text for embeddings | Words per section, topics by section, most cited works, chunks |

The examples follow real research questions: the gut microbiome in frailty and sarcopenia, and the oral and gut microbiomes in Alzheimer's disease.

## Running them

```bash
git clone https://github.com/melhzy/pubmed-stream.git
cd pubmed-stream
pip install -e ".[tutorials]"     # pubmed-stream plus jupyter, matplotlib, networkx, pandas
cd tutorials
jupyter notebook
```

Each notebook takes one to three minutes. Setting the `NCBI_API_KEY` environment variable makes them about three times faster. Everything they download or build goes to `tutorials/workspace/`, which git ignores; delete it to start fresh.

Results change over time, because PMC returns the newest matches first and new papers keep appearing. The saved outputs show one run.

## Also in this folder

| File | What it is |
|------|------------|
| [`kg_study.py`](kg_study.py) | Tutorial 5's study as a short script to copy and adapt; run it again with `--refresh` to add new papers |
| [`tutorial_utils.py`](tutorial_utils.py) | Helpers the notebooks share: chart style and colours, and `read_kg`, which reads a knowledge graph's notes into Python |
| [`keywords/`](keywords/) | Keyword lists from real projects, with categories, priorities and rationales; tutorial 3 uses one |
| [`tools/manage_text_field.py`](tools/manage_text_field.py) | Add, remove or check the `text` field of downloaded files, to save space or restore it from the XML |

## Colours

The charts share one colour code, which also matches the knowledge graph's colours in Obsidian: **blue** for papers with full text, **grey** for stub papers, **aqua** for MeSH concepts and **orange** for collections. The palette was checked for colour-blind readers, and every chart labels its values directly.
