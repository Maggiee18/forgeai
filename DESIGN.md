# ForgeAI design notes

The hard part of this assignment is not any single stage. It is that every stage runs on a small,
unreliable model, and each stage's output becomes the next stage's input. A factory that trusts its own
pipeline will happily ship an agent that passes a test set it wrote for itself. So the design principle is:

> **The model proposes, deterministic code verifies.** Wherever a small model makes a claim that matters
> (this topic is supported, this fact is in the passage, this tool is needed, this answer states that fact),
> the factory checks the claim against the documents or the answer text before using it.

```
brief + docs
   │
   ▼
[1] Intake ──► ≤5 questions ──► requester / answers file / recorded assumption
   │
   ▼
[2] Groundability guard ── LLM verdict + verified evidence quote per topic ──► flags, ungroundable topics
   │                                                         (optional human checkpoint: approve / edit)
   ▼
[3] Generator ── tools: LLM proposal ∩ deterministic evidence
   │           ── system prompt in sections (role/scope/grounding/refusal/tools/style/contract)
   │           ── retrieval params from document statistics, hard guardrails re-injected
   │           ── 3 prompt variants for the tournament
   ▼
[4] Eval generator ── answerable / cross-doc / ambiguous / out-of-scope / ungroundable / tool cases
   │                ── every case validated, rejects logged, dev / holdout split
   ▼
[5] Judge self test ── known-good, corrupted, padded answers; LLM judge disabled if < 80% agreement
   ▼
[5b] Tournament ── candidate prompts scored on a stratified dev subset; best pass rate wins
   ▼
[6] Loop (≤3): run evals → critic classifies each failure → optimizer applies ONE targeted fix per
   category → re-run → keep if dev improves, else revert and never retry that fix; early stop on budget
   or diminishing returns
   ▼
[7] Report: final definition, per-iteration scorecard, iteration log, what still fails and why
```

## Stage by stage

**1. Intake.** The interviewer sees the brief and a compact inventory of the folder (section headings,
CSV columns and sample rows), so its questions are about real ambiguities, not generic ones. The cap of
5 is enforced in code, not left to the prompt. Answers come from the terminal, from a recorded answers
file, or, when unattended, from the interviewer's own suggested default, which is labelled `assumed`
in `requirements.md` so a reviewer can see exactly which decisions nobody made.

**2. Groundability guard.** For each must-answer topic: hybrid retrieval finds the best passages, the model says
supported / partial / unsupported **and must quote the sentence that proves it**. If the quote does not
occur in the passages, the claim is overruled to unsupported. Needs for live data ("live freight rates")
are checked against the tool registry, not the documents, and computations over document data ("order total
with discount", "delivery date from lead time") count as supported when a registry tool can perform them.

*Contradictions across documents.* Candidate pairs are passages from different documents ranked by embedding
similarity, shared heading words and word overlap, kept only if they state different values of the same kind
(INR vs INR, days vs days). The decider model (configurable as `guard_model`) must name who each rule applies to;
code rejects pairs whose scopes do not overlap (two suppliers' different terms are not a contradiction), checks
both quotes exist verbatim and carry different values, and records the second model's vote beside every accepted
conflict. Every candidate checked, accepted or rejected, is saved in `requirements.json` (`conflict_checks`).
In our runs gpt-oss-20b called six pairs of supplier terms "conflicts" and qwen correctly rejected them, while
qwen alone caught the planted gift limit contradiction; that is why qwen decides. Unsupported topics are (a) flagged in the
requirements, (b) written into the agent's refusal section as hard rules after generation, so a weak
generator cannot drop them, and (c) turned into refusal test cases. The gap is never silently papered over.

**3. Generator.** Output is a declarative `AgentDefinition` JSON: prompt sections, retrieval parameters,
tools, output contract, refusal message, docs folder. Prompt sections are kept separate so the optimizer
can edit one section without regenerating the agent. Tool selection is the intersection of what the model
proposes and what the requirements evidence supports (keywords per tool, CSV presence for `csv_lookup`,
two independent signals for `calculator`). The mock model in the test suite deliberately proposes the
weather tool for every brief, and the tests assert it is rejected.

**4. Eval generator.** Cases are generated from document passages, then validated:
- answerable: each key fact must be found in the source passage (all numbers exactly); unverifiable facts
  are dropped, and a case with none left is rejected as a possible hallucination. Facts that merely restate the
  question are dropped, long facts are shortened around their numbers, and a second model call checks that each
  remaining fact is actually required to answer *exactly* the question asked (over-specified facts turned
  correct answers into false failures in our first real runs);
- cross-doc: needs a verified fact from each of two different documents;
- ambiguous: informal rewrites of answerable cases; rejected if too close to the original or if they
  change a number;
- out-of-scope: rejected if the guard finds the documents actually answer it;
- tool: built in Python straight from CSV rows, so the expected total is computed exactly, never by a model.
Each case keeps its origin (chunk ids), and ~30% are held out. Ambiguous rewrites follow their source case
into the same split, so a held-out fact never leaks into dev.

**5. Judge.** Four checks per case: refusal correctness, fact recall, grounding (every number in the answer
must appear in the retrieved passages, tool results or the question), and citation of an expected source.
Known LLM-judge failure modes and the defence for each:

| Failure mode | Defence |
|---|---|
| Position bias | No pairwise judging anywhere. Answers are graded against fixed facts; the tournament compares pass rates. Facts are shuffled before the LLM sees them. |
| Self preference | Deterministic string/number matching decides first; the LLM only adds credit for facts the matcher missed. The judge model is configurable separately (`judge_model`) so it can be a different family from the agent. |
| Unsupported claims | Every number in an answer must appear in the retrieved passages (bodies and section headings), tool results or the question; labels such as "Section 5" are exempt. Any other number fails grounding and is classified as a hallucination. |
| Verbosity bias | Binary per-fact verdicts. A "stated" verdict counts only if the judge's quote really occurs in the answer and every number of the fact is present. Padding cannot earn credit, and any unsupported number in a long answer fails grounding. |
| Leniency / judge hallucination | Self test before every run on synthetic answers with known grades (paraphrased gold, corrupted numbers, long but empty, long and correct). Below 80% agreement the LLM judge is switched off and the report says so. |

*Suspected test defects.* When the LLM judge reads an answer as correct but a strict rule rejected it, the case
stays a failure (the score is not changed) but is flagged as a suspected test defect, listed separately in the
report, and never sent to the optimizer: changing the agent cannot fix a wrong test, it can only overfit to it.

**6. Critic and optimizer.** The critic is deterministic, using evidence the runtime recorded:

| Category | Rule | Targeted fix |
|---|---|---|
| retrieval_miss | expected source not in the retrieved passages | learn query expansions (LLM proposes user→document terms; terms must exist in the corpus vocabulary), then grid search top_k / chunk size / min_score scored by how many expected facts land in retrieved text. No LLM calls in the scoring. |
| hallucination | answer has numbers found in no passage/tool result, or answers a must-refuse question with specifics | patch the GROUNDING section only |
| wrong_refusal | refused although the passage was retrieved, or answered a must-refuse question | patch the REFUSAL section only, with over- and under-refusal described separately |
| prompt_defect | right passage retrieved, answer incomplete, uncited, or broke the JSON contract | patch the STYLE section only |

Guards on the loop: only dev failures are shown to the optimizer; patches that quote eval questions are
rejected (7-gram overlap check); hard guardrails are re-applied after every patch; an iteration is kept only
if the dev pass rate improves, otherwise it is reverted and that category's fix is not retried; the loop
stops early on budget exhaustion, on a gain below `min_gain`, or after two non-improving iterations. Every
change logs what changed, why, which cases it targeted, which it actually fixed, what it broke, and the
dev/holdout score before and after.

**7. Reporting.** `REPORT.md` leads with the number and immediately explains it: per-iteration scorecard
with dev vs holdout, guard flags, tool decisions (kept and rejected with reasons), tournament table, judge
reliability, every remaining failure with its category and diagnosis, eval provenance including how many
generated cases were rejected, and the limitations of the measurement itself.

## Regression mode
`forgeai regress` answers "the documents changed; is the agent still right?" It changes exactly one thing: the shipped
agent definition is replayed unchanged (same prompt, tools, retrieval settings) on the new documents, against the
original eval set. It also diffs old and new documents sentence by sentence and marks which changes an existing test
covers. A broken test is labelled a *stale test* when its expected facts are gone from the new documents, otherwise an
*agent regression*. Changes no test covers are listed separately, because a passing replay says nothing about them;
the remedy is to rebuild the eval set on the new documents.

## Runtime

`forgeai chat <definition>` (or the web Playground) loads any definition. Per question: hybrid retrieval
→ up to two tool planning rounds (look up, then compute) → answer in a JSON contract
`{answer, refused, citations}`. The runtime validates the contract and drops invented citations, so format
defects are visible to the judge instead of being silently tolerated.

## Retrieval: hybrid BM25 + embeddings
BM25 is exact on part numbers, amounts and policy terms; embeddings catch paraphrases ("vacation" for "annual
leave"). The two rankings are fused with weighted reciprocal rank fusion, which combines ranks rather than raw
scores, so nothing needs calibrating. The default embedding model is WordLlama, a 16 MB static model shipped inside
its pip package, so retrieval works offline and on free hosting tiers; `fastembed:BAAI/bge-small-en-v1.5` is one
config line away where Hugging Face is reachable, and the definition records which provider actually loaded.
`scripts/retrieval_benchmark.py` measures it: on hand-written paraphrased questions hybrid found the right passage
7 of 10 times against 5 of 10 for BM25 alone, with no loss on questions using the documents' own words.

## Model backends
`ollama` (fully local), `groq` (hosted small open models), `openai` (any OpenAI compatible server, such as
vLLM or LM Studio), `mock` (deterministic, offline tests). Every call goes through one token/time budget and
an on-disk cache, so re-running a completed run is free and reproducible. Rate limits are handled visibly: short
per-minute limits are retried with capped waits, and a daily quota is waited out with a clear line in the run log,
never silently. Roles (factory, agent, judge, contradiction decider) can each use a different model.
