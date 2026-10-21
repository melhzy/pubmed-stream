# Studies

Research done with pubmed-stream, kept with its data so the numbers in each study can be checked and the study rerun. A tutorial teaches one step of the tool on a small example; a study asks a research question, freezes what it downloaded, and records what it found. Each study is a folder with its own README, its scripts, its data and its notes. A study may also carry a web page (`index.html` with its app, stylesheet and a data file built from its files), published with the documentation site at `melhzy.github.io/pubmed-stream/studies/<study>/`.

| Study | Page | Question | Status |
|---|---|---|---|
| [`abeta56_retraction_impact`](abeta56_retraction_impact/) | [Open the page](https://melhzy.github.io/pubmed-stream/studies/abeta56_retraction_impact/) | How far did the retracted 2006 *Nature* paper on Aβ\*56 (PMID 16541076, retracted June 2024) spread through the literature, what exactly was wrong with it, and how much of it did language models learn? Continues [tutorial 8](../tutorials/08_retraction_impact.ipynb). | Citation tree frozen; corpus string counts and PMC Open Access membership done; model probes designed and smoke-tested; a context-control unlearning pilot run |

To start a study, copy the layout of an existing one: `README.md` (question, headline numbers, how to reproduce, status), `docs/` (the write-up and sources), `data/` (frozen tables, each dated), `scripts/` (one script per step, runnable from the study folder), and `probes/`, `notebooks/`, `figures/` or `manuscript/` as needed. Everything a script downloads while reproducing goes in `workspace/`, which git ignores.
