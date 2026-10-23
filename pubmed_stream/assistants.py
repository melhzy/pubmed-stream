"""Set up a research folder for AI assistants.

``init_folder`` writes what Claude Code, Codex and Gemini CLI need to work
with pubmed-stream in a folder: the instructions (``AGENTS.md``, imported by
``CLAUDE.md`` and ``GEMINI.md``) and the settings that start pubmed-stream's
MCP server (``.mcp.json`` for Claude Code, ``.codex/config.toml`` for Codex,
``.gemini/settings.json`` for Gemini CLI).
Existing files are kept, and settings are added to them rather than replaced.
Where the pubmed-stream plugin is installed, Claude Code or Codex has the
server in every folder already, so its settings get none, and lose one that
an earlier ``init`` added, or the assistant would list every tool twice.

It can also choose models for the folder: Claude Code's in
``.claude/settings.json``, and the local model of ``pubmed-stream review``
in ``.pubmed-stream.json``; and save the user's NCBI API key, which belongs
to the person rather than the folder, in ``~/.pubmed-stream.json``.  Codex 0.163 ignores a folder's model setting,
so its model is chosen with ``codex -m`` or ``/model`` instead.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

from .settings import NCBI_API_KEY_SETTING, SETTINGS_FILE, read_settings, set_setting, user_settings_file

PathLike = Union[str, Path]

INSTRUCTIONS_FILE = Path(__file__).parent / "data" / "AGENTS.md"
SERVER_NAME = "pubmed-stream"
PLUGIN = "pubmed-stream@"               # the plugin's id, followed by the marketplace it came from
CODEX_TABLE = f"[mcp_servers.{SERVER_NAME}]"


def instructions() -> str:
    """The instructions for AI assistants, as shipped with pubmed-stream."""
    return INSTRUCTIONS_FILE.read_text(encoding="utf-8")


def server_command() -> Tuple[str, List[str]]:
    """The command that starts the MCP server, with the Python that has pubmed-stream installed."""
    return sys.executable, ["-m", "pubmed_stream", "mcp"]


def plugin_installed(assistant: str, folder: PathLike = ".") -> bool:
    """Whether the pubmed-stream plugin is enabled in Claude Code or Codex (*assistant*), for the user or *folder*.

    Claude Code lists enabled plugins in its settings files, except a plugin
    added on the claude.ai account, which it syncs into its plugins folder and
    loads with no settings entry unless the user turns it off; Codex enables
    one with a ``[plugins."pubmed-stream@<marketplace>"]`` table in ``config.toml``.
    """
    home, folder = Path.home(), Path(folder)
    if assistant == "claude":
        # the most specific settings file that mentions the plugin decides, as in Claude Code
        for path in (folder / ".claude" / "settings.local.json", folder / ".claude" / "settings.json",
                     home / ".claude" / "settings.json"):
            enabled = read_settings(path).get("enabledPlugins")
            ours = [bool(on) for name, on in enabled.items() if name.startswith(PLUGIN)] if isinstance(enabled, dict) else []
            if ours:
                return any(ours)
        synced = home / ".claude" / "plugins" / "synced"
        return any(p.is_dir() for pattern in ("*/pubmed-stream", "*/pubmed-stream~*") for p in synced.glob(pattern))
    for path in (home / ".codex" / "config.toml", folder / ".codex" / "config.toml"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for table in re.finditer(r'^\[plugins\."pubmed-stream@[^"]*"\]\n(.*?)(?=^\[|\Z)', text, re.M | re.S):
            if re.search(r"^\s*enabled\s*=\s*true", table.group(1), re.M):
                return True
    return False


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


def _json_settings(path: Path, plugin: bool = False, **extra: Any) -> str:
    """Add the server to the ``mcpServers`` of a JSON settings file, as Claude Code and Gemini CLI read them.

    With the *plugin* installed, the file gets no server, and loses one an earlier ``init`` added.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except ValueError as e:
        raise ValueError(f"{path} is not valid JSON: {e}") from None
    servers = data.setdefault("mcpServers", {})
    if plugin:
        if SERVER_NAME not in servers:
            return "plugin"
        del servers[SERVER_NAME]
    elif SERVER_NAME in servers:
        return "kept"
    else:
        command, args = server_command()
        servers[SERVER_NAME] = {"command": command, "args": args, **extra}
    action = "plugin" if plugin else "updated" if path.exists() else "created"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return action


def _codex_settings(folder: Path, plugin: bool = False) -> str:
    path = folder / ".codex" / "config.toml"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    # the server's table, and any sub-table such as [mcp_servers.pubmed-stream.env], each to the next table
    tables = rf"^\[mcp_servers\.{re.escape(SERVER_NAME)}(\.[^\]]*)?\]\n(.*?)(?=^\[|\Z)"
    if plugin:
        if not re.search(tables, text, flags=re.M | re.S):
            return "plugin"
        text = re.sub(tables, "", text, flags=re.M | re.S)
        path.write_text(text.rstrip("\n") + "\n" if text.strip() else "", encoding="utf-8")
        return "plugin"
    if CODEX_TABLE in text:
        return "kept"
    command, args = server_command()
    # JSON strings are valid TOML basic strings
    # Codex forwards only the environment variables a server lists
    block = (f"[mcp_servers.{SERVER_NAME}]\ncommand = {json.dumps(command)}\nargs = {json.dumps(args)}\n"
             'env_vars = ["NCBI_API_KEY", "NCBI_EMAIL"]\nstartup_timeout_sec = 60\ntool_timeout_sec = 600\n')
    action = "updated" if path.exists() else "created"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text((text.rstrip("\n") + "\n\n" if text.strip() else "") + block, encoding="utf-8")
    return action


def review_model(folder: PathLike = ".") -> Optional[str]:
    """The local model chosen for ``pubmed-stream review`` in *folder*, if any."""
    return read_settings(Path(folder) / SETTINGS_FILE).get("review_model") or None


def init_folder(
    folder: PathLike = ".",
    force: bool = False,
    claude_model: Optional[str] = None,
    review_model: Optional[str] = None,
    ncbi_api_key: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """Prepare *folder* for Claude Code, Codex and Gemini CLI; returns ``(file, action)`` pairs.

    *force* rewrites ``AGENTS.md`` with the current instructions; the
    other files are always kept, with pubmed-stream's settings added.
    Where the pubmed-stream plugin is installed, the settings of Claude Code
    or Codex get no server, with the action ``plugin``, because the plugin
    provides it in every folder.  The model options choose each tool's model
    for this folder; *ncbi_api_key* is saved for the user, in the home folder,
    and that file is named by its full path.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    claude_plugin, codex_plugin = plugin_installed("claude", folder), plugin_installed("codex", folder)
    actions = [
        ("AGENTS.md", _write_instructions(folder, force)),
        ("CLAUDE.md", _import_instructions(folder / "CLAUDE.md")),
        ("GEMINI.md", _import_instructions(folder / "GEMINI.md")),
        (".mcp.json", _json_settings(folder / ".mcp.json", plugin=claude_plugin)),
        (".codex/config.toml", _codex_settings(folder, plugin=codex_plugin)),
        # Gemini CLI's timeout is in milliseconds; downloads can take minutes
        (".gemini/settings.json", _json_settings(folder / ".gemini" / "settings.json", timeout=600000)),
    ]
    if claude_model:
        actions.append((".claude/settings.json", set_setting(folder / ".claude" / "settings.json",
                                                             "model", claude_model)))
    if review_model:
        actions.append((SETTINGS_FILE, set_setting(folder / SETTINGS_FILE, "review_model", review_model)))
    if ncbi_api_key:
        actions.append((str(user_settings_file()), set_setting(user_settings_file(), NCBI_API_KEY_SETTING, ncbi_api_key)))
    return actions
