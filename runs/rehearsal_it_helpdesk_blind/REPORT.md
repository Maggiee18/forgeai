# ForgeAI report: `corvane-it-assistant`

**Final agent:** v0 · **overall pass rate 80%** (dev 72%, holdout 100%) on 25 generated cases.
Models: factory `openai/gpt-oss-20b` · agent `qwen/qwen3.8-27b` · judge `openai/gpt-oss-120b` via `groq`.
Loop stopped because: optimizer found no applicable targeted fix.

## Deployment readiness

**PILOT ONLY WITH HUMAN REVIEW OF ANSWERS**

- refusal accuracy 80% is below 90%

Completeness (fact recall on answered questions) 86% · citation precision 98% · answer relevance (embedding similarity, informational) 0.622 · grounded 100% · refusal accuracy 80%

## Scorecard per iteration

| Iter | Agent ver | Overall | Dev | Holdout | Fact recall | Refusal acc | Grounded | Retrieval hit | Ret.miss | Halluc. | Wrong ref. | Prompt def. | Kept? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | v0 | 80% | 72% | 100% | 86% | 80% | 100% | 100% | 0 | 0 | 1 | 4 | baseline |
| 1 | v1 | 80% | 72% | 100% | 86% | 80% | 100% | 100% | 0 | 0 | 1 | 4 | reverted (dev score did not improve) |

Holdout cases were never shown to the optimizer. A gap between dev and holdout is the overfitting signal.

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
| strict | 50% | 1670 | 10101 |  |
| helpful | 67% | 1737 | 6584 | ✅ |

Winner chosen by pass rate on a stratified dev subset (no pairwise LLM verdicts, so no position bias); ties go to the shorter (cheaper) system prompt.

## Judge reliability

LLM judge self test on synthetic answers with known grades: **100%** agreement over 16 trials → llm judge enabled.

Deterministic checks (numbers, refusal flag, unsupported-number grounding, citations) decide first; the LLM judge can only add credit for a fact when it quotes the answer verbatim and every number in the fact is present.

## What still fails, and why

### prompt_defect (4)
The right passage was retrieved but the answer left out required facts, did not cite, or broke the JSON contract.
- `ans-04` [dev] How long does a security review for new software take before it can be installed?  
  → right passage retrieved but answer missed key facts ['Licences unused for 60 days are reclaimed automatically']. Answer: _A security review for new software not in the Company Portal takes up to 5 business days._
- `cro-01` [dev] How should employees install software not listed in the Company Portal, and what approvals are required?  
  → right passage retrieved but answer missed key facts ['Software Request Procedure (IT-PRC-03)']. Answer: _Employees must request software not listed in the Company Portal through the IT Self Service Portal under 'Request Software,' including the catalogue item code, quantity, and busin_
- `cro-04` [dev] If a major incident affects 30 users, how often will the Service Desk post updates and what should you do with your laptop when leaving your desk?  
  → right passage retrieved but answer missed key facts ['For outages affecting more than 25 users posts updates on the IT Status page every', 'Laptops lock automatically after 5 minutes of inactivity']. Answer: _For a major incident affecting 30 users, the Service Desk will post updates on the IT Status page every 30 minutes. The provided excerpts do not contain information regarding what_
- `amb-03` [dev] How long till a new app gets a security check before we can use it?  
  → right passage retrieved but answer missed key facts ['Licences unused for 60 days are reclaimed automatically']. Answer: _New software not in the Company Portal requires a security review by Information Security, which takes up to 5 business days._

### wrong_refusal (1)
The model refused when the answer was present, or answered something it should have declined. Small models are inconsistent about where the scope boundary is.
- `out-04` [dev] Where can I find the latest company policy on remote work?  
  → should have refused (out of scope or not covered) but answered. Answer: _The latest company policy on remote work is detailed in Section 6 of the Information Security Policy, which covers remote work and network requirements._

## Eval set provenance

25 cases generated from the documents (types: ambiguous=3, answerable=10, cross_doc=4, out_of_scope=5, tool=3).
16 candidate cases were rejected by validation (unverifiable facts, duplicates, out-of-scope questions the documents actually answer). See `eval_generation_log.json`.

## Known limitations of this run (read before trusting the number)

- The eval set is generated by the same small model family that builds the agent; questions it cannot imagine are not tested. Holdout reduces, but does not remove, this blind spot.
- Key facts are short string facts. An answer that is correct but phrased with different numbers formatting (e.g. 'two weeks' vs '14 days') can be marked wrong; check the failure list above for such cases.
- Out-of-scope cases are only as hard as the generator made them; adversarial prompts (jailbreaks) are not covered.
- Tool cases are computed exactly in Python, but only the first CSV is sampled.
- Budget used: 120339 tokens across 177 model calls (50 served from cache), 709.9 s.

Note: later iterations were reverted, so the shipped definition is v0; every score above the iteration table is for that version.