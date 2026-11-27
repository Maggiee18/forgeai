"""Offline test suite (mock backend, no network). Run: pytest -q"""
import json
from pathlib import Path

import pytest

from forgeai.config import Config
from forgeai.critic import classify
from forgeai.docs import load_folder
from forgeai.evalgen import EvalGenerator
from forgeai.guard import check_topic
from forgeai.intake import ask_questions
from forgeai.judge import Judge
from forgeai.llm import Budget, BudgetExceeded, LLMClient, extract_json
from forgeai.mock import mock_llm
from forgeai.pipeline import Factory
from forgeai.retrieval import BM25Index, chunk_documents
from forgeai.runner import Agent
from forgeai.schemas import AgentResponse, EvalCase, Requirements
from forgeai.tools import calculator, select_tools

ROOT = Path(__file__).resolve().parent.parent
HR = ROOT / "demos/hr_policy/docs"
SP = ROOT / "demos/ship_spares/docs"


def fake_llm(reply):
    """LLM that always returns `reply` (dict -> JSON)."""
    return LLMClient("mock", "fake", mock_fn=lambda m, j: json.dumps(reply) if not isinstance(reply, str) else reply)


# ------------------------------------------------------------------ llm layer
def test_extract_json_repairs_common_breakage():
    assert extract_json('```json\n{"a": 1,}\n```') == {"a": 1}
    assert extract_json('Sure! Here it is: {"x": [1, 2]} hope that helps') == {"x": [1, 2]}
    assert extract_json('<think>hmm</think>{"ok": true}') == {"ok": True}


def test_json_retries_then_validates():
    calls = {"n": 0}

    def fn(m, j):
        calls["n"] += 1
        return "not json" if calls["n"] == 1 else '{"v": 3}'

    llm = LLMClient("mock", "m", mock_fn=fn)
    assert llm.json([{"role": "user", "content": "x"}]) == {"v": 3}
    assert calls["n"] == 2


def test_budget_enforced():
    b = Budget(max_tokens=10)
    llm = LLMClient("mock", "m", budget=b, mock_fn=lambda m, j: "x" * 400)
    llm.chat([{"role": "user", "content": "hello" * 20}])
    with pytest.raises(BudgetExceeded):
        llm.chat([{"role": "user", "content": "again"}])


# ---------------------------------------------------------------------- tools
def test_calculator_is_safe_and_exact():
    assert calculator("12 * 412.5 * (1 - 5%)")["result"] == pytest.approx(4702.5)
    assert "error" in calculator("__import__('os').system('ls')")
    assert "error" in calculator("2 ** 1000000")


def test_tool_selection_rejects_unneeded_tools():
    hr_text = "Answer HR policy questions on leave, travel claims, code of conduct and grievances for shore staff."
    kept, rejected = select_tools([{"name": "weather_forecast"}, {"name": "calculator"}, {"name": "csv_lookup"}], hr_text, has_csv=False,
                                  enabled=["csv_lookup", "calculator", "weather_forecast", "current_date"])
    assert kept == []
    assert {r["name"] for r in rejected} == {"weather_forecast", "calculator", "csv_lookup"}


def test_tool_selection_keeps_needed_tools():
    text = "look up parts in the catalogue, compute total cost for a quantity with discount, estimate delivery date from lead time"
    kept, rejected = select_tools([{"name": "csv_lookup"}, {"name": "calculator"}, {"name": "current_date"}, {"name": "weather_forecast"}], text, True,
                                  ["csv_lookup", "calculator", "weather_forecast", "current_date"])
    assert {k["name"] for k in kept} == {"csv_lookup", "calculator", "current_date"}
    assert [r["name"] for r in rejected] == ["weather_forecast"]


# ------------------------------------------------------------------ retrieval
def test_retrieval_finds_the_right_section():
    idx = BM25Index(chunk_documents(load_folder(HR), 160, 30))
    top = idx.search("how many days of annual leave do I get", 2)
    assert any("21 days" in c.text for c, _ in top)
    top = idx.search("hotel limit per night", 2)
    assert top[0][0].doc_id == "Travel_and_Expense_Policy.pdf"


def test_query_expansion_bridges_vocabulary():
    chunks = chunk_documents(load_folder(HR), 160, 30)
    plain = BM25Index(chunks).search("PTO carryover", 1)
    expanded = BM25Index(chunks, query_expansion={"pto": ["annual leave"], "carryover": ["carried forward"]}).search("PTO carryover", 1)
    assert "carried forward" in expanded[0][0].text
    assert not plain or "carried forward" not in plain[0][0].text


# ---------------------------------------------------------------------- guard
def test_guard_overrules_supported_claim_with_fake_quote():
    idx = BM25Index(chunk_documents(load_folder(HR), 160, 30))
    liar = fake_llm({"status": "supported", "evidence_quote": "Salary bands range from INR 4 lakh to INR 40 lakh per year.", "source": "Leave_Policy_Shore_Staff.pdf"})
    chk = check_topic("salary bands and payroll dates", idx, liar)
    assert chk.status == "unsupported"
    assert "overruled" in chk.method


def test_guard_flags_live_data_without_tool():
    idx = BM25Index(chunk_documents(load_folder(SP), 160, 30))
    chk = check_topic("live freight rates for shipping spares", idx, fake_llm({"status": "supported", "evidence_quote": "", "source": ""}))
    assert chk.status == "unsupported"


# --------------------------------------------------------------------- intake
def test_intake_caps_questions_at_five():
    many = fake_llm({"questions": [{"question": f"Q{i}?", "default_answer": "d"} for i in range(9)]})
    assert len(ask_questions("brief", load_folder(HR), many)) == 5


# ---------------------------------------------------------------------- judge
def _case(**kw):
    base = dict(id="t-1", type="answerable", question="How many days of annual leave?", expected_behavior="answer",
                expected_sources=["Leave_Policy_Shore_Staff.pdf"], key_facts=["21 days of annual leave"])
    base.update(kw)
    return EvalCase(**base)


def _resp(answer, refused=False, cites=("Leave_Policy_Shore_Staff.pdf",), ctx="Every confirmed employee is entitled to 21 days of annual leave per leave year."):
    return AgentResponse(answer=answer, refused=refused, citations=list(cites), retrieved=[{"doc": "Leave_Policy_Shore_Staff.pdf", "text": ctx, "chunk_id": "x", "score": 1}])


def test_judge_passes_correct_grounded_answer():
    r = Judge(None, use_llm=False).score(_case(), _resp("You get 21 days of annual leave each year."))
    assert r.passed and r.grounded and r.fact_recall == 1


def test_judge_catches_hallucinated_number():
    r = Judge(None, use_llm=False).score(_case(), _resp("You get 21 days of annual leave, plus 8 floating days."))
    assert not r.passed and r.unsupported_numbers == ["8"]


def test_judge_verbosity_cannot_buy_credit():
    padding = "We value every employee and want everyone to rest well and feel supported. " * 20
    r = Judge(None, use_llm=False).score(_case(), _resp(padding + "Annual leave rules apply as usual."))
    assert not r.passed and r.fact_recall == 0


def test_llm_judge_needs_a_real_quote():
    lenient = fake_llm({"verdicts": [{"fact": 1, "stated": True, "quote": "you get twenty one days"}]})
    r = Judge(lenient).score(_case(), _resp("Leave depends on your grade."))
    assert not r.passed  # the judge said yes, but its quote is not in the answer


def test_judge_refusal_cases():
    c = _case(id="o-1", type="out_of_scope", question="Best stock to buy?", expected_behavior="refuse", expected_sources=[], key_facts=[])
    assert Judge(None, use_llm=False).score(c, _resp("Not covered by my documents.", refused=True, cites=())).passed
    assert not Judge(None, use_llm=False).score(c, _resp("Buy shipping stocks.", refused=False, cites=())).passed


# --------------------------------------------------------------------- critic
def test_critic_categories():
    j = Judge(None, use_llm=False)
    miss = j.score(_case(), AgentResponse(answer="Not covered.", refused=True, retrieved=[{"doc": "Travel_and_Expense_Policy.pdf", "text": "hotel caps", "chunk_id": "y", "score": 1}]))
    assert classify(miss)[0] == "retrieval_miss"
    over = j.score(_case(), _resp("I cannot answer that.", refused=True, cites=()))
    assert classify(over)[0] == "wrong_refusal"
    hall = j.score(_case(), _resp("You get 25 days."))
    assert classify(hall)[0] == "hallucination"
    incomplete = j.score(_case(key_facts=["21 days of annual leave", "accrues monthly"]), _resp("Leave accrues monthly.", ctx="21 days of annual leave accrues monthly"))
    assert classify(incomplete)[0] == "prompt_defect"


# ------------------------------------------------------------------- evalgen
def test_evalgen_drops_facts_not_in_source():
    req = Requirements(agent_name="x", purpose="p", scope="s", audience="staff", tone="t", must_answer_topics=["a", "b"], must_refuse_topics=["c", "d"])
    liar = fake_llm({"question": "How much leave do interns get?", "key_facts": ["Interns get 40 days of leave"]})
    cfg = Config(backend="mock")
    eg = EvalGenerator(req, load_folder(HR), liar, cfg, log=lambda *a: None)
    eg.answerable(3)
    assert eg.cases == []
    assert any("hallucinated" in r["reason"] for r in eg.rejected)


def test_tool_cases_are_computed_exactly():
    req = Requirements(agent_name="x", purpose="p", scope="s", audience="buyers", tone="t", must_answer_topics=["a", "b"], must_refuse_topics=["c", "d"])
    eg = EvalGenerator(req, load_folder(SP), fake_llm({}), Config(backend="mock"), log=lambda *a: None)
    eg.tool_cases(3, ["csv_lookup", "calculator"])
    import re
    catalogue = {r["part_number"]: r for r in next(d for d in load_folder(SP) if d.kind == "csv").rows}
    total_case = next(c for c in eg.cases if "in total" in c.question)
    qty = int(re.search(r"What would (\d+) units", total_case.question).group(1))
    part = re.search(r"\(([A-Z0-9-]+)\)", total_case.question).group(1)
    expected = float(catalogue[part]["unit_price_usd"]) * qty
    assert float(total_case.key_facts[0]) == pytest.approx(expected)


# --------------------------------------------------------------- end to end
@pytest.mark.parametrize("demo", ["hr_policy", "ship_spares"])
def test_factory_end_to_end_mock(tmp_path, demo, monkeypatch):
    monkeypatch.setenv("FORGE_CACHE", str(tmp_path / "cache"))
    cfg = Config(backend="mock", model="mock", interactive=False, answers_file=str(ROOT / f"demos/{demo}/answers.yaml"), verbose=False)
    out = Factory(cfg, mock_fn=mock_llm, log=lambda *a: None).build(str(ROOT / f"demos/{demo}/brief.txt"), str(ROOT / f"demos/{demo}/docs"), str(tmp_path / demo))
    run = Path(out["run_dir"])
    for f in ["requirements.json", "requirements.md", "agent_definition.json", "evalset.jsonl", "iteration_log.json", "scorecard.md", "REPORT.md", "judge_selftest.json"]:
        assert (run / f).exists(), f
    cases = [json.loads(l) for l in (run / "evalset.jsonl").read_text().splitlines()]
    assert len(cases) >= 20
    types = {c["type"] for c in cases}
    assert {"answerable", "cross_doc", "ambiguous", "out_of_scope"} <= types
    defn = json.loads((run / "agent_definition.json").read_text())
    names = {t["name"] for t in defn["tools"]}
    assert "weather_forecast" not in names
    if demo == "hr_policy":
        assert names == set()
    else:
        assert {"csv_lookup", "calculator"} <= names
    # the generic runner loads the produced definition
    agent = Agent.from_file(run / "agent_definition.json", LLMClient("mock", "mock", mock_fn=mock_llm))
    assert agent.answer("What is the capital of France?").refused


# ------------------------------------------------------------- hybrid retrieval
def test_hybrid_beats_keyword_on_paraphrases():
    import sys
    sys.path.insert(0, str(ROOT))
    from scripts.retrieval_benchmark import run

    r = run()
    assert r["hybrid"]["doc words"][0] == r["hybrid"]["doc words"][1]          # no loss on exact wording
    assert r["hybrid"]["paraphrase"][0] > r["bm25"]["paraphrase"][0]           # real gain on paraphrases


def test_definition_records_actual_embedding_provider():
    from forgeai.generator import retrieval_defaults

    r = retrieval_defaults(load_folder(HR), "fastembed:BAAI/bge-small-en-v1.5")
    # this sandbox cannot reach Hugging Face: the definition must say what really loaded, not what was asked
    assert r["embedding"]["provider"] in ("fastembed", "wordllama")
    if r["embedding"]["provider"] == "wordllama":
        assert "fell back" in r["embedding"].get("note", "")


# -------------------------------------------------------------- conflict guard
def _hr_req(**kw):
    base = dict(agent_name="hr", purpose="p", scope="s", audience="staff", tone="t",
                must_answer_topics=["gifts and hospitality limits"], must_refuse_topics=["legal advice", "medical advice"])
    base.update(kw)
    return Requirements(**base)


def test_guard_finds_real_contradiction():
    from forgeai.guard import find_conflicts
    from forgeai.retrieval import default_index

    honest = fake_llm({"conflict": True, "about": "gift value limit",
                       "quote_a": "Employees may accept gifts or hospitality from suppliers, agents or clients only if the value is below INR 2,000 per occasion.",
                       "quote_b": "Gifts received from clients or agents during an official trip may be retained if their value does not exceed INR 5,000.",
                       "same_subject_reason": "both set the maximum gift value an employee may keep"})
    # the fake model answers the same for every pair; only the pair whose quotes really exist may pass
    found = find_conflicts(_hr_req(), default_index(load_folder(HR)), honest, log=lambda *a: None)
    assert len(found) == 1
    assert {"inr 2,000", "inr 5,000"} <= set(found[0].values)
    assert {found[0].doc_a, found[0].doc_b} == {"Code_of_Conduct_and_Grievance.pdf", "Travel_and_Expense_Policy.pdf"}


def test_guard_rejects_invented_contradiction():
    from forgeai.guard import find_conflicts
    from forgeai.retrieval import default_index

    liar = fake_llm({"conflict": True, "about": "gift value limit", "quote_a": "Gifts are capped at INR 1,000.",
                     "quote_b": "Gifts are capped at INR 9,000.", "same_subject_reason": "made up"})
    assert find_conflicts(_hr_req(), default_index(load_folder(HR)), liar, log=lambda *a: None) == []


def test_intake_skips_questions_the_documents_answer():
    from forgeai.intake import interview

    calls = {"n": 0}

    def fn(m, j):
        u = m[-1]["content"]
        if "TASK: intake_questions" in u:
            return json.dumps({"questions": [{"question": "How many days of annual leave do employees get?", "default_answer": "x"},
                                             {"question": "Should the assistant use a formal tone?", "default_answer": "friendly"}]})
        if "TASK: guard_topic" in u and "annual leave" in u.split("EXCERPTS")[0]:
            return json.dumps({"status": "supported", "evidence_quote": "Every confirmed employee is entitled to 21 days of annual leave per leave year.", "source": ""})
        return json.dumps({"status": "unsupported", "evidence_quote": "", "source": ""})

    clar = interview("HR assistant", load_folder(HR), LLMClient("mock", "m", mock_fn=fn), interactive=False, answers_file=None, log=lambda *a: None)
    by_src = {c.source: c for c in clar}
    assert "21 days" in by_src["documents"].answer          # answered from the docs, never asked
    assert by_src["assumed"].question.startswith("Should the assistant use a formal tone")


def test_readiness_verdict_is_strict_about_hallucination():
    from forgeai.report import readiness

    sc = {"holdout_pass_rate": 0.95, "pass_rate": 0.95, "refusal_accuracy": 1.0,
          "failures_by_category": {"hallucination": 1, "retrieval_miss": 0, "wrong_refusal": 0, "prompt_defect": 0}}
    verdict, reasons = readiness(sc, _hr_req(), {"ran": True, "accuracy": 1.0})
    assert verdict == "NOT READY FOR USERS" and any("hallucination" in r for r in reasons)


def test_tools_have_input_and_output_schemas():
    from forgeai.tools import REGISTRY

    for spec in REGISTRY.values():
        d = spec.describe()
        assert d["input_schema"]["properties"] and d["output_schema"]["properties"]


def test_report_headline_uses_shipped_version_not_reverted_one(tmp_path):
    from forgeai.report import final_report
    from forgeai.schemas import AgentDefinition

    def sc(p, d, h):
        return {"pass_rate": p, "dev_pass_rate": d, "holdout_pass_rate": h, "refusal_accuracy": 1.0, "answer_fact_recall": 1, "grounded_rate": 1,
                "retrieval_hit_rate": 1, "by_type": {}, "failures_by_category": {"retrieval_miss": 0, "hallucination": 0, "wrong_refusal": 0, "prompt_defect": 0}}
    its = [{"iteration": 0, "agent_version": 0, "scorecard": sc(0.84, 0.82, 0.88), "decision": "baseline"},
           {"iteration": 1, "agent_version": 1, "scorecard": sc(0.80, 0.82, 0.75), "decision": "reverted (dev score did not improve)"}]
    d = AgentDefinition(name="x", version=0, system_prompt_sections={"role": "r"})
    rep = final_report(tmp_path, _hr_req(), d, [], [], its, [], {"ran": True, "accuracy": 1.0, "trials": 4, "decision": "ok", "details": []},
                       {}, {}, None, [], {"model": "m", "backend": "b"}, "done")
    assert "overall pass rate 84%" in rep and "holdout 88%" in rep
    assert "holdout pass rate 75%" not in rep


def test_number_words_match_digits():
    from forgeai.textutil import numbers

    assert numbers("more than two consecutive days") == {"2"}
    assert numbers("twenty one days, 1,500.00 rupees") >= {"20", "1500"}


def test_fact_necessity_check_drops_unasked_facts():
    def fn(m, j):
        u = m[-1]["content"]
        if "TASK: evalgen_fact_check" in u:
            return json.dumps({"verdicts": [{"fact": 1, "required": True}, {"fact": 2, "required": False, "why": "not asked"}]})
        return "{}"

    eg = EvalGenerator(_hr_req(), load_folder(HR), LLMClient("mock", "m", mock_fn=fn), Config(backend="mock"), log=lambda *a: None)
    kept = eg._necessary("How many weeks of maternity leave?", ["26 weeks of paid maternity leave", "up to 8 weeks before delivery"], "answerable")
    assert kept == ["26 weeks of paid maternity leave"]
    assert any("not required" in r["reason"] for r in eg.rejected)


def test_conflict_needs_same_scope_and_second_model():
    from forgeai.guard import find_conflicts
    from forgeai.retrieval import default_index

    two_suppliers = fake_llm({"applies_to_a": "Poseidon Marine Supplies", "applies_to_b": "Harbourline Spares", "conflict": True, "about": "quote validity",
                              "quote_a": "Quotations are valid for 30 days from the date of issue.", "quote_b": "Quotations are valid for 21 days from the date of issue."})
    assert find_conflicts(_hr_req(must_answer_topics=["quotation validity"]), default_index(load_folder(SP)), two_suppliers, log=lambda *a: None) == []
    real = {"applies_to_a": "gifts employees receive", "applies_to_b": "gifts employees receive on official trips", "conflict": True, "about": "gift value limit",
            "quote_a": "Employees may accept gifts or hospitality from suppliers, agents or clients only if the value is below INR 2,000 per occasion.",
            "quote_b": "Gifts received from clients or agents during an official trip may be retained if their value does not exceed INR 5,000.", "same_subject_reason": "x"}
    sceptic = fake_llm({**real, "conflict": False})
    # the judge model decides; the factory model's vote is only recorded
    assert find_conflicts(_hr_req(), default_index(load_folder(HR)), fake_llm(real), log=lambda *a: None, verifier=sceptic) == []
    checks = []
    found = find_conflicts(_hr_req(), default_index(load_folder(HR)), sceptic, log=lambda *a: None, verifier=fake_llm(real), checks=checks)
    assert len(found) == 1 and "disagreed" in found[0].reason
    assert any(c.get("outcome") == "accepted" and c.get("other_vote") is False for c in checks)


def test_guard_counts_tool_computations_as_supported():
    from forgeai.guard import check_topic
    from forgeai.retrieval import default_index

    chk = check_topic("order total with volume discount", default_index(load_folder(SP)), fake_llm({"status": "unsupported", "evidence_quote": ""}))
    assert chk.status == "supported" and "calculator" in chk.evidence
    chk = check_topic("payroll dates", default_index(load_folder(HR)), fake_llm({"status": "unsupported", "evidence_quote": ""}))
    assert chk.status == "unsupported"


def test_section_references_are_not_hallucinations():
    ctx = "Sick leave of more than 2 consecutive days must be supported by a medical certificate uploaded within 3 working days."
    resp = AgentResponse(answer="Upload a medical certificate within 3 working days, as stated in Section 5 of the Leave Policy.", refused=False,
                         citations=["Leave_Policy_Shore_Staff.pdf"], retrieved=[{"doc": "Leave_Policy_Shore_Staff.pdf", "section": "5. Sick Leave", "text": ctx, "chunk_id": "x", "score": 1}])
    r = Judge(None, use_llm=False).score(_case(key_facts=["within 3 working days"]), resp)
    assert r.grounded and r.unsupported_numbers == [] and r.passed


def test_shorthand_thousands_are_the_same_number():
    from forgeai.textutil import numbers

    assert numbers("thresholds 15k and 2.5k") == numbers("USD 15,000 and USD 2,500")


def test_regression_regenerates_and_replays_and_finds_document_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_CACHE", str(tmp_path / "cache"))
    cfg = Config(backend="mock", model="mock", interactive=False, answers_file=str(ROOT / "demos/hr_policy/answers.yaml"), max_iterations=1, tournament=False)
    f = Factory(cfg, mock_fn=mock_llm, log=lambda *a: None)
    f.build(str(ROOT / "demos/hr_policy/brief.txt"), str(ROOT / "demos/hr_policy/docs"), str(tmp_path / "hr"))
    shipped = json.loads((tmp_path / "hr" / "agent_definition.json").read_text())
    out = f.regress(str(tmp_path / "hr"), str(ROOT / "demos/hr_policy/docs_v2"), str(tmp_path / "reg"))
    replay = json.loads((tmp_path / "reg" / "agent_definition.replayed.json").read_text())
    assert replay["system_prompt_sections"] == shipped["system_prompt_sections"] and replay["version"] == shipped["version"]
    regen = json.loads((tmp_path / "reg" / "agent_definition.regenerated.json").read_text())
    assert regen["version"] == 0 and regen["docs_folder"] == replay["docs_folder"]
    assert {"pass_rate", "broke", "newly_passing"} <= set(out["regenerated"]) and {"pass_rate", "broke"} <= set(out["replayed"])
    assert "Regenerated agent" in (tmp_path / "reg" / "REGRESSION.md").read_text()
    changed = " ".join(c["old"] + " " + c["new"] for c in out["document_changes"])
    assert "21 days of annual leave" in changed and "24 days of annual leave" in changed
    assert "Uncovered" in (tmp_path / "reg" / "REGRESSION.md").read_text() or "no existing test covers" in (tmp_path / "reg" / "REGRESSION.md").read_text() or all(c["covered_by"] for c in out["document_changes"])


# --- found by the blind rehearsal (runs/rehearsal_it_helpdesk_blind) --------------------------------------
def test_brief_wording_live_data_is_found_even_if_requirements_dropped_it():
    from forgeai.guard import brief_live_needs
    it = (ROOT / "rehearsal/it_helpdesk/brief.txt").read_text()
    needs = brief_live_needs(it)
    assert any("open tickets" in n for n in needs) and any("right now" in n for n in needs)
    # tool-servable or document-only briefs are left alone
    assert brief_live_needs((ROOT / "demos/hr_policy/brief.txt").read_text()) == []
    assert brief_live_needs("Estimate the delivery date from today using the lead time.") == []


def test_live_need_from_brief_overrules_a_document_supported_topic(monkeypatch):
    from forgeai.guard import run_guard
    from forgeai.schemas import Requirements, TopicCheck
    import forgeai.guard as g
    docs = load_folder(str(ROOT / "rehearsal/it_helpdesk/docs"))
    req = Requirements(agent_name="x", purpose="p", scope="s", audience="a", tone="t",
                       must_answer_topics=["live ticket status", "password rules"], must_refuse_topics=["a", "b"])
    monkeypatch.setattr(g, "check_topic", lambda topic, index, llm: TopicCheck(topic=topic, status="supported", evidence="q", sources=["d"], method="stub"))
    monkeypatch.setattr(g, "find_conflicts", lambda *a, **k: [])
    out = run_guard(req, docs, None, log=lambda *a: None, brief="It should tell employees the live status of their open tickets.")
    status = {c.topic: c.status for c in out.groundability}
    assert status["live ticket status"] == "unsupported" and status["password rules"] == "supported"


def test_universal_scope_overlaps_a_subgroup_but_named_suppliers_do_not():
    from forgeai.guard import _same_scope
    assert _same_scope("All employees with company accounts", "New joiners")
    assert not _same_scope("Poseidon Marine Supplies", "Harbourline Spares")


def test_unattended_intake_never_assumes_an_integration():
    from forgeai.intake import INTEGRATION, NO_INTEGRATION
    assert INTEGRATION.search("What is the expected method for providing live status of open tickets?")
    assert INTEGRATION.search("Use the existing ticketing system API")
    assert "No live system" in NO_INTEGRATION


def test_judge_flags_off_topic_and_title_facts_as_suspected_test_defects():
    from forgeai.judge import _doc_reference, _off_topic
    assert _off_topic("Licences unused for 60 days are reclaimed automatically",
                      "How long does a security review for new software take before it can be installed?")
    assert not _off_topic("Laptops lock automatically after 5 minutes of inactivity", "What should I do with my laptop when leaving my desk?")
    assert _doc_reference("Software Request Procedure (IT-PRC-03)") and not _doc_reference("Compliance Officer")


def test_live_need_does_not_overrule_a_procedure_sharing_one_word(monkeypatch):
    from forgeai.guard import run_guard
    from forgeai.schemas import Requirements, TopicCheck
    import forgeai.guard as g
    docs = load_folder(str(ROOT / "rehearsal/it_helpdesk/docs"))
    req = Requirements(agent_name="x", purpose="p", scope="s", audience="a", tone="t",
                       must_answer_topics=["raise ticket", "ticket status", "system outage"], must_refuse_topics=["a", "b"])
    monkeypatch.setattr(g, "check_topic", lambda topic, index, llm: TopicCheck(topic=topic, status="supported", evidence="q", sources=["d"], method="stub"))
    monkeypatch.setattr(g, "find_conflicts", lambda *a, **k: [])
    out = run_guard(req, docs, None, log=lambda *a: None, brief=(ROOT / "rehearsal/it_helpdesk/brief.txt").read_text())
    status = {c.topic: c.status for c in out.groundability}
    assert status["raise ticket"] == "supported"
    assert status["ticket status"] == "unsupported" and status["system outage"] == "unsupported"


def test_numbered_steps_are_not_counted_as_unsupported_numbers():
    from forgeai.judge import _LIST_MARKER
    from forgeai.textutil import value_numbers
    ans = "1. Photograph the item.\n2. Report it within 7 days.\n4) Keep the packaging."
    assert value_numbers(_LIST_MARKER.sub(" ", ans)) == {"7"}


def test_live_need_already_flagged_under_another_name_is_not_added_twice(monkeypatch):
    from forgeai.guard import run_guard
    from forgeai.schemas import Requirements, TopicCheck
    import forgeai.guard as g
    docs = load_folder(str(ROOT / "demos/ship_spares/docs"))
    req = Requirements(agent_name="x", purpose="p", scope="s", audience="a", tone="t",
                       must_answer_topics=["freight quote", "lead time"], must_refuse_topics=["a", "b"])
    monkeypatch.setattr(g, "check_topic", lambda topic, index, llm: TopicCheck(topic=topic, status="unsupported" if "freight" in topic else "supported", evidence="", method="stub"))
    monkeypatch.setattr(g, "find_conflicts", lambda *a, **k: [])
    out = run_guard(req, docs, None, log=lambda *a: None, brief=(ROOT / "demos/ship_spares/brief.txt").read_text())
    assert out.ungroundable_topics == ["freight quote"]
