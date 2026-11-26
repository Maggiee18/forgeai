"""Print the README results table from stored run artifacts (no numbers typed by hand)."""
import json
import re
from pathlib import Path


def pct(x):
    return "n/a" if x is None else f"{x * 100:.0f}%"


rows = []
for name in ("hr_policy", "ship_spares"):
    d = Path("runs") / name
    its = json.loads((d / "scorecard.json").read_text())
    defn = json.loads((d / "agent_definition.json").read_text())
    shipped = [i for i in its if i["agent_version"] == defn["version"] and not str(i.get("decision", "")).startswith("reverted")][-1]["scorecard"]
    first = its[0]["scorecard"]
    req = json.loads((d / "requirements.json").read_text())
    tools = ", ".join(t["name"] for t in defn["tools"]) or "none"
    verdict = re.search(r"## Deployment readiness\s+\*\*(.+?)\*\*", (d / "REPORT.md").read_text()).group(1)
    rows.append(f"| [{name}](runs/{name}/REPORT.md) | {first['n_cases']} | {pct(first['pass_rate'])} | **{pct(shipped['pass_rate'])}** | {pct(shipped['dev_pass_rate'])} / {pct(shipped['holdout_pass_rate'])} "
                f"| {shipped['failures_by_category']['hallucination']} | {pct(shipped['refusal_accuracy'])} | {tools} | {len(req['ungroundable_topics'])} gap(s), {len(req['conflicts'])} contradiction(s) | {verdict.lower()} |")
print("| Demo | Cases | Iteration 0 | Shipped | Dev / holdout | Hallucinations | Refusal accuracy | Tools attached | Guard found | Readiness |")
print("|---|---|---|---|---|---|---|---|---|---|")
print("\n".join(rows))
