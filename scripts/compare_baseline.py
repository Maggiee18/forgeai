"""Compare the hand-written human baseline agent with the factory's agent on the SAME generated eval set.
Reads only stored artifacts; writes runs/<run>/BASELINE_COMPARISON.md.
Run: python scripts/compare_baseline.py runs/hr_policy"""
import json
import sys
from pathlib import Path


def pct(x):
    return "n/a" if x is None else f"{x * 100:.0f}%"


def main(run: str):
    d = Path(run)
    its = json.loads((d / "scorecard.json").read_text())
    defn = json.loads((d / "agent_definition.json").read_text())
    shipped = [i for i in its if i["agent_version"] == defn["version"] and not str(i.get("decision", "")).startswith("reverted")][-1]["scorecard"]
    human = json.loads((d / "human_baseline_scorecard.json").read_text())
    hres = {r["case_id"]: r for r in map(json.loads, (d / "human_baseline_results.jsonl").read_text().splitlines()) if r}
    fres = {r["case_id"]: r for r in map(json.loads, (d / "final_results.jsonl").read_text().splitlines()) if r}
    rows = [("Overall pass rate", "pass_rate"), ("Dev", "dev_pass_rate"), ("Holdout", "holdout_pass_rate"), ("Fact recall", "answer_fact_recall"),
            ("Refusal accuracy", "refusal_accuracy"), ("Grounded", "grounded_rate"), ("Citation precision", "citation_precision"), ("Retrieval hit", "retrieval_hit_rate")]
    L = [f"# Human baseline vs factory agent: `{defn['name']}`", "",
         "Both agents answer the same generated test cases, with the same agent model, judge and retrieval engine. The human baseline",
         "(`baseline/hr_human_agent.json`) was written by hand in about 25 minutes, without seeing the eval set.", "",
         "| Metric | Factory agent (v%d) | Human baseline |" % defn["version"], "|---|---|---|"]
    for label, k in rows:
        L.append(f"| {label} | {pct(shipped.get(k))} | {pct(human.get(k))} |")
    fh = sorted(k for k in fres if fres[k]["passed"] and not hres.get(k, {}).get("passed"))
    hf = sorted(k for k in hres if hres[k]["passed"] and not fres.get(k, {}).get("passed"))
    L += ["", f"Cases only the factory agent passes: {', '.join(fh) or 'none'}", f"Cases only the human baseline passes: {', '.join(hf) or 'none'}", ""]
    for k in fh + hf:
        winner = "factory" if k in fh else "human"
        loser = hres[k] if k in fh else fres[k]
        L.append(f"- `{k}` ({winner} passes): {loser['question']}  \n  the other agent failed with **{loser['failure_category']}**: {loser['diagnosis']}")
    (d / "BASELINE_COMPARISON.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "runs/hr_policy")
