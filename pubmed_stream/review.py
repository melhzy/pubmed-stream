"""Summarize downloaded articles with a local model, through Ollama.

A small local model cannot run pubmed-stream itself, so the work is split:
pubmed-stream collects the articles, the model summarizes one abstract at a
time through Ollama's local server (https://ollama.com), and ``review``
attaches each article's PubMed ID itself, so a summary is never credited to
the wrong paper.  The model does not see the question while it summarizes,
so it cannot present the question as a finding.  Every number in a summary must appear in its abstract;
others are flagged.

With ``answer=True`` the model also writes one answer from all the
summaries.  Small models often mix up or invent claims across papers, so the
answer is checked too: every PubMed ID it cites must be among the articles
read.  Generation uses temperature 0, so the same input gives the same
output while the model stays loaded; after Ollama reloads it, the output
can differ.
"""

import datetime
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import requests

from .corpus import list_articles

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

DEFAULT_MODEL = "hf.co/unsloth/Llama-3.2-1B-Instruct-GGUF:Q4_K_M"
DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_CONTEXT = 8192

# The question is left out on purpose: given it, small models open with it restated as a finding
# ("The gut microbiota is linked to frailty.") even when the article did not test it.
PAPER_PROMPT = """Article: {title} ({year}, {journal})
Abstract: {abstract}

Summarize this abstract in at most three sentences. First say what kind of study it is and who or what it studied. Then give its main result in the abstract's own words, keeping the direction of every effect as the abstract states it. Copy numbers exactly as written and add no others. Do not repeat the title, and write nothing but the summary."""

ANSWER_PROMPT = """Question: {question}

Below are summaries of {n} articles. Each starts with its PubMed ID in square brackets.

{summaries}

Answer the question in one paragraph of at most 150 words, using only these summaries. After each \
statement, cite the articles that support it by their PubMed IDs in square brackets, exactly as given, \
for example [{example}]. Do not cite anything else. Say where the articles disagree."""

ANSWER_WARNING = ("Small models often credit a finding to the wrong paper or invent a disagreement, which no "
                  "automatic check catches. Use this answer only as a draft, and check every statement "
                  "against the summaries above.")


class OllamaError(RuntimeError):
    """Ollama is not running, or does not have the model."""


@dataclass
class Summary:
    """One article and the model's summary of its abstract."""
    article: Dict[str, Any]
    text: str
    unsupported_numbers: List[str] = field(default_factory=list)


@dataclass
class Review:
    """A local model's summaries of downloaded articles, with checks."""
    question: str
    model: str
    summaries: List[Summary]
    answer: Optional[str] = None
    not_read: List[str] = field(default_factory=list)      # cited by the answer, but not among the articles
    not_cited: List[str] = field(default_factory=list)     # read, but not cited by the answer
    date: datetime.date = field(default_factory=datetime.date.today)

    def markdown(self, wikilinks: bool = False) -> str:
        """The review as Markdown; with *wikilinks*, papers link to their notes in a knowledge graph."""
        lines = [
            f"Summaries by the local model `{self.model}`, {self.date:%d %B %Y}, of the abstracts of "
            f"{len(self.summaries)} articles downloaded with pubmed-stream. Each article's PubMed ID was "
            "attached by pubmed-stream, not by the model. A small model makes mistakes: check each summary "
            "against its abstract.",
            "",
        ]
        for s in self.summaries:
            a = s.article
            link = (f"[[PMID{a['pmid']}|PMID {a['pmid']}]]" if wikilinks
                    else f"[PMID {a['pmid']}](https://pubmed.ncbi.nlm.nih.gov/{a['pmid']}/)")
            lines += [f"## {a['title']}", "", f"{a['year']}, *{a['journal']}*, {link}", "", s.text, ""]
            if s.unsupported_numbers:
                lines += [f"> [!warning] Check: these numbers are not in the abstract: "
                          f"{', '.join(s.unsupported_numbers)}", ""]
        if self.answer is not None:
            lines += ["## Answer from all the summaries (experimental)", "", f"> [!caution] {ANSWER_WARNING}",
                      "", self.answer, "",
                      f"- Cited PubMed IDs that are not among the articles read: "
                      f"**{', '.join(self.not_read) or 'none'}**",
                      f"- Articles read but not cited: {', '.join(self.not_cited) or 'none'}", ""]
        return "\n".join(lines)

    def __str__(self) -> str:
        return f"# {self.question}\n\n{self.markdown()}"


_UNITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
          "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_WORD_NUMBERS = {word: n for n, word in enumerate(_UNITS)}
_WORD_NUMBERS.update({word: 20 + 10 * i for i, word in enumerate(_TENS)})


def numbers(text: str) -> set:
    """Numbers in *text*, written as digits (5.8, 1,200) or as words below 100 (Seventy-two)."""
    found = {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}
    for tens, units in re.findall(r"\b([a-z]+)(?:[- ]([a-z]+))?\b", text.lower()):
        if tens in _WORD_NUMBERS:
            value = _WORD_NUMBERS[tens]
            if value >= 20 and 0 < _WORD_NUMBERS.get(units, 0) < 10:   # seventy-two
                value += _WORD_NUMBERS[units]
            found.add(str(value))
    return found


def tidy(summary: str) -> str:
    """Drop an opening line such as 'Here is the finding:' that small models add."""
    lines = summary.strip().splitlines()
    if (len(lines) > 1 and lines[0].rstrip().endswith(":")
            and re.match(r"(here|this article|the article)\b", lines[0].strip(), re.I)):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _host(host: Optional[str]) -> str:
    host = (host or os.getenv("OLLAMA_HOST") or DEFAULT_HOST).rstrip("/")
    if not host.startswith(("http://", "https://")):
        host = "http://" + host
    return host.replace("://0.0.0.0", "://127.0.0.1")


def generate(prompt: str, model: str = DEFAULT_MODEL, host: Optional[str] = None,
             num_ctx: int = DEFAULT_CONTEXT, session: Optional[requests.Session] = None,
             max_tokens: int = 300) -> str:
    """One answer from a local model, at temperature 0, at most *max_tokens* long.

    At temperature 0 a small model can repeat itself without end, so the
    answer is capped, and repetition is discouraged; a capped answer ends
    with a note saying so.  Models that think before answering, such as
    Qwen3, are asked not to, so the cap is not spent on thinking.

    Raises:
        OllamaError: Ollama is not running at *host*, or does not have *model*.
    """
    url = f"{_host(host)}/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": False, "think": False,
               "options": {"temperature": 0, "num_ctx": num_ctx, "num_predict": max_tokens,
                           "repeat_penalty": 1.15}}
    try:
        resp = (session or requests).post(url, json=payload, timeout=900)
    except requests.ConnectionError:
        raise OllamaError(f"Ollama is not running at {_host(host)}. Install it from https://ollama.com, "
                          "or start it with 'ollama serve'.") from None
    if resp.status_code == 404:
        raise OllamaError(f"Ollama does not have the model {model}. Download it with: ollama pull {model}")
    if not resp.ok:
        raise OllamaError(f"Ollama answered {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    if data.get("prompt_eval_count", 0) >= num_ctx:
        logger.warning("The prompt filled the model's %d-token context and was cut; raise num_ctx", num_ctx)
    text = (data.get("response") or "").strip()
    if data.get("done_reason") == "length":
        text += f" [cut at {max_tokens} tokens]"
    return text


def review(
    question: str,
    path: PathLike = "publications",
    ids: Optional[Sequence[str]] = None,
    limit: int = 10,
    model: str = DEFAULT_MODEL,
    answer: bool = False,
    host: Optional[str] = None,
    num_ctx: int = DEFAULT_CONTEXT,
    session: Optional[requests.Session] = None,
) -> Review:
    """Summarize downloaded articles with a local model, one abstract at a time.

    *ids* selects articles by PubMed ID or PMC ID; without it, the newest
    *limit* articles under *path* are used.  Articles without an abstract or
    a PubMed ID are skipped.

    Raises:
        OllamaError: Ollama is not running, or does not have *model*.
        ValueError: no downloaded article qualifies.
    """
    records = list_articles(path)
    if ids:
        wanted = {str(i).strip().upper() for i in ids}
        records = [r for r in records if str(r["pmid"]) in wanted or r["pmcid"].upper() in wanted]
    else:
        records = records[:limit]
    records = [r for r in records if r["abstract"] and r["pmid"]]
    if not records:
        raise ValueError(f"No downloaded articles with an abstract and a PubMed ID in {path}")

    summaries = []
    for i, r in enumerate(records, 1):
        logger.info("Summarizing %d of %d: PMID %s", i, len(records), r["pmid"])
        text = tidy(generate(PAPER_PROMPT.format(**r), model, host, num_ctx, session))
        summary = re.sub(r" \[cut at \d+ tokens\]$", "", text)   # without the note on a cut reply
        unsupported = sorted(numbers(summary) - numbers(f"{r['abstract']} {r['title']}") - {str(r["year"])})
        summaries.append(Summary(r, text, unsupported))

    result = Review(question, model, summaries)
    if answer:
        listing = "\n\n".join(f"[{s.article['pmid']}] {s.text}" for s in summaries)
        result.answer = generate(ANSWER_PROMPT.format(question=question, n=len(summaries), summaries=listing,
                                                      example=records[0]["pmid"]),
                                 model, host, num_ctx, session, max_tokens=500)
        read = {str(r["pmid"]) for r in records}
        cited = {a or b for a, b in re.findall(r"\[(\d{1,9})\]|PMID:?\s*(\d{1,9})", result.answer)}
        result.not_read, result.not_cited = sorted(cited - read), sorted(read - cited)
    return result


def save_to_vault(result: Review, vault_dir: PathLike) -> Path:
    """Write *result* as a note in a knowledge graph's ``reviews`` folder, linked to the paper notes."""
    from .vault import _safe_name, _yaml_entry

    folder = Path(vault_dir) / "reviews"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{_safe_name(result.question)} ({result.date:%Y-%m-%d}).md"
    properties = [
        _yaml_entry("type", "review"),
        _yaml_entry("question", result.question),
        _yaml_entry("model", result.model),
        _yaml_entry("date", f"{result.date:%Y-%m-%d}"),
        _yaml_entry("papers", [f"[[PMID{s.article['pmid']}]]" for s in result.summaries]),
        _yaml_entry("tags", ["pubmed/local-review"]),
    ]
    path.write_text("---\n" + "\n".join(properties) + "\n---\n"
                    + f"# {result.question}\n\n" + result.markdown(wikilinks=True), encoding="utf-8")
    return path
