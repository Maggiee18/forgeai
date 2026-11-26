import clsx from "clsx";
import { ArrowRight, RotateCcw, ShieldAlert, Wrench } from "lucide-react";
import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, CATEGORY_LABEL, pct, type Change, type RunDetail } from "../api";
import { RunPicker, useSelectedRun } from "../components/RunPicker";
import { Badge, Card, Empty, ErrorBox, LoadingGrid, PageHeader } from "../components/ui";
import { useChartColors } from "../lib/theme";


function LineDiff({ before, after }: { before: string; after: string }) {
  const b = new Set(before.split("\n").map((l) => l.trim()));
  const a = new Set(after.split("\n").map((l) => l.trim()));
  return (
    <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap break-words rounded-md border border-ink-700 bg-ink-900 p-2.5 font-mono text-[11px] leading-relaxed">
      {before.split("\n").filter((l) => l.trim() && !a.has(l.trim())).map((l, i) => <div key={`r${i}`} className="text-fail/90">- {l}</div>)}
      {after.split("\n").map((l, i) => <div key={i} className={b.has(l.trim()) ? "text-ink-500" : "text-pass"}>{b.has(l.trim()) ? "  " : "+ "}{l}</div>)}
    </pre>
  );
}

function ChangeView({ c }: { c: Change }) {
  return (
    <div className="rounded-md border border-ink-700 p-3">
      <div className="flex flex-wrap items-center gap-2 text-[12px]">
        <Badge tone="warn">{CATEGORY_LABEL[c.category] || c.category}</Badge><ArrowRight className="h-3 w-3 text-ink-500" /><span className="font-mono text-ink-100">{c.target}</span>
        {c.skipped && <Badge>skipped</Badge>}
      </div>
      <p className="mt-2 text-[12px] text-ink-300">{c.rationale || c.skipped}</p>
      {c.addressed_cases && <div className="mt-1.5 text-[11px] text-ink-500">Targeted: {c.addressed_cases.join(", ")}{c.fixed_cases ? <> · <span className="text-pass">fixed: {c.fixed_cases.join(", ") || "none"}</span></> : null}</div>}
      {c.target === "retrieval" && c.before && (
        <div className="mt-2 grid grid-cols-3 gap-x-4 gap-y-0.5 font-mono text-[11px]">
          <span className="text-ink-500">param</span><span className="text-ink-500">before</span><span className="text-ink-500">after</span>
          {Object.keys(c.before).map((k) => <><span key={k} className="text-ink-400">{k}</span><span className="text-ink-300">{String(c.before[k])}</span><span className={c.before[k] !== c.after?.[k] ? "text-pass" : "text-ink-300"}>{String(c.after?.[k])}</span></>)}
        </div>
      )}
      {c.learned_expansions && Object.keys(c.learned_expansions).length > 0 && (
        <div className="mt-2 text-[11px] text-ink-400">Learned query expansions: {Object.entries(c.learned_expansions).map(([u, d]) => <span key={u} className="mr-2 font-mono"><span className="text-ink-300">{u}</span> → {d.join(" / ")}</span>)}</div>
      )}
      {c.target?.startsWith("prompt.") && typeof c.before === "string" && typeof c.after === "string" && <div className="mt-2"><LineDiff before={c.before} after={c.after} /></div>}
    </div>
  );
}

export default function Optimization() {
  const cc = useChartColors();
  const [run, setRun, runs] = useSelectedRun();
  const [d, setD] = useState<RunDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState(0);
  useEffect(() => { if (run) { setD(null); api.run(run).then((x) => { setD(x); setSel(0); }).catch((e) => setErr(e.message)); } }, [run]);
  if (err) return <ErrorBox error={err} />;
  if (!runs.length) return <Empty title="Nothing optimized yet" body="The critic and optimizer loop runs after the first evaluation of each new agent." />;
  if (!d) return <LoadingGrid />;
  const chart = d.scorecard.map((s) => ({ it: `it ${s.iteration}`, Dev: Math.round((s.scorecard.dev_pass_rate ?? 0) * 100), Holdout: Math.round((s.scorecard.holdout_pass_rate ?? 0) * 100), decision: s.decision }));
  const log = d.iteration_log;
  const it = log[sel];
  const stop = d.stop_reason || log.find((x) => x.stop_reason)?.stop_reason;
  const stages = ["Run evals", "Classify failures", "Targeted fix", "Re-run + keep or revert"];
  return (
    <div>
      <PageHeader title="Optimization lab" subtitle="Run evals → classify every failure → one targeted fix per category → re-run. At most three iterations, every change logged." actions={<RunPicker value={run} onChange={setRun} runs={runs} />} />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Score per iteration" className="lg:col-span-2">
          <div className="h-56"><ResponsiveContainer><LineChart data={chart}><CartesianGrid stroke={cc.grid} vertical={false} /><XAxis dataKey="it" axisLine={false} stroke={cc.axis} fontSize={11} tickLine={false} /><YAxis stroke={cc.axis} fontSize={11} unit="%" domain={[0, 100]} tickLine={false} axisLine={false} width={40} />
            <Tooltip contentStyle={cc.tooltip} formatter={(v, n) => [`${v}%`, n]} labelFormatter={(l, p) => `${l} · ${p?.[0]?.payload?.decision ?? ""}`} /><Legend wrapperStyle={{ fontSize: 11 }} />
            <Line type="monotone" dataKey="Dev" stroke={cc.strong} strokeWidth={2} dot={{ r: 4, fill: cc.strong }} animationDuration={900} /><Line type="monotone" dataKey="Holdout" stroke={cc.info} strokeWidth={2} strokeDasharray="5 4" dot={{ r: 4, fill: cc.info }} animationDuration={1100} /></LineChart></ResponsiveContainer></div>
          <p className="mt-1 text-[11px] text-ink-500">Only dev failures reach the optimizer. Holdout shows whether a fix generalises or just overfits the dev cases.</p>
        </Card>
        <Card title="The loop">
          <div className="space-y-2">
            {stages.map((s, i) => (
              <div key={s} className="flex items-center gap-3">
                <span className="num flex h-6 w-6 items-center justify-center rounded-full border border-pass/60 text-[11px] text-pass">{i + 1}</span>
                <span className="text-[13px] text-ink-100">{s}</span>
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-md border border-ink-700 bg-ink-900 p-3 text-[12px]">
            <div className="label">Iterations run</div><div className="num text-ink-100">{log.length} of 3</div>
            <div className="label mt-2">Stopped because</div><div className="text-ink-300">{stop || (log.length >= 3 ? "reached the 3 iteration limit" : log.length === 0 ? "no dev failures to fix" : "loop finished")}</div>
          </div>
          <p className="mt-3 flex gap-2 text-[11px] text-ink-500"><ShieldAlert className="h-3.5 w-3.5 shrink-0" /> Patches that quote test questions are rejected, and suspected test defects are never sent to the optimizer.</p>
        </Card>
      </div>

      {log.length === 0 ? (
        <div className="mt-4"><Empty title="No optimization iterations" body="Iteration 0 had no dev failures the optimizer could act on." /></div>
      ) : (
        <div className="mt-4 grid gap-4 lg:grid-cols-4">
          <div className="space-y-2">
            {log.map((x, i) => (
              <button key={i} onClick={() => setSel(i)} className={clsx("card w-full px-3 py-2.5 text-left transition-colors", sel === i ? "border-pass/60" : "hover:border-ink-600")}>
                <div className="flex items-center justify-between text-[13px] text-ink-100">Iteration {x.iteration}{x.decision?.startsWith("kept") ? <Badge tone="pass">kept</Badge> : x.decision?.startsWith("reverted") ? <Badge tone="fail"><RotateCcw className="h-3 w-3" /> reverted</Badge> : <Badge>{x.decision}</Badge>}</div>
                <div className="num mt-1 text-[12px] text-ink-400">dev {pct(x.dev_before)} → {pct(x.dev_after)}</div>
                <div className="text-[11px] text-ink-500">v{x.from_version} → v{x.to_version}</div>
              </button>
            ))}
          </div>
          {it && (
            <Card className="lg:col-span-3" title={<span className="flex items-center gap-2"><Wrench className="h-4 w-4 text-warn" /> Iteration {it.iteration}: {it.decision}</span>}>
              <div className="grid grid-cols-2 gap-3 text-[12px] md:grid-cols-4">
                <div><div className="label">Dev before → after</div><div className="num text-ink-100">{pct(it.dev_before)} → {pct(it.dev_after)}</div></div>
                <div><div className="label">Holdout before → after</div><div className="num text-ink-100">{pct(it.holdout_before)} → {pct(it.holdout_after)}</div></div>
                <div><div className="label">Newly fixed</div><div className="text-pass">{it.newly_fixed?.join(", ") || "none"}</div></div>
                <div><div className="label">Newly broken</div><div className={it.newly_broken?.length ? "text-fail" : "text-ink-400"}>{it.newly_broken?.join(", ") || "none"}</div></div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-[12px]"><span className="label">Failures going in (dev + holdout; only dev reach the optimizer):</span>{Object.entries(it.failures_in).map(([k, v]) => <Badge key={k} tone={v ? "warn" : "muted"}>{CATEGORY_LABEL[k]} {v}</Badge>)}</div>
              <div className="mt-4 space-y-3">{it.changes.map((c, i) => <ChangeView key={i} c={c} />)}</div>
              {it.stop_reason && <div className="mt-3 text-[12px] text-ink-400">Loop stopped: {it.stop_reason}</div>}
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
