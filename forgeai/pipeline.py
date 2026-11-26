"""The factory: brief + documents -> requirements -> agent -> evals -> critic/optimizer loop -> report.

Run directory layout (everything is committed as evidence):
  brief.txt, config.json
  requirements.json / requirements.md          (stage 1 + 2)
  agent_definition.v0.json ... vN.json          (every version)
  agent_definition.json                         (the shipped one = best dev score)
  evalset.jsonl, eval_generation_log.json       (stage 4)
  judge_selftest.json                           (stage 5)
  tournament.json                               (stretch)
  iterations/iter_<k>_results.jsonl             (per case results each iteration)
  iteration_log.json / iteration_log.md         (stage 6)
  scorecard.json / scorecard.md, REPORT.md      (stage 7)
  budget.json
"""
from __future__ import annotations

import json
import os
import random
import shutil
from pathlib import Path

from . import generator, intake
from .config import Config
from .docs import load_folder
from .evalgen import EvalGenerator
from .evaluate import run_evals, scorecard
from .guard import run_guard
from .judge import Judge
from .llm import Budget, BudgetExceeded, make_clients
from .optimizer import Optimizer
from .report import pct, dump, dump_jsonl, final_report, iteration_log_md, scorecard_md
from .runner import Agent
from .schemas import AgentDefinition, CaseResult, EvalCase, Requirements
from .textutil import fact_in_text


def _stratified_subset(cases: list[EvalCase], n: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    dev = [c for c in cases if c.split == "dev"]
    by: dict[str, list] = {}
    for c in dev:
        by.setdefault(c.type, []).append(c)
    for v in by.values():
        rng.shuffle(v)
    out, i = [], 0
    while len(out) < min(n, len(dev)):
        t = list(by)[i % len(by)]
        if by[t]:
            out.append(by[t].pop().id)
        i += 1
        if not any(by.values()):
            break
    return out


class Factory:
    def __init__(self, cfg: Config, mock_fn=None, log=print):
        self.cfg, self.log, self.mock_fn = cfg, log, mock_fn

    def _clients(self, run_dir: Path, budget: Budget):
        cache = Path(os.environ.get("FORGE_CACHE", run_dir / ".cache"))
        return make_clients(self.cfg, budget, cache, mock_fn=self.mock_fn, verbose=False)

    def _guard_client(self, run_dir: Path, budget: Budget, judge_llm):
        """Model that decides cross-document contradictions: guard_model if set, else the judge."""
        if not self.cfg.guard_model:
            return judge_llm
        from .llm import LLMClient

        cache = Path(os.environ.get("FORGE_CACHE", run_dir / ".cache"))
        return LLMClient(self.cfg.judge_backend or self.cfg.backend, self.cfg.guard_model, budget=budget, cache_dir=cache, mock_fn=self.mock_fn,
                         base_url=self.cfg.base_url, api_key=self.cfg.api_key, temperature=0.0, role="guard")

    # ------------------------------------------------------------------ build
    def requirements_only(self, brief: str, docs_folder: str, answers: list[str] | None = None) -> Requirements:
        """Stages 1 + 2 only (for the web UI's human checkpoint): returns requirements for review."""
        cfg, log = self.cfg, self.log
        budget = Budget(max_tokens=cfg.max_tokens)
        factory_llm, _, _judge = self._clients(Path(docs_folder).parent, budget)
        docs = load_folder(docs_folder)
        from .retrieval import default_index

        idx = default_index(docs, embedding=cfg.embedding)
        tmp_answers = None
        if answers is not None:
            import tempfile, yaml

            tmp_answers = Path(tempfile.mkstemp(suffix=".yaml")[1])
            tmp_answers.write_text(yaml.safe_dump({"answers": answers}), encoding="utf-8")
        clar = intake.interview(brief, docs, factory_llm, False, str(tmp_answers) if tmp_answers else cfg.answers_file, log, index=idx)
        req = intake.write_requirements(brief, docs, clar, factory_llm)
        return run_guard(req, docs, factory_llm, log, index=idx, verifier=self._guard_client(Path(docs_folder).parent, budget, _judge))

    def build(self, brief_path: str, docs_folder: str, out_dir: str, requirements: Requirements | None = None) -> dict:
        cfg, log = self.cfg, self.log
        run = Path(out_dir)
        run.mkdir(parents=True, exist_ok=True)
        brief = Path(brief_path).read_text(encoding="utf-8").strip()
        shutil.copy(brief_path, run / "brief.txt")
        dump(run / "config.json", cfg.public_dict())
        budget = Budget(max_tokens=cfg.max_tokens, max_seconds=cfg.max_seconds)
        factory_llm, agent_llm, judge_llm = self._clients(run, budget)
        docs = load_folder(docs_folder)
        if not docs:
            raise SystemExit(f"no supported documents in {docs_folder}")
        rel_docs = os.path.relpath(Path(docs_folder).resolve(), run.resolve())
        log(f"\n=== ForgeAI · {len(docs)} documents · backend {cfg.backend}:{cfg.model}")

        if requirements is not None:
            # requirements were produced and approved earlier (web UI human checkpoint)
            req = requirements
            log("\n[1-2/7] Using requirements approved by the requester")
        else:
            # 1. intake ---------------------------------------------------------
            budget.stage = "intake"
            log("\n[1/7] Intake interview")
            from .retrieval import default_index

            stage_index = default_index(docs, embedding=cfg.embedding)
            clar = intake.interview(brief, docs, factory_llm, cfg.interactive, cfg.answers_file, log, index=stage_index)
            req = intake.write_requirements(brief, docs, clar, factory_llm)

            # 2. groundability guard ---------------------------------------------
            budget.stage = "guard"
            log("\n[2/7] Groundability guard")
            req = run_guard(req, docs, factory_llm, log, index=stage_index, verifier=self._guard_client(run, budget, judge_llm))
            if cfg.human_checkpoint:
                req = intake.human_checkpoint(req, run / "requirements.json", log)
            else:
                req.approved, req.approval_note = True, "human checkpoint disabled (unattended run)"
        dump(run / "requirements.json", req)
        (run / "requirements.md").write_text(intake.requirements_markdown(req), encoding="utf-8")
        for f in req.flags:
            log(f"    ⚠ {f}")

        # 3. generate (tournament candidates share one tool decision) ----------
        budget.stage = "generate"
        log("\n[3/7] Agent generation")
        tools, rejected = generator.choose_tools(req, docs, factory_llm, cfg.tools_enabled)
        log(f"    tools attached: {[t['name'] for t in tools] or 'none'}; rejected: {[t['name'] for t in rejected] or 'none'}")
        variants = list(generator.VARIANTS)[: cfg.tournament_candidates] if cfg.tournament else ["strict"]
        candidates = []
        for v in variants:
            d, _ = generator.generate(req, docs, rel_docs, factory_llm, cfg.tools_enabled, variant=v, tools=tools, embedding=cfg.embedding)
            candidates.append(d)
        gen_meta = {"tools_kept": tools, "tools_rejected": rejected}
        dump(run / "tool_selection.json", gen_meta)

        # 4. eval generation --------------------------------------------------
        budget.stage = "evalgen"
        log("\n[4/7] Eval generation")
        eg = EvalGenerator(req, docs, factory_llm, cfg, log)
        cases = eg.run([t["name"] for t in tools])
        dump_jsonl(run / "evalset.jsonl", cases)
        dump(run / "eval_generation_log.json", {"accepted": len(cases), "rejected": eg.rejected})
        log(f"    {len(cases)} cases accepted, {len(eg.rejected)} rejected by validation "
            f"({', '.join(f'{t}={sum(1 for c in cases if c.type == t)}' for t in sorted({c.type for c in cases}))})")
        if len(cases) < 20:
            log("    ⚠ fewer than 20 cases survived validation; topping up answerable cases")
            eg.answerable(20 - len(cases) + 2)
            eg._split()
            cases = eg.cases
            dump_jsonl(run / "evalset.jsonl", cases)

        # 5. judge self test --------------------------------------------------
        budget.stage = "judge_selftest"
        log("\n[5/7] Judge self test")
        judge = Judge(judge_llm, use_llm=True, seed=cfg.seed)
        st = judge.self_test(cases) if cfg.judge_selftest else {"ran": False, "reason": "disabled in config"}
        dump(run / "judge_selftest.json", st)
        log(f"    {st.get('decision', st.get('reason'))} (accuracy {st.get('accuracy', 'n/a')})")

        # tournament ------------------------------------------------------------
        tournament = None
        budget.stage = "tournament"
        if len(candidates) > 1:
            log("\n[5b] Prompt tournament")
            subset = _stratified_subset(cases, cfg.tournament_cases, cfg.seed)
            rows = []
            for d in candidates:
                t0 = budget.tokens_used
                res = run_evals(Agent(d, agent_llm, docs=docs), cases, judge, subset=subset)
                rows.append({"variant": d.provenance["variant"], "pass_rate": round(sum(r.passed for r in res) / len(res), 3), "tokens": budget.tokens_used - t0,
                             "prompt_chars": len(d.system_prompt), "passed": [r.case_id for r in res if r.passed]})
                log(f"    {d.provenance['variant']:<10} {rows[-1]['pass_rate']:.0%}")
            win = max(rows, key=lambda r: (r["pass_rate"], -r["prompt_chars"]))
            tournament = {"subset": subset, "candidates": rows, "winner": win["variant"],
                          "note": "Winner chosen by pass rate on a stratified dev subset (no pairwise LLM verdicts, so no position bias); ties go to the shorter (cheaper) system prompt."}
            dump(run / "tournament.json", tournament)
            for d in candidates:
                dump(run / "candidates" / f"agent_{d.provenance['variant']}.json", d)
            defn = next(d for d in candidates if d.provenance["variant"] == win["variant"])
        else:
            defn = candidates[0]

        # 6. iterate ------------------------------------------------------------
        log("\n[6/7] Evaluate → critic → optimizer loop")
        budget.stage = "eval_iter0"
        results = run_evals(Agent(defn, agent_llm, docs=docs), cases, judge, log=log)
        dump(run / f"agent_definition.v{defn.version}.json", defn)
        dump_jsonl(run / "iterations" / "iter_0_results.jsonl", results)
        sc = scorecard(results)
        iterations = [{"iteration": 0, "agent_version": defn.version, "scorecard": sc, "decision": "baseline"}]
        log(f"    iteration 0: overall {pct(sc['pass_rate'])}, dev {pct(sc['dev_pass_rate'])}, holdout {pct(sc['holdout_pass_rate'])}; failures {sc['failures_by_category']}")
        best_def, best_res, best_sc = defn, results, sc
        opt = Optimizer(req, docs, factory_llm, log)
        loop_log, stop_reason = [], f"reached the maximum of {cfg.max_iterations} iterations"
        next_version, tried = defn.version + 1, set()
        for k in range(1, cfg.max_iterations + 1):
            dev_fail = [r for r in best_res if not r.passed and r.split == "dev" and not r.suspected_eval_defect]
            if not dev_fail:
                stop_reason = "no dev failures left to fix"
                break
            try:
                budget.stage = f"optimize_{k}"
                budget.check()
                new_def, changes = opt.improve(best_def, best_res, cases, exclude=tried)
                new_def.version = next_version
                next_version += 1
                applied = [c for c in changes if not c.get("skipped")]
                entry = {"iteration": k, "from_version": best_def.version, "to_version": new_def.version, "dev_before": best_sc["dev_pass_rate"],
                         "holdout_before": best_sc["holdout_pass_rate"], "failures_in": best_sc["failures_by_category"], "changes": changes}
                if not applied:
                    entry.update(decision="no change", stop_reason="optimizer found no applicable targeted fix")
                    loop_log.append(entry)
                    stop_reason = "optimizer found no applicable targeted fix"
                    break
                for c in applied:
                    log(f"    iter {k}: {c['category']} → {c['target']}: {c.get('rationale', '')[:110]}")
                budget.stage = f"eval_iter{k}"
                new_res = run_evals(Agent(new_def, agent_llm, docs=docs), cases, judge, log=log)
            except BudgetExceeded as e:
                stop_reason = f"budget exhausted during iteration {k}: {e}"
                log(f"    ⚠ {stop_reason}")
                break
            new_sc = scorecard(new_res)
            old_pass = {r.case_id for r in best_res if r.passed}
            new_pass = {r.case_id for r in new_res if r.passed}
            for c in applied:
                c["fixed_cases"] = [i for i in c.get("addressed_cases", []) if i in new_pass]
            entry["newly_broken"] = sorted(old_pass - new_pass)
            entry["newly_fixed"] = sorted(new_pass - old_pass)
            entry["dev_after"], entry["holdout_after"] = new_sc["dev_pass_rate"], new_sc["holdout_pass_rate"]
            dump(run / f"agent_definition.v{new_def.version}.json", new_def)
            dump_jsonl(run / "iterations" / f"iter_{k}_results.jsonl", new_res)
            gain = (new_sc["dev_pass_rate"] or 0) - (best_sc["dev_pass_rate"] or 0)
            if gain > 0 or (gain == 0 and (new_sc["pass_rate"] or 0) > (best_sc["pass_rate"] or 0)):
                entry["decision"] = "kept"
                best_def, best_res, best_sc = new_def, new_res, new_sc
            else:
                entry["decision"] = "reverted (dev score did not improve)"
                # do not retry the same targeted fix on the same failures; the next iteration tries other categories
                tried |= {c["category"] for c in applied}
            iterations.append({"iteration": k, "agent_version": new_def.version, "scorecard": new_sc, "decision": entry["decision"]})
            log(f"    iteration {k}: dev {pct(new_sc['dev_pass_rate'])}, holdout {pct(new_sc['holdout_pass_rate'])} ({entry['decision']}); fixed {entry['newly_fixed']}, broke {entry['newly_broken']}")
            loop_log.append(entry)
            if entry["decision"] == "kept" and gain < cfg.min_gain and k < cfg.max_iterations:
                stop_reason = f"early stop: iteration {k} gained {gain:+.0%} on dev, below the {cfg.min_gain:.0%} threshold (not paying for itself)"
                entry["stop_reason"] = stop_reason
                break
            if entry["decision"] != "kept" and k >= 2 and loop_log[-2].get("decision", "").startswith("reverted"):
                stop_reason = "early stop: two consecutive iterations failed to improve"
                entry["stop_reason"] = stop_reason
                break

        # 7. report ---------------------------------------------------------------
        budget.stage = "report"
        log("\n[7/7] Report")
        dump(run / "agent_definition.json", best_def)
        dump_jsonl(run / "final_results.jsonl", best_res)
        dump(run / "scorecard.json", iterations)
        (run / "scorecard.md").write_text("# Scorecard\n\n" + scorecard_md(iterations) + "\n", encoding="utf-8")
        dump(run / "iteration_log.json", loop_log)
        (run / "iteration_log.md").write_text(iteration_log_md(loop_log), encoding="utf-8")
        b = budget.to_dict()
        dump(run / "budget.json", b)
        rep = final_report(run, req, best_def, cases, best_res, iterations, loop_log, st, gen_meta, b, tournament, eg.rejected, cfg.public_dict(), stop_reason)
        (run / "REPORT.md").write_text(rep, encoding="utf-8")
        log(f"    final: v{best_def.version}, overall {pct(best_sc['pass_rate'])} (dev {pct(best_sc['dev_pass_rate'])}, holdout {pct(best_sc['holdout_pass_rate'])}); {b['tokens_used']} tokens; report at {run/'REPORT.md'}")
        return {"run_dir": str(run), "scorecard": best_sc, "stop_reason": stop_reason}

    # ------------------------------------------------------------- evaluate only
    def evaluate_definition(self, definition_path: str, run_dir: str, out_name: str, docs_folder: str | None = None) -> dict:
        run = Path(run_dir)
        budget = Budget(max_tokens=self.cfg.max_tokens)
        _, agent_llm, judge_llm = self._clients(run, budget)
        cases = [EvalCase.model_validate_json(l) for l in (run / "evalset.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        agent = Agent.from_file(definition_path, agent_llm, docs_folder=docs_folder)
        judge = Judge(judge_llm, use_llm=True, seed=self.cfg.seed)
        st = json.loads((run / "judge_selftest.json").read_text()) if (run / "judge_selftest.json").exists() else {}
        if st.get("decision", "").startswith("llm judge DISABLED"):
            judge.use_llm = False
        res = run_evals(agent, cases, judge, log=self.log)
        dump_jsonl(run / f"{out_name}_results.jsonl", res)
        sc = scorecard(res)
        dump(run / f"{out_name}_scorecard.json", sc)
        return {"scorecard": sc, "results": res, "budget": budget.to_dict()}

    # --------------------------------------------------------------- regression
    def regress(self, old_run: str, new_docs: str, out_dir: str) -> dict:
        """Documents changed: regenerate the agent from the SAME requirements, replay the OLD eval set,
        and separate genuine regressions from eval cases the new documents made stale."""
        cfg, log = self.cfg, self.log
        old = Path(old_run)
        run = Path(out_dir)
        run.mkdir(parents=True, exist_ok=True)
        budget = Budget(max_tokens=cfg.max_tokens)
        factory_llm, agent_llm, judge_llm = self._clients(run, budget)
        req = Requirements.model_validate_json((old / "requirements.json").read_text(encoding="utf-8"))
        old_def = AgentDefinition.model_validate_json((old / "agent_definition.json").read_text(encoding="utf-8"))
        cases = [EvalCase.model_validate_json(l) for l in (old / "evalset.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        old_res = {r.case_id: r for r in (CaseResult.model_validate_json(l) for l in (old / "final_results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}
        docs = load_folder(new_docs)
        log(f"\n=== Regression: {old_def.name} on changed documents ({len(docs)} files)")
        req = run_guard(req, docs, factory_llm, log, verifier=self._guard_client(run, budget, judge_llm))
        rel_docs = os.path.relpath(Path(new_docs).resolve(), run.resolve())
        new_def, meta = generator.generate(req, docs, rel_docs, factory_llm, cfg.tools_enabled, variant=old_def.provenance.get("variant", "strict"), tools=old_def.tools, embedding=cfg.embedding)
        new_def.retrieval = {**new_def.retrieval, **{k: old_def.retrieval[k] for k in ("top_k", "min_score", "query_expansion", "bm25_weight", "dense_weight") if k in old_def.retrieval}}
        new_def.name = old_def.name
        dump(run / "agent_definition.json", new_def)
        judge = Judge(judge_llm, use_llm=True, seed=cfg.seed)
        res = run_evals(Agent(new_def, agent_llm, docs=docs), cases, judge, log=log)
        corpus = " ".join(d.text for d in docs)
        rows = []
        for r in res:
            was = old_res.get(r.case_id)
            if was and was.passed and not r.passed:
                case = next(c for c in cases if c.id == r.case_id)
                still = all(fact_in_text(f, corpus) for f in case.key_facts) if case.key_facts else True
                kind = "agent regression (facts still in documents)" if still else "stale eval: expected facts no longer in documents (policy changed)"
                rows.append({"case": r.case_id, "question": r.question, "verdict": kind, "missing_facts": [f for f in case.key_facts if not fact_in_text(f, corpus)], "new_answer": r.answer[:300]})
        fixed = [r.case_id for r in res if r.passed and old_res.get(r.case_id) and not old_res[r.case_id].passed]
        sc = scorecard(res)
        old_sc = scorecard(list(old_res.values()))
        dump_jsonl(run / "regression_results.jsonl", res)
        out = {"old_pass_rate": old_sc["pass_rate"], "new_pass_rate": sc["pass_rate"], "broke": rows, "newly_passing": fixed, "guard_flags": req.flags}
        dump(run / "regression.json", out)
        L = [f"# Regression report: {old_def.name}", "", f"Old documents: pass rate {old_sc['pass_rate']:.0%} · New documents: {sc['pass_rate']:.0%} on the same {len(cases)} cases.", ""]
        L += ["## Cases that broke", "", "| Case | Question | Verdict | Facts gone from docs |", "|---|---|---|---|"]
        for x in rows:
            L.append(f"| {x['case']} | {x['question'][:80]} | {x['verdict']} | {', '.join(x['missing_facts']) or '-'} |")
        if not rows:
            L.append("| - | none | - | - |")
        L += ["", f"Newly passing: {', '.join(fixed) or 'none'}", "", "## Guard flags on the new documents"] + [f"- {f}" for f in req.flags]
        L += ["", "Stale cases should be regenerated (run `forgeai build` again); agent regressions are real defects."]
        (run / "REGRESSION.md").write_text("\n".join(L), encoding="utf-8")
        log(f"    {len(rows)} previously passing cases broke; report at {run/'REGRESSION.md'}")
        return out
