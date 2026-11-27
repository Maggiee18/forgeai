# ForgeAI report: `corvane-it-assistant`

**Final agent:** v0 · **overall pass rate 90%** (dev 86%, holdout 100%) on 29 generated cases.
Models: factory `openai/gpt-oss-20b` · agent `qwen/qwen3.8-27b` · judge `openai/gpt-oss-120b` via `groq`.
Loop stopped because: optimizer found no applicable targeted fix.

## Deployment readiness

**READY FOR A SUPERVISED PILOT**

- 1 contradiction(s) between source documents must be resolved by their owners
- 2 requested topic(s) cannot be served from the documents

Completeness (fact recall on answered questions) 92% · citation precision 96% · answer relevance (embedding similarity, informational) 0.621 · grounded 100% · refusal accuracy 100%

## Scorecard per iteration

| Iter | Agent ver | Overall | Dev | Holdout | Fact recall | Refusal acc | Grounded | Retrieval hit | Ret.miss | Halluc. | Wrong ref. | Prompt def. | Kept? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | v0 | 90% | 86% | 100% | 88% | 100% | 100% | 100% | 0 | 0 | 1 | 2 | baseline |
| 1 | v1 | 86% | 81% | 100% | 85% | 100% | 100% | 100% | 0 | 0 | 1 | 3 | reverted (dev score did not improve) |

Holdout cases were never shown to the optimizer. A gap between dev and holdout is the overfitting signal.

## Flagged at requirements stage (groundability guard)
- 'ticket status' is requested by the brief but the documents do not support it. The agent will state that the documents do not cover it instead of answering.
- 'system outage' is requested by the brief but the documents do not support it. The agent will state that the documents do not cover it instead of answering.
- Conflicting information on Password change frequency: Information_Security_Policy.pdf says "Passwords must be changed every 90 days; the system prompts you 7 days before expiry." while Hardware_and_Software_Requests.pdf says "Passwords must then be changed every 60 days.". The agent will present both and suggest confirming with the document owner.

## Why the factory made these choices

- **Retrieval:** hybrid (weighted reciprocal rank fusion), embedding `wordllama`. Chunking: chunk size = 2.2 x median paragraph length (252 words), clamped to 100..260 so a chunk holds one policy section; overlap 20% so rules split across a boundary survive; top_k 4 keeps the context small for a small model; CSV rows are chunked one per row so each part is retrievable on its own.
- **Final retrieval parameters:** top_k 4, chunk size 260, min_score 0.15, keyword weight 1.0, embedding weight 1.0, 0 learned query expansions.
- **Tool csv_lookup attached** because: documents include CSV data that needs exact row lookups; evidence in the requirements: documents include CSV data.
- **System prompt:** the 'helpful' variant won the prompt tournament on a stratified dev subset.
- **Output contract:** JSON {answer, refused, citations}, validated by the runtime, so format failures are measured instead of hidden.

## Tool selection

- attached **csv_lookup**: documents include CSV data that needs exact row lookups (evidence: documents include CSV data)

## Prompt tournament

| Variant | Dev subset pass rate | System prompt chars | Tokens spent | Winner |
|---|---|---|---|---|
| strict | 50% | 1672 | 0 |  |
| helpful | 67% | 2021 | 0 | ✅ |

Winner chosen by pass rate on a stratified dev subset (no pairwise LLM verdicts, so no position bias); ties go to the shorter (cheaper) system prompt.

## Judge reliability

LLM judge self test on synthetic answers with known grades: **100%** agreement over 16 trials → llm judge enabled.

Deterministic checks (numbers, refusal flag, unsupported-number grounding, citations) decide first; the LLM judge can only add credit for a fact when it quotes the answer verbatim and every number in the fact is present.

## What still fails, and why

### prompt_defect (2)
The right passage was retrieved but the answer left out required facts, did not cite, or broke the JSON contract.
- `ans-04` [dev] How long does the security review take for new software not in the Company Portal?  
  → right passage retrieved but answer missed key facts ['pre approved']. Answer: _The security review for new software not in the Company Portal takes up to 5 business days. This applies to both paid and free/open-source tools, and the process is part of the Har_
- `amb-03` [dev] How long does it take to review new software that isn’t in the Company Portal?  
  → right passage retrieved but answer missed key facts ['pre approved']. Answer: _New software not in the Company Portal requires a security review by Information Security, which takes up to 5 business days. This applies to both paid and free/open-source tools._

### wrong_refusal (1)
The model refused when the answer was present, or answered something it should have declined. Small models are inconsistent about where the scope boundary is.
- `amb-02` [dev] When do we get new laptops at Corvane Analytics?  
  → the answer was in the retrieved passages but the agent refused. Answer: _The provided documents do not specify the schedule or criteria for when employees receive new laptops. Please contact the Service Desk for specific hardware replacement policies._

## Eval set provenance

29 cases generated from the documents (types: ambiguous=4, answerable=10, conflict=1, cross_doc=4, out_of_scope=5, tool=3, ungroundable=2).
10 candidate cases were rejected by validation (unverifiable facts, duplicates, out-of-scope questions the documents actually answer). See `eval_generation_log.json`.

## Known limitations of this run (read before trusting the number)

- The eval set is generated by the same small model family that builds the agent; questions it cannot imagine are not tested. Holdout reduces, but does not remove, this blind spot.
- Key facts are short string facts. An answer that is correct but phrased with different numbers formatting (e.g. 'two weeks' vs '14 days') can be marked wrong; check the failure list above for such cases.
- Out-of-scope cases are only as hard as the generator made them; adversarial prompts (jailbreaks) are not covered.
- Tool cases are computed exactly in Python, but only the first CSV is sampled.
- Budget used: 0 tokens across 0 model calls (237 served from cache), 0.6 s.

Note: later iterations were reverted, so the shipped definition is v0; every score above the iteration table is for that version.