#!/usr/bin/env python3
"""Create a review queue, NOT a forget set, from the frozen citation snapshot.

python scripts/prepare_unlearning.py --out data/unlearning_review
All rows start unreviewed. No citation, keyword or retraction flag is a stance label.
The output directory must be new so that a rerun cannot erase annotations.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
SEED = "16541076"
KINDS = {
    "Names Aβ*56", "Cites it in general", "Discusses the retraction or doubts",
    "No full text, or citation not found",
}
ALIASES = re.compile(
    r"\ba\s*(?:beta|b)\s*(?:\*|star)?\s*56\b|\b56\s*-?\s*kda\b|"
    r"\bdodecamer\w*|\b12\s*-?\s*mer\b|\btwelve[ -]subunit\b", re.I
)


def normalized(text):
    text = unicodedata.normalize("NFKC", text).lower().replace("β", "beta")
    for char in "∗⁎✱":
        text = text.replace(char, "*")
    for char in "‐‑–—−":
        text = text.replace(char, "-")
    return " ".join(text.split())


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def triage(row):
    text = row.get("citation_sentence", "").strip()
    kind = row.get("citation_kind", "")
    if row["pmid"] == SEED:
        return "seed_paper_review", "known retracted source; retrieve claim-level passages"
    if kind not in KINDS:
        raise ValueError(f"Unknown citation_kind for PMID {row['pmid']}: {kind!r}")
    if not text:
        return "missing_context_review", "no frozen citation excerpt"
    if kind == "Discusses the retraction or doubts":
        return "correction_or_criticism_review", "may include criticism, failed replication, or overcorrection"
    if kind == "Names Aβ*56" or ALIASES.search(normalized(text)):
        return "specific_claim_review", "specific-assembly marker; endorsement and dependence unverified"
    return "general_citation_review", "inspect claim dependence; other evidence may support this claim"


def build_queue(citers, snapshot):
    seeds = [r for r in snapshot if r["pmid"] == SEED]
    if len(seeds) != 1:
        raise ValueError("snapshot must contain exactly one seed paper")
    rows, seen = [], set()
    for source in seeds + citers:
        pmid = source["pmid"]
        if not pmid or pmid in seen:
            raise ValueError(f"Missing or duplicate PMID: {pmid!r}")
        seen.add(pmid)
        queue, reason = triage(source)
        excerpt = source.get("citation_sentence", "")
        rows.append({
            "candidate_id": f"PMID{pmid}", "pmid": pmid, "doi": source.get("doi", ""),
            "pmcid": source.get("pmcid", ""), "year": source.get("year", ""),
            "title": source.get("title", ""), "paper_retracted_in_snapshot": source.get("retracted", ""),
            "snapshot_date": source.get("snapshot_date", ""),
            "citation_kind_in_snapshot": source.get("citation_kind", ""),
            "citation_source": source.get("citation_source", ""),
            "citation_excerpt": excerpt, "excerpt_sha256": digest(excerpt) if excerpt else "",
            "exact_text_group": digest(normalized(excerpt)) if excerpt else "",
            "excerpt_may_be_shortened": bool(excerpt and ("…" in excerpt or len(excerpt) >= 399)),
            "review_queue": queue, "triage_reason": reason,
            "full_context_checked": False, "review_status": "unreviewed",
            "claim_id": "", "stance": "", "dependence": "", "evidence_status": "",
            "decision": "", "evidence_url": "", "evidence_passage": "", "reviewer": "", "notes": "",
        })
    return sorted(rows, key=lambda r: (r["review_queue"], int(r["year"] or 0), int(r["pmid"])))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--citers", type=Path, default=ROOT / "data/citing_papers.csv")
    ap.add_argument("--snapshot", type=Path, default=ROOT / "data/kg_snapshot_papers.csv")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    with args.citers.open(encoding="utf-8", newline="") as f:
        citers = list(csv.DictReader(f))
    with args.snapshot.open(encoding="utf-8", newline="") as f:
        snapshot = list(csv.DictReader(f))
    rows = build_queue(citers, snapshot)
    summary = {
        "purpose": "triage_only_not_training_data", "seed_pmid": SEED,
        "input_sha256": {args.citers.name: hashlib.sha256(args.citers.read_bytes()).hexdigest(),
                         args.snapshot.name: hashlib.sha256(args.snapshot.read_bytes()).hexdigest()},
        "rows": len(rows), "queues": dict(sorted(Counter(r["review_queue"] for r in rows).items())),
        "additional_specific_candidates_from_general": sum(
            r["review_queue"] == "specific_claim_review" and
            r["citation_kind_in_snapshot"] == "Cites it in general" for r in rows),
        "excerpts_may_be_shortened": sum(r["excerpt_may_be_shortened"] for r in rows),
        "approved_forget_examples": 0,
        "warnings": [
            "Citation reach is not claim endorsement or causal influence on a model.",
            "Original excerpts were shortened to 400 characters and may join separate sentences.",
            "Retrieve full context and verify editorial status before adjudication.",
            "An unretracted supporting paper is not invalid just because it cites a retracted paper.",
            "No second-hop paper is assigned a forget label by graph distance.",
        ],
    }
    args.out.mkdir(parents=True, exist_ok=False)
    with (args.out / "review_queue.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (args.out / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
