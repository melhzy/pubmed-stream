"""Offline tests of reviews by AI assistants (Claude Code, Codex, Gemini CLI); the assistants are faked."""

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from pubmed_stream import cli
from pubmed_stream.review import AssistantError, assistant, review, save_to_vault

review_module = importlib.import_module("pubmed_stream.review")


def write_article(folder, pmid, title, abstract):
    folder.mkdir(parents=True, exist_ok=True)
    data = {"pmcid": f"PMC{pmid}", "metadata": {"pmid": pmid, "pmcid": f"PMC{pmid}", "year": "2024",
                                                "journal": "Gut", "title": title, "abstract": abstract}, "text": "x"}
    (folder / f"PMC{pmid}.json").write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def papers(tmp_path):
    write_article(tmp_path, "111", "Trial one", "Seventy-two patients improved by 5.8 points.")
    write_article(tmp_path, "222", "Trial two", "Placebo was no different.")
    return tmp_path


@pytest.fixture
def fake(monkeypatch):
    """A fake assistant: records each command line and answers with the abstract's first word."""
    calls = []

    def run(line, input, cwd, **kwargs):
        calls.append({"line": line, "input": input, "cwd": cwd})
        reply = "It found 13 trials." if "Placebo" in input else "In 72 patients the score improved by 5.8 points."
        if "-o" in line:   # Codex writes its last message to a file
            Path(line[line.index("-o") + 1]).write_text(reply, encoding="utf-8")
            reply = "progress output"
        return subprocess.CompletedProcess(line, 0, stdout=reply, stderr="")

    monkeypatch.setattr(review_module.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(review_module.subprocess, "run", run)
    return calls


def test_assistant_names_are_told_apart_from_ollama_models():
    assert assistant("claude") == ("claude", None)
    assert assistant("codex:gpt-5") == ("codex", "gpt-5")
    assert assistant("qwen3.5:4b") is None and assistant("hf.co/unsloth/Llama-3.2-1B-Instruct-GGUF:Q4_K_M") is None


def test_claude_summarizes_without_tools_or_the_question(papers, fake):
    result = review("Does FMT help?", papers, model="claude:opus")

    # In the articles' order, although up to four are summarized at once
    assert [s.article["pmid"] for s in result.summaries] == ["222", "111"]
    assert result.summaries[0].unsupported_numbers == ["13"] and result.summaries[1].unsupported_numbers == []
    line = fake[0]["line"]
    assert line[:2] == ["/bin/claude", "-p"] and line[line.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in line and line[-2:] == ["--model", "opus"]
    assert all("Does FMT help?" not in call["input"] for call in fake)
    assert all(Path(call["cwd"]).name.startswith("pubmed-stream-") for call in fake)   # a new, empty folder
    assert "Summaries by Claude Code (`claude:opus`)" in result.markdown()
    assert "The abstracts were sent to Anthropic" in result.markdown()


def test_codex_answer_comes_from_its_last_message_file(papers, fake):
    result = review("Does FMT help?", papers, model="codex", ids=["111"])

    assert result.summaries[0].text == "In 72 patients the score improved by 5.8 points."
    line = fake[0]["line"]
    assert line[:2] == ["/bin/codex", "exec"] and line[-1] == "-" and "--ignore-user-config" in line
    assert line[line.index("-s") + 1] == "read-only"


def test_gemini_reads_the_prompt_on_stdin_in_plan_mode(papers, fake):
    review("Does FMT help?", papers, model="gemini:gemini-3-pro", ids=["222"])

    line = fake[0]["line"]
    assert line[:2] == ["/bin/gemini", "-p"] and line[line.index("--approval-mode") + 1] == "plan"
    assert line[-2:] == ["-m", "gemini-3-pro"] and "Placebo was no different." in fake[0]["input"]


def test_assistant_notes_are_tagged_apart_from_local_ones(papers, fake, tmp_path):
    note = save_to_vault(review("Does FMT help?", papers, model="codex"), tmp_path / "kg")

    text = note.read_text(encoding="utf-8")
    assert note.name.endswith(", codex).md")
    local = save_to_vault(review("Does FMT help?", papers, model="claude:opus"), tmp_path / "kg")
    assert local.name.endswith(", claude opus).md") and local != note
    assert '"pubmed/assistant-review"' in text and "local-review" not in text and 'model: "codex"' in text


def test_missing_or_failing_assistants_explain_the_fix(papers, monkeypatch):
    monkeypatch.setattr(review_module.shutil, "which", lambda name: None)
    with pytest.raises(AssistantError, match="Codex is not installed"):
        review("Q?", papers, model="codex")

    monkeypatch.setattr(review_module.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(review_module.subprocess, "run", lambda line, **kw: subprocess.CompletedProcess(
        line, 1, stdout="", stderr="Error: not logged in"))
    with pytest.raises(AssistantError, match="Claude Code failed .exit 1.: Error: not logged in"):
        review("Q?", papers, model="claude")


def test_cli_review_with_an_assistant_exits_2_when_it_fails(papers, monkeypatch, capsys):
    monkeypatch.setattr(review_module.shutil, "which", lambda name: None)
    monkeypatch.setattr(sys, "argv", ["pubmed-stream", "review", "Q?", "--path", str(papers), "--model", "gemini"])

    assert cli.main() == 2
    assert "Gemini CLI is not installed" in capsys.readouterr().err
