# Measuring the paper's footprint in language-model training

The question: how much of what language models learned about Aβ\*56 came from the retracted paper and the papers built on it, and do models know that it fell? Three measurements, from text to model.

## 1. Which of the citing papers are in open training corpora

The 1,240 papers citing the retracted paper (first step) and the ~45,000 citing one of those (second step) are the text through which its claim reached models. Three public corpora can be checked directly.

| Corpus | What it holds | How to test membership |
|---|---|---|
| **The Pile** (Gao et al., 2020, arXiv:2101.00027; datasheet Biderman et al., 2022, arXiv:2201.07311) | *PubMed Central*: the PMC Open Access subset, about 90 GiB, 14.4% of training weight at 2 epochs. *PubMed Abstracts*: abstracts of about 30 million PubMed records (19 GiB, 3.07%), excluding articles already in PMC and about a third dropped for malformed titles or abstracts | Every PubMed record before the 2020 snapshot with an abstract is in it; every PMC OA article is in it in full. Membership of a citing paper is therefore: has an abstract (PubMed), and is in the PMC OA subset (PMC `open access[filter]`) |
| **peS2o** (Soldaini & Lo, Hugging Face `allenai/peS2o`) and **Dolma** (Soldaini et al., 2024, arXiv:2402.00159), which contains it | About 40 million open-access papers from S2ORC; v1 knowledge cutoff 3 January 2023 | Semantic Scholar's open-access flag on each citing paper approximates it; exact membership needs the dataset's corpus IDs |
| **Models trained on them** | GPT-Neo, GPT-J, GPT-NeoX, Pythia (The Pile); OLMo (Dolma); and, less transparently, most models whose cards list PubMed or PMC | Compare by training cutoff rather than by corpus |

`scripts/corpus_membership.py` converts PMIDs to PMCIDs through E-utilities, asks PMC which are in the Open Access subset, and writes `data/corpus_membership.csv`. The second-step flags from `scripts/fetch_hop2.py` already give how many of the ~45,000 are in PMC at all.

## 2. How often the claim and its correction appear in training text

Document membership says a paper was seen; it does not say what the model read about Aβ\*56. Two counts fix that.

- **String counts in whole corpora.** infini-gram (Liu et al., 2024, arXiv:2401.17377; API at infini-gram.readthedocs.io) counts any string in Dolma v1.7 (`v4_dolma-v1_7_llama`) and The Pile's training set (`v4_piletrain_llama`). Count the claim strings (`Aβ*56`, `Abeta*56`, `Aβ star 56`, `56-kDa`, `Aβ*56 impairs memory`) against the correction strings (`Lesné` near `retract`, `Aβ*56` near `artifact`, `manipulated`). The ratio is the corpus's own balance between the claim and its doubt. `scripts/corpus_membership.py --strings` does this.
- **Citing sentences by period.** pubmed-stream's reading of the citing papers' full text, frozen in `data/citing_papers.csv`, says how each paper used the retracted one. By period, among the papers that could be read:

| Period | Names Aβ\*56 | Cites it in general | Discusses the doubts or retraction |
|---|---:|---:|---:|
| 2006–2011 | 71 | 220 | 1 |
| 2012–2016 | 59 | 253 | 0 |
| 2017–2021 | 42 | 170 | 0 |
| 2022–2023 | 7 | 33 | 4 |
| 2024–2026 | 1 | 11 | 7 |

Until 2022, essentially every sentence a model could have read that cited the paper either took Aβ\*56 as a finding or used the paper as support for a general claim; the corrective sentences are 12 of 879 and all but one are from 2022 on. Full text for 1,156 of the 1,240 citing papers is in PubMed Central, and 301 of them are reviews, the papers most likely to be paraphrased into textbooks and other secondary text.

## 3. What models say

`probes/questions.yaml` holds the questions, grouped by the four classes in `docs/what_was_wrong.md` (Aβ\*56-specific claims, general oligomer claims, over-correction traps, retraction awareness), each with the points a correct answer must contain and the errors to score. `scripts/probe_models.py` asks each question of:

- local models through Ollama, with tools off by construction (`gpt-oss:20b`, `qwen3.5`, `gemma4` are installed; add models with cutoffs before July 2022, such as Llama 2, and between July 2022 and June 2024, such as Llama 3);
- the installed assistants through pubmed-stream's `ask_assistant`, which runs Claude Code, Codex or Gemini CLI in an empty folder with their tools turned off, so the answer is parametric knowledge only.

Each question is asked three times per model; the answers are saved as JSON lines under `probes/answers/` and scored by hand with the rubric in the questions file (an LLM judge can pre-score, but the final scores are read by a person). The analysis crosses the score with the model's published training cutoff relative to the three dates: 21 July 2022, 24 June 2024 and 23 December 2025.

Prior work found the same failure for other retracted papers: ChatGPT answered questions from retracted cancer-imaging papers without noting the retraction in most cases (Li & Wang, 2025, [10.1016/j.jare.2025.03.020](https://doi.org/10.1016/j.jare.2025.03.020)); across 217 retracted or otherwise concerning studies, none of 6,510 ChatGPT reports mentioned a retraction (Thelwall et al., 2025, [10.1002/leap.2018](https://doi.org/10.1002/leap.2018)); no AI tool handled 15 retracted articles consistently (Labenbacher et al., 2026, [10.2196/88766](https://doi.org/10.2196/88766)); and models' awareness of retractions is patchy (Thelwall, 2026, [10.1108/lm-04-2026-0052](https://doi.org/10.1108/lm-04-2026-0052)). Adetayo (2026, [10.1177/02663821261460796](https://doi.org/10.1177/02663821261460796)) argues the mechanism: publisher licensing deals deliver whole archives into training data without retraction filtering. This study adds what those did not have: one paper with a measured citation tree, a classified reading of how each citing paper used it, and a claim with a known correct status in three parts.

### String counts, measured 20 October 2026

infini-gram counts of each string in Dolma v1.7 (the corpus of the OLMo models, assembled before the retraction) and in The Pile's training set (assembled in 2020). The claim strings are present; the correction strings are absent, except the title of the *Science* investigation, which appears 12 times in Dolma.

| String | Kind | Dolma v1.7 | Pile (train) |
|---|---|---:|---:|
| `Aβ*56` | claim | 1,960 | 85 |
| `Abeta*56` | claim | 80 | 15 |
| `Aβ*56 impairs memory` | claim | 7 | 0 |
| `56-kDa soluble` | claim | 26 | 10 |
| `Lesné` | name | 2,477 | 272 |
| `Blots on a field` | correction | 12 | 0 |
| `Lesné retracted`, `Aβ*56 retracted`, `Aβ*56 artifact`, `Lesné image manipulation`, `Aβ*56 could not be replicated` | correction | 0 | 0 |

Counts are of exact token sequences under the Llama-2 tokenizer, so paraphrases of the correction are not counted; the asymmetry is still the point. `data/corpus_strings.json` holds the raw result.

## 4. Controls

- A retracted paper with an older, louder correction: Wakefield et al. 1998 (PMID 9500320), retracted in 2010, is pubmed-stream's own example in its README and lets the same pipeline run on a case where the correction dominates the corpus.
- A non-retracted paper of similar age and citation count from the same field, for the baseline rate at which models hedge.

## Status

| Step | Script | State |
|---|---|---|
| Freeze the citing papers from tutorial 8's saved graph | `scripts/freeze_from_kg.py` | Done, snapshot of 19 October 2026 |
| Fetch the second step and size the field | `scripts/fetch_hop2.py` | See `data/reach.json` |
| String counts in Dolma and The Pile | `scripts/corpus_membership.py --strings` | Done, 20 October 2026 |
| PMC Open Access membership of the citing papers | `scripts/corpus_membership.py --membership` | Done, 20 October 2026: 535 of 1,240 and 29,875 of 44,957 in the Open Access subset |
| Model probes | `scripts/probe_models.py`, `probes/questions.yaml` | Runner tested on gpt-oss:20b (two questions: both answered with confident fabrications and no retraction); full run not started |
| Analysis notebooks and figures | `notebooks/` | Not started |
