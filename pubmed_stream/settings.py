"""pubmed-stream's own settings files.

Two JSON files hold what pubmed-stream remembers between runs, one key per
setting:

- ``~/.pubmed-stream.json``, the user's: the NCBI API key, which
  ``pubmed-stream init --ncbi-api-key`` saves there so that the command line
  and the MCP server use it in every folder
- ``.pubmed-stream.json`` in a research folder: the folder's own settings,
  such as the model ``pubmed-stream review`` uses

This module imports nothing from the package, so every layer can read them.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

PathLike = Union[str, Path]

SETTINGS_FILE = ".pubmed-stream.json"
NCBI_API_KEY_SETTING = "ncbi_api_key"


def user_settings_file() -> Path:
    """The user's settings file, in the home folder."""
    return Path.home() / SETTINGS_FILE


def read_settings(path: PathLike) -> Dict[str, Any]:
    """The settings in *path*, or none when the file is missing or unreadable."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def set_setting(path: PathLike, key: str, value: Any) -> str:
    """Save ``key: value`` in the JSON file *path*, keeping its other keys; returns created, updated or kept.

    A file that is not valid JSON raises rather than being replaced.
    """
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except ValueError as e:
        raise ValueError(f"{path} is not valid JSON: {e}") from None
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not hold a JSON object")
    if path.exists() and data.get(key) == value:
        return "kept"
    action = "updated" if path.exists() else "created"
    data[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return action


def saved_api_key() -> Optional[str]:
    """The NCBI API key saved for the user, if any."""
    return read_settings(user_settings_file()).get(NCBI_API_KEY_SETTING) or None
