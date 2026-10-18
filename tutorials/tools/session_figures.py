"""Chart a literature search done with pubmed-stream, such as an AI assistant's session.

A single file you can copy into any research folder. Run it there, after
pubmed-stream has downloaded papers and built a knowledge graph:

    python session_figures.py                          # charts go to ./figures
    python session_figures.py my-folder --out charts
    python session_figures.py --searches searches.txt  # also chart the searches

| Chart | From |
|---|---|
| ``searches.png`` | ``--searches``: a text file, one ``label | search`` per line, counted again in PMC now |
| ``years.png`` | The downloaded papers in ``publications/`` |
| ``cited.png`` | The works the downloaded papers cite most |
| ``evidence.png`` | The publication types and MeSH headings in the knowledge graph's paper notes, ``kg_*/papers`` |
| ``neighborhood.png`` | ``publications/neighborhood_*/neighborhood.json``, the key paper's neighborhood |

Needs pubmed-stream and matplotlib: ``python -m pip install pubmed-stream matplotlib``.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    sys.exit("This script needs matplotlib: python -m pip install matplotlib")

from pubmed_stream import list_articles, most_cited, search_pmc

# The tutorials' colours: a validated blue for papers, orange for reviews as in Obsidian's graph
BLUE, ORANGE = "#2a78d6", "#eb6834"
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"

OBSERVATIONAL = {"Cohort Studies", "Case-Control Studies", "Cross-Sectional Studies", "Prospective Studies",
                 "Retrospective Studies", "Longitudinal Studies"}
EVIDENCE_ORDER = ["Systematic review or meta-analysis", "Randomized controlled trial", "Other clinical trial",
                  "Observational study", "Animal study", "Other original research", "Narrative review",
                  "Not indexed by PubMed"]


def style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "font.size": 10, "text.color": INK, "axes.labelcolor": INK_2, "axes.edgecolor": GRID,
        "axes.titlesize": 12, "axes.titlelocation": "left", "axes.spines.top": False,
        "axes.spines.right": False, "xtick.color": INK_2, "ytick.color": INK_2, "legend.frameon": False,
    })


def short(text, length):
    text = " ".join((text or "").split())
    return text if len(text) <= length else text[:length - 1].rstrip() + "…"


def properties(note):
    """The list and scalar properties of a note written by pubmed-stream."""
    text = note.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    props, key = {}, None
    for line in text[4:text.find("\n---", 3)].splitlines():
        if line.startswith("  - ") and key:
            props.setdefault(key, []).append(json.loads(line[4:]) if line[4:].startswith('"') else line[4:])
        elif ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            if value.strip():
                props[key] = json.loads(value) if value.strip().startswith('"') else value.strip()
    return props


def evidence(props):
    """A rough evidence type from PubMed's publication types and MeSH headings."""
    types, mesh = set(props.get("publication_types") or []), set(props.get("mesh") or [])
    if types & {"Meta-Analysis", "Systematic Review"}:
        return "Systematic review or meta-analysis"
    if "Randomized Controlled Trial" in types:
        return "Randomized controlled trial"
    if any(t.startswith("Clinical Trial") for t in types):
        return "Other clinical trial"
    if mesh & OBSERVATIONAL:
        return "Observational study"
    if "Review" in types:
        return "Narrative review"
    if "Animals" in mesh and "Humans" not in mesh:
        return "Animal study"
    return "Other original research" if mesh else "Not indexed by PubMed"


def save(fig, out, name):
    path = out / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {path}")


def hbars(ax, labels, values, xlabel):
    bars = ax.barh(labels[::-1], values[::-1], color=BLUE, height=0.62)
    for bar in bars:
        ax.annotate(f"{bar.get_width():,.0f}", (bar.get_width(), bar.get_y() + bar.get_height() / 2),
                    xytext=(4, 0), textcoords="offset points", va="center", fontsize=9, color=INK)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel(xlabel)


def chart_searches(path, out):
    rows = [line.split("|", 1) for line in path.read_text(encoding="utf-8").splitlines() if "|" in line]
    labels = [label.strip() for label, _ in rows]
    counts = [search_pmc(query.strip(), max_results=0).total_found for _, query in rows]
    fig, ax = plt.subplots(figsize=(8, 0.55 * len(labels) + 1.2))
    hbars(ax, labels, counts, "Articles in PubMed Central, log scale")
    ax.set_xscale("log")
    ax.set_title("How many articles each version of the search finds")
    save(fig, out, "searches.png")


def chart_years(records, out):
    years = Counter(int(r["year"]) for r in records if str(r["year"]).isdigit())
    span = list(range(min(years), max(years) + 1))
    fig, ax = plt.subplots(figsize=(8, 3))
    bars = ax.bar(span, [years[y] for y in span], color=BLUE, width=0.7)
    for bar in bars:
        if bar.get_height():
            ax.annotate(f"{bar.get_height():.0f}", (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        xytext=(0, 2), textcoords="offset points", ha="center", fontsize=9, color=INK)
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_ylabel("Papers")
    ax.set_title(f"The {len(records)} downloaded papers by year")
    save(fig, out, "years.png")


def chart_cited(publications, total, out, n=8):
    works = [w for w in most_cited(publications, n * 2) if w["title"]][:n]
    labels = [f"{short(w['title'], 58)} ({w['year'] or 'n.d.'})" for w in works]
    fig, ax = plt.subplots(figsize=(9, 0.5 * len(labels) + 1.2))
    hbars(ax, labels, [w["cited_by"] for w in works], f"Downloaded papers that cite it, of {total}")
    ax.set_title("The works this literature cites most")
    save(fig, out, "cited.png")


def chart_evidence(vault, out):
    notes = [properties(p) for p in sorted((vault / "papers").glob("*.md"))]
    notes = [p for p in notes if p.get("status") == "full-text"]
    if not notes:
        return
    kinds = Counter(evidence(p) for p in notes)
    labels = [k for k in EVIDENCE_ORDER if kinds[k]]
    fig, ax = plt.subplots(figsize=(8, 0.5 * len(labels) + 1.2))
    hbars(ax, labels, [kinds[k] for k in labels], "Downloaded papers")
    ax.set_title(f"What kind of evidence the {len(notes)} downloaded papers are")
    save(fig, out, "evidence.png")


def chart_neighborhood(path, out):
    hood = json.loads(path.read_text(encoding="utf-8"))
    relations = [("similar", "Similar"), ("cited_by", "Citing it"), ("references", "Cited by it")][::-1]
    totals, flags = hood.get("totals", {}), hood.get("flag_counts", {})
    labels = [label for _, label in relations]
    reviews = [flags.get(r, {}).get("reviews", 0) for r, _ in relations]
    others = [totals.get(r, 0) - n for (r, _), n in zip(relations, reviews)]
    fig, ax = plt.subplots(figsize=(8, 2.8))
    ax.barh(labels, others, color=BLUE, height=0.6, edgecolor=SURFACE, lw=1.5, label="Other papers")
    ax.barh(labels, reviews, left=others, color=ORANGE, height=0.6, edgecolor=SURFACE, lw=1.5, label="Reviews")
    for i, (o, r) in enumerate(zip(others, reviews)):
        ax.annotate(f"{r} of {o + r} are reviews", (o + r, i), xytext=(4, 0), textcoords="offset points",
                    va="center", fontsize=9, color=INK)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_xlim(0, max(o + r for o, r in zip(others, reviews)) * 1.45)
    ax.set_xlabel("Papers linked in PubMed")
    ax.legend(loc="lower right")
    ax.set_title(f"The evidence around PMID {hood.get('pmid') or path.parent.name.split('_')[-1]}")
    save(fig, out, "neighborhood.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", nargs="?", default=".", help="The research folder (default: this folder)")
    parser.add_argument("--out", default="figures", help="Where to save the charts (default: ./figures)")
    parser.add_argument("--searches", type=Path, help="A file of 'label | search' lines to count and chart")
    args = parser.parse_args()

    folder, out = Path(args.folder), Path(args.out)
    publications = folder / "publications"
    records = list_articles(publications) if publications.exists() else []
    if not records and not args.searches:
        sys.exit(f"Nothing to chart: no downloaded papers in {publications}")
    out.mkdir(parents=True, exist_ok=True)
    style()

    if args.searches:
        chart_searches(args.searches, out)
    if records:
        chart_years(records, out)
        chart_cited(publications, len(records), out)
    for vault in sorted(folder.glob("kg_*"))[:1]:
        chart_evidence(vault, out)
    for hood in sorted(publications.glob("neighborhood_*/neighborhood.json"))[:1]:
        chart_neighborhood(hood, out)


if __name__ == "__main__":
    main()
