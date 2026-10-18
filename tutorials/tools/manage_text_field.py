"""Add, remove or check the ``text`` field of downloaded PMC JSON files.

The ``text`` field holds an article's plain text, one paragraph per line.  It
can be regenerated from the ``xml`` field, so it can be dropped to save space
and added back later:

    python tutorials/tools/manage_text_field.py check  publications/gut_microbiome
    python tutorials/tools/manage_text_field.py remove publications/gut_microbiome
    python tutorials/tools/manage_text_field.py add    publications --recursive

``add`` needs the ``xml`` field, so it works on files downloaded with
``--format xml`` or ``--format both``.
"""

import argparse
import json
import sys
from pathlib import Path

# Run from a clone without installing: use the repository's package
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pubmed_stream import extract_text_from_pmc_xml  # noqa: E402


def add_text(data: dict) -> str:
    if data.get("text"):
        return "skipped: already has text"
    if "xml" not in data:
        return "skipped: no xml field to generate text from"
    data["text"] = extract_text_from_pmc_xml(data["xml"])
    return "added"


def remove_text(data: dict) -> str:
    if "text" not in data:
        return "skipped: no text field"
    size = len(data.pop("text").encode("utf-8")) / 1024
    return f"removed, {size:.1f} KB saved"


def check_text(data: dict) -> str:
    if data.get("text"):
        return f"has text, {len(data['text'].encode('utf-8')) / 1024:.1f} KB"
    return "no text"


OPERATIONS = {"add": add_text, "remove": remove_text, "check": check_text}


def process(folder: Path, operation: str) -> None:
    files = sorted(folder.glob("PMC*.json"))
    if not files:
        return
    print(f"\n{folder}: {len(files)} files")
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        message = OPERATIONS[operation](data)
        if operation != "check" and not message.startswith("skipped"):
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {path.name}: {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("operation", choices=sorted(OPERATIONS))
    parser.add_argument("folder", type=Path, help="Folder of PMC*.json files")
    parser.add_argument("--recursive", "-r", action="store_true", help="Also process every subfolder")
    args = parser.parse_args()

    if not args.folder.is_dir():
        print(f"Error: not a folder: {args.folder}", file=sys.stderr)
        return 1
    folders = [args.folder] + (sorted(p for p in args.folder.rglob("*") if p.is_dir()) if args.recursive else [])
    for folder in folders:
        process(folder, args.operation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
