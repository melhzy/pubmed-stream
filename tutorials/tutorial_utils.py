"""Helpers shared by the pubmed-stream tutorials.

- ``setup(name)`` makes the repository's package importable when running from a
  clone, and moves into ``tutorials/workspace/`` so downloads stay out of the way.
- ``read_kg(kg_dir)`` reads a knowledge graph's Obsidian notes into plain Python
  data; ``to_networkx(kg)`` turns it into a networkx graph.
- ``style()`` and the colour constants give every chart the same look: papers
  with full text blue, stub papers grey, MeSH concepts aqua, collections orange.

Needs ``matplotlib``, ``networkx`` and ``pandas``:
``pip install "pubmed-stream[tutorials]"``.
"""

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

TUTORIALS = Path(__file__).resolve().parent
WORKSPACE = TUTORIALS / "workspace"

# Validated categorical slots (all pairs) plus a neutral for stubs, on a light surface
BLUE = "#2a78d6"     # papers with full text, and single-series charts
ORANGE = "#eb6834"   # collections
AQUA = "#1baf7a"     # MeSH concepts
GREY = "#a3a29c"     # stub papers
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
EDGE = "#c9c8c2"
BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#1c5cab", "#104281", "#0d366b"]


def setup(name: str = "") -> Path:
    """Import the repository's package when run from a clone; work in tutorials/workspace."""
    repo = TUTORIALS.parent
    if (repo / "pubmed_stream").is_dir() and str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    folder = WORKSPACE / name if name else WORKSPACE
    folder.mkdir(parents=True, exist_ok=True)
    os.chdir(folder)
    return folder


def style() -> None:
    """Quiet, consistent matplotlib defaults for the tutorials."""
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "figure.dpi": 110, "font.size": 10, "text.color": INK,
        "axes.labelcolor": INK_2, "axes.edgecolor": GRID, "axes.titlesize": 12,
        "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
        "xtick.color": INK_2, "ytick.color": INK_2, "legend.frameon": False,
    })


def gridlines(ax, axis: str = "y") -> None:
    ax.grid(True, axis=axis, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def bar_labels(ax, bars, fmt="{:g}", horizontal: bool = False, zero: bool = False) -> None:
    """Value labels at the end of each bar, in text ink; *zero* labels empty bars too."""
    for bar in bars:
        value = bar.get_width() if horizontal else bar.get_height()
        if not value and not zero:
            continue
        if horizontal:
            ax.annotate(fmt.format(value), (value, bar.get_y() + bar.get_height() / 2),
                        xytext=(4, 0), textcoords="offset points", va="center", fontsize=9, color=INK)
        else:
            ax.annotate(fmt.format(value), (bar.get_x() + bar.get_width() / 2, value),
                        xytext=(0, 3), textcoords="offset points", ha="center", fontsize=9, color=INK)


def short(text: str, length: int = 60) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= length else text[:length - 1].rstrip() + "…"


# ---------------------------------------------------------------------------
# Reading a knowledge graph
# ---------------------------------------------------------------------------

def _frontmatter(text: str):
    """Parse the simple YAML pubmed-stream writes: scalars and lists of scalars."""
    if not text.startswith("---"):
        return {}, text
    _, raw, body = text.split("---", 2)
    props, key = {}, None
    for line in raw.strip().splitlines():
        item = re.match(r"\s+-\s+(.*)$", line)
        if item and key:
            props.setdefault(key, []).append(item.group(1).strip().strip('"'))
            continue
        pair = re.match(r"([A-Za-z_][\w-]*):\s*(.*)$", line)
        if pair:
            key, value = pair.group(1), pair.group(2).strip()
            if value:
                props[key] = value.strip('"')
    return props, body


def _section(body: str, heading: str) -> str:
    match = re.search(rf"^## {heading}.*?$(.*?)(?=^## |^%%)", body, re.S | re.M)
    return match.group(1) if match else ""


def _links(text: str):
    """(target, label) of every wikilink in *text*."""
    return [(m.group(1), m.group(2) or m.group(1)) for m in re.finditer(r"\[\[([^|\]]+)(?:\|([^\]]+))?\]\]", text)]


def read_kg(kg_dir) -> dict:
    """Read a knowledge graph's notes.

    Returns ``{"papers": {...}, "concepts": {...}, "collections": {...}}``.  Each
    paper has its properties (``title``, ``year``, ``journal``, ``authors``,
    ``publication_types``, ``mesh``, ``status``, ``tags``) and its links:
    ``cites``, ``similar`` (target to score), ``concepts`` (name to major
    topic) and ``collections``.
    """
    kg_dir = Path(kg_dir)
    papers, concepts, collections = {}, defaultdict(dict), {}
    for path in sorted((kg_dir / "papers").glob("*.md")):
        props, body = _frontmatter(path.read_text(encoding="utf-8"))
        year = props.get("year", "")
        paper = {
            "key": path.stem,
            "title": props.get("title", path.stem),
            "year": int(year) if str(year).isdigit() else None,
            "journal": props.get("journal"),
            "authors": props.get("authors", []),
            "publication_types": props.get("publication_types", []),
            "mesh": props.get("mesh", []),
            "keywords": props.get("keywords", []),
            "status": props.get("status"),
            "retracted": props.get("retracted") == "true",
            "tags": props.get("tags", []),
            "cites": [t for t, _ in _links(_section(body, "Cites"))],
            "similar": {},
            "concepts": {},
            "collections": [],
        }
        for line in _section(body, "Similar articles").splitlines():
            found = _links(line)
            if found:
                score = re.search(r"score (\d+)", line)
                paper["similar"][found[0][0]] = int(score.group(1)) if score else None
        for line in _section(body, "MeSH concepts").splitlines():
            found = _links(line)
            if found:
                name = found[0][1]
                paper["concepts"][name] = "(major topic)" in line
                concepts[name][path.stem] = "(major topic)" in line
        collections_line = re.search(r"^\*\*Collections:\*\*(.*)$", body, re.M)
        if collections_line:
            paper["collections"] = [t for t, _ in _links(collections_line.group(1))]
        papers[path.stem] = paper
    for path in sorted((kg_dir / "collections").glob("*.md")):
        props, body = _frontmatter(path.read_text(encoding="utf-8"))
        collections[path.stem] = {
            "kind": props.get("kind"),
            "query": props.get("query"),
            "papers": [t for t, _ in _links(_section(body, "Papers"))],
        }
    return {"papers": papers, "concepts": dict(concepts), "collections": collections}


def to_networkx(kg: dict, min_concept_papers: int = 1, collections: bool = True):
    """A networkx graph of the knowledge graph.

    Nodes carry ``kind`` (``full``, ``stub``, ``concept`` or ``collection``);
    edges carry ``kind`` (``cites``, ``similar``, ``concept`` or ``collection``).
    Citation and similarity links are kept only between papers in the graph.
    """
    import networkx as nx

    papers = kg["papers"]
    g = nx.Graph()
    for key, paper in papers.items():
        g.add_node(key, kind="full" if paper["status"] == "full-text" else "stub", label=paper["title"])
    for key, paper in papers.items():
        for target in paper["cites"]:
            if target in papers and target != key:
                g.add_edge(key, target, kind="cites")
        for target in paper["similar"]:
            if target in papers and target != key and not g.has_edge(key, target):
                g.add_edge(key, target, kind="similar")
    for name, members in kg["concepts"].items():
        if len(members) >= min_concept_papers:
            g.add_node(name, kind="concept", label=name)
            g.add_edges_from(((p, name) for p in members), kind="concept")
    if collections:
        for name, collection in kg["collections"].items():
            g.add_node(name, kind="collection", label=name)
            g.add_edges_from(((name, p) for p in collection["papers"] if p in papers), kind="collection")
    return g


def draw_network(kg: dict, ax, min_concept_papers: int = 10, label_hub: bool = True):
    """Radial drawing: concepts and collections on an outer ring, papers inside.

    Concepts linked by at least *min_concept_papers* papers are shown.  Returns
    the networkx graph that was drawn.
    """
    import math

    import networkx as nx
    from matplotlib.lines import Line2D

    g = to_networkx(kg, min_concept_papers=min_concept_papers)
    for _, _, data in g.edges(data=True):
        data["weight"] = {"cites": 1.0, "similar": 1.0, "concept": 0.15, "collection": 0.03}[data["kind"]]
    concepts = [n for n, d in g.nodes(data=True) if d["kind"] == "concept"]
    collections = [n for n, d in g.nodes(data=True) if d["kind"] == "collection"]
    ring = sorted(concepts, key=lambda c: (-len(kg["concepts"][c]), c))
    for i, name in enumerate(collections):
        ring.insert(i * (len(ring) // max(len(collections), 1) + 1), name)
    angles = [math.pi / 2 - 2 * math.pi * i / len(ring) for i in range(len(ring))]
    fixed = {name: (math.cos(a), math.sin(a)) for name, a in zip(ring, angles)}
    pos = nx.spring_layout(g, pos=fixed, fixed=list(fixed), k=0.3, iterations=600, seed=7, weight="weight")
    inner = [n for n in g if n not in fixed]
    radii = sorted(math.hypot(*pos[n]) for n in inner) or [1]
    radius = radii[int(0.95 * (len(radii) - 1))] or 1
    for n in inner:
        r = math.hypot(*pos[n]) / radius
        pos[n] = pos[n] / radius * (0.78 if r <= 1 else 0.78 / r * min(r, 1.1))

    links = [(u, v) for u, v, d in g.edges(data=True) if d["kind"] in ("cites", "similar")]
    others = [(u, v) for u, v, d in g.edges(data=True) if d["kind"] not in ("cites", "similar")]
    nx.draw_networkx_edges(g, pos, edgelist=others, ax=ax, edge_color=EDGE, width=0.5, alpha=0.45)
    nx.draw_networkx_edges(g, pos, edgelist=links, ax=ax, edge_color=INK_2, width=0.8, alpha=0.55)
    degree = dict(g.degree)
    for kind, colour, base in [("stub", GREY, 18), ("full", BLUE, 26), ("concept", AQUA, 40), ("collection", ORANGE, 70)]:
        nodes = [n for n, d in g.nodes(data=True) if d["kind"] == kind]
        sizes = [base + 6 * min(degree[n], 25) for n in nodes] if kind in ("full", "stub") else base * 9
        nx.draw_networkx_nodes(g, pos, nodelist=nodes, ax=ax, node_color=colour, node_size=sizes,
                               edgecolors=SURFACE, linewidths=1.2)
    for name, angle in zip(ring, angles):
        dx, dy = math.cos(angle), math.sin(angle)
        is_collection = name in collections
        label = (name.replace("(Title)", "").replace("(Title-Abstract)", "").replace(" - ", "\n", 1)
                 if is_collection else f"{name} ({len(kg['concepts'][name])})")
        ax.annotate(label, pos[name], xytext=(dx * 20, dy * 20), textcoords="offset points",
                    ha="center" if abs(dx) < 0.3 else ("left" if dx > 0 else "right"),
                    va="center" if abs(dy) < 0.3 else ("bottom" if dy > 0 else "top"),
                    fontsize=9, fontweight="bold" if is_collection else "normal", color=INK)
    if label_hub and links:
        hub = max((n for n in g if g.nodes[n]["kind"] in ("full", "stub")),
                  key=lambda n: sum(1 for e in links if n in e))
        ax.annotate(f"{hub.replace('PMID', 'PMID ')}\n{short(kg['papers'][hub]['title'], 40)}", pos[hub],
                    xytext=(-80, 120), textcoords="offset points", fontsize=8.5, color=INK,
                    arrowprops=dict(arrowstyle="-", color=INK_2, lw=0.8),
                    bbox=dict(boxstyle="round,pad=0.25", fc=SURFACE, ec=GRID))
    n_full = sum(1 for _, d in g.nodes(data=True) if d["kind"] == "full")
    n_stub = sum(1 for _, d in g.nodes(data=True) if d["kind"] == "stub")
    ax.legend(handles=[
        Line2D([], [], marker="o", ls="", ms=9, mfc=BLUE, mec=SURFACE, label=f"Paper with full text ({n_full})"),
        Line2D([], [], marker="o", ls="", ms=8, mfc=GREY, mec=SURFACE, label=f"Stub paper ({n_stub})"),
        Line2D([], [], marker="o", ls="", ms=10, mfc=AQUA, mec=SURFACE,
               label=f"MeSH concept in {min_concept_papers}+ papers, paper count"),
        Line2D([], [], marker="o", ls="", ms=12, mfc=ORANGE, mec=SURFACE, label="Collection"),
        Line2D([], [], color=INK_2, lw=1.2, label=f"Cites or similar ({len(links)})"),
        Line2D([], [], color=EDGE, lw=1.2, label="Belongs to collection or concept"),
    ], loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=3, fontsize=9, labelcolor=INK_2)
    ax.set_axis_off()
    return g
