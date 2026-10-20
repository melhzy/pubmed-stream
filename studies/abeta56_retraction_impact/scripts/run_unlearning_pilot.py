#!/usr/bin/env python3
"""Compare untouched Ollama inference with a fixed evidence note (no weight updates).

python scripts/run_unlearning_pilot.py --out probes/runs/gpt_oss_20b_pilot
Outputs are new files; an existing output directory is never overwritten.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

import requests
import yaml

from probe_models import ask_ollama

ROOT = Path(__file__).resolve().parent.parent


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_prompt(question, as_of, context=""):
    preamble = (
        f"Answer the scientific question as of {as_of}. Use your knowledge and any "
        "evidence note provided below. No browsing or other tools are available. "
        "Do not claim to have searched. Distinguish reported findings from established "
        "evidence; say when you are uncertain. Keep the answer under 180 words.\n\n"
    )
    return preamble + (context.strip() + "\n\n" if context else "") + "Question: " + question.strip()


def valid_answer(result):
    return bool((result.get("answer") or "").strip()) and result.get("done_reason") == "stop"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="gpt-oss:20b")
    ap.add_argument("--host", default=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    ap.add_argument("--questions", type=Path, default=ROOT / "probes/unlearning_pilot.yaml")
    ap.add_argument("--context", type=Path, default=ROOT / "probes/retraction_context.txt")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--num-predict", type=int, default=4096)
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()
    if args.num_predict <= 0 or args.timeout <= 0:
        ap.error("num-predict and timeout must be positive")
    host = args.host.rstrip("/")
    question_text = args.questions.read_text(encoding="utf-8")
    context = args.context.read_text(encoding="utf-8")
    spec = yaml.safe_load(question_text)
    questions = spec["questions"]
    ids = [q["id"] for q in questions]
    if not questions or len(set(ids)) != len(ids):
        ap.error("questions must be nonempty and have unique IDs")
    if not context.strip():
        ap.error("the evidence note must be nonempty")
    response = requests.get(f"{host}/api/tags", timeout=15)
    response.raise_for_status()
    model = next((m for m in response.json()["models"] if m["name"] == args.model), None)
    if model is None:
        ap.error(f"{args.model} is not installed at the selected Ollama host")
    response = requests.get(f"{host}/api/version", timeout=15)
    response.raise_for_status()
    manifest = {
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "study": "abeta56_retraction_impact", "experiment": "context_control_only",
        "weight_updates": False, "model": model, "ollama": response.json(),
        "seed": args.seed, "temperature": 0.0, "think": "low",
        "num_predict": args.num_predict, "timeout_seconds": args.timeout,
        "questions_sha256": sha256(question_text), "context_sha256": sha256(context),
        "as_of": str(spec["as_of"]), "question_ids": ids,
        "conditions": ["baseline", "evidence_context"],
        "note": "Exploratory development probes; no statistical independence claimed.",
    }
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (args.out / "questions.yaml").write_text(question_text, encoding="utf-8")
    (args.out / "context.txt").write_text(context, encoding="utf-8")
    failures = 0
    with (args.out / "answers.jsonl").open("w", encoding="utf-8") as out:
        for i, q in enumerate(questions):
            # Alternate order. Each request is a fresh conversation with no history.
            conditions = ["baseline", "evidence_context"]
            if i % 2:
                conditions.reverse()
            for condition in conditions:
                prompt = make_prompt(q["prompt"], spec["as_of"], context if condition == "evidence_context" else "")
                record = {
                    "time": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "model": args.model, "model_digest": model["digest"],
                    "question_id": q["id"], "class": q["class"], "condition": condition,
                    "prompt": prompt, "prompt_sha256": sha256(prompt), "error": None,
                }
                try:
                    record.update(ask_ollama(prompt, args.model, temperature=0.0, think="low",
                                            host=host, seed=args.seed, num_predict=args.num_predict,
                                            timeout=args.timeout))
                except Exception as exc:
                    record["error"] = f"{type(exc).__name__}: {exc}"
                record["valid"] = not record["error"] and valid_answer(record)
                failures += not record["valid"]
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()
                print(f"{q['id']} {condition}: valid={record['valid']}, tokens={record.get('eval_count')}", flush=True)
    manifest.update(completed_at=dt.datetime.now(dt.timezone.utc).isoformat(), invalid_answers=failures)
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise SystemExit(f"{failures} invalid answers; retain these as failures, not successful forgetting")


if __name__ == "__main__":
    main()
