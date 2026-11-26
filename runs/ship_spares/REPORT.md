# ForgeAI report: `spareproc-assistant`

**Final agent:** v0 · **overall pass rate 93%** (dev 89%, holdout 100%) on 27 generated cases.
Models: factory `openai/gpt-oss-20b` · agent `qwen/qwen3.8-27b` · judge `openai/gpt-oss-120b` via `groq`.
Loop stopped because: optimizer found no applicable targeted fix.

## Deployment readiness

**READY FOR A SUPERVISED PILOT**

- 1 requested topic(s) cannot be served from the documents

Completeness (fact recall on answered questions) 98% · citation precision 82% · answer relevance (embedding similarity, informational) 0.721 · grounded 100% · refusal accuracy 100%

## Scorecard per iteration

| Iter | Agent ver | Overall | Dev | Holdout | Fact recall | Refusal acc | Grounded | Retrieval hit | Ret.miss | Halluc. | Wrong ref. | Prompt def. | Kept? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | v0 | 93% | 89% | 100% | 93% | 100% | 100% | 100% | 0 | 0 | 1 | 1 | baseline |
| 1 | v1 | 93% | 89% | 100% | 93% | 100% | 100% | 100% | 0 | 0 | 1 | 1 | reverted (dev score did not improve) |

Holdout cases were never shown to the optimizer. A gap between dev and holdout is the overfitting signal.

## Flagged at requirements stage (groundability guard)
- 'freight quote' is requested by the brief but the documents do not support it. The agent will state that the documents do not cover it instead of answering.

## Why the factory made these choices

- **Retrieval:** hybrid (weighted reciprocal rank fusion), embedding `wordllama`. Chunking: chunk size = 2.2 x median paragraph length (278 words), clamped to 100..260 so a chunk holds one policy section; overlap 20% so rules split across a boundary survive; top_k 4 keeps the context small for a small model; CSV rows are chunked one per row so each part is retrievable on its own.
- **Final retrieval parameters:** top_k 4, chunk size 260, min_score 0.15, keyword weight 1.0, embedding weight 1.0, 0 learned query expansions.
- **Tool csv_lookup attached** because: lookup part in catalogue; evidence in the requirements: catalogue, catalog, lookup, documents include CSV data.
- **Tool calculator attached** because: calculate price with discount and add freight to total; evidence in the requirements: total, cost, calculate, compute, discount, price, estimate.
- **Tool current_date attached** because: compute delivery date from today; evidence in the requirements: today, date, lead time, delivery date.
- **System prompt:** the 'helpful' variant won the prompt tournament on a stratified dev subset.
- **Output contract:** JSON {answer, refused, citations}, validated by the runtime, so format failures are measured instead of hidden.

## Tool selection

- attached **csv_lookup**: lookup part in catalogue (evidence: catalogue, catalog, lookup, documents include CSV data)
- attached **calculator**: calculate price with discount and add freight to total (evidence: total, cost, calculate, compute, discount, price, estimate)
- attached **current_date**: compute delivery date from today (evidence: today, date, lead time, delivery date)

## Prompt tournament

| Variant | Dev subset pass rate | System prompt chars | Tokens spent | Winner |
|---|---|---|---|---|
| strict | 100% | 1832 | 1822 |  |
| helpful | 100% | 1808 | 0 | ✅ |

Winner chosen by pass rate on a stratified dev subset (no pairwise LLM verdicts, so no position bias); ties go to the shorter (cheaper) system prompt.

## Judge reliability

LLM judge self test on synthetic answers with known grades: **100%** agreement over 16 trials → llm judge enabled.

Deterministic checks (numbers, refusal flag, unsupported-number grounding, citations) decide first; the LLM judge can only add credit for a fact when it quotes the answer verbatim and every number in the fact is present.

## What still fails, and why

### prompt_defect (1)
The right passage was retrieved but the answer left out required facts, did not cite, or broke the JSON contract.
- `cro-04` [dev] When ordering a spare part costing $12,000 from a non‑OEM supplier, how many quotations are required and what is the restocking fee if the part is returned unused?  
  → right passage retrieved but answer missed key facts ['Orders above USD 10,000 require three quotations'] [suspected test defect: the judge model reads the answer as correct, but a strict rule (exact numbers or quote) rejected it; not sent to the optimizer]. Answer: _For an order of $12,000, three quotations are required unless the part is available only from the original equipment maker, in which case a single source is permitted with a record_

### wrong_refusal (1)
The model refused when the answer was present, or answered something it should have declined. Small models are inconsistent about where the scope boundary is.
- `amb-03` [dev] How many quotes do we need for a $12k purchase order?  
  → the answer was in the retrieved passages but the agent refused. Answer: _The provided excerpts do not specify the number of quotes required for a purchase order._

## Failures that may be test defects (still counted as failures)

1 failing case(s) were read as correct by the judge model, but rejected by a strict deterministic rule. They stay in the score; a human should check them. They were not sent to the optimizer.

- `cro-04` When ordering a spare part costing $12,000 from a non‑OEM supplier, how many quotations are required and what is the restocking fee if the part is returned unused?  
  missing per strict rule: ['Orders above USD 10,000 require three quotations']

## Eval set provenance

27 cases generated from the documents (types: ambiguous=4, answerable=10, cross_doc=4, out_of_scope=5, tool=3, ungroundable=1).
13 candidate cases were rejected by validation (unverifiable facts, duplicates, out-of-scope questions the documents actually answer). See `eval_generation_log.json`.

## Known limitations of this run (read before trusting the number)

- The eval set is generated by the same small model family that builds the agent; questions it cannot imagine are not tested. Holdout reduces, but does not remove, this blind spot.
- Key facts are short string facts. An answer that is correct but phrased with different numbers formatting (e.g. 'two weeks' vs '14 days') can be marked wrong; check the failure list above for such cases.
- Out-of-scope cases are only as hard as the generator made them; adversarial prompts (jailbreaks) are not covered.
- Tool cases are computed exactly in Python, but only the first CSV is sampled.
- Budget used: 35042 tokens across 41 model calls (185 served from cache), 229.5 s.

Note: later iterations were reverted, so the shipped definition is v0; every score above the iteration table is for that version.