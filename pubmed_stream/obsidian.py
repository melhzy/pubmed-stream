"""Open a knowledge graph in Obsidian.

Obsidian opens a note from another program through its URI scheme,
``obsidian://open?path=...`` (https://obsidian.md/help/uri), but only in a
folder it already knows as a vault.  A new knowledge graph is added once, in
Obsidian, with **Open folder as vault**; after that ``open_vault`` opens it
directly.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Union
from urllib.parse import quote

PathLike = Union[str, Path]


def config_path() -> Path:
    """Where Obsidian lists the vaults it knows, on this operating system."""
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "obsidian" / "obsidian.json"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "obsidian" / "obsidian.json"


def known_vaults(config: Optional[PathLike] = None) -> List[Path]:
    """The vault folders Obsidian knows; empty when Obsidian is not installed."""
    try:
        data = json.loads(Path(config or config_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [Path(v["path"]) for v in (data.get("vaults") or {}).values() if isinstance(v, dict) and v.get("path")]


def _same(a: Path, b: Path) -> bool:
    a, b = os.path.normcase(str(a.resolve())), os.path.normcase(str(b.resolve()))
    return a == b


def open_uri(path: Path, note: str = "PubMed Stream.md") -> str:
    """The Obsidian URI that opens *note* in the vault at *path*."""
    return "obsidian://open?path=" + quote(str((path / note).resolve()), safe="")


def open_vault(kg_dir: PathLike, config: Optional[PathLike] = None, launch: bool = True) -> Tuple[bool, str]:
    """Open a knowledge graph's home note in Obsidian.

    Returns ``(opened, message)``.  When Obsidian does not know the folder
    yet, nothing is launched and the message says how to add it.
    """
    path = Path(kg_dir).resolve()
    if not path.is_dir():
        return False, f"{path} does not exist"
    if not any(_same(path, vault) for vault in known_vaults(config)):
        return False, (f"Obsidian does not know this knowledge graph yet. Open it once in Obsidian: choose "
                       f"Open folder as vault, and select\n  {path}\n"
                       "After that, 'pubmed-stream open' opens it directly.")
    uri = open_uri(path)
    if launch:
        try:
            if sys.platform == "win32":
                os.startfile(uri)   # noqa: S606 - hands the URI to Obsidian
            else:
                subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", uri], check=False)
        except OSError as e:
            return False, f"Could not start Obsidian: {e}\nOpen this link instead: {uri}"
    return True, f"Opened {path.name} in Obsidian"
