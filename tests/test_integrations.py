"""MCP server, Ollama review, Obsidian helpers and assistant setup."""

import importlib
import io
import json

import pytest
import requests

from pubmed_stream import build_vault, cli
from pubmed_stream.assistants import init_folder, instructions
from pubmed_stream.mcp_server import TOOLS, Server, serve
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
    assert replies[1]["result"]["content"][0]["text"] == "done"
    assert replies[2]["error"]["code"] == -32700


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
    assert "[PMID 111](https://pubmed.ncbi.nlm.nih.gov/111/)" in result.markdown()


def test_review_marks_a_reply_cut_at_its_length_limit(make_session, tmp_path):
    write_article(tmp_path / "a", "111", "2024", "Trial one")
    session, _ = ollama(make_session, [("The study found the same thing again and", "length")])

    assert review("Q?", tmp_path, session=session).summaries[0].text.endswith("[cut at 300 tokens]")


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
                       ".mcp.json": "updated", ".codex/config.toml": "created"}
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == instructions()
    assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "# My notes\n\n@AGENTS.md\n"
    servers = json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]
    assert set(servers) == {"other", "pubmed-stream"} and servers["pubmed-stream"]["args"][-1] == "mcp"
    assert '[mcp_servers.pubmed-stream]\ncommand = "' in (tmp_path / ".codex" / "config.toml").read_text()
    assert set(dict(init_folder(tmp_path)).values()) == {"kept"}


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
