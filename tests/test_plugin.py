"""The Claude Code and Codex plugin in plugins/pubmed-stream, its marketplaces, and the texts that must agree."""

import json
import re
from pathlib import Path

from pubmed_stream import __version__
from pubmed_stream.assistants import instructions
from pubmed_stream.mcp_server import TOOLS

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "pubmed-stream"
RELEASE = f"pubmed-stream=={__version__}"
NUMBERS = {7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_every_copy_of_the_version_matches_the_package():
    assert re.search(r'^version: "(.+)"$', read("CITATION.cff"), re.M).group(1) == __version__
    for manifest in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        data = load(PLUGIN / manifest)
        assert data["name"] == "pubmed-stream"
        assert data["version"] == __version__, f"{manifest} names version {data['version']}"


def test_plugin_runs_the_release_of_its_own_version():
    codex = load(PLUGIN / ".codex-plugin" / "plugin.json")
    assert codex["mcpServers"] == "./.codex-plugin/mcp.json"
    server = load(PLUGIN / ".codex-plugin" / "mcp.json")["mcpServers"]["pubmed-stream"]   # read by Codex
    assert server["command"] == "uvx"
    assert server["args"] == ["--from", RELEASE, "pubmed-stream", "mcp"]
    # Codex allows a server 10 s to start and 60 s per call unless told otherwise: the first start downloads
    # pubmed-stream, and a large download or a knowledge graph takes minutes (Codex 0.163 reads both fields from
    # a plugin's file, verified)
    assert (server["startup_timeout_sec"], server["tool_timeout_sec"]) == (60, 600)
    # Claude Code: the same command inline, with the key; its own tool timeout is long enough. The plugin has no
    # root .mcp.json, so one server starts, and Anthropic's directory has no file to check against its schema
    assert not (PLUGIN / ".mcp.json").exists()
    claude = load(PLUGIN / ".claude-plugin" / "plugin.json")
    inline = claude["mcpServers"]["pubmed-stream"]
    timeouts = {"startup_timeout_sec", "tool_timeout_sec"}
    assert {k: v for k, v in inline.items() if k != "env"} == {k: v for k, v in server.items() if k not in timeouts}
    assert inline["env"] == {"PUBMED_STREAM_NCBI_API_KEY": "${user_config.ncbi_api_key}"}
    option = claude["userConfig"]["ncbi_api_key"]
    assert option["sensitive"] is True
    # Cowork ignores an MCP server that references an option without a default; an empty key means none
    assert option["default"] == "" and not option.get("required")


def test_skill_is_the_folder_instructions_under_a_plugin_note():
    skill = (PLUGIN / "skills" / "literature-search" / "SKILL.md").read_text(encoding="utf-8")
    assert re.match(r"---\nname: literature-search\ndescription: .+\n---\n", skill)
    assert f"pubmed-stream {__version__} through `uvx`" in skill
    assert f'uvx --from "{RELEASE}" pubmed-stream' in skill
    assert "/plugin configure pubmed-stream@pubmed-stream" in skill
    # Edit pubmed_stream/data/AGENTS.md, then copy it below the skill's header and note
    assert skill.endswith(instructions())


def test_instructions_name_every_tool():
    for tool in TOOLS:
        assert f"`{tool['name']}`" in instructions(), f"AGENTS.md does not name {tool['name']}"
    count = f"{NUMBERS[len(TOOLS)]} tools"
    assert count in read("README.md") and count in read("docs/ARCHITECTURE.md")


def test_marketplaces_point_at_the_plugin():
    claude = load(ROOT / ".claude-plugin" / "marketplace.json")["plugins"]
    codex = load(ROOT / ".agents" / "plugins" / "marketplace.json")["plugins"]
    assert [(p["name"], p["source"]) for p in claude] == [("pubmed-stream", "./plugins/pubmed-stream")]
    assert [(p["name"], p["source"]["path"]) for p in codex] == [("pubmed-stream", "./plugins/pubmed-stream")]
