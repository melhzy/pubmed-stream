"""Draw the figures of docs/ARCHITECTURE.md from a pubmed-stream knowledge graph.

    pip install matplotlib networkx
    python examples/kg_study.py                      # builds ./kg_gut_microbiome_frailty
    python docs/figures/make_figures.py kg_gut_microbiome_frailty docs/figures

The figures are drawn from the notes themselves (properties and wikilinks), so
they show exactly what Obsidian shows.  Colours follow one mapping in every
figure: papers with full text blue, stub papers grey, MeSH concepts aqua and
collections orange.
"""

import math
import re
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

# Validated categorical slots 1-3 (all pairs) plus a neutral for stubs
FULL_TEXT = "#2a78d6"
COLLECTION = "#eb6834"
CONCEPT = "#1baf7a"
STUB = "#a3a29c"
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
EDGE = "#c9c8c2"

MIN_CONCEPT_PAPERS = 10  # concepts shown in the network figure

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "text.color": INK,
    "axes.labelcolor": INK_2,
    "xtick.color": INK_2,
    "ytick.color": INK_2,
    "axes.edgecolor": GRID,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
})


def read_note(path):
    text = path.read_text(encoding="utf-8")
    _, frontmatter, body = text.split("---", 2)
    props = dict(re.findall(r'^([a-z_]+): "?([^"\n]*)"?$', frontmatter, re.M))
    return props, body


def links(body, heading):
    match = re.search(rf"^## {heading}.*?$(.*?)(?=^## |^%%)", body, re.S | re.M)
    return re.findall(r"\[\[([^|\]]+)", match.group(1)) if match else []


def load(kg):
    papers, concepts, collections = {}, Counter(), {}
    for path in (kg / "papers").glob("*.md"):
        props, body = read_note(path)
        papers[path.stem] = {
            "status": props.get("status"),
            "year": int(props["year"]) if props.get("year", "").isdigit() else None,
            "title": props.get("title", path.stem),
            "cites": links(body, "Cites"),
            "similar": links(body, "Similar articles"),
            "concepts": links(body, "MeSH concepts"),
        }
        concepts.update(papers[path.stem]["concepts"])
    for path in (kg / "collections").glob("*.md"):
        _, body = read_note(path)
        collections[path.stem] = links(body, "Papers")
    return papers, concepts, collections


def style_axes(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def study_graph(papers, concepts, collections, out):
    shown = {c for c, n in concepts.items() if n >= MIN_CONCEPT_PAPERS}
    g = nx.Graph()
    for key, paper in papers.items():
        g.add_node(key, kind="full" if paper["status"] == "full-text" else "stub")
    for name in shown:
        g.add_node(name, kind="concept")
    for name, members in collections.items():
        g.add_node(name, kind="collection")
        # Weak pull: collections are hubs of 40-60 papers and would crush the layout
        g.add_edges_from(((name, p) for p in members if p in papers), weight=0.03)
    citation_edges = []
    for key, paper in papers.items():
        for target in paper["cites"] + paper["similar"]:
            if target in papers and target != key:
                g.add_edge(key, target, weight=1.0)
                citation_edges.append((key, target))
        g.add_edges_from(((key, c) for c in paper["concepts"] if c in shown), weight=0.15)

    # Radial layout: concepts and collections on a fixed outer ring, so their
    # labels cannot collide; papers inside, pulled toward what they link to
    ring = sorted(shown, key=lambda c: (-concepts[c], c))
    for i, name in enumerate(collections):
        ring.insert(i * (len(ring) // len(collections) + 1), name)
    angles = [math.pi / 2 - 2 * math.pi * i / len(ring) for i in range(len(ring))]
    fixed = {name: (math.cos(a), math.sin(a)) for name, a in zip(ring, angles)}
    pos = nx.spring_layout(g, pos=fixed, fixed=list(fixed), k=0.3, iterations=600, seed=7, weight="weight")
    inner = [n for n in g if n not in fixed]
    # Scale by the 95th-percentile radius so a few loose papers do not shrink the rest
    radii = sorted(math.hypot(*pos[n]) for n in inner)
    radius = radii[int(0.95 * (len(radii) - 1))] or 1
    for n in inner:
        r = math.hypot(*pos[n]) / radius
        pos[n] = pos[n] / radius * (0.78 if r <= 1 else 0.78 / r * min(r, 1.1))  # keep papers inside the ring

    fig, ax = plt.subplots(figsize=(11, 11))
    ax.set_axis_off()
    other_edges = [e for e in g.edges if e not in citation_edges and e[::-1] not in citation_edges]
    nx.draw_networkx_edges(g, pos, edgelist=other_edges, ax=ax, edge_color=EDGE, width=0.5, alpha=0.45)
    nx.draw_networkx_edges(g, pos, edgelist=citation_edges, ax=ax, edge_color=INK_2, width=0.8, alpha=0.55)

    degree = dict(g.degree)
    layers = [("stub", STUB, 18), ("full", FULL_TEXT, 26), ("concept", CONCEPT, 40), ("collection", COLLECTION, 70)]
    for kind, colour, base in layers:
        nodes = [n for n, d in g.nodes(data=True) if d["kind"] == kind]
        sizes = [base + 6 * min(degree[n], 25) for n in nodes] if kind in ("full", "stub") else base * 9
        nx.draw_networkx_nodes(g, pos, nodelist=nodes, ax=ax, node_color=colour, node_size=sizes,
                               edgecolors=SURFACE, linewidths=1.2)

    for name, angle in zip(ring, angles):
        x, y = pos[name]
        dx, dy = math.cos(angle), math.sin(angle)
        is_collection = name in collections
        label = name.replace("(Title)", "").replace("(Title-Abstract)", "").replace(" - ", "\n", 1)
        if not is_collection:
            label = f"{name} ({concepts[name]})"
        ax.annotate(label, (x, y), xytext=(dx * 20, dy * 20), textcoords="offset points",
                    ha="center" if abs(dx) < 0.3 else ("left" if dx > 0 else "right"),
                    va="center" if abs(dy) < 0.3 else ("bottom" if dy > 0 else "top"),
                    fontsize=9.5 if is_collection else 9, fontweight="bold" if is_collection else "normal",
                    color=INK)

    # Name the most connected paper: in a study with a seed, the seed itself
    hub = max(papers, key=lambda k: sum(1 for e in citation_edges if k in e))
    x, y = pos[hub]
    ax.annotate(f"{hub.replace('PMID', 'PMID ')}\n{papers[hub]['title'][:38]}...", (x, y), xytext=(-250, 115),
                textcoords="offset points", fontsize=8.5, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK_2, lw=0.8),
                bbox=dict(boxstyle="round,pad=0.25", fc=SURFACE, ec=GRID))

    n_full = sum(p["status"] == "full-text" for p in papers.values())
    legend = [
        Line2D([], [], marker="o", ls="", ms=9, mfc=FULL_TEXT, mec=SURFACE, label=f"Paper with full text ({n_full})"),
        Line2D([], [], marker="o", ls="", ms=8, mfc=STUB, mec=SURFACE, label=f"Stub paper ({len(papers) - n_full})"),
        Line2D([], [], marker="o", ls="", ms=10, mfc=CONCEPT, mec=SURFACE,
               label=f"MeSH concept in {MIN_CONCEPT_PAPERS}+ papers ({len(shown)} of {len(concepts)}), paper count"),
        Line2D([], [], marker="o", ls="", ms=12, mfc=COLLECTION, mec=SURFACE, label=f"Collection ({len(collections)})"),
        Line2D([], [], color=INK_2, lw=1.2, label=f"Cites or similar ({len(citation_edges)})"),
        Line2D([], [], color=EDGE, lw=1.2, label="Belongs to collection or concept"),
    ]
    ax.legend(handles=legend, loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=3, frameon=False,
              fontsize=9, labelcolor=INK_2)
    ax.set_title("The example study's knowledge graph, drawn from its Obsidian notes",
                 loc="left", fontsize=13, color=INK, pad=12)
    fig.tight_layout()
    fig.savefig(out / "study_graph.png", dpi=150)
    plt.close(fig)


def top_concepts(concepts, out, limit=12):
    top = concepts.most_common(limit)[::-1]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    bars = ax.barh([name for name, _ in top], [n for _, n in top], height=0.62, color=CONCEPT)
    for bar, (_, n) in zip(bars, top):
        ax.text(bar.get_width() + 0.8, bar.get_y() + bar.get_height() / 2, str(n), va="center", fontsize=9, color=INK)
    ax.set_xlabel("Papers linking to the concept note")
    ax.xaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    style_axes(ax)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0, labelcolor=INK)
    ax.set_title(f"Most connected MeSH concepts ({len(concepts)} in total)", loc="left", fontsize=12, color=INK)
    fig.tight_layout()
    fig.savefig(out / "top_concepts.png", dpi=150)
    plt.close(fig)


def papers_by_year(papers, out):
    years = sorted({p["year"] for p in papers.values() if p["year"]})
    years = list(range(years[0], years[-1] + 1))
    full = [sum(p["year"] == y and p["status"] == "full-text" for p in papers.values()) for y in years]
    stub = [sum(p["year"] == y and p["status"] != "full-text" for p in papers.values()) for y in years]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar(years, full, width=0.7, color=FULL_TEXT, edgecolor=SURFACE, linewidth=1.5, label="Full text, from searches")
    ax.bar(years, stub, width=0.7, bottom=full, color=STUB, edgecolor=SURFACE, linewidth=1.5,
           label="Stub, from the seed's neighborhood")
    for y, f, s in zip(years, full, stub):
        if f + s:
            ax.text(y, f + s + 0.6, str(f + s), ha="center", fontsize=8.5, color=INK)
    ax.set_ylabel("Papers")
    ax.set_xticks(years[::2] if len(years) > 12 else years)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    style_axes(ax)
    ax.legend(frameon=False, loc="upper left", fontsize=9, labelcolor=INK_2)
    ax.set_title("Papers by publication year", loc="left", fontsize=12, color=INK)
    fig.tight_layout()
    fig.savefig(out / "papers_by_year.png", dpi=150)
    plt.close(fig)


def main():
    kg, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    papers, concepts, collections = load(kg)
    study_graph(papers, concepts, collections, out)
    top_concepts(concepts, out)
    papers_by_year(papers, out)
    citations = sum(len([t for t in p["cites"] if t in papers]) for p in papers.values())
    similar = sum(len([t for t in p["similar"] if t in papers]) for p in papers.values())
    print(f"papers={len(papers)} full={sum(p['status'] == 'full-text' for p in papers.values())} "
          f"concepts={len(concepts)} collections={len(collections)} "
          f"citations_in_graph={citations} similar_in_graph={similar}")


if __name__ == "__main__":
    main()
