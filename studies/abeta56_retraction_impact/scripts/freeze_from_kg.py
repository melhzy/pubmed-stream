#!/usr/bin/env python3
"""Freeze the citing-paper table from tutorial 8's saved knowledge graph.

pubmed-stream's tutorial 8 annotates every note of the retracted paper's citing
papers with ``hop``, ``citation_kind``, ``citation_sentence`` and
``citation_source``.  This script reads those notes and writes two tables:

  data/citing_papers.csv       the papers citing the retracted paper (hop 1)
  data/kg_snapshot_papers.csv  every paper in the graph, with its hop if any

Usage:
  python scripts/freeze_from_kg.py <kg_dir> --snapshot-date YYYY-MM-DD

Only the Python standard library is needed.  The notes' frontmatter is the
simple YAML pubmed-stream writes: quoted scalars, booleans, integers and lists.
"""

import argparse
import csv
import re
from pathlib import Path

KEY = re.compile(r"^([A-Za-z_][\w-]*):(.*)$")


def scalar(value: str):
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if value == "true":
        return True
    if value == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def frontmatter(text: str) -> dict:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    data, key = {}, None
    for line in text[4:end].split("\n"):
        if line.startswith("  - ") and key is not None:
            if not isinstance(data.get(key), list):
                data[key] = []
            data[key].append(scalar(line[4:]))
        else:
            m = KEY.match(line)
            if m:
                key, value = m.group(1), m.group(2).strip()
                data[key] = scalar(value) if value else []
    return data


def row(note: dict, snapshot: str) -> dict:
    tags = note.get("tags") or []
    types = note.get("publication_types") or []
    authors = note.get("authors") or []
    return {
        "pmid": note.get("pmid", ""),
        "year": note.get("year", ""),
        "title": note.get("title", ""),
        "journal": note.get("journal", ""),
        "first_author": authors[0] if authors else "",
        "n_authors": len(authors),
        "pmcid": note.get("pmcid", ""),
        "doi": note.get("doi", ""),
        "review": any("Review" in t for t in types),
        "retracted": bool(note.get("retracted")) or "pubmed/retracted" in tags,
        "nih_funded": "pubmed/nih-funded" in tags,
        "has_full_text": note.get("status") == "paper" or note.get("status") == "full",
        "status": note.get("status", ""),
        "hop": note.get("hop", ""),
        "citation_kind": note.get("citation_kind", ""),
        "citation_source": note.get("citation_source", ""),
        "citation_sentence": note.get("citation_sentence", ""),
        "snapshot_date": snapshot,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kg_dir", type=Path)
    ap.add_argument("--snapshot-date", required=True, help="the date tutorial 8 was run, YYYY-MM-DD")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "data")
    args = ap.parse_args()

    notes = [frontmatter(p.read_text(encoding="utf-8")) for p in sorted((args.kg_dir / "papers").glob("PMID*.md"))]
    rows = [row(n, args.snapshot_date) for n in notes if n.get("pmid")]
    fields = list(rows[0].keys())
    args.out.mkdir(parents=True, exist_ok=True)

    def write(name, subset):
        path = args.out / name
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
            w.writeheader()
            w.writerows(subset)
        print(f"{path.name}: {len(subset)} rows")

    write("kg_snapshot_papers.csv", rows)
    citing = sorted((r for r in rows if r["hop"] == 1), key=lambda r: (r["year"], r["pmid"]))
    write("citing_papers.csv", citing)
    kinds = {}
    for r in citing:
        kinds[r["citation_kind"]] = kinds.get(r["citation_kind"], 0) + 1
    for kind, n in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print(f"  {n:5d}  {kind}")
    print(f"  {sum(r['retracted'] for r in citing):5d}  retracted citing papers")
    print(f"  {sum(1 for r in rows if r['hop'] == 2):5d}  second-hop papers in the graph (a sample, not all of them)")


if __name__ == "__main__":
    main()
