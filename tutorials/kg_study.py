"""Build the knowledge graph of a scientific study with pubmed-stream.

Edit STUDY below, then run from the repository root:

    python tutorials/kg_study.py            # start or grow the study
    python tutorials/kg_study.py --refresh  # later: add newly published papers

The graph is written to ./kg_<topic>; open that folder in Obsidian with
"Open folder as vault".  Downloads go to ./publications.  The same study
from the command line:

    pubmed-stream kg "gut microbiome frailty" \\
        -q '"gut microbiota"[Title] AND frailty[Title/Abstract]' \\
        -q '"gut microbiota"[Title] AND sarcopenia[Title/Abstract]' \\
        --seed 31319564 --max-results 25 --max-per-relation 30
"""

import argparse
import sys
from pathlib import Path

# Run from a clone without installing: use the repository's package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pubmed_stream import create_kg  # noqa: E402

STUDY = {
    # Names the graph folder: ./kg_gut_microbiome_frailty
    "topic": "gut microbiome frailty",
    # PubMed searches that collect the study's literature (PMC full text)
    "queries": [
        '"gut microbiota"[Title] AND frailty[Title/Abstract]',
        '"gut microbiota"[Title] AND sarcopenia[Title/Abstract]',
    ],
    # Key articles whose similar, citing and cited papers join the study.
    # 31319564: Gut Microbiota, Muscle Mass and Function in Aging (2019 review)
    "seeds": ["31319564"],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the knowledge graph of STUDY.")
    parser.add_argument("--refresh", action="store_true",
                        help="Run every search and seed again to add newly published papers")
    args = parser.parse_args()

    result = create_kg(
        STUDY["topic"],
        queries=STUDY["queries"],
        seeds=STUDY["seeds"],
        refresh=args.refresh,
        max_results=25,         # articles per search
        max_per_relation=30,    # similar, citing and cited articles per seed
    )
    print(result)

    hood_papers = sum(len(h.articles()) for h in result.neighborhoods)
    retracted = [a for h in result.neighborhoods for a in h.articles() if a.is_retracted]
    print(f"\nNeighborhood articles fetched this run: {hood_papers}")
    for article in retracted:
        print(f"[RETRACTED] PMID {article.pmid}: {article.title}")
    print(f"\nOpen this folder in Obsidian as a vault: {result.kg_dir}")
    print('Start at the "PubMed Stream" note, then open the graph view.')
    return 2 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
