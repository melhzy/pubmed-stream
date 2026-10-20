"""Checks that data triage and inference failures cannot become forgetting results."""
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prepare_unlearning import build_queue, triage
from probe_models import ask_ollama
from run_unlearning_pilot import make_prompt, valid_answer


class ReviewQueueTests(unittest.TestCase):
    def row(self, text, kind="Cites it in general", pmid="123"):
        return {"pmid": pmid, "year": "2010", "citation_kind": kind, "citation_sentence": text}

    def test_aliases_in_general_citations_are_only_candidates(self):
        for text in ["Aβ∗56 impairs memory", "Abeta star 56", "56‑kDa oligomer", "A b 56", "a dodecamer"]:
            with self.subTest(text=text):
                self.assertEqual(triage(self.row(text))[0], "specific_claim_review")

    def test_criticism_takes_priority_over_entity_match(self):
        self.assertEqual(triage(self.row("Aβ*56 could not be detected", "Discusses the retraction or doubts"))[0],
                         "correction_or_criticism_review")

    def test_citers_and_retracted_rows_are_never_autoapproved(self):
        seed = self.row("", kind="", pmid="16541076")
        candidate = self.row("Aβ*56 causes memory loss")
        candidate["retracted"] = "True"
        for r in build_queue([candidate], [seed]):
            self.assertEqual(r["review_status"], "unreviewed")
            self.assertEqual(r["decision"], "")
            self.assertFalse(r["full_context_checked"])

    def test_missing_context_and_duplicate_ids(self):
        self.assertEqual(triage(self.row("", "Names Aβ*56"))[0], "missing_context_review")
        seed = self.row("", kind="", pmid="16541076")
        with self.assertRaises(ValueError):
            build_queue([self.row("x"), self.row("y")], [seed])


class PilotTests(unittest.TestCase):
    def test_context_is_not_in_baseline(self):
        self.assertNotIn("EVIDENCE", make_prompt("QUESTION", "2026-10-20"))
        self.assertIn("EVIDENCE", make_prompt("QUESTION", "2026-10-20", "EVIDENCE"))

    def test_empty_and_truncated_answers_are_invalid(self):
        self.assertFalse(valid_answer({"answer": "", "done_reason": "stop"}))
        self.assertFalse(valid_answer({"answer": "No", "done_reason": "length"}))
        self.assertTrue(valid_answer({"answer": "No", "done_reason": "stop"}))

    @patch("probe_models.requests.post")
    def test_generation_parameters_reach_ollama(self, post):
        response = Mock()
        response.json.return_value = {"response": "Answer", "done_reason": "stop"}
        post.return_value = response
        ask_ollama("Prompt", "gpt-oss:20b", seed=17, num_predict=4096, timeout=30)
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["json"]["options"]["seed"], 17)
        self.assertEqual(kwargs["json"]["options"]["num_predict"], 4096)
        self.assertEqual(kwargs["json"]["think"], "low")
        self.assertEqual(kwargs["timeout"], 30)


if __name__ == "__main__":
    unittest.main()
