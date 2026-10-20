#!/usr/bin/env python3
"""Ask the probe questions of language models and save their answers.

Models are named on the command line:

  ollama:<model>      a model served by Ollama on this computer (tools off by nature)
  claude, codex, gemini, or claude:<model>, codex:<model>, gemini:<model>
                      an AI assistant installed on this computer, run through
                      pubmed-stream's ask_assistant in an empty folder with its
                      tools turned off, so the answer is parametric knowledge only

Each question in probes/questions.yaml is asked --repeats times.  Answers are
appended to probes/answers/<model>.jsonl, one JSON object per line, with the
time, the model, the question and the answer.  Scoring is done afterwards, by a
person, with the keys in the questions file.

Usage:
  python scripts/probe_models.py --models ollama:gpt-oss:20b claude --repeats 3
"""

import argparse
import datetime as dt
import sys
import json
import os
import re
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent          # this study
sys.path.insert(0, str(ROOT.parent.parent))             # the repository: run from a clone without installing

PREAMBLE = ("Answer from your own knowledge, without searching the web or any files. "
            "If you are not sure, say so. Be specific about papers, dates and evidence.\n\n")


NUM_PREDICT = 8192   # tokens a local model may generate, reasoning included


def ask_ollama(prompt: str, model: str, temperature: float = 0.0, think=None, host: str = "",
               seed=None, num_predict: int = NUM_PREDICT, timeout: int = 1800) -> dict:
    """One answer from a model in Ollama; returns the answer with its reasoning and stop reason.

    Reasoning models can spend their whole budget thinking and return an empty
    answer, so the budget is large and ``think`` ("low", "medium", "high" for
    gpt-oss, True or False for others) can be set; gpt-oss defaults to "low".
    """
    host = (host or os.environ.get("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
    body = {"model": model, "prompt": prompt, "stream": False,
            "options": {"temperature": temperature, "num_predict": num_predict}}
    if seed is not None:
        body["options"]["seed"] = seed
    if think is None and model.startswith("gpt-oss"):
        think = "low"
    if think is not None:
        body["think"] = think
    r = requests.post(f"{host}/api/generate", timeout=timeout, json=body)
    r.raise_for_status()
    data = r.json()
    return {"answer": (data.get("response") or "").strip(), "thinking": (data.get("thinking") or "").strip(),
            "done_reason": data.get("done_reason"), "eval_count": data.get("eval_count")}


def ask(prompt: str, model: str, temperature: float, think=None) -> dict:
    if model.startswith("ollama:"):
        return ask_ollama(prompt, model[len("ollama:"):], temperature, think)
    from pubmed_stream import ask_assistant   # claude, codex, gemini, optionally with :model
    return {"answer": ask_assistant(prompt, model), "thinking": "", "done_reason": None, "eval_count": None}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.0, help="Ollama models only")
    ap.add_argument("--think", default=None,
                    help="Ollama reasoning: low, medium or high for gpt-oss (default low), true or false for others")
    ap.add_argument("--questions", type=Path, default=ROOT / "probes" / "questions.yaml")
    ap.add_argument("--out", type=Path, default=ROOT / "probes" / "answers")
    ap.add_argument("--only", nargs="*", default=[], help="question IDs to ask, default all")
    args = ap.parse_args()
    think = {None: None, "true": True, "false": False}.get(args.think, args.think)

    with open(args.questions, encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    questions = [q for q in spec["questions"] if not args.only or q["id"] in args.only]
    args.out.mkdir(parents=True, exist_ok=True)

    for model in args.models:
        path = args.out / (re.sub(r"[^A-Za-z0-9_.-]+", "_", model) + ".jsonl")
        with open(path, "a", encoding="utf-8") as f:
            for q in questions:
                for repeat in range(1, args.repeats + 1):
                    record = {"time": dt.datetime.now().isoformat(timespec="seconds"), "model": model,
                              "question_id": q["id"], "class": q["class"], "repeat": repeat,
                              "prompt": q["prompt"].strip(), "answer": None, "thinking": None,
                              "done_reason": None, "eval_count": None, "error": None}
                    try:
                        record.update(ask(PREAMBLE + q["prompt"].strip(), model, args.temperature, think))
                    except Exception as e:   # one failure must not stop the run
                        record["error"] = f"{type(e).__name__}: {e}"
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    f.flush()
                    status = ("error" if record["error"] else
                              f"{len(record['answer'])} chars, stopped: {record['done_reason'] or 'n/a'}")
                    print(f"{model} {q['id']} #{repeat}: {status}", flush=True)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
