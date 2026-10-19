"""The charts of tutorial 8, measuring the impact of a paper.

Each function draws one chart from plain data and shows it.  Every chart
states its finding in the title and says how to read it in a line under the
title, so it can be understood without the code.  Colours follow the
tutorials: blue for papers that name the paper's finding, aqua for general
citations, orange for papers that discuss its retraction or doubts, grey for
papers that could not be read.
"""

import math
from typing import Dict, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

import tutorial_utils as tu


def _fig_title(fig, title: str, how: str) -> None:
    inch = 1 / fig.get_figheight()   # spaced in inches, so short and tall figures look the same
    fig.text(0.01, 1 - 0.05 * inch, title, fontsize=13, fontweight="bold", color=tu.INK, va="top")
    fig.text(0.01, 1 - 0.34 * inch, how, fontsize=9.5, color=tu.INK_2, va="top")


def _legend(ax, items: Sequence[Tuple[str, str]], **kwargs) -> None:
    handles = [Rectangle((0, 0), 1, 1, color=c) for _, c in items]
    ax.legend(handles, [label for label, _ in items], frameon=False, fontsize=9, handlelength=1, **kwargs)


def key_numbers(numbers: Sequence[Tuple[str, str, str]], title: str) -> None:
    """Tiles of headline numbers: (number, what it counts, note) each."""
    columns = 3
    rows = math.ceil(len(numbers) / columns)
    fig = plt.figure(figsize=(11, 0.4 + 1.55 * rows))
    fig.add_axes([0, 0, 1, 1]).set_axis_off()   # notebooks show only figures with axes
    fig.text(0.01, 0.99, title, fontsize=13, fontweight="bold", color=tu.INK, va="top")
    top = 1 - 0.45 / fig.get_figheight()
    height = (top - 0.02) / rows
    for i, (number, label, note) in enumerate(numbers):
        row, col = divmod(i, columns)
        x, y = 0.01 + col * 0.33, top - (row + 1) * height
        fig.patches.append(FancyBboxPatch((x, y + 0.012), 0.315, height - 0.03, boxstyle="round,pad=0,rounding_size=0.012",
                                          transform=fig.transFigure, fc="white", ec=tu.GRID, lw=1))
        fig.text(x + 0.015, y + height - 0.05, number, fontsize=22, fontweight="bold", color=tu.BLUE, va="top")
        fig.text(x + 0.015, y + height * 0.36, label, fontsize=10, color=tu.INK, va="center")
        fig.text(x + 0.015, y + height * 0.14, note, fontsize=8.5, color=tu.INK_2, va="center")
    plt.show()


def reach(seed_label: str, first: int, second: int, field_total: int, field_near: int, field: str) -> None:
    """The two citation steps as a diagram, and the share of a field they cover as one bar."""
    fig = plt.figure(figsize=(11, 4.6))
    _fig_title(fig, f"Two citation steps reach {first + second:,} papers",
               "Each box counts papers. An arrow means “are cited by”. The bar below puts the reach in "
               f"proportion to all {field} papers.")
    ax = fig.add_axes([0.0, 0.36, 1, 0.5])
    ax.set_xlim(0, 3)
    ax.set_ylim(0, 1)
    ax.set_axis_off()
    boxes = [(seed_label, "the retracted paper", tu.INK),
             (f"{first:,}", "papers cite it", tu.BLUE),
             (f"{second:,}", "more papers cite those\n(but not the paper itself)", tu.BLUES[3])]
    for i, (number, label, colour) in enumerate(boxes):
        x = 0.08 + i * 1.0
        ax.add_patch(FancyBboxPatch((x, 0.12), 0.78, 0.76, boxstyle="round,pad=0,rounding_size=0.06",
                                    fc="white", ec=colour, lw=2))
        ax.text(x + 0.39, 0.62, number, ha="center", va="center", fontsize=20 if i else 15, fontweight="bold",
                color=colour)
        ax.text(x + 0.39, 0.3, label, ha="center", va="center", fontsize=10, color=tu.INK)
        if i:
            ax.add_patch(FancyArrowPatch((x - 0.2, 0.5), (x - 0.03, 0.5), arrowstyle="-|>", mutation_scale=16,
                                         color=tu.INK_2, lw=1.5))
            ax.text(x - 0.115, 0.6, "cited by", ha="center", fontsize=8.5, color=tu.INK_2)

    bar = fig.add_axes([0.02, 0.08, 0.96, 0.12])
    share = field_near / field_total
    bar.barh(0, field_near, color=tu.BLUE, height=0.8)
    bar.barh(0, field_total - field_near, left=field_near, color=tu.GRID, height=0.8)
    bar.set_xlim(0, field_total)
    bar.set_axis_off()
    bar.text(field_near / 2, 0, f"{share:.0%}", ha="center", va="center", color="white", fontweight="bold")
    bar.text(field_near + field_total * 0.01, 0, f"{field_total - field_near:,} not within two steps",
             va="center", fontsize=9, color=tu.INK_2)
    bar.text(0, 0.62, f"{field_near:,} of the {field_total:,} {field} papers in PubMed since the paper appeared "
             "cite it, or cite a paper that does", fontsize=10, color=tu.INK, va="bottom", transform=bar.transData)
    plt.show()


def _event_lines(ax, events: Sequence[Tuple[float, str]], label: bool) -> None:
    for i, (x, text) in enumerate(events):
        ax.axvline(x, color=tu.INK, lw=1, ls=(0, (4, 3)), zorder=0)
        if label:   # the last label to the right of its line, the others to the left, so they never collide
            right = i == len(events) - 1
            ax.annotate(text, (x, 1), xycoords=("data", "axes fraction"), xytext=(4 if right else -4, -2),
                        textcoords="offset points", fontsize=8.5, color=tu.INK, va="top",
                        ha="left" if right else "right")


def timeline(years: Sequence[int], research: Sequence[int], reviews: Sequence[int], second: Dict[int, int],
             events: Sequence[Tuple[float, str]], partial: Optional[int] = None) -> None:
    """Citations per year, then the second step per year, with dated events."""
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(11, 7), sharex=True, gridspec_kw={"height_ratios": [1.15, 1]})
    fig.subplots_adjust(top=0.84, hspace=0.42)
    totals = [a + b for a, b in zip(research, reviews)]
    peak = max(range(len(years)), key=lambda i: totals[i])
    full = [y for y in years if y != partial]
    peak2 = max(full, key=lambda y: second.get(y, 0))
    _fig_title(fig, f"Papers citing it peaked in {years[peak]}; papers citing those, in {peak2}",
               "Top: papers citing it, per year. Bottom: papers citing those papers, per year. "
               "Dashed lines mark when doubts were published and when it was retracted.")
    alpha = [0.45 if partial and y == partial else 1 for y in years]
    for i, y in enumerate(years):
        top.bar(y, research[i], color=tu.BLUE, alpha=alpha[i], width=0.78)
        top.bar(y, reviews[i], bottom=research[i], color=tu.ORANGE, alpha=alpha[i], width=0.78,
                edgecolor=tu.SURFACE, lw=0.8)
    top.annotate(f"peak: {totals[peak]} papers", (years[peak], totals[peak]), xytext=(0, 4), textcoords="offset points",
                 ha="center", fontsize=9, color=tu.INK)
    _legend(top, [("Original research", tu.BLUE), ("Reviews", tu.ORANGE)], loc="upper right",
            bbox_to_anchor=(1, 0.86))
    top.set_ylabel("Papers citing it")
    top.set_title("Papers citing the retracted paper", loc="left", fontsize=10.5, color=tu.INK)
    values = [second.get(y, 0) for y in years]
    bottom.bar(years, values, color=tu.BLUES[3], alpha=1, width=0.78)
    for bar_x, a in zip(years, alpha):
        if a < 1:
            bottom.patches[years.index(bar_x)].set_alpha(a)
    bottom.set_ylabel("Papers")
    bottom.set_title("Papers citing those papers (the second step)", loc="left", fontsize=10.5, color=tu.INK)
    bottom.yaxis.set_major_formatter(plt.matplotlib.ticker.StrMethodFormatter("{x:,.0f}"))
    for ax in (top, bottom):
        tu.gridlines(ax)
        _event_lines(ax, events, label=ax is top)
    if partial:
        bottom.annotate("part of\nthe year", (partial, max(values) * 0.08), ha="center", fontsize=8,
                        color=tu.INK_2)
    plt.show()


def kinds_by_period(periods: Sequence[str], counts: Dict[str, Dict[str, int]], unread: Dict[str, int],
                    kinds: Sequence[str], colours: Dict[str, str], title: str) -> None:
    """For each period, the shares of the readable citing papers by kind of citation."""
    height = 0.62 * len(periods) + 2.2
    fig, ax = plt.subplots(figsize=(11, height))
    fig.subplots_adjust(top=1 - 1.1 / height, left=0.12, right=0.84)
    _fig_title(fig, title, "Each bar is one period: the citing papers we could read, split by how they cite the "
                           "paper. Right: how many were read.")
    for row, period in enumerate(periods):
        n = sum(counts[period].get(k, 0) for k in kinds)
        left = 0
        for kind in kinds:
            share = counts[period].get(kind, 0) / n if n else 0
            ax.barh(row, share, left=left, color=colours[kind], height=0.66, edgecolor=tu.SURFACE, lw=1.5)
            if share >= 0.07:
                ax.text(left + share / 2, row, f"{share:.0%}", ha="center", va="center", fontsize=9.5,
                        color="white" if kind != kinds[-1] else tu.INK)
            elif share > 0:
                ax.annotate(f"{share:.0%}", (left + share, row), xytext=(2, 9), textcoords="offset points",
                            fontsize=8.5, color=tu.INK)
            left += share
        ax.text(1.02, row, f"{n} of {n + unread.get(period, 0)} read", va="center", fontsize=9, color=tu.INK_2,
                transform=ax.get_yaxis_transform())
    ax.set_yticks(range(len(periods)), periods)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(plt.matplotlib.ticker.PercentFormatter(1))
    ax.tick_params(axis="y", length=0)
    _legend(ax, [(k, colours[k]) for k in kinds], loc="lower left", bbox_to_anchor=(0, 1.0), ncol=len(kinds))
    plt.show()


def waffle(kinds_in_order: Sequence[str], kinds: Sequence[str], colours: Dict[str, str], title: str,
           how: str, columns: int = 25) -> None:
    """One square per paper, coloured by kind, so small counts can be seen and counted."""
    order = sorted(range(len(kinds_in_order)), key=lambda i: kinds.index(kinds_in_order[i]))
    rows = math.ceil(len(order) / columns)
    height = 0.44 * rows + 1.7
    fig = plt.figure(figsize=(11, height))
    _fig_title(fig, title, how)
    ax = fig.add_axes([0.01, 0.55 / height, 0.98, 1 - 1.25 / height])
    for n, i in enumerate(order):
        row, col = divmod(n, columns)
        ax.add_patch(Rectangle((col, -row), 0.86, 0.86, color=colours[kinds_in_order[i]]))
    ax.set_xlim(-0.05, columns)
    ax.set_ylim(-rows + 0.9, 0.9)
    ax.set_aspect("equal", anchor="W")
    ax.set_axis_off()
    counts = {k: sum(1 for x in kinds_in_order if x == k) for k in kinds}
    fig.legend([Rectangle((0, 0), 1, 1, color=colours[k]) for k in kinds if counts[k]],
               [f"{k} ({counts[k]})" for k in kinds if counts[k]], loc="lower left", bbox_to_anchor=(0.005, 0),
               ncol=4, frameon=False, fontsize=9, handlelength=1)
    plt.show()


def carriers(labels: Sequence[str], values: Sequence[int], kinds_of: Sequence[str], colours: Dict[str, str],
             title: str) -> None:
    """The citing papers with the most citations of their own, coloured and labelled by kind."""
    height = 0.42 * len(labels) + 1.6
    fig, ax = plt.subplots(figsize=(11, height))
    fig.subplots_adjust(top=1 - 0.8 / height, left=0.42)
    _fig_title(fig, title, "Each bar is a paper citing the retracted one; its length is how many papers cite it "
                           "in turn.")
    y = range(len(labels))
    ax.barh(y, values, color=[colours[k] for k in kinds_of], height=0.68)
    short_kind = {k: s for k, s in zip(colours, ["discusses the doubts", None, "cites it in general", "not read"])}
    for row, (value, kind) in enumerate(zip(values, kinds_of)):
        ax.annotate(f"{value:,}  ·  {short_kind.get(kind) or kind}", (value, row),
                    xytext=(4, 0), textcoords="offset points", va="center", fontsize=8.5, color=tu.INK)
    ax.set_yticks(list(y), labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, max(values) * 1.45)
    ax.tick_params(axis="y", length=0)
    tu.gridlines(ax, "x")
    ax.set_xlabel("Papers citing this paper")
    plt.show()


def composition(parts: Sequence[Tuple[str, int, str]], total: int, title: str, how: str) -> None:
    """One bar split into parts that do not overlap: (label, count, colour) each."""
    fig, ax = plt.subplots(figsize=(11, 2.5))
    fig.subplots_adjust(top=0.62, bottom=0.32, left=0.01, right=0.99)
    _fig_title(fig, title, how)
    left = 0
    for label, n, colour in parts:
        ax.barh(0, n, left=left, color=colour, height=0.8, edgecolor=tu.SURFACE, lw=1.5)
        if n / total >= 0.08:
            ax.text(left + n / 2, 0, f"{n:,}\n{n / total:.0%}", ha="center", va="center", fontsize=9,
                    color="white" if colour not in (tu.GRID, tu.GREY) else tu.INK)
        left += n
    ax.set_xlim(0, total)
    ax.set_axis_off()
    _legend(ax, [(f"{label} ({n:,})", c) for label, n, c in parts], loc="upper left", bbox_to_anchor=(0, -0.05),
            ncol=2)
    plt.show()


def compared(years: Sequence[int], citations: Sequence[int], seed_year: int, seed_citations: int,
             seed_label: str, title: str) -> None:
    """The paper's citations among those of its most similar papers."""
    fig, ax = plt.subplots(figsize=(11, 4.6))
    fig.subplots_adjust(top=1 - 0.8 / 4.6)
    _fig_title(fig, title, f"Each blue dot is one of the {len(years)} papers PubMed finds most similar to it, placed by "
                           "year and by how many papers cite it (log scale).")
    ax.scatter(years, [max(c, 1) for c in citations], s=30, color=tu.BLUE, alpha=0.75, edgecolor=tu.SURFACE, lw=0.8)
    ax.scatter([seed_year], [seed_citations], s=190, color=tu.ORANGE, edgecolor=tu.INK, lw=1.2, zorder=3)
    ax.annotate(seed_label, (seed_year, seed_citations), xytext=(16, -4), textcoords="offset points", fontsize=9.5,
                fontweight="bold", color=tu.INK, va="center")
    ax.axhline(sorted(citations)[len(citations) // 2], color=tu.INK_2, lw=1, ls=":")
    ax.annotate("median of the similar papers", (1, sorted(citations)[len(citations) // 2]),
                xycoords=("axes fraction", "data"), xytext=(-4, 4), textcoords="offset points", ha="right",
                fontsize=8.5, color=tu.INK_2)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(plt.matplotlib.ticker.StrMethodFormatter("{x:,.0f}"))
    tu.gridlines(ax)
    ax.set_xlabel("Year published")
    ax.set_ylabel("Papers citing it")
    plt.show()


def radial_map(kg: dict, seed: str, kinds: Dict[str, str], kind_order: Sequence[str], colours: Dict[str, str],
               expanded: Sequence[str], title: str) -> None:
    """The knowledge graph as rings: the paper, the papers citing it by kind, and the expanded neighborhoods.

    Papers citing it sit on the inner ring, grouped by kind and ordered by
    year clockwise.  The citing papers whose own neighborhoods were fetched
    are labelled, with the papers linked to them fanned out on the outer ring.
    """
    papers = kg["papers"]
    ring = sorted((p for p in kinds if f"PMID{p}" in papers),
                  key=lambda p: (kind_order.index(kinds[p]), papers[f"PMID{p}"]["year"] or 0))
    angle = {p: math.pi / 2 - 2 * math.pi * (i + 0.5) / len(ring) for i, p in enumerate(ring)}
    fig = plt.figure(figsize=(11, 9.6))
    _fig_title(fig, title, "Centre: the retracted paper. Ring: every paper citing it, grouped by kind, oldest first "
                           "clockwise. Fans: papers linked to the labelled\nciting papers, whose own neighborhoods "
                           "were fetched. A black ring marks a retracted paper.")
    ax = fig.add_axes([0.0, 0.07, 1, 0.83])
    ax.set_aspect("equal")
    ax.set_xlim(-2.3, 2.3)
    ax.set_ylim(-1.2, 1.75)
    ax.set_axis_off()

    # Sectors: a faint wedge per kind, labelled with its count
    start = 0
    for kind in kind_order:
        members = [p for p in ring if kinds[p] == kind]
        if not members:
            continue
        a0, a1 = angle[members[0]], angle[members[-1]]
        theta = [a0 - (a0 - a1) * t / 60 for t in range(61)]
        ax.plot([1.0 * math.cos(t) for t in theta], [1.0 * math.sin(t) for t in theta], color=colours[kind],
                lw=7, alpha=0.25, solid_capstyle="round")
        mid = (a0 + a1) / 2
        ax.text(0.72 * math.cos(mid), 0.72 * math.sin(mid), f"{len(members):,}", ha="center", va="center",
                fontsize=11, fontweight="bold", color=colours[kind])
        start += len(members)
    for p in ring:
        a = angle[p]
        ax.plot([0.18 * math.cos(a), 0.93 * math.cos(a)], [0.18 * math.sin(a), 0.93 * math.sin(a)],
                color=colours[kinds[p]], lw=0.25, alpha=0.25, zorder=0)
    ax.scatter([math.cos(angle[p]) for p in ring], [math.sin(angle[p]) for p in ring], s=9,
               c=[colours[kinds[p]] for p in ring], lw=0, zorder=2)

    # Expanded neighborhoods: fans of linked papers outside the ring
    linked = {}
    for key, paper in papers.items():
        for target in paper["cites"]:
            linked.setdefault(target, set()).add(key)
            linked.setdefault(key, set()).add(target)
    inner = {f"PMID{p}" for p in ring} | {f"PMID{seed}"}
    shown = sorted((p for p in expanded if p in angle), key=lambda p: -angle[p])
    for p in shown:
        a = angle[p]
        fan = sorted(n for n in linked.get(f"PMID{p}", ()) if n not in inner)
        for j, n in enumerate(fan):
            b = a + (j - (len(fan) - 1) / 2) * min(0.006, 0.18 / max(len(fan), 1))
            r = 1.18 + 0.22 * (j % 4) / 3
            ax.plot([math.cos(a), r * math.cos(b)], [math.sin(a), r * math.sin(b)], color=tu.EDGE, lw=0.35, zorder=0)
            ax.scatter([r * math.cos(b)], [r * math.sin(b)], s=5, color=tu.GREY, lw=0, zorder=1)
    # Labels on an outer circle, spread so that neighbours never overlap
    spots = [angle[p] for p in shown]
    gap = 0.2
    for i in range(1, len(spots)):
        spots[i] = min(spots[i], spots[i - 1] - gap)
    shift = (sum(angle[p] for p in shown) - sum(spots)) / max(len(spots), 1)
    spots = [s + shift for s in spots]
    for p, s in zip(shown, spots):
        key, a = f"PMID{p}", angle[p]
        x, y = math.cos(a), math.sin(a)
        retracted = papers[key]["retracted"]
        ax.scatter([x], [y], s=70, color=colours[kinds[p]], edgecolor=tu.INK if retracted else tu.SURFACE,
                   lw=1.8 if retracted else 1, zorder=4)
        lx, ly = 1.62 * math.cos(s), 1.62 * math.sin(s)
        ax.annotate(f"PMID {p}, {papers[key]['year']}" + (", retracted" if retracted else ""), (x, y), (lx, ly),
                    ha="left" if lx >= 0 else "right", va="center", fontsize=8.5, color=tu.INK,
                    fontweight="bold" if retracted else "normal",
                    arrowprops=dict(arrowstyle="-", color=tu.INK_2, lw=0.6, shrinkA=0, shrinkB=4))

    ax.scatter([0], [0], s=420, color=tu.INK, zorder=5)
    ax.text(0, -0.13, f"PMID {seed}\n(retracted)", ha="center", va="top", fontsize=9, fontweight="bold", color=tu.INK)
    handles = [Line2D([], [], marker="o", ls="", ms=7, mfc=colours[k], mec=colours[k],
                      label=f"{k} ({sum(1 for p in ring if kinds[p] == k):,})") for k in kind_order]
    handles += [Line2D([], [], marker="o", ls="", ms=5, mfc=tu.GREY, mec=tu.GREY, label="Linked papers outside the ring"),
                Line2D([], [], marker="o", ls="", ms=9, mfc="white", mec=tu.INK, mew=1.8, label="Retracted")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.02), ncol=3, fontsize=9, frameon=False)
    plt.show()
