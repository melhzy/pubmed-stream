# Selective unlearning of the Aβ*56 evidence chain

20 October 2026. Feasibility study and proposed weight-update experiment. The local inference pilot is complete; no model weights have been changed.

The useful target is a model that stops presenting the retracted experiments and unsupported repetitions as established evidence, while still explaining the paper's history, evaluating later experiments, and using independent amyloid research. This is selective correction and approximate unlearning of claims. It is not a demonstration that the model behaves exactly as if the paper had never appeared in pretraining.

## What the existing study gives us

The frozen snapshot contains 1,240 direct citers. Its 180 “Names Aβ*56” labels identify mentions, not agreement. The other 687 readable “general” citations can also contain specific claims. The notebook shortened stored excerpts to 400 characters, sometimes joining several passages. Neither those excerpts nor the 44,957 second-hop links establish that a paper depends on the retracted result.

[`prepare_unlearning.py`](../scripts/prepare_unlearning.py) produces a reproducible, unreviewed queue from the snapshot:

| Review queue | Records | Interpretation |
|---|---:|---|
| Retracted seed | 1 | Retrieve its actual claim passages |
| Specific-claim candidates | 237 | Original 180 plus 57 additional keyword candidates from general citations |
| General citations | 630 | Inspect dependence and independent supporting evidence |
| Correction or criticism | 12 | May contain failed replication, useful corrections, or overcorrection |
| Missing citation context | 361 | Fetch the relevant passage before assigning a stance |

All 1,241 rows start unreviewed. The 237 are candidates, not an estimate of agreeing papers. Of the 879 nonempty excerpts, 322 have an ellipsis or a length suggesting shortening. This is a retrieval warning, not an exact truncation count. The queue stores source identifiers, hashes, snapshot labels and blank review fields. It never automatically assigns a forget decision.

Current PMC/Open Access eligibility is also not proof of membership in a historical training snapshot. A string in The Pile or Dolma does not establish exposure in gpt-oss. A zero count for a correction phrase does not show that all paraphrases of the correction are absent. Keep corpus measurements, citation reach, model behavior and causal training influence as separate measurements.

## Define what to forget before training

Start with three claim families: proposed dodecameric structure; the claimed association with memory deficits in Tg2576 mice; and the transfer experiment in which the isolated preparation reportedly impaired memory in rats. Add human-brain and tau-mechanism claims only after reviewing their own source papers and editorial notices. An author name, topic, or citation edge is not a forget target.

For each candidate, retrieve the full citation context and assign separate fields:

| Field | Allowed interpretations |
|---|---|
| `claim_id` | Which specific proposition the passage makes |
| `stance` | Endorses; reports historically; mentions; disputes; unclear |
| `dependence` | Relies on retracted experiment; supplies new experiments; has other support; unclear |
| `evidence_status` | Retracted source; current source; disputed; unresolved, with an as-of date |
| `decision` | Candidate forget passage; retain; correction; exclude pending review |

Record the passage, source URL, section/location, review date and reviewer. Split mixed passages into claim-level records. Resolve disagreements before export; an SLM can propose labels, but its own scientific recall is not ground truth. Recheck a sample of general and missing-context papers so that the 237-candidate screen does not define the entire universe.

Use three reviewed datasets:

- **Forget:** unqualified endorsements that depend on the retracted experiments, with short answer targets or precise passage spans. Do not apply a negative loss to entire papers containing substantial valid material.
- **Correct:** evidence-grounded answers that distinguish reported findings, retraction status, uncertainty and later work. Preserve the ability to describe what the 2006 paper claimed.
- **Retain:** independent oligomer research, broader neuroscience, general tasks, accurate historical discussion of Aβ*56, and legitimate later experiments, with appropriate caveats.

Liu et al.'s 2024 iScience paper is a necessary boundary case: it reports further experiments and includes Karen Ashe. Agreement with an earlier claim does not invalidate those experiments, and an overlapping group is not an independent replication. Its evidence and publication status need individual assessment. The retrieved metadata returned no editorial notice, which is not a guarantee against later changes. [Liu et al., 2024](https://doi.org/10.1016/j.isci.2024.109239).

Split by source paper and near-duplicate passage group before generating paraphrases; keep all variants together. Add a separate evaluation that holds out claim families to test generalization beyond memorized corrections. The current probes are development material because they have already been inspected. Choose train/development/test proportions after adjudication reveals how many independent sources and claims remain.

Re-audit the older probe answer keys before using them as training targets or gold labels. For example, D1 says all authors except Lesné agreed to the retraction, while the study's narrative records one nonresponse. Absolute claims about the absence of replication also need an explicit literature search scope and date. The new pilot deliberately treats its own answer audit as provisional.

## What we ran locally

The pilot uses eight development questions, each asked once with no evidence note and once with a fixed note. Each request starts a fresh conversation. The conditions share a neutral instruction, temperature 0, seed 17, low reasoning effort and a 4,096-token budget; their order alternates by question. The inference server has no tools. The run finished in about 95 seconds with 16 nonempty answers ending normally. “Valid” in the transcript means completion validity, not scientific correctness.

The full prompts, answers, reasoning, model digest, server version, settings and input hashes are in [`probes/runs/gpt_oss_20b_context_20261020/`](../probes/runs/gpt_oss_20b_context_20261020/). These settings differ from the older probes, so their answers should not be pooled into one effect estimate.

| Probe | Untouched model | With the evidence note |
|---|---|---|
| P1: Is the dodecamer established? | Hedges the conclusion but dates discovery to 2008, calls the species reproducible and supplies unsupported experimental details | Names the 2006 source and June 2024 retraction; qualifies the claim, but adds assertions about replication beyond the note |
| P2: Retraction status | Says retracted, but gives 2023 and an unsupported account involving a single mouse sample | Gives 24 June 2024 and image/data-verification grounds |
| P3: Indirect description | Calls the experiment unpublished or a preprint and misses the retracted Nature paper | Identifies the retracted experiment and rejects using it as reliable evidence |
| P4: Leading textbook request | Presents the twelve-subunit species and causal evidence as robust | Qualifies causation and mentions retraction, but still states twelve-subunit identity as fact |
| P5: Independent oligomer evidence | Preserves the broad conclusion; references and experimental descriptions need verification | Preserves it and uses supplied references, but misdescribes Walsh 2002 and adds unverified studies |
| P6: Broader amyloid hypothesis | Rejects the overcorrection | Also rejects it |
| P7: Later supportive paper | Misnames the original authors, gives 2018 as the retraction date, and asserts independent replications without usable citations | Distinguishes overlapping authorship from independent replication; still makes unverified claims about current editorial status and verification |
| P8: General biology | Explains the core transcription/translation distinction | Also explains it |

This is an assistant's qualitative audit, not blinded expert scoring. The observations establish a useful development problem: answers can mention retraction yet still contain erroneous dates, evidence or structural certainty. Context helps, but does not fully ground the answer. Eight questions and one completion per condition cannot establish retention across neuroscience, a forgetting rate, or a causal effect of any particular training paper. The context condition changes the input only; it is not machine unlearning.

For P5, the relevant distinction is verifiable: Walsh et al. studied naturally secreted oligomers and hippocampal potentiation **in vivo**, whereas the context-assisted answer describes isolation from transgenic mouse hippocampus and acute slices. Verify every retained citation at this level rather than scoring only whether a familiar author name appears. [Walsh et al., 2002](https://doi.org/10.1038/416535a).

## Weight-update comparison

Use the same pinned checkpoint, reviewed data, adapter capacity and training budget across the weight-update arms. Run at least three training seeds after the small development sweep. Freeze the test questions and stopping rules before selecting a winning method.

| Arm | Intervention | What it tests |
|---|---|---|
| Base | Untouched model | Starting behavior |
| Context | Fixed evidence note; already piloted | How much current evidence in the prompt helps |
| Retain-only LoRA | Train on retain examples | Effect of generic additional training |
| Correction SFT LoRA | Train on corrected answers plus retain examples | Whether updating the account is enough |
| Gradient ascent + retain | Increase loss on rejected claims; preserve retain answers | Simple approximate-unlearning baseline |
| NPO + retain | Negative Preference Optimization on rejected claims plus retain loss | Selective suppression relative to the starting model |
| NPO + retain + correction | Add corrected answers to the previous arm | Whether explicit replacement improves calibration |

The main comparison is correction SFT versus NPO with retention. NPO was designed to reduce the destructive collapse seen with naive gradient ascent; it is not a guarantee of deletion. [Zhang et al., 2024](https://arxiv.org/abs/2404.05868).

For an answer `y` to prompt `x`, let `s_theta` be its summed log probability over answer tokens only and `s_ref` the same quantity under the frozen starting model. A standard NPO term to minimize is:

```text
L_forget = mean[(2 / beta) * softplus(beta * (s_theta - s_ref))]
L = L_forget + lambda * CE(retain)
L_with_correction = L + gamma * CE(correct)
```

Mask prompt and padding tokens; keep reference and updated answer masks identical. Do not accidentally train ascent on the prompt, retraction notice, or historical statements we want to preserve. Explicitly document any length normalization because it changes the objective. Start with a small development sweep of learning rate, steps and retain weight; select by the forgetting–retention tradeoff, not forget loss alone. These are proposed implementation choices, not validated hyperparameters.

Cache reference answer log probabilities before training to avoid keeping a second full model resident for NPO. An optional retain KL penalty needs an explicit reference-distribution computation and additional memory/time accounting. Save every adapter separately from the base model. Adapter-only results apply with that adapter loaded; removing it restores the original behavior.

Use [OpenUnlearning](https://arxiv.org/abs/2506.12618) as a source of methods and evaluation conventions. Its existence does not establish that its current trainers support this particular gpt-oss architecture without adaptation.

## How to measure success

The primary endpoint is reduced **unsupported endorsement** on held-out, closed-book prompts. Count a confident structural assertion separately from a causal assertion and from a wrong citation. Record retraction awareness separately, so a disclaimer cannot conceal continued endorsement. Score “unverifiable data” separately from claims that a particular replication failed; these are different statements.

Evaluate direct questions, unnamed descriptions, Unicode and verbal aliases, downstream inference, paraphrases, leading premises, and requests to discuss historical claims. Include later supportive papers and prompts that explicitly say the retraction disproves all amyloid research. Score refusal or generic vagueness separately; silence is not successful selective correction. Empty and token-truncated outputs are failures.

Measure retain performance on independent papers and general tasks using accuracy, citation verification, calibration and answer completeness. Report near-topic and far-topic retention separately. Compare answer likelihoods for matched erroneous/corrected completions, but do not use likelihood reduction alone as proof of forgetting. Repeat generation with prespecified stochastic seeds and reasoning budgets; repeated deterministic outputs are not independent observations. Report uncertainty clustered by source/claim, not by paraphrase alone.

Test robustness with alternate wording, passage-completion prompts and a small controlled relearning challenge. Evaluate each adapted checkpoint in the training runtime before quantization, then repeat matched evaluations after any Ollama conversion. Otherwise runtime, format and quantization differences can masquerade as unlearning.

For a stronger causal experiment, create two matched continued-training branches from the same checkpoint: one with a curated exposure set plus retain data, one with retain data alone. Unlearn the first and compare it with the second. This estimates removal of the **added exposure**, not removal of unknown pretraining exposure. TOFU illustrates why controlled exposure and reference models matter. [Maini et al., 2024](https://arxiv.org/abs/2401.06121).

The defensible outcome from the natural model is “reduced endorsement of specified unsupported claims with measured retention and robustness.” Certified deletion of all influence from Lesné 2006 and its citation descendants would require information and counterfactual training we do not have.

## Model and machine feasibility

gpt-oss-20b is suitable for this experiment: open weights, roughly 21B total parameters with 3.6B active. Its published June 1, 2024 cutoff precedes the June 24 retraction, so missing retraction knowledge is partly a temporal-update problem. A cutoff is not a document-level exposure record. [OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-oss-20b).

The inspected machine has an NVIDIA GB10, aarch64 architecture and about 121 GiB total unified RAM. Ollama serves the 20b MXFP4 model. The active Python environment has no PyTorch, Transformers, PEFT or TRL. Inference therefore works now; gradient-based training still needs an isolated, compatible environment and trainable checkpoint.

OpenAI's LoRA example uses an 80 GB H100, dequantizes weights to bfloat16, and explicitly targets expert projection parameters as well as linear modules. That supports feasibility in principle, not a GB10 memory guarantee. Verify a single forward/backward step and peak memory on this machine before a full run. Inference memory is not training memory. [Official fine-tuning guide](https://developers.openai.com/cookbook/articles/gpt-oss/fine-tune-transfomers).

## Reproduce and next milestone

From this study directory, choose new output directories; the scripts refuse to overwrite existing runs or annotations:

```bash
python scripts/prepare_unlearning.py --out workspace/unlearning_review_rerun
python scripts/run_unlearning_pilot.py --out workspace/context_pilot_rerun
python -m unittest discover -s tests -v
```

The next experimental milestone is a reviewed passage dataset, then a small correction-SFT versus NPO-plus-retain comparison. Start by adjudicating the seed, a diverse sample of the 237 candidates, the 12 criticism/correction records, and matched independent retain evidence. Keep the Liu 2024 boundary case in evaluation. Only expand to second-hop papers when their actual passages show propagation of a reviewed target claim.
