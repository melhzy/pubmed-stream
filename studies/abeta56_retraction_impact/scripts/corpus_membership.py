#!/usr/bin/env python3
"""Which citing papers sit in open training corpora, and how often the claim and its correction appear there.

Two measurements, both from public services:

1. Membership.  The Pile's PubMed Central component is the PMC Open Access
   subset; its PubMed Abstracts component is every PubMed record with an
   abstract.  For the first- and second-step papers this asks PubMed which
   have an abstract, converts PubMed IDs to PMC IDs, and asks PMC which are in
   the Open Access subset.  Writes data/corpus_membership.csv (one row per
   paper) and data/corpus_membership_summary.json.

2. Strings.  infini-gram (https://infini-gram.io) counts any string in Dolma
   v1.7 and The Pile's training set.  This counts the strings that carry the
   claim and the strings that carry its correction.  Writes
   data/corpus_strings.json.

Usage:
  python scripts/corpus_membership.py             # both
  python scripts/corpus_membership.py --strings   # string counts only (seconds)
  python scripts/corpus_membership.py --membership

The E-utilities calls go through pubmed-stream's rate-limited client, so they
respect NCBI's limits with or without NCBI_API_KEY.
"""

import argparse
import csv
import datetime as dt
import sys
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent.parent          # this study
sys.path.insert(0, str(ROOT.parent.parent))             # the repository: run from a clone without installing
from pubmed_stream import impact  # noqa: E402
from pubmed_stream.downloader import _eutils_request, _prepare_client  # noqa: E402
BATCH = 100          # IDs per ELink request
POST_BATCH = 10000   # IDs per EPost request
INFINI = "https://api.infini-gram.io/"
INDEXES = {"dolma_v1_7": "v4_dolma-v1_7_llama", "pile_train": "v4_piletrain_llama"}
CLAIM = ["Aβ*56", "Abeta*56", "Aβ star 56", "Aβ*56 impairs memory", "56-kDa soluble", "Lesné"]
CORRECTION = ["Lesné retracted", "Aβ*56 retracted", "Aβ*56 artifact", "Lesné image manipulation",
              "Blots on a field", "Aβ*56 could not be replicated"]


def _client():
    api_key, limiter, session, _ = _prepare_client(None, None, None, None, None)
    return api_key, session, limiter


def pmc_ids(pmids):
    """PubMed ID -> PMC ID (digits only) for the papers that have a PMC article."""
    client = _client()
    out = {}
    for n, start in enumerate(range(0, len(pmids), BATCH), 1):
        _pmc_batch(pmids[start:start + BATCH], out, client)
        if n % 50 == 0:
            print(f"    {start + BATCH} of {len(pmids)} looked up", flush=True)
    return out


def _pmc_batch(batch, out, client):
    """One ELink request; when NCBI keeps failing on it, wait and try each half separately."""
    try:
        resp = _eutils_request("elink.fcgi", {"dbfrom": "pubmed", "db": "pmc", "retmode": "json",
                                              "linkname": "pubmed_pmc", "id": batch}, *client, post=True)
    except requests.RequestException:
        if len(batch) == 1:
            raise
        time.sleep(5)
        half = len(batch) // 2
        _pmc_batch(batch[:half], out, client)
        _pmc_batch(batch[half:], out, client)
        return
    for linkset in resp.json().get("linksets", []):
        links = [str(i) for db in linkset.get("linksetdbs", []) for i in db.get("links", [])]
        if links:
            out[str(linkset["ids"][0])] = links[0]


def pmc_open_access(pmcids):
    """The PMC IDs, among *pmcids*, that are in PMC's Open Access subset."""
    key, session, limiter = _client()
    found = set()
    pmcids = sorted(set(pmcids))
    for start in range(0, len(pmcids), POST_BATCH):
        batch = pmcids[start:start + POST_BATCH]
        root = ET.fromstring(_eutils_request("epost.fcgi", {"db": "pmc", "id": ",".join(batch)},
                                             key, session, limiter, post=True).text)
        webenv, qk = root.findtext("WebEnv"), root.findtext("QueryKey")
        for attempt in range(4):
            resp = _eutils_request("esearch.fcgi", {"db": "pmc", "term": f"#{qk} AND open access[filter]",
                                                    "WebEnv": webenv, "usehistory": "y", "retmax": POST_BATCH,
                                                    "retmode": "json"}, key, session, limiter)
            result = resp.json().get("esearchresult", {})
            if "idlist" in result:
                break
            time.sleep(2 ** attempt)
        found.update(result.get("idlist", []))
    return found


def membership(data: Path) -> None:
    with open(data / "citing_papers.csv", encoding="utf-8") as f:
        hop1 = sorted({r["pmid"] for r in csv.DictReader(f)})
    hop2 = sorted(set((data / "hop2_pmids.txt").read_text().split()))
    rows, summary = [], {"measured": dt.date.today().isoformat()}
    for hop, pmids in ((1, hop1), (2, hop2)):
        print(f"hop {hop}: {len(pmids)} papers; abstracts ...", flush=True)
        abstracts = impact.count_matching(pmids, {"has_abstract": "hasabstract"})["has_abstract"]
        print("  PMC IDs ...", flush=True)
        ids = pmc_ids(pmids)
        print(f"  {len(ids)} in PMC; Open Access subset ...", flush=True)
        oa = pmc_open_access(list(ids.values()))
        for p in pmids:
            pmcid = ids.get(p, "")
            rows.append({"pmid": p, "hop": hop, "pmcid": f"PMC{pmcid}" if pmcid else "",
                         "in_pmc": bool(pmcid), "in_pmc_open_access": pmcid in oa})
        summary[f"hop{hop}"] = {"papers": len(pmids), "with_abstract": abstracts, "in_pmc": len(ids),
                                "in_pmc_open_access": sum(1 for v in ids.values() if v in oa)}
        print("  ", json.dumps(summary[f"hop{hop}"]), flush=True)
    with open(data / "corpus_membership.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    with open(data / "corpus_membership_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def strings(data: Path) -> None:
    out = {"measured": dt.date.today().isoformat(), "indexes": INDEXES, "counts": {}}
    for name, index in INDEXES.items():
        out["counts"][name] = {}
        for kind, queries in (("claim", CLAIM), ("correction", CORRECTION)):
            for q in queries:
                try:
                    r = requests.post(INFINI, json={"index": index, "query_type": "count", "query": q}, timeout=60)
                    body = r.json()
                    value = body.get("count", body.get("error", r.status_code))
                except (requests.RequestException, ValueError) as e:
                    value = f"error: {e}"
                out["counts"][name][q] = {"kind": kind, "count": value}
                print(f"{name:12s} {kind:10s} {q!r}: {value}", flush=True)
                time.sleep(0.5)
    with open(data / "corpus_strings.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strings", action="store_true", help="string counts only")
    ap.add_argument("--membership", action="store_true", help="membership only")
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    args = ap.parse_args()
    if args.strings or not args.membership:
        strings(args.data)
    if args.membership or not args.strings:
        membership(args.data)


if __name__ == "__main__":
    main()
