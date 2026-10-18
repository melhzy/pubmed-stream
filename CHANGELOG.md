# Changelog

Notable changes to pubmed-stream. Versions follow [semantic versioning](https://semver.org/).

## Unreleased

### Added

- A `tutorials/` folder for researchers without programming experience, replacing `examples/`. Tutorial 0 takes a research question to a knowledge graph, a reading list and a list of gaps in one afternoon; tutorials 1 to 6 cover each step in depth. Every notebook has one settings cell and runs in Google Colab.
- Guides: setting up from zero, reading a knowledge graph in Obsidian, a glossary, what pubmed-stream can and cannot do, and troubleshooting.
- The `tutorials` install extra: `pip install "pubmed-stream[tutorials]"`.
- `LICENSE`, `CITATION.cff` and this changelog.

### Changed

- The README is rewritten as one guide, from downloading to building a knowledge graph.

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
