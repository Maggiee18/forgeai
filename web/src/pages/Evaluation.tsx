import clsx from "clsx";
import { Check, ChevronDown, ChevronRight, ShieldCheck, X } from "lucide-react";
import { Fragment, useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, CATEGORY_LABEL, pct, type CaseResult, type EvalCase, type RunDetail } from "../api";
import { RunPicker, useSelectedRun } from "../components/RunPicker";
import { Badge, Card, Empty, ErrorBox, LoadingGrid, PageHeader, tone } from "../components/ui";
import { useChartColors } from "../lib/theme";

const TYPES = ["answerable", "cross_doc", "ambiguous", "conflict", "tool", "out_of_scope", "ungroundable"];

function Yes({ ok, label }: { ok: boolean; label: string }) {
  return <span className={clsx("inline-flex items-center gap-1 text-[11px]", ok ? "text-pass" : "text-fail")}>{ok ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}{label}</span>;
}

function CaseDetail({ c, r }: { c: EvalCase; r: CaseResult }) {
  return (
    <div className="grid gap-4 bg-ink-900 px-5 py-4 text-[12px] lg:grid-cols-2">
      <div className="space-y-3">
        <div>
          <div className="label mb-1">Expected behaviour</div>
          {c.expected_behavior === "refuse" ? <div><Badge tone="info">refuse</Badge> <span className="ml-1 text-ink-300">{c.refusal_reason}</span></div> : (
            <ul className="space-y-1">
              {c.key_facts.map((f) => <li key={f} className="flex gap-2">{r.facts_matched.includes(f) ? <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-pass" /> : <X className="mt-0.5 h-3.5 w-3.5 shrink-0 text-fail" />}<span>{f}</span></li>)}
            </ul>
          )}
        </div>
        {c.evidence.length > 0 && (
          <div>
            <div className="label mb-1">Supporting evidence in the documents</div>
            {c.evidence.map((e, i) => <blockquote key={i} className="mb-1.5 border-l-2 border-ink-600 pl-2 text-ink-400"><span className="text-ink-500">{e.doc}:</span> "{e.quote}"</blockquote>)}
          </div>
        )}
        <div className="text-ink-500">Origin: {c.origin}{c.note ? ` · ${c.note}` : ""}</div>
      </div>
      <div className="space-y-3">
        <div>
          <div className="label mb-1">Agent answer {r.refused && <Badge tone="info">refused</Badge>}</div>
          <p className="whitespace-pre-wrap rounded-md border border-ink-700 bg-ink-850 p-2.5 leading-relaxed text-ink-100">{r.answer}</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Yes ok={r.refusal_ok} label="refusal correct" />
          <Yes ok={r.grounded} label="grounded" />
          <Yes ok={r.cited_expected} label="cited expected source" />
          <Yes ok={r.retrieval_hit} label="retrieved expected source" />
          <Yes ok={r.contract_ok} label="contract" />
        </div>
        <div className="grid grid-cols-2 gap-2 text-ink-400">
          <div>Cited: <span className="text-ink-300">{r.citations.join(", ") || "none"}</span></div>
          <div>Retrieved: <span className="text-ink-300">{r.retrieved_sources.join(", ") || "none"}</span></div>
          <div>Fact recall: <span className="num text-ink-100">{pct(r.fact_recall)}</span></div>
          <div>Citation precision: <span className="num text-ink-100">{pct(r.citation_precision)}</span></div>
          {r.answer_relevance !== null && <div>Relevance: <span className="num text-ink-100">{r.answer_relevance.toFixed(2)}</span></div>}
          <div>Judge: <span className="text-ink-300">{r.judge_method}</span></div>
        </div>
        {r.unsupported_numbers.length > 0 && <div className="text-fail">Numbers with no source: {r.unsupported_numbers.join(", ")}</div>}
        {r.tool_calls.length > 0 && <div><div className="label mb-1">Tool calls</div>{r.tool_calls.map((t, i) => <div key={i} className="font-mono text-[11px] text-ink-400">{t.tool}({JSON.stringify(t.args)}) → {JSON.stringify(t.result ?? t.error).slice(0, 160)}</div>)}</div>}
        {!r.passed && <div className="rounded-md border border-warn/30 bg-warn-dim/40 p-2 text-warn"><span className="text-ink-100">{CATEGORY_LABEL[r.failure_category || ""] || r.failure_category}:</span> {r.diagnosis}</div>}
      </div>
    </div>
  );
}

export default function Evaluation() {
  const cc = useChartColors();
  const [run, setRun, runs] = useSelectedRun();
  const [d, setD] = useState<RunDetail | null>(null);
  const [cases, setCases] = useState<EvalCase[]>([]);
  const [results, setResults] = useState<CaseResult[] | null>(null);
  const [iter, setIter] = useState<number | "final">("final");
  const [filter, setFilter] = useState({ type: "all", status: "all", split: "all" });
  const [open, setOpen] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { if (run) { setD(null); setResults(null); Promise.all([api.run(run), api.evalset(run)]).then(([x, e]) => { setD(x); setCases(e); }).catch((e) => setErr(e.message)); } }, [run]);
  useEffect(() => { if (run) api.results(run, iter === "final" ? undefined : iter).then(setResults).catch((e) => setErr(e.message)); }, [run, iter]);
  const byId = useMemo(() => Object.fromEntries(cases.map((c) => [c.id, c])), [cases]);
  if (err) return <ErrorBox error={err} />;
  if (!runs.length) return <Empty title="No evaluations yet" body="Each build generates its own test set from the documents; results land here." />;
  if (!d || !results) return <LoadingGrid />;
  const sc = iter === "final" ? d.scorecard.reduce((a, b) => ((b.scorecard.dev_pass_rate ?? 0) > (a.scorecard.dev_pass_rate ?? 0) ? b : a)).scorecard : d.scorecard.find((s) => s.iteration === iter)?.scorecard;
  const shown = results.filter((r) => (filter.type === "all" || r.type === filter.type) && (filter.status === "all" || (filter.status === "pass" ? r.passed : !r.passed)) && (filter.split === "all" || r.split === filter.split));
  const typeChart = TYPES.filter((t) => sc?.by_type[t]).map((t) => ({ type: t.replaceAll("_", " "), pass: Math.round((sc!.by_type[t].pass_rate ?? 0) * 100), n: sc!.by_type[t].n }));
  const st = d.judge_selftest;
  return (
    <div>
      <PageHeader title="Evaluation center" subtitle={`${cases.length} test cases generated from the documents, never written by hand. Failed cases stay visible.`}
        actions={<>
          <label className="flex items-center gap-2 text-xs text-ink-400">Iteration
            <select className="input w-32 py-1.5" value={iter} onChange={(e) => setIter(e.target.value === "final" ? "final" : +e.target.value)}>
              <option value="final">shipped</option>{d.scorecard.map((s) => <option key={s.iteration} value={s.iteration}>{s.iteration} (v{s.agent_version})</option>)}</select></label>
          <RunPicker value={run} onChange={setRun} runs={runs} /></>} />
      {sc && (
        <div className="card grid grid-cols-2 divide-ink-700 sm:grid-cols-4 xl:grid-cols-8 xl:divide-x">
          {([["Overall", sc.pass_rate, true], ["Dev", sc.dev_pass_rate, true], ["Holdout", sc.holdout_pass_rate, true], ["Fact recall", sc.answer_fact_recall, false],
             ["Refusals", sc.refusal_accuracy, true], ["Grounded", sc.grounded_rate, true], ["Citations", sc.citation_precision, false], ["Retrieval", sc.retrieval_hit_rate, false]] as [string, number | null, boolean][]).map(([label, v, toned]) => (
            <div key={label} className="px-5 py-4">
              <div className="text-[12px] text-ink-500">{label}</div>
              <div className={`num mt-1 text-[24px] ${toned ? `text-${tone(v)}` : "text-ink-100"}`}>{pct(v)}</div>
            </div>
          ))}
        </div>
      )}
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Pass rate by test category" className="lg:col-span-2">
          <div className="h-44"><ResponsiveContainer><BarChart data={typeChart}><CartesianGrid stroke={cc.grid} vertical={false} /><XAxis dataKey="type" stroke={cc.axis} fontSize={11} tickLine={false} axisLine={false} /><YAxis stroke={cc.axis} fontSize={11} unit="%" domain={[0, 100]} tickLine={false} axisLine={false} width={40} /><Tooltip contentStyle={cc.tooltip} cursor={{ fill: cc.cursor }} formatter={(v, _n, p) => [`${v}% of ${p.payload.n}`, "pass"]} /><Bar dataKey="pass" fill={cc.strong} radius={[6, 6, 0, 0]} animationDuration={800} /></BarChart></ResponsiveContainer></div>
        </Card>
        <Card title={<span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-pass" /> Judge reliability</span>}>
          {st.ran ? (<>
            <div className="num text-2xl text-ink-100">{pct(st.accuracy)}</div>
            <div className="text-[12px] text-ink-400">agreement with known grades over {st.trials} synthetic trials</div>
            <div className="mt-2 text-[12px] text-ink-300">{st.decision}</div>
            <p className="mt-3 text-[11px] leading-relaxed text-ink-500">Deterministic checks decide first. The {d.config.judge_model || d.config.model} judge can only add credit by quoting the answer verbatim with every value present. It grades against fixed facts, never answer against answer, so there is no position bias.</p>
          </>) : <div className="text-[12px] text-ink-400">{st.reason}</div>}
          {sc && (sc.suspected_eval_defects ?? 0) > 0 && <div className="mt-3 text-[12px] text-warn">{sc.suspected_eval_defects} failure(s) may be test defects; listed in the report.</div>}
        </Card>
      </div>

      <Card title="Individual results" className="mt-4" pad={false}
        actions={<div className="flex gap-2">
          <select className="input w-36 py-1" value={filter.type} onChange={(e) => setFilter({ ...filter, type: e.target.value })}><option value="all">all types</option>{TYPES.map((t) => <option key={t}>{t}</option>)}</select>
          <select className="input w-28 py-1" value={filter.status} onChange={(e) => setFilter({ ...filter, status: e.target.value })}><option value="all">all</option><option value="pass">passed</option><option value="fail">failed</option></select>
          <select className="input w-28 py-1" value={filter.split} onChange={(e) => setFilter({ ...filter, split: e.target.value })}><option value="all">dev + holdout</option><option value="dev">dev</option><option value="holdout">holdout</option></select>
        </div>}>
        <table className="w-full text-[12.5px]">
          <thead><tr className="border-b border-ink-700 text-left text-[11px] text-ink-500"><th className="w-8" /><th className="py-2">Case</th><th>Question</th><th>Type</th><th>Split</th><th>Facts</th><th>Result</th></tr></thead>
          <tbody>
            {shown.map((r) => (
              <Fragment key={r.case_id}>
                <tr className="cursor-pointer border-b border-ink-700/60 hover:bg-ink-800/50" onClick={() => setOpen(open === r.case_id ? null : r.case_id)}>
                  <td className="pl-3 text-ink-500">{open === r.case_id ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}</td>
                  <td className="num py-2 text-ink-400">{r.case_id}</td>
                  <td className="max-w-md truncate pr-3 text-ink-100">{r.question}</td>
                  <td><Badge>{r.type.replaceAll("_", " ")}</Badge></td>
                  <td className="text-ink-400">{r.split}</td>
                  <td className="num">{r.expected_behavior === "refuse" ? "n/a" : `${r.facts_matched.length}/${r.facts_matched.length + r.facts_missing.length}`}</td>
                  <td className="pr-3">{r.passed ? <Badge tone="pass">pass</Badge> : <Badge tone={r.failure_category === "hallucination" ? "fail" : "warn"} title={r.diagnosis}>{CATEGORY_LABEL[r.failure_category || ""] || "fail"}{r.suspected_eval_defect ? " · test?" : ""}</Badge>}</td>
                </tr>
                {open === r.case_id && byId[r.case_id] && <tr><td colSpan={7}><CaseDetail c={byId[r.case_id]} r={r} /></td></tr>}
              </Fragment>
            ))}
          </tbody>
        </table>
        {!shown.length && <div className="px-4 py-6 text-center text-[13px] text-ink-500">No cases match these filters.</div>}
      </Card>

      {d.eval_generation.rejected.length > 0 && (
        <Card title={`Rejected while generating the test set (${d.eval_generation.rejected.length})`} className="mt-4">
          <ul className="space-y-1 text-[12px]">{d.eval_generation.rejected.map((x, i) => <li key={i}><Badge>{x.type}</Badge> <span className="text-ink-400">{x.reason}</span> <span className="text-ink-500">· {typeof x.candidate === "string" ? x.candidate : JSON.stringify(x.candidate)?.slice(0, 120)}</span></li>)}</ul>
        </Card>
      )}
    </div>
  );
}
