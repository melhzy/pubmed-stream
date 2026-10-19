# Example knowledge graphs

Knowledge graphs built by the tutorials, saved so you can explore them in [Obsidian](https://obsidian.md) without running anything. Download the repository (on GitHub: **Code > Download ZIP**), unzip it, and in Obsidian choose **Open folder as vault** and select a graph's folder. The [Obsidian guide](../guides/obsidian.md) explains what you will see.

| Graph | Built by | What it holds |
|---|---|---|
| [`kg_abeta56_retraction_impact`](kg_abeta56_retraction_impact/) | [Tutorial 8](../08_retraction_impact.ipynb), 19 October 2026 | The retracted 2006 *Nature* paper on Aβ\*56 ([PMID 16541076](https://pubmed.ncbi.nlm.nih.gov/16541076/)), the 1,240 papers citing it and its 100 most similar papers, and the neighborhoods of 10 citing papers: 6 that were retracted themselves and the 4 most cited that name Aβ\*56. 2,023 papers, 2,426 MeSH concepts. |

## In `kg_abeta56_retraction_impact`

- **PubMed Stream.md** is the home note: start there.
- **Citation impact.base** is a table of the papers citing the retracted one, with one view per kind of citation: those that discuss the retraction or doubts about it, those that name Aβ\*56, those that cite it in general, and the retracted citing papers. Its last column is the sentence in which each paper cites it.
- Each citing paper's note has four properties added by tutorial 8: `hop` (1 for a paper citing it, 2 for a paper citing one of those), `citation_kind`, `citation_sentence`, and `citation_source`, which says whether the sentence was read from the full text or from Semantic Scholar.
- **Papers.base** lists every paper, as in any graph pubmed-stream builds.

The notes hold each paper's title, journal, authors, publication types, MeSH topics, flags and links, not its full text. The graph is a snapshot: papers published since are not in it. To bring it up to date, run tutorial 8 again; it builds a fresh copy in `tutorials/workspace/retraction_impact/`. (`pubmed-stream kg --refresh` is not enough here: it would fetch every seed with the same limit, and the retracted paper needs 5,000 citing papers where the others need 30.)
