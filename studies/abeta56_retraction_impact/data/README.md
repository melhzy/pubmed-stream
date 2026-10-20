# Data

All tables derive from PubMed and PubMed Central records through NCBI's E-utilities, and, for citing sentences of papers whose full text is not in PubMed Central, from Semantic Scholar. PubMed's citation links exist only where the citing article's full text was deposited in PubMed Central, so counts are lower than Google Scholar's or Web of Science's.

| File | Made by | Date | What it holds |
|---|---|---|---|
| `citing_papers.csv` | `scripts/freeze_from_kg.py` from tutorial 8's saved graph | 19 Oct 2026 | The 1,240 papers citing PMID 16541076: `pmid`, `year`, `title`, `journal`, `first_author`, `n_authors`, `pmcid`, `doi`, `review`, `retracted`, `nih_funded`, `status`, `hop` (1), `citation_kind` (one of: Names Aβ\*56; Cites it in general; Discusses the retraction or doubts; No full text, or citation not found), `citation_source` (full text, Semantic Scholar, or empty), `citation_sentence` (the sentence citing the paper, with `[PMID 16541076]` marking the citation), `snapshot_date` |
| `kg_snapshot_papers.csv` | same | 19 Oct 2026 | Every paper in the saved graph (2,023): the retracted paper (hop 0), its citers (hop 1), a sample of second-step papers fetched as neighborhoods (hop 2), and the 100 most similar papers (no hop) |
| `hop1_citers.json` | `scripts/fetch_hop2.py` | 20 Oct 2026 | `{pmid of a citing paper: [pmids of the papers citing it]}` |
| `hop2_pmids.txt` | same | 20 Oct 2026 | The 44,957 second-step papers (cite a citer, do not cite the paper, are not the paper) |
| `hop2_by_year.csv` | same | 20 Oct 2026 | Second-step papers by publication year; the current year is incomplete |
| `hop2_flags.json` | same | 20 Oct 2026 | Second-step counts: reviews, retracted, NIH-funded, in PubMed Central |
| `reach.json` | same | 20 Oct 2026 | The headline counts and the share of Alzheimer's disease papers (MeSH) since 2006 within two steps |
| `corpus_membership.csv`, `corpus_membership_summary.json` | `scripts/corpus_membership.py` | 20 Oct 2026 | Per paper: in PubMed Central, in the PMC Open Access subset; per hop: with abstract |
| `corpus_strings.json` | same | 20 Oct 2026 | infini-gram counts of claim and correction strings in Dolma v1.7 and The Pile |

The `has_full_text` column of the two CSVs is always false: the saved graph holds stub notes (metadata only), not full texts. `pmcid` says whether PubMed Central has the article.
