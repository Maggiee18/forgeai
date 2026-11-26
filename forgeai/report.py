"""Stage 7: honest reporting. Writes the per-iteration scorecard and a report that states what still
fails and why, including the factory's own blind spots."""
from __future__ import annotations

import json
from pathlib import Path

from .schemas import AgentDefinition, CaseResult, EvalCase, Requirements


def pct(x) -> str:
    return "n/a" if x is None else f"{x*100:.0f}%"


def scorecard_md(iterations: list[dict]) -> str:
    L = ["| Iter | Agent ver | Overall | Dev | Holdout | Fact recall | Refusal acc | Grounded | Retrieval hit | Ret.miss | Halluc. | Wrong ref. | Prompt def. | Kept? |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for it in iterations:
        s, c = it["scorecard"], it["scorecard"]["failures_by_category"]
        L.append(
            f"| {it['iteration']} | v{it['agent_version']} | {pct(s['pass_rate'])} | {pct(s['dev_pass_rate'])} | {pct(s['holdout_pass_rate'])} | "
            f"{pct(s['answer_fact_recall'])} | {pct(s['refusal_accuracy'])} | {pct(s['grounded_rate'])} | {pct(s['retrieval_hit_rate'])} | "
            f"{c['retrieval_miss']} | {c['hallucination']} | {c['wrong_refusal']} | {c['prompt_defect']} | {it.get('decision','')} |"
        )
    return "\n".join(L)


def iteration_log_md(log: list[dict]) -> str:
    L = ["# Critic → optimizer iteration log", ""]
    for it in log:
        L.append(f"## Iteration {it['iteration']}  (agent v{it['from_version']} → v{it['to_version']})")
        L.append(f"Dev pass rate before: **{pct(it['dev_before'])}**, after: **{pct(it.get('dev_after'))}** · holdout before {pct(it.get('holdout_before'))}, after {pct(it.get('holdout_after'))} · decision: **{it.get('decision','')}**")
        L.append("")
        L.append(f"Failures going in, dev and holdout together (only dev failures reach the optimizer): {it['failures_in']}")
        for ch in it["changes"]:
            L.append(f"- **{ch['category']} → {ch['target']}**: {ch.get('rationale') or ch.get('skipped','')}")
            if ch.get("skipped"):
                L.append(f"  - skipped: {ch['skipped']}")
            if ch.get("addressed_cases"):
                L.append(f"  - addressed cases: {', '.join(ch['addressed_cases'])}")
            if ch.get("fixed_cases") is not None:
                L.append(f"  - actually fixed: {', '.join(ch['fixed_cases']) or 'none'}; newly broken anywhere: {', '.join(it.get('newly_broken', [])) or 'none'}")
            if ch["target"] == "retrieval":
                L.append(f"  - before: `{ch['before']}` after: `{ch['after']}`")
                if ch.get("learned_expansions"):
                    L.append(f"  - learned query expansions: `{ch['learned_expansions']}`")
            elif ch.get("after"):
                L.append("  - new section text:")
                L.append("    ```")
                L += ["    " + l for l in ch["after"].splitlines()]
                L.append("    ```")
        if it.get("stop_reason"):
            L.append(f"\nStopped: {it['stop_reason']}")
        L.append("")
    return "\n".join(L)


def readiness(sc: dict, req: Requirements, judge_selftest: dict) -> tuple[str, list[str]]:
    """Rule based verdict. Thresholds are deliberately strict for a document grounded assistant:
    hallucinations and failures to refuse matter more than missed facts."""
    hold = sc.get("holdout_pass_rate")
    hold = sc.get("pass_rate") if hold is None else hold
    hall = sc["failures_by_category"]["hallucination"]
    ref = sc.get("refusal_accuracy")
    reasons = []
    if hall:
        reasons.append(f"{hall} hallucination failure(s): the agent stated numbers that no source supports")
    if ref is not None and ref < 0.9:
        reasons.append(f"refusal accuracy {pct(ref)} is below 90%")
    if hold is not None and hold < 0.8:
        reasons.append(f"holdout pass rate {pct(hold)} is below 80%")
    if not judge_selftest.get("ran") or (judge_selftest.get("accuracy", 1) < 0.8):
        reasons.append("LLM judge was not validated (self test skipped or failed); scores rest on deterministic checks only")
    if req.conflicts:
        reasons.append(f"{len(req.conflicts)} contradiction(s) between source documents must be resolved by their owners")
    if req.ungroundable_topics:
        reasons.append(f"{len(req.ungroundable_topics)} requested topic(s) cannot be served from the documents")
    if hall == 0 and (ref or 0) >= 0.9 and (hold or 0) >= 0.8:
        verdict = "READY FOR A SUPERVISED PILOT"
    elif hall == 0 and (ref or 0) >= 0.8 and (hold or 0) >= 0.6:
        verdict = "PILOT ONLY WITH HUMAN REVIEW OF ANSWERS"
    else:
        verdict = "NOT READY FOR USERS"
    return verdict, reasons


def why_section(defn: AgentDefinition, gen_meta: dict, tournament: dict | None) -> list[str]:
    r = defn.retrieval
    emb = r.get("embedding", {})
    L = ["## Why the factory made these choices", ""]
    L.append(f"- **Retrieval:** {r.get('strategy')} ({r.get('fusion', 'keyword only')}), embedding `{emb.get('provider')}`"
             f"{' (' + emb['note'] + ')' if emb.get('note') else ''}. Chunking: {r.get('derived_from', '')}.")
    L.append(f"- **Final retrieval parameters:** top_k {r.get('top_k')}, chunk size {r.get('chunk_size')}, min_score {r.get('min_score')}, "
             f"keyword weight {r.get('bm25_weight')}, embedding weight {r.get('dense_weight')}, {len(r.get('query_expansion') or {})} learned query expansions.")
    for t in gen_meta.get("tools_kept", []):
        L.append(f"- **Tool {t['name']} attached** because: {t.get('reason') or 'requirements need it'}; evidence in the requirements: {', '.join(t.get('evidence', []))}.")
    for t in gen_meta.get("tools_rejected", []):
        L.append(f"- **Tool {t['name']} rejected:** {t['reason']}.")
    if tournament:
        L.append(f"- **System prompt:** the '{tournament['winner']}' variant won the prompt tournament on a stratified dev subset.")
    L.append("- **Output contract:** JSON {answer, refused, citations}, validated by the runtime, so format failures are measured instead of hidden.")
    return L + [""]


def final_report(run_dir: Path, req: Requirements, defn: AgentDefinition, cases: list[EvalCase], results: list[CaseResult],
                 iterations: list[dict], loop_log: list[dict], judge_selftest: dict, gen_meta: dict, budget: dict,
                 tournament: dict | None, evalgen_rejects: list, cfg_public: dict, stop_reason: str) -> str:
    # the SHIPPED version's scores, not the last iteration's: a reverted iteration must never set the headline
    shipped = [it for it in iterations if it["agent_version"] == defn.version and not str(it.get("decision", "")).startswith("reverted")]
    final = (shipped[-1] if shipped else iterations[-1])["scorecard"] if iterations else {}
    best_it = max(iterations, key=lambda x: (x["scorecard"]["dev_pass_rate"] or 0)) if iterations else None
    fails = [r for r in results if not r.passed]
    L = [f"# ForgeAI report: `{defn.name}`", ""]
    L += [f"**Final agent:** v{defn.version} · **overall pass rate {pct(final.get('pass_rate'))}** "
          f"(dev {pct(final.get('dev_pass_rate'))}, holdout {pct(final.get('holdout_pass_rate'))}) on {len(cases)} generated cases.",
          f"Models: factory `{cfg_public['model']}` · agent `{cfg_public.get('agent_model') or cfg_public['model']}` · judge `{cfg_public.get('judge_model') or cfg_public['model']}` via `{cfg_public['backend']}`.",
          f"Loop stopped because: {stop_reason}.", ""]
    verdict, why_not = readiness(final, req, judge_selftest) if final else ("NOT EVALUATED", [])
    L += ["## Deployment readiness", "", f"**{verdict}**", ""] + ([f"- {x}" for x in why_not] or ["- no blocking issues found by the factory's checks"]) + [""]
    L += [f"Completeness (fact recall on answered questions) {pct(final.get('completeness'))} · citation precision {pct(final.get('citation_precision'))} · "
          f"answer relevance (embedding similarity, informational) {final.get('answer_relevance')} · grounded {pct(final.get('grounded_rate'))} · refusal accuracy {pct(final.get('refusal_accuracy'))}", ""]
    L += ["## Scorecard per iteration", "", scorecard_md(iterations), "",
          "Holdout cases were never shown to the optimizer. A gap between dev and holdout is the overfitting signal.", ""]
    if req.flags:
        L += ["## Flagged at requirements stage (groundability guard)"] + [f"- {f}" for f in req.flags] + [""]
    L += why_section(defn, gen_meta, tournament)
    L += ["## Tool selection", ""]
    for t in gen_meta.get("tools_kept", []):
        L.append(f"- attached **{t['name']}**: {t.get('reason','')} (evidence: {', '.join(t.get('evidence', [])) or 'n/a'})")
    for t in gen_meta.get("tools_rejected", []):
        L.append(f"- rejected **{t['name']}**: {t['reason']}")
    if not gen_meta.get("tools_kept"):
        L.append("- no tools attached (documents only)")
    L.append("")
    if tournament:
        L += ["## Prompt tournament", "", "| Variant | Dev subset pass rate | System prompt chars | Tokens spent | Winner |", "|---|---|---|---|---|"]
        for c in tournament["candidates"]:
            L.append(f"| {c['variant']} | {pct(c['pass_rate'])} | {c.get('prompt_chars','')} | {c.get('tokens','')} | {'✅' if c['variant']==tournament['winner'] else ''} |")
        L += ["", tournament.get("note", ""), ""]
    L += ["## Judge reliability", ""]
    if judge_selftest.get("ran"):
        L.append(f"LLM judge self test on synthetic answers with known grades: **{pct(judge_selftest['accuracy'])}** agreement over {judge_selftest['trials']} trials → {judge_selftest['decision']}.")
        wrong = [d for d in judge_selftest["details"] if not d["agree"]]
        if wrong:
            L.append("Disagreements: " + "; ".join(f"{d['case']}/{d['variant']} (expected {'pass' if d['expected_pass'] else 'fail'})" for d in wrong))
    else:
        L.append(f"Self test not run: {judge_selftest.get('reason','')}")
    L += ["", "Deterministic checks (numbers, refusal flag, unsupported-number grounding, citations) decide first; the LLM judge can only add credit for a fact when it quotes the answer verbatim and every number in the fact is present.", ""]
    L += ["## What still fails, and why", ""]
    if not fails:
        L.append("Every generated case passes. Treat that with suspicion: see limitations below.")
    by_cat: dict[str, list] = {}
    for r in fails:
        by_cat.setdefault(r.failure_category or "unclassified", []).append(r)
    explain = {
        "retrieval_miss": "The passage with the answer never reached the model. BM25 is lexical, so paraphrased or very short questions can miss; the optimizer's query expansions only cover wording seen in dev failures.",
        "hallucination": "The answer contains numbers that appear in no passage or tool result. This is the most dangerous class for a policy assistant.",
        "wrong_refusal": "The model refused when the answer was present, or answered something it should have declined. Small models are inconsistent about where the scope boundary is.",
        "prompt_defect": "The right passage was retrieved but the answer left out required facts, did not cite, or broke the JSON contract.",
    }
    for cat, rs in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        L.append(f"### {cat} ({len(rs)})")
        L.append(explain.get(cat, ""))
        for r in rs:
            L.append(f"- `{r.case_id}` [{r.split}] {r.question}  \n  → {r.diagnosis}. Answer: _{r.answer[:180].strip()}_")
        L.append("")
    sus = [r for r in fails if r.suspected_eval_defect]
    if sus:
        L += ["## Failures that may be test defects (still counted as failures)", "",
              f"{len(sus)} failing case(s) were read as correct by the judge model, but rejected by a strict deterministic rule. "
              "They stay in the score; a human should check them. They were not sent to the optimizer.", ""]
        L += [f"- `{r.case_id}` {r.question}  \n  missing per strict rule: {r.facts_missing}" for r in sus] + [""]
    L += ["## Eval set provenance", "",
          f"{len(cases)} cases generated from the documents (types: " + ", ".join(f"{t}={sum(1 for c in cases if c.type==t)}" for t in sorted({c.type for c in cases})) + ").",
          f"{len(evalgen_rejects)} candidate cases were rejected by validation (unverifiable facts, duplicates, out-of-scope questions the documents actually answer). See `eval_generation_log.json`.", ""]
    L += ["## Known limitations of this run (read before trusting the number)", "",
          "- The eval set is generated by the same small model family that builds the agent; questions it cannot imagine are not tested. Holdout reduces, but does not remove, this blind spot.",
          "- Key facts are short string facts. An answer that is correct but phrased with different numbers formatting (e.g. 'two weeks' vs '14 days') can be marked wrong; check the failure list above for such cases.",
          "- Out-of-scope cases are only as hard as the generator made them; adversarial prompts (jailbreaks) are not covered.",
          "- Tool cases are computed exactly in Python, but only the first CSV is sampled.",
          f"- Budget used: {budget.get('tokens_used')} tokens across {budget.get('llm_calls')} model calls ({budget.get('cached_calls')} served from cache), {budget.get('elapsed_seconds')} s.", ""]
    if iterations and iterations[-1]["agent_version"] != defn.version:
        L.append(f"Note: later iterations were reverted, so the shipped definition is v{defn.version}; every score above the iteration table is for that version.")
    return "\n".join(L)


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def dump_jsonl(path: Path, items) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for x in items:
            f.write(json.dumps(x.model_dump() if hasattr(x, "model_dump") else x, ensure_ascii=False) + "\n")
