#!/usr/bin/env python3
"""Fetch the second citation step: every PubMed article citing one of the citing papers.

Reads data/citing_papers.csv (the first step, frozen from tutorial 8) and asks
PubMed, through pubmed-stream's ``impact`` module, which articles cite each of
them.  Writes:

  data/hop1_citers.json   {citing paper PMID: [PMIDs of the papers citing it]}
  data/hop2_pmids.txt     the second-step papers, one PMID per line, sorted
  data/hop2_by_year.csv   how many second-step papers PubMed dates to each year
  data/hop2_flags.json    how many are reviews, retracted, NIH-funded, in PubMed Central
  data/reach.json         the headline counts and the share of the field they cover

PubMed links a citation only when the citing article's full text is in PubMed
Central, so these counts are lower than Google Scholar's or Web of Science's.
Set NCBI_API_KEY to run about three times faster.

Usage:  python scripts/fetch_hop2.py [--seed 16541076] [--field "Alzheimer Disease"]
"""

import argparse
import csv
import datetime as dt
import sys
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent          # this study
sys.path.insert(0, str(ROOT.parent.parent))             # the repository: run from a clone without installing
from pubmed_stream import impact  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", default="16541076", help="PubMed ID of the retracted paper")
    ap.add_argument("--field", default="Alzheimer Disease", help="MeSH heading of its field")
    ap.add_argument("--first-year", type=int, default=2006)
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    args = ap.parse_args()

    with open(args.data / "citing_papers.csv", encoding="utf-8") as f:
        hop1 = sorted({row["pmid"] for row in csv.DictReader(f)})
    print(f"{len(hop1)} citing papers; asking PubMed who cites each of them ...", flush=True)
    citers = impact.citers_of(hop1)
    hop2 = sorted(set().union(*citers.values()) - set(hop1) - {args.seed})
    print(f"{len(hop2)} second-step papers", flush=True)

    with open(args.data / "hop1_citers.json", "w", encoding="utf-8") as f:
        json.dump(citers, f)
    (args.data / "hop2_pmids.txt").write_text("\n".join(hop2) + "\n", encoding="utf-8")

    today = dt.date.today()
    print("counting by year ...", flush=True)
    by_year = impact.count_by_year(hop2, args.first_year, today.year)
    with open(args.data / "hop2_by_year.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["year", "papers"])
        w.writerows(sorted(by_year.items()))

    print("counting flags ...", flush=True)
    flags = impact.count_flags(hop2)
    with open(args.data / "hop2_flags.json", "w", encoding="utf-8") as f:
        json.dump(flags, f, indent=2)

    print("sizing the field ...", flush=True)
    field_total = impact.pubmed_count(f'"{args.field}"[mh] AND {args.first_year}:3000[dp]')
    field_near = impact.count_matching(set(hop1) | set(hop2), {"field": f'"{args.field}"[mh]'})["field"]
    reach = {
        "seed": args.seed, "fetched": today.isoformat(), "first_step": len(hop1), "second_step": len(hop2),
        "field": args.field, "field_papers_since_first_year": field_total,
        "field_papers_within_two_steps": field_near,
        "share_of_field": round(field_near / field_total, 4) if field_total else None,
        "note": "PubMed citation links only; the second step is an upper bound on influence, not a measure of harm.",
    }
    with open(args.data / "reach.json", "w", encoding="utf-8") as f:
        json.dump(reach, f, indent=2)
    print(json.dumps(reach, indent=2))
    print("flags:", json.dumps(flags))


if __name__ == "__main__":
    main()
