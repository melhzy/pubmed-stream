#!/usr/bin/env python3
"""Build data.js, the study's data for its web page.

The page is index.html (the shell), app.js (a React application) and
styles.css, all written by hand, plus data.js, which this script builds from
the frozen tables in data/, the documents in docs/, the probe questions and
answers in probes/, and the README's status table.  The page needs no server:
open index.html in a browser.  Rebuild data.js after the data changes.

Usage, from the study folder:
  python scripts/build_viewer.py                    # writes data.js
  python scripts/build_viewer.py --publish-dir DIR  # also copies the page into DIR with index.html
                                                    # stripped of its document skeleton, for a host that adds one
"""

import argparse
import csv
import datetime as dt
import json
import posixpath
import re
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
GITHUB = "https://github.com/melhzy/pubmed-stream/blob/main/studies/abeta56_retraction_impact/"
SEED = "16541076"

TIMELINE = [
    ("16 Mar 2006", "Nature publishes Lesné et al.; Aβ*56 named", True),
    ("2011–2017", "Reed 2011, Larson 2012 (×2), Lesné 2013, Handoko 2013 and Amar 2017 extend the claim to potency, mechanism, human brain and CSF", False),
    ("Jan 2022", "Matthew Schrag reports image concerns to the NIH", False),
    ("13 May 2022", "Brain erratum on Lesné 2013", False),
    ("21 Jun 2022", "Science Signaling expressions of concern (2016 and 2017 papers)", False),
    ("14 Jul 2022", "Nature editor's note on the 2006 paper", False),
    ("21 Jul 2022", "Science publishes the investigation, “Blots on a field?”", True),
    ("22 Jul 2022", "Ashe: images “inappropriately altered”; her labs “reproducibly detect Aβ*56”", False),
    ("3 Aug 2022", "Cure Alzheimer's Fund: its funded replication “could not be validated”", False),
    ("15 Feb 2024", "Liu et al., iScience: the Ashe lab's own re-characterisation", False),
    ("4 Jun 2024", "Science reports the authors' retraction request; Lesné alone disagrees", False),
    ("24 Jun 2024", "Nature retraction note (Fig. 2c, Supplementary Fig. 4)", True),
    ("1 Mar 2025", "Lesné's resignation from the University of Minnesota takes effect (as reported)", False),
    ("23 Dec 2025", "Science Signaling retracts Amar et al. 2017", True),
]

EXTERNAL = {
    "retraction_watch_citations": 2400,
    "retraction_watch_rank": "fifth",
    "scite_citing_publications": 2805,
    "scite_note": "124 supporting, 5 contrasting, 2,585 mentioning statements",
}


def read_csv(path: Path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def read_jsonl(folder: Path):
    out = []
    for path in sorted(folder.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out


def resolve_links(md: str, base: str) -> str:
    """Point relative Markdown links at the study's folder on GitHub, so they work anywhere."""
    def fix(m):
        text, target = m.group(1), m.group(2)
        if re.match(r"^(https?:|mailto:|#)", target):
            return m.group(0)
        path = posixpath.normpath(posixpath.join(base, target))
        return f"[{text}](https://github.com/melhzy/pubmed-stream/blob/main/{path})"
    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", fix, md)


def status_table(readme: str):
    """The rows of the README's Status table: (step, state)."""
    rows, in_status = [], False
    for line in readme.splitlines():
        if line.startswith("## "):
            in_status = line.strip() == "## Status"
            continue
        if in_status and line.startswith("|") and not re.match(r"^\|\s*-", line):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 2 and cells[0] not in ("Step",):
                rows.append([re.sub(r"`([^`]*)`", r"\1", cells[0]), re.sub(r"`([^`]*)`", r"\1", cells[1])])
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT / "data.js")
    ap.add_argument("--publish-dir", type=Path, default=None, help="also copy the page there, index.html without its document skeleton")
    args = ap.parse_args()

    data = ROOT / "data"
    citing = read_csv(data / "citing_papers.csv")
    keep = ["pmid", "year", "title", "journal", "first_author", "pmcid", "doi", "review", "retracted", "nih_funded",
            "citation_kind", "citation_source", "citation_sentence"]
    citing = [{k: (r[k] == "True" if k in ("review", "retracted", "nih_funded") else r[k]) for k in keep} for r in citing]
    snapshot = read_csv(data / "citing_papers.csv")[0].get("snapshot_date", "")

    with open(data / "hop2_by_year.csv", encoding="utf-8") as f:
        hop2_by_year = [[int(y), int(n)] for y, n in list(csv.reader(f))[1:]]

    with open(ROOT / "probes" / "questions.yaml", encoding="utf-8") as f:
        questions = yaml.safe_load(f)
    answers = read_jsonl(ROOT / "probes" / "answers")

    docs = ROOT / "docs"
    payload = {
        "seed": SEED,
        "built": dt.date.today().isoformat(),
        "snapshot_date": snapshot,
        "github_base": GITHUB,
        "citing": citing,
        "hop2_by_year": hop2_by_year,
        "hop2_flags": read_json(data / "hop2_flags.json", {}),
        "reach": read_json(data / "reach.json", {}),
        "strings": read_json(data / "corpus_strings.json"),
        "membership": read_json(data / "corpus_membership_summary.json"),
        "questions": questions,
        "answers": answers,
        "timeline": [{"date": d, "event": e, "key": k} for d, e, k in TIMELINE],
        "external": EXTERNAL,
        "status": status_table((ROOT / "README.md").read_text(encoding="utf-8")),
        "docs": {
            "what_was_wrong": resolve_links((docs / "what_was_wrong.md").read_text(encoding="utf-8"), "studies/abeta56_retraction_impact/docs"),
            "plan": resolve_links((docs / "plan.md").read_text(encoding="utf-8"), "studies/abeta56_retraction_impact/docs"),
            "data_readme": resolve_links((data / "README.md").read_text(encoding="utf-8"), "studies/abeta56_retraction_impact/data"),
        },
    }
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)   # YAML dates
    data_js = ("/* Built by scripts/build_viewer.py on " + payload["built"] + " from the study's files; do not edit by hand. */\n"
               "window.STUDY_DATA = " + blob + ";\n")
    args.out.write_text(data_js, encoding="utf-8")
    print(f"{args.out}: {len(data_js) / 1e6:.2f} MB; {len(citing)} citing papers, {len(answers)} probe answers, "
          f"{len(payload['status'])} status rows, membership {'yes' if payload['membership'] else 'not yet'}")

    if args.publish_dir:
        args.publish_dir.mkdir(parents=True, exist_ok=True)
        skeleton = re.compile(r"^\s*(<!doctype html>|</?html[^>]*>|</?head>|</?body>|<meta charset=[^>]*>|<meta name=\"viewport\"[^>]*>)\s*$", re.I)
        shell = (ROOT / "index.html").read_text(encoding="utf-8").splitlines()
        bare = "\n".join(line for line in shell if not skeleton.match(line)) + "\n"
        (args.publish_dir / "index.html").write_text(bare, encoding="utf-8")
        for name in ("app.js", "styles.css"):
            shutil.copyfile(ROOT / name, args.publish_dir / name)
        shutil.copyfile(args.out, args.publish_dir / "data.js")
        print(f"publish set in {args.publish_dir}: index.html (bare), app.js, styles.css, data.js")


if __name__ == "__main__":
    main()
