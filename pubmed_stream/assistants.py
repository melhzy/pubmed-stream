"""Set up a research folder for AI assistants.

``init_folder`` writes what Claude Code, Codex and Gemini CLI need to work
with pubmed-stream in a folder: the instructions (``AGENTS.md``, imported by
``CLAUDE.md`` and ``GEMINI.md``) and the settings that start pubmed-stream's
MCP server (``.mcp.json`` for Claude Code, ``.codex/config.toml`` for Codex,
``.gemini/settings.json`` for Gemini CLI).
Existing files are kept, and settings are added to them rather than replaced.

It can also choose models for the folder: Claude Code's in
``.claude/settings.json``, and the local model of ``pubmed-stream review``
in ``.pubmed-stream.json``.  Codex 0.163 ignores a folder's model setting,
so its model is chosen with ``codex -m`` or ``/model`` instead.
"""

import json
import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

PathLike = Union[str, Path]

INSTRUCTIONS_FILE = Path(__file__).parent / "data" / "AGENTS.md"
SERVER_NAME = "pubmed-stream"
SETTINGS_FILE = ".pubmed-stream.json"   # the folder's own pubmed-stream settings, such as the review model


def instructions() -> str:
    """The instructions for AI assistants, as shipped with pubmed-stream."""
    return INSTRUCTIONS_FILE.read_text(encoding="utf-8")


def server_command() -> Tuple[str, List[str]]:
    """The command that starts the MCP server, with the Python that has pubmed-stream installed."""
    return sys.executable, ["-m", "pubmed_stream", "mcp"]


def _write_instructions(folder: Path, force: bool) -> str:
    path = folder / "AGENTS.md"
    if path.exists() and not force:
        return "kept"
    action = "updated" if path.exists() else "created"
    path.write_text(instructions(), encoding="utf-8")
    return action


def _import_instructions(path: Path) -> str:
    """CLAUDE.md and GEMINI.md import AGENTS.md with an @ line."""
    line = "@AGENTS.md"
    if not path.exists():
        path.write_text(f"{line}\n", encoding="utf-8")
        return "created"
    text = path.read_text(encoding="utf-8")
    if any(row.strip() == line for row in text.splitlines()):
        return "kept"
    path.write_text(text.rstrip("\n") + f"\n\n{line}\n", encoding="utf-8")
    return "updated"


def _json_settings(path: Path, **extra: Any) -> str:
    """Add the server to the ``mcpServers`` of a JSON settings file, as Claude Code and Gemini CLI read them."""
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    servers = data.setdefault("mcpServers", {})
    if SERVER_NAME in servers:
        return "kept"
    command, args = server_command()
    servers[SERVER_NAME] = {"command": command, "args": args, **extra}
    action = "updated" if path.exists() else "created"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return action


def _codex_settings(folder: Path) -> str:
    path = folder / ".codex" / "config.toml"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if f"[mcp_servers.{SERVER_NAME}]" in text:
        return "kept"
    command, args = server_command()
    # JSON strings are valid TOML basic strings
    block = (f"[mcp_servers.{SERVER_NAME}]\ncommand = {json.dumps(command)}\nargs = {json.dumps(args)}\n"
             "startup_timeout_sec = 60\ntool_timeout_sec = 600\n")
    action = "updated" if path.exists() else "created"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text((text.rstrip("\n") + "\n\n" if text.strip() else "") + block, encoding="utf-8")
    return action


def _set_json_key(path: Path, key: str, value: str) -> str:
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if data.get(key) == value:
        return "kept"
    action = "updated" if path.exists() else "created"
    data[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return action


def review_model(folder: PathLike = ".") -> Optional[str]:
    """The local model chosen for ``pubmed-stream review`` in *folder*, if any."""
    try:
        return json.loads((Path(folder) / SETTINGS_FILE).read_text(encoding="utf-8")).get("review_model") or None
    except (OSError, ValueError):
        return None


def init_folder(
    folder: PathLike = ".",
    force: bool = False,
    claude_model: Optional[str] = None,
    review_model: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """Prepare *folder* for Claude Code, Codex and Gemini CLI; returns ``(file, action)`` pairs.

    *force* rewrites ``AGENTS.md`` with the current instructions; the
    other files are always kept, with pubmed-stream's settings added.
    The model options choose each tool's model for this folder.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    actions = [
        ("AGENTS.md", _write_instructions(folder, force)),
        ("CLAUDE.md", _import_instructions(folder / "CLAUDE.md")),
        ("GEMINI.md", _import_instructions(folder / "GEMINI.md")),
        (".mcp.json", _json_settings(folder / ".mcp.json")),
        (".codex/config.toml", _codex_settings(folder)),
        # Gemini CLI's timeout is in milliseconds; downloads can take minutes
        (".gemini/settings.json", _json_settings(folder / ".gemini" / "settings.json", timeout=600000)),
    ]
    if claude_model:
        actions.append((".claude/settings.json", _set_json_key(folder / ".claude" / "settings.json",
                                                               "model", claude_model)))
    if review_model:
        actions.append((SETTINGS_FILE, _set_json_key(folder / SETTINGS_FILE, "review_model", review_model)))
    return actions
