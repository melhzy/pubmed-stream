# Aβ\*56 retraction impact: a study

How a retracted Alzheimer's paper spread through the literature, and how much of it language models learned.

The paper is Lesné et al., "A specific amyloid-β protein assembly in the brain impairs memory", *Nature* 440:352–357 (16 March 2006), [PMID 16541076](https://pubmed.ncbi.nlm.nih.gov/16541076/), [10.1038/nature04533](https://doi.org/10.1038/nature04533). It reported Aβ\*56, a 56-kDa soluble amyloid-β assembly that appeared in Tg2576 mice when their memory failed and impaired memory when injected into rats. *Nature* retracted it on 24 June 2024 for "excessive manipulation, including splicing, duplication and the use of an eraser tool" in its figures. It has about 2,400 citations and is the fifth most cited retracted paper on record. **[docs/what_was_wrong.md](docs/what_was_wrong.md)** says what it claimed, exactly what was wrong, and what the retraction does not overturn, with every statement sourced.

The study asks three questions:

1. **How far did the paper reach?** Through the papers citing it and the papers citing those, measured with [tutorial 8](../../tutorials/08_retraction_impact.ipynb) and the package's `impact` module.
2. **How much of that text is in language-model training corpora**, and what did it say: the claim, or its correction?
3. **What do models say** about Aβ\*56 today, by training cutoff?

## Headline numbers

Measured on 19 and 20 October 2026 from PubMed's citation links, which exist only where the citing article's full text was deposited in PubMed Central, so they undercount Google Scholar or Web of Science.

| | Count |
|---|---:|
| Papers citing the retracted paper (first step) | 1,240 |
| Papers citing one of those (second step) | 44,957 |
| Alzheimer's disease papers in PubMed since 2006 within those two steps | 15,050 of 107,315 (14%) |
| Second-step papers that are reviews / NIH-funded / in PubMed Central | 13,473 / 16,488 / 41,778 |
| Second-step papers that are themselves retracted | 118 |
| First-step papers whose citing sentence could be read (full text or Semantic Scholar) | 879 |
| ... of which cite it for a general statement about oligomers and memory | 687 |
| ... of which name Aβ\*56 as a finding | 180 |
| ... of which discuss the retraction or doubts | 12 (11 from 2022 on) |
| First-step papers in PubMed Central / reviews / NIH-funded | 1,156 / 301 / 639 |
| First-step papers with a PubMed abstract / in the PMC Open Access subset (The Pile's two PubMed components) | 1,229 / 535 |
| First-step papers that are themselves retracted | 6 (four with Lesné as an author) |
| Citing publications in scite / citations on Retraction Watch's leaderboard | 2,805 / about 2,400 |

Citations of the paper itself peaked in 2012. The second step still grows: about 4,000 papers a year through 2025 (`data/hop2_by_year.csv`).

## What was wrong, in one paragraph

The record contradicts the data: the retraction names Fig. 2c and Supplementary Fig. 4, and five Lesné papers are now retracted, including the ones that gave Aβ\*56 a dose–response (2011), a receptor (2012) and a signaling pathway to tau (2017). The entity was fragile all along: a dodecamer inferred from a band on a denaturing gel, detected with antibodies that also bind APP fragments, rare and protocol-dependent by its discoverers' own account, never confirmed by another laboratory, and reported as "could not be validated" by a funded replication. What the retraction does not touch is the general claim the paper was cited for most: that soluble Aβ oligomers impair synaptic function and memory, which has independent evidence before and after 2006, and the amyloid hypothesis, which rests on genetics, biomarkers and antibody trials. A correct state of knowledge therefore has three parts, and a model can fail in either direction: stating Aβ\*56 as fact, or rejecting the oligomer evidence because of the retraction. The full account, with sources and a timeline, is in [docs/what_was_wrong.md](docs/what_was_wrong.md).

## How the training footprint is measured

[docs/plan.md](docs/plan.md) gives the design: membership of the citing papers in The Pile (PubMed Central and PubMed Abstracts components), peS2o and Dolma; string counts of the claim and of its correction in those corpora through infini-gram; the citing sentences by period (until 2022, 12 corrective sentences among 879); and probes of local models and installed assistants with their tools off, scored against the four claim classes in `probes/questions.yaml`, crossed with each model's training cutoff relative to 21 July 2022, 24 June 2024 and 23 December 2025.

## First results

**The training text carries the claim, not the correction.** infini-gram counts of exact strings in two open pretraining corpora (`data/corpus_strings.json`, 20 October 2026):

| String | Dolma v1.7 | The Pile (train) |
|---|---:|---:|
| `Aβ*56` | 1,960 | 85 |
| `Abeta*56` | 80 | 15 |
| `Lesné` | 2,477 | 272 |
| `Blots on a field` (the *Science* investigation's title) | 12 | 0 |
| `Lesné retracted`, `Aβ*56 retracted`, `Aβ*56 artifact`, `Lesné image manipulation` | 0 | 0 |

**A first probe answer.** The runner was tested on the local `gpt-oss:20b` with two questions, one repeat each (`probes/answers/ollama_gpt-oss_20b.jsonl`). Asked whether the 2006 *Nature* paper has been retracted, it answered "No", with a table of invented evidence: a wrong PMID, a wrong volume and page range, and "J. L. Selkoe, J. M. Karran, J. A. Hardy" as authors. Asked whether Aβ\*56 is a dodecamer that causes memory loss in mice, it answered "Yes", attributed the discovery to a non-existent "Selkoe et al., *J. Neurosci.* 2008" series with invented experiments, called the dodecamer "widely accepted", and never mentioned Lesné, the investigation or the retraction. Its first attempt at that question spent its whole token budget on hidden reasoning and returned nothing, which is why the runner now caps reasoning effort and records the stop reason. Two answers are an anecdote; the design is 12 questions, three repeats, every installed model.

## View it

Open [`index.html`](index.html) in a browser: the headline numbers, the two citation steps by year, how the citing papers use the paper with every citing sentence searchable, the account of what was wrong, the corpus counts, and the probe questions with the answers so far. The page is a React application, [`app.js`](app.js), with its stylesheet [`styles.css`](styles.css); React and the Markdown renderer load from a CDN, so there is no build step and the page opens from disk. Its data is [`data.js`](data.js), built from the study's files by `python scripts/build_viewer.py`; rebuild it after the data changes.

## Layout

```
studies/abeta56_retraction_impact/
├── README.md
├── index.html                   the study as a web page; open it in a browser
├── app.js                       the page's React application (no build step)
├── styles.css                   its stylesheet
├── data.js                      its data, built from the files below by scripts/build_viewer.py
├── requirements.txt             pyyaml; the rest comes with pip install -e ".[tutorials]"
├── docs/
│   ├── what_was_wrong.md        the claim, what was wrong, what still stands, timeline, sources
│   ├── plan.md                  the measurement design and the status of each step
│   └── references.bib           the sources, formatted from scite's records
├── data/
│   ├── citing_papers.csv        the 1,240 citing papers with the kind of citation and the citing sentence
│   ├── kg_snapshot_papers.csv   every paper in tutorial 8's saved graph (2,023), with its hop
│   ├── hop1_citers.json         for each citing paper, the PubMed IDs of the papers citing it
│   ├── hop2_pmids.txt           the 44,957 second-step papers
│   ├── hop2_by_year.csv         second-step papers by year
│   ├── hop2_flags.json          second-step reviews, retracted, NIH-funded, in PubMed Central
│   ├── reach.json               the headline counts and the share of the field
│   ├── corpus_strings.json      infini-gram counts of the claim and its correction in Dolma and The Pile
│   └── README.md                what each file holds and when it was made
├── scripts/
│   ├── freeze_from_kg.py        data/citing_papers.csv from tutorial 8's saved knowledge graph
│   ├── fetch_hop2.py            the second step, by year and flag, and the field's size
│   ├── corpus_membership.py     PMC Open Access membership and infini-gram string counts
│   ├── probe_models.py          asks the probe questions of Ollama models and installed assistants
│   └── build_viewer.py          builds data.js from the data, documents and probe answers
├── probes/
│   ├── questions.yaml           12 questions in four classes, with expected points and error keys
│   └── answers/                 one JSON-lines file per model
├── notebooks/                   analysis (to come)
├── figures/
└── manuscript/
```

## Reproduce

From the repository root, with the package installed in editable mode:

```bash
pip install -e ".[tutorials]" -r studies/abeta56_retraction_impact/requirements.txt
export NCBI_API_KEY=...                       # optional, three times faster
cd studies/abeta56_retraction_impact

# 1. Freeze the citing papers from tutorial 8's saved graph (or from a fresh run of the notebook)
python scripts/freeze_from_kg.py ../../tutorials/knowledge_graphs/kg_abeta56_retraction_impact --snapshot-date 2026-10-19

# 2. The second step, by year and flag, and the field's size (a few minutes)
python scripts/fetch_hop2.py

# 3. Which citing papers are in the PMC Open Access subset; how often the claim and its correction appear in Dolma and The Pile
python scripts/corpus_membership.py

# 4. Ask the probe questions; answers go to probes/answers/
python scripts/probe_models.py --models ollama:gpt-oss:20b ollama:qwen3.5 ollama:gemma4 claude codex gemini --repeats 3
```

The scripts find the package in the repository, so a clone works without installing; `pyyaml` is the only extra dependency. To study another paper, run tutorial 8 with its settings changed, freeze its graph with step 1, and change `--seed` in step 2.

## Status

| Step | State |
|---|---|
| Citing papers frozen from tutorial 8's run of 19 October 2026 | done |
| Second step fetched (20 October 2026) | done |
| String counts in Dolma and The Pile | done (20 October 2026) |
| PMC Open Access membership of the citing papers | first step done; second step see `data/corpus_membership_summary.json` |
| Model probes | runner tested on gpt-oss:20b with two questions; full run not started |
| Analysis, figures, manuscript | not started |

## Where this sits in pubmed-stream

[Tutorial 8](../../tutorials/08_retraction_impact.ipynb) teaches the tool on this paper: it follows a retracted paper through two citation steps, reads how each citing paper cites it, and builds a knowledge graph of its impact, with the helpers in the package's `impact` module. This folder holds the study the tutorial cannot: the frozen data, the sourced account of what was wrong, the corpus measurements, the probe transcripts and, in time, the manuscript. [`studies/README.md`](../README.md) explains the folder.

## License

MIT, with the repository. The data files derive from PubMed and PubMed Central records (public domain) and from Semantic Scholar's citing sentences (used under its API terms).
