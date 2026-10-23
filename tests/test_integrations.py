"""MCP server, Ollama review, Obsidian helpers and assistant setup."""

import importlib
import io
import json

import pytest
import requests

from pubmed_stream import build_vault, cli, downloader
from pubmed_stream.downloader import DownloadStats
from pubmed_stream.assistants import init_folder, instructions
from pubmed_stream.mcp_server import INSTRUCTIONS, TOOLS, Server, console_is_own, serve
from pubmed_stream.obsidian import known_vaults, open_uri, open_vault
from pubmed_stream.review import OllamaError, numbers, review, save_to_vault, tidy
from pubmed_stream.vault import PAPERS_BASE


def write_article(folder, pmid, year, title, abstract="An abstract.", text="One two three.\nButyrate rose."):
    folder.mkdir(parents=True, exist_ok=True)
    data = {"pmcid": f"PMC{pmid}0", "metadata": {"pmid": pmid, "pmcid": f"PMC{pmid}0", "year": year,
                                                  "journal": "Nutrients", "title": title, "abstract": abstract},
            "text": text}
    (folder / f"PMC{pmid}0.json").write_text(json.dumps(data), encoding="utf-8")


# -- MCP server ---------------------------------------------------------------

def rpc(server, method, params=None, msg_id=1):
    return server.handle({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}})


def test_mcp_initialize_negotiates_the_version(tmp_path):
    server = Server(tmp_path)

    assert rpc(server, "initialize", {"protocolVersion": "2025-06-18"})["result"]["protocolVersion"] == "2025-06-18"
    result = rpc(server, "initialize", {"protocolVersion": "1999-01-01"})["result"]
    assert result["protocolVersion"] == "2025-11-25"
    assert result["capabilities"] == {"tools": {"listChanged": False}}
    assert "Cite only articles" in result["instructions"]


def test_mcp_lists_tools_with_schemas(tmp_path):
    tools = rpc(Server(tmp_path), "tools/list")["result"]["tools"]

    assert [t["name"] for t in tools] == [t["name"] for t in TOOLS]
    assert all(t["inputSchema"]["type"] == "object" for t in tools)
    assert next(t for t in tools if t["name"] == "list_articles")["annotations"]["readOnlyHint"] is True


def test_mcp_notifications_and_unknown_methods(tmp_path):
    server = Server(tmp_path)

    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert rpc(server, "ping")["result"] == {}
    assert rpc(server, "resources/list")["error"]["code"] == -32601
    assert rpc(server, "tools/call", {"name": "nope", "arguments": {}})["error"]["code"] == -32602


def test_mcp_list_and_read_articles(tmp_path):
    write_article(tmp_path / "publications" / "frailty", "111", "2024", "Butyrate and muscle")
    server = Server(tmp_path)

    listed = rpc(server, "tools/call", {"name": "list_articles", "arguments": {"ids": ["111", "999"],
                                                                              "abstracts": True}})["result"]
    text = listed["content"][0]["text"]
    assert not listed["isError"] and "Butyrate and muscle" in text and "An abstract." in text
    assert "Not downloaded: 999" in text

    found = rpc(server, "tools/call", {"name": "read_article", "arguments": {"id": "PMC1110", "find": "butyrate"}})
    assert '1 paragraphs mention "butyrate"' in found["result"]["content"][0]["text"]
    assert "[2] Butyrate rose." in found["result"]["content"][0]["text"]


def test_mcp_tool_problems_are_results_not_protocol_errors(tmp_path):
    result = rpc(Server(tmp_path), "tools/call", {"name": "list_articles", "arguments": {"path": "missing"}})["result"]

    assert result["isError"] is True and "does not exist" in result["content"][0]["text"]


def test_mcp_keeps_library_output_off_the_protocol(tmp_path, monkeypatch):
    def noisy(*args, **kwargs):
        print("Progress: 1/1 processed")
        return "done"
    monkeypatch.setattr("pubmed_stream.mcp_server.search_pmc", noisy)
    monkeypatch.setattr("pubmed_stream.mcp_server.count_pubmed", lambda query: 12)
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "search_pmc", "arguments": {"query": "x"}}},
    ]
    stdin = io.BytesIO(("\n".join(json.dumps(m) for m in messages) + "\nnot json\n").encode())
    stdout = io.BytesIO()

    serve(tmp_path, stdin=stdin, stdout=stdout)

    replies = [json.loads(line) for line in stdout.getvalue().decode().splitlines()]
    assert [r.get("id") for r in replies] == [1, 2, None]
    assert replies[1]["result"]["content"][0]["text"].startswith("done\n12 articles in PubMed")
    assert replies[2]["error"]["code"] == -32700


def test_mcp_hides_only_a_console_of_its_own():
    # a desktop app's server gets a console of its own: uv, the launcher and Python
    assert console_is_own(["uvx.exe", "pubmed-stream.exe", "python.exe"])
    assert console_is_own(["Python.exe"])
    # a terminal's console also holds the shell and the assistant, and must stay
    assert not console_is_own(["powershell.exe", "node.exe", "uvx.exe", "python.exe"])
    assert not console_is_own(["python.exe", "?"])     # a process that could not be inspected
    assert not console_is_own([])                      # no console at all


def test_mcp_instructions_name_every_tool():
    for tool in TOOLS:
        assert tool["name"] in INSTRUCTIONS, f"the server's instructions do not name {tool['name']}"


def test_mcp_reports_progress_when_the_client_asks(tmp_path, monkeypatch):
    def fake_download(query, max_results, output_dir, progress=None):
        for done in (5, 10):
            if progress:
                progress(done, 10, f"{done} of 10 articles")
        return DownloadStats(keyword=query, total_found=10, requested=10, successful=10, failed=0, skipped=0,
                             unavailable=0, errors=0, duration_seconds=1.0, output_dir=output_dir / "q")
    monkeypatch.setattr("pubmed_stream.mcp_server.search_and_download", fake_download)
    call = {"name": "download", "arguments": {"query": "q"}}
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {**call, "_meta": {"progressToken": "t1"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": call},   # no token: no notifications
    ]
    stdin = io.BytesIO(("\n".join(json.dumps(m) for m in messages) + "\n").encode())
    stdout = io.BytesIO()

    serve(tmp_path, stdin=stdin, stdout=stdout)

    replies = [json.loads(line) for line in stdout.getvalue().decode().splitlines()]
    assert [r.get("method") or r["id"] for r in replies] == ["notifications/progress", "notifications/progress", 1, 2]
    assert replies[0]["params"] == {"progressToken": "t1", "progress": 5, "total": 10, "message": "5 of 10 articles"}
    assert "10 downloaded" in replies[2]["result"]["content"][0]["text"]


# -- Ollama review --------------------------------------------------------------

def ollama(make_session, answers, status=200):
    """A fake Ollama whose replies are taken in order; records the prompts."""
    prompts, replies = [], iter(answers)

    def reply(request):
        body = json.loads(request.body)
        prompts.append(body)
        text, reason = next(replies)
        return json.dumps({"response": text, "done_reason": reason, "prompt_eval_count": 50})
    return make_session(routes={"api/generate": reply}, status=status), prompts


def test_review_attaches_ids_and_checks_numbers(make_session, tmp_path):
    folder = tmp_path / "publications"
    write_article(folder / "a", "111", "2024", "Trial one", abstract="Seventy-two patients improved by 5.8 points.")
    write_article(folder / "a", "222", "2023", "Trial two", abstract="Placebo was no different.")
    session, prompts = ollama(make_session, [
        ("Here is the finding:\nIn 72 patients the score improved by 5.8 points.", "stop"),
        ("It found 13 trials.", "stop"),
        ("FMT may help [111] but not in [222] or [333].", "stop"),
    ])

    result = review("Does FMT help?", folder, answer=True, session=session)

    assert [s.article["pmid"] for s in result.summaries] == ["111", "222"]
    assert result.summaries[0].text.startswith("In 72 patients")
    assert result.summaries[0].unsupported_numbers == [] and result.summaries[1].unsupported_numbers == ["13"]
    assert (result.not_read, result.not_cited) == (["333"], [])
    assert prompts[0]["options"]["temperature"] == 0 and prompts[0]["options"]["num_predict"] == 300
    assert prompts[0]["think"] is False
    # Summaries are written without the question, so it cannot be restated as a finding; the answer uses it
    assert "Does FMT help?" not in prompts[0]["prompt"] and "Does FMT help?" in prompts[2]["prompt"]
    assert "[PMID 111](https://pubmed.ncbi.nlm.nih.gov/111/)" in result.markdown()


def test_review_marks_a_reply_cut_at_its_length_limit(make_session, tmp_path):
    write_article(tmp_path / "a", "111", "2024", "Trial one")
    session, _ = ollama(make_session, [("The study found the same thing again and", "length")])

    summary = review("Q?", tmp_path, session=session).summaries[0]
    assert summary.text.endswith("[cut at 300 tokens]") and summary.unsupported_numbers == []


def test_review_explains_ollama_problems(make_session, tmp_path):
    write_article(tmp_path / "a", "111", "2024", "Trial one")

    with pytest.raises(OllamaError, match="not running"):
        review("Q?", tmp_path, session=make_session(error=requests.ConnectionError("refused")))
    with pytest.raises(OllamaError, match="ollama pull"):
        review("Q?", tmp_path, session=make_session(status=404, body='{"error": "model not found"}'))
    with pytest.raises(ValueError):
        review("Q?", tmp_path / "empty", session=make_session())


def test_review_saved_in_the_knowledge_graph(make_session, tmp_path):
    write_article(tmp_path / "pubs" / "a", "111", "2024", "Trial one")
    session, _ = ollama(make_session, [("It helped.", "stop")])
    result = review("Does FMT help?", tmp_path / "pubs", session=session)

    note = save_to_vault(result, tmp_path / "kg_fmt").read_text(encoding="utf-8")

    assert '  - "[[PMID111]]"' in note and "[[PMID111|PMID 111]]" in note and "pubmed/local-review" in note


def test_numbers_and_tidy():
    assert numbers("Seventy-two patients, eleven mice, 1,200 cells, 5.8 points") == {"72", "11", "1200", "5.8"}
    assert tidy("Here is the finding in two sentences:\n\nIt worked.") == "It worked."
    assert tidy("The study found that it worked.") == "The study found that it worked."


# -- Obsidian -------------------------------------------------------------------

def test_open_vault_only_opens_known_vaults(tmp_path):
    vault, other = tmp_path / "kg_fmt", tmp_path / "kg_other"
    vault.mkdir()
    other.mkdir()
    config = tmp_path / "obsidian.json"
    config.write_text(json.dumps({"vaults": {"abc": {"path": str(vault), "ts": 1}}}), encoding="utf-8")

    assert known_vaults(config) == [vault]
    assert open_vault(vault, config, launch=False) == (True, "Opened kg_fmt in Obsidian")
    opened, message = open_vault(other, config, launch=False)
    assert not opened and "Open folder as vault" in message
    assert known_vaults(tmp_path / "missing.json") == []
    assert open_uri(vault).startswith("obsidian://open?path=") and "%20" in open_uri(vault)


def test_vault_gets_property_types_and_a_papers_base(tmp_path):
    write_article(tmp_path / "pubs" / "a", "111", "2024", "Trial one")
    vault = tmp_path / "kg"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".obsidian" / "types.json").write_text(json.dumps({"types": {"year": "text", "rating": "number"}}))

    build_vault([tmp_path / "pubs" / "a"], vault, offline=True)

    types = json.loads((vault / ".obsidian" / "types.json").read_text())["types"]
    assert types["year"] == "text" and types["rating"] == "number"   # the user's types are kept
    assert types["retracted"] == "checkbox" and types["authors"] == "multitext"
    assert "file.inFolder(\"papers\")" in (vault / PAPERS_BASE).read_text()
    assert "![[Papers.base]]" in (vault / "PubMed Stream.md").read_text(encoding="utf-8")

    (vault / PAPERS_BASE).write_text("views: []\n")
    build_vault([tmp_path / "pubs" / "a"], vault, offline=True)
    assert (vault / PAPERS_BASE).read_text() == "views: []\n"   # never overwritten


# -- assistant setup ------------------------------------------------------------

def test_init_folder_writes_and_merges(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# My notes\n", encoding="utf-8")
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8")

    actions = dict(init_folder(tmp_path))

    assert actions == {"AGENTS.md": "created", "CLAUDE.md": "updated", "GEMINI.md": "created",
                       ".mcp.json": "updated", ".codex/config.toml": "created", ".gemini/settings.json": "created"}
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == instructions()
    assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "# My notes\n\n@AGENTS.md\n"
    servers = json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]
    assert set(servers) == {"other", "pubmed-stream"} and servers["pubmed-stream"]["args"][-1] == "mcp"
    codex = (tmp_path / ".codex" / "config.toml").read_text()
    assert '[mcp_servers.pubmed-stream]\ncommand = "' in codex and 'env_vars = ["NCBI_API_KEY", "NCBI_EMAIL"]' in codex
    gemini = json.loads((tmp_path / ".gemini" / "settings.json").read_text())["mcpServers"]["pubmed-stream"]
    assert gemini["args"][-1] == "mcp" and gemini["timeout"] == 600000
    assert set(dict(init_folder(tmp_path)).values()) == {"kept"}


def test_init_leaves_the_server_to_the_plugin(tmp_path, home):
    folder = tmp_path / "study"
    assert dict(init_folder(folder))[".mcp.json"] == "created"      # set up before the plugin was installed
    mcp, codex = folder / ".mcp.json", folder / ".codex" / "config.toml"
    data = json.loads(mcp.read_text(encoding="utf-8"))
    data["mcpServers"]["other"] = {"command": "x"}
    mcp.write_text(json.dumps(data), encoding="utf-8")
    codex.write_text(codex.read_text(encoding="utf-8") + "\n[other]\nx = 1\n", encoding="utf-8")

    (home / ".claude").mkdir()
    (home / ".claude" / "settings.json").write_text(json.dumps({"enabledPlugins": {"pubmed-stream@pubmed-stream": True}}))
    (home / ".codex").mkdir()
    (home / ".codex" / "config.toml").write_text('model = "o3"\n\n[plugins."pubmed-stream@pubmed-stream"]\nenabled = true\n')

    actions = dict(init_folder(folder))
    assert actions[".mcp.json"] == "plugin" and actions[".codex/config.toml"] == "plugin"
    assert actions[".gemini/settings.json"] == "kept"                # Gemini CLI has no plugin
    assert set(json.loads(mcp.read_text(encoding="utf-8"))["mcpServers"]) == {"other"}
    assert codex.read_text(encoding="utf-8") == "[other]\nx = 1\n"
    assert dict(init_folder(folder))[".mcp.json"] == "plugin"       # and stays that way

    # a folder that switches the plugin off overrides the user's settings
    (folder / ".claude").mkdir(exist_ok=True)
    (folder / ".claude" / "settings.local.json").write_text(json.dumps({"enabledPlugins": {"pubmed-stream@pubmed-stream": False}}))
    assert dict(init_folder(folder))[".mcp.json"] == "updated"
    (folder / ".claude" / "settings.local.json").unlink()
    assert dict(init_folder(folder))[".mcp.json"] == "plugin"

    # a sub-table of the server goes with it, or Codex would see a server without a command
    codex.write_text('[mcp_servers.pubmed-stream]\ncommand = "x"\n\n[mcp_servers.pubmed-stream.env]\nA = "1"\n\n[other]\nx = 1\n', encoding="utf-8")
    assert dict(init_folder(folder))[".codex/config.toml"] == "plugin"
    assert codex.read_text(encoding="utf-8") == "[other]\nx = 1\n"

    # a disabled plugin does not count
    (home / ".claude" / "settings.json").write_text(json.dumps({"enabledPlugins": {"pubmed-stream@pubmed-stream": False}}))
    (home / ".codex" / "config.toml").write_text('[plugins."pubmed-stream@pubmed-stream"]\nenabled = false\n')
    actions = dict(init_folder(folder))
    assert actions[".mcp.json"] == "updated" and actions[".codex/config.toml"] == "updated"
    assert "pubmed-stream" in json.loads(mcp.read_text(encoding="utf-8"))["mcpServers"]


def test_init_counts_a_plugin_synced_from_claude_ai(tmp_path, home):
    # Claude Code syncs a plugin added on the claude.ai account into its plugins folder, with no settings entry
    synced = home / ".claude" / "plugins" / "synced" / "account-id" / "pubmed-stream" / ".claude-plugin"
    synced.mkdir(parents=True)
    (synced / "plugin.json").write_text('{"name": "pubmed-stream"}', encoding="utf-8")

    assert dict(init_folder(tmp_path))[".mcp.json"] == "plugin"

    # turned off in Claude Code, it does not count
    settings = home / ".claude" / "settings.json"
    settings.write_text(json.dumps({"enabledPlugins": {"pubmed-stream@synced": False}}))
    assert dict(init_folder(tmp_path))[".mcp.json"] == "created"

    # a disabled copy of one's own does not hide the synced one, which Claude Code then loads
    settings.write_text(json.dumps({"enabledPlugins": {"pubmed-stream@pubmed-stream": False}}))
    assert dict(init_folder(tmp_path))[".mcp.json"] == "plugin"


def test_init_keeps_the_server_where_claude_code_would_not_load_the_synced_plugin(tmp_path, home, monkeypatch):
    (home / ".claude" / "plugins" / "synced" / "account-id" / "pubmed-stream").mkdir(parents=True)
    settings = home / ".claude" / "settings.json"

    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "token")                # another credential signs in
    assert dict(init_folder(tmp_path))[".mcp.json"] == "created"
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN")
    assert dict(init_folder(tmp_path))[".mcp.json"] == "plugin"
    for data in ({"apiKeyHelper": "~/bin/key.sh"}, {"syncClaudeAiPlugins": False},
                 {"env": {"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}}):
        settings.write_text("{}")
        assert dict(init_folder(tmp_path))[".mcp.json"] == "plugin"           # the synced copy counts
        settings.write_text(json.dumps(data))
        assert dict(init_folder(tmp_path))[".mcp.json"] == "updated", data    # Claude Code would not load it
    settings.write_text("{}")
    assert dict(init_folder(tmp_path))[".mcp.json"] == "plugin"

    # the settings merge one id at a time: the folder's off overrides the user's on, and the synced copy counts
    settings.write_text(json.dumps({"enabledPlugins": {"pubmed-stream@pubmed-stream": True}}))
    (tmp_path / ".claude").mkdir(exist_ok=True)
    (tmp_path / ".claude" / "settings.local.json").write_text(json.dumps({"enabledPlugins": {"pubmed-stream@pubmed-stream": False}}))
    assert dict(init_folder(tmp_path))[".mcp.json"] == "plugin"
    (home / ".claude" / "plugins" / "synced" / "account-id" / "pubmed-stream").rmdir()
    assert dict(init_folder(tmp_path))[".mcp.json"] == "updated"                # no copy left: the server returns


def test_init_saves_the_api_key_for_the_user(tmp_path, home, monkeypatch, capsys):
    verdicts = {"typed-key": "ok", "bad-key": "invalid", "unchecked": "unknown"}
    monkeypatch.setattr("pubmed_stream.downloader.check_api_key", lambda key, session=None: verdicts[key])
    file = home / ".pubmed-stream.json"
    assert (str(file), "created") in init_folder(tmp_path, ncbi_api_key="abc")
    assert json.loads(file.read_text(encoding="utf-8")) == {"ncbi_api_key": "abc"}

    # in a terminal, init asks for the key only while none is configured and the question is new
    monkeypatch.setattr("sys.argv", ["pubmed-stream", "init", str(tmp_path)])
    monkeypatch.setattr(cli, "_interactive", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": pytest.fail("asked although a key is saved"))
    assert cli.main() == 0
    assert f"NCBI API key: on (…abc, from {file})" in capsys.readouterr().out
    file.unlink()
    monkeypatch.setattr("builtins.input", lambda prompt="": "  typed-key ")
    assert cli.main() == 0
    out = capsys.readouterr().out
    assert "three times faster" in out and "NCBI accepted the key." in out and f"created  {file}" in out
    assert json.loads(file.read_text(encoding="utf-8"))["ncbi_api_key"] == "typed-key"
    file.unlink()
    monkeypatch.setattr("builtins.input", lambda prompt="": "")          # Enter skips, and the answer is remembered
    assert cli.main() == 0
    assert json.loads(file.read_text(encoding="utf-8")) == {"ncbi_api_key": ""}
    assert "NCBI API key: off;" in capsys.readouterr().out
    monkeypatch.setattr("builtins.input", lambda prompt="": pytest.fail("asked again after a skip"))
    assert cli.main() == 0
    file.unlink()
    monkeypatch.setattr(cli, "_interactive", lambda: False)             # as when an assistant runs init
    monkeypatch.setattr("builtins.input", lambda prompt="": pytest.fail("asked outside a terminal"))
    assert cli.main() == 0 and not file.exists()

    # a key is checked with NCBI before it is saved
    monkeypatch.setattr("sys.argv", ["pubmed-stream", "init", str(tmp_path), "--ncbi-api-key", "bad-key"])
    assert cli.main() == 1 and not file.exists()
    assert "NCBI rejected this key" in capsys.readouterr().err
    monkeypatch.setattr("sys.argv", ["pubmed-stream", "init", str(tmp_path), "--ncbi-api-key", "unchecked"])
    assert cli.main() == 0 and json.loads(file.read_text(encoding="utf-8"))["ncbi_api_key"] == "unchecked"
    assert "could not be reached" in capsys.readouterr().out

    # a corrupt settings file is reported, never replaced
    file.write_text("{", encoding="utf-8")
    assert cli.main() == 1 and file.read_text(encoding="utf-8") == "{"
    assert f"{file} is not valid JSON" in capsys.readouterr().err


def test_server_saves_the_plugin_key_after_ncbi_accepted_it(tmp_path, home, monkeypatch):
    """The plugin's key reaches ~/.pubmed-stream.json after a tool call checked it, never before, and a rejected
    key is reported to the assistant once."""
    monkeypatch.setattr("pubmed_stream.mcp_server.search_pmc", lambda *a, **k: "found")
    monkeypatch.setattr("pubmed_stream.mcp_server.count_pubmed", lambda query: 1)
    verdicts = {}
    monkeypatch.setattr(downloader, "_checked_keys", verdicts)
    file = home / ".pubmed-stream.json"
    server = Server(tmp_path)

    plain = "found\n1 articles in PubMed; fetch_abstracts saves the abstracts of the rest."

    def call():
        return rpc(server, "tools/call", {"name": "search_pmc", "arguments": {"query": "x"}})["result"]["content"][0]["text"]

    monkeypatch.setenv("PUBMED_STREAM_NCBI_API_KEY", "plug-key")
    assert call() == plain and not file.exists()                               # NCBI has not been asked yet
    verdicts["plug-key"] = ("ok", 0.0)
    assert call() == plain
    assert json.loads(file.read_text(encoding="utf-8")) == {"ncbi_api_key": "plug-key"}

    file.write_text(json.dumps({"ncbi_api_key": "mine"}), encoding="utf-8")
    Server(tmp_path).call_tool("search_pmc", {"query": "x"})                   # a saved key is kept
    assert json.loads(file.read_text(encoding="utf-8")) == {"ncbi_api_key": "mine"}

    file.unlink()
    monkeypatch.setenv("PUBMED_STREAM_NCBI_API_KEY", "bad-key")
    verdicts["bad-key"] = ("invalid", 0.0)
    server = Server(tmp_path)
    text = call()
    assert text.startswith(plain) and text.endswith("THE-KEY` in a terminal.") and not file.exists()   # reported, not spread
    assert call() == plain                                                     # once


def test_download_tool_says_what_a_key_would_save(tmp_path, monkeypatch):
    stats = DownloadStats(keyword="x", total_found=50, requested=50, successful=10, failed=40, skipped=0,
                          unavailable=40, errors=0, duration_seconds=30.0, output_dir=tmp_path / "publications" / "x")
    monkeypatch.setattr("pubmed_stream.mcp_server.search_and_download", lambda *a, **k: stats)
    text = Server(tmp_path).call_tool("download", {"query": "x"})["content"][0]["text"]
    # 50 requests, not 90: failed already counts the unavailable articles
    assert "10 downloaded" in text and "took 30 s" in text and "about 18 s" in text


def test_mcp_tells_the_assistant_when_no_api_key_is_configured(tmp_path, monkeypatch):
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    monkeypatch.delenv("PUBMED_STREAM_NCBI_API_KEY", raising=False)
    server = Server(tmp_path)
    assert "No NCBI API key" in rpc(server, "initialize", {"protocolVersion": "2025-06-18"})["result"]["instructions"]
    monkeypatch.setenv("NCBI_API_KEY", "k")
    assert "No NCBI API key" not in rpc(server, "initialize", {"protocolVersion": "2025-06-18"})["result"]["instructions"]


def test_cli_init_and_open(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["pubmed-stream", "init", str(tmp_path)])
    assert cli.main() == 0
    assert "created" in capsys.readouterr().out

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["pubmed-stream", "open"])
    assert cli.main() == 1
    assert "name the knowledge graph folder" in capsys.readouterr().err


def test_init_chooses_models_for_the_folder(tmp_path, monkeypatch, make_session):
    from pubmed_stream.assistants import review_model

    actions = init_folder(tmp_path, claude_model="opus", review_model="llama3.2:3b")

    assert (".claude/settings.json", "created") in actions and (".pubmed-stream.json", "created") in actions
    assert json.loads((tmp_path / ".claude" / "settings.json").read_text())["model"] == "opus"
    assert review_model(tmp_path) == "llama3.2:3b" and review_model(tmp_path / "elsewhere") is None
    assert (".claude/settings.json", "kept") in init_folder(tmp_path, claude_model="opus")
    assert (".claude/settings.json", "updated") in init_folder(tmp_path, claude_model="sonnet")

    # review uses the folder's model when --model is not given
    write_article(tmp_path / "publications" / "a", "111", "2024", "Trial one")
    session, prompts = ollama(make_session, [("It helped.", "stop")])
    review_module = importlib.import_module("pubmed_stream.review")   # the package exports a function of that name
    monkeypatch.setattr(review_module, "requests", session)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["pubmed-stream", "review", "Q?"])
    assert cli.main() == 0
    assert prompts[0]["model"] == "llama3.2:3b"
