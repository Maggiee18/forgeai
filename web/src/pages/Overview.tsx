import { ArrowUpRight, Plus } from "lucide-react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, CATEGORY_LABEL, pct, type RunSummaryExtra } from "../api";
import { Badge, Empty, ErrorBox, LoadingGrid, ScoreBar, tone } from "../components/ui";
import { useAsync } from "../lib/hooks";
import { useChartColors } from "../lib/theme";

function readinessTone(r: string | null) {
  if (!r) return "muted" as const;
  if (r.startsWith("READY")) return "pass" as const;
  if (r.startsWith("PILOT")) return "warn" as const;
  return "fail" as const;
}

function Figure({ label, value, note, className = "" }: { label: string; value: string; note?: string; className?: string }) {
  return (
    <div className={`px-0 py-1 sm:px-6 sm:first:pl-0 ${className}`}>
      <div className="label">{label}</div>
      <div className="serif mt-2 text-[34px] leading-none text-ink-100">{value}</div>
      {note && <div className="mt-2 text-[12px] text-ink-500">{note}</div>}
    </div>
  );
}

export default function Overview() {
  const { data, error, loading, reload } = useAsync(api.overview, []);
  const c = useChartColors();
  if (loading && !data) return <LoadingGrid />;
  if (error) return <ErrorBox error={error} retry={reload} />;
  if (!data) return null;
  const runs = data.runs as RunSummaryExtra[];
  const failTotals: Record<string, number> = {};
  runs.forEach((r) => Object.entries(r.failures || {}).forEach(([k, v]) => (failTotals[k] = (failTotals[k] || 0) + v)));
  const totalFails = Object.values(failTotals).reduce((a, b) => a + b, 0);
  const chart = runs.map((r) => ({ name: r.name, "Iteration 0": Math.round((r.initial_pass_rate ?? 0) * 100), Shipped: Math.round((r.final_pass_rate ?? 0) * 100), Holdout: Math.round((r.holdout_pass_rate ?? 0) * 100) }));
  const flags = runs.reduce((a, r) => a + r.flags, 0);

  if (!runs.length)
    return (
      <div>
        <div className="eyebrow mb-3">Overview</div>
        <h1 className="serif max-w-3xl text-[36px] leading-[1.1] text-ink-100">Give it a paragraph and a folder. Get back a tested agent.</h1>
        <div className="mt-10"><Empty title="Build your first agent" body="ForgeAI interviews you, checks the documents can support the brief, generates the agent, writes its exam from the documents, and reports honestly how it did." action={<Link to="/create" className="btn btn-primary"><Plus className="h-4 w-4" /> Create agent</Link>} /></div>
      </div>
    );

  return (
    <div>
      <div className="mb-10 flex flex-wrap items-end justify-between gap-6">
        <div className="max-w-3xl">
          <h1 className="serif text-[30px] leading-[1.15] text-ink-100 sm:text-[40px]">
            {data.agents_generated === 1 ? "1 agent built, passing" : `${data.agents_generated} agents built, passing`} <span className="text-ink-100 underline decoration-ink-600 decoration-2 underline-offset-[6px]">{pct(data.avg_final_pass_rate)}</span> of {data.agents_generated === 1 ? "its own exam" : "their own exams"}{data.agents_generated === 1 ? "" : " on average"}.
          </h1>
          <p className="mt-4 text-[15px] leading-relaxed text-ink-400">
            {(data.avg_final_pass_rate ?? 0) > (data.avg_initial_pass_rate ?? 0) ? `Up from ${pct(data.avg_initial_pass_rate)} at first evaluation` : (data.avg_final_pass_rate ?? 0) < (data.avg_initial_pass_rate ?? 0) ? `Down from ${pct(data.avg_initial_pass_rate)} at first evaluation` : "Unchanged since first evaluation; the optimizer kept nothing that didn't help"}, across {data.total_eval_cases} test cases generated from the documents. Every figure on this page is read from stored run artifacts.
          </p>
        </div>
        </div>

      {data.status.mock_mode && (
        <div className="mb-8 rounded-xl border border-warn/30 bg-warn-dim/60 px-4 py-3 text-[13px] text-ink-300">
          No model is reachable (no API key and no Ollama), so new builds here use the deterministic offline stand-in. Each run below records the model that built it.
        </div>
      )}

      <div className="card grid grid-cols-2 gap-y-6 px-6 py-6 sm:grid-cols-4 sm:divide-x sm:divide-ink-700">
        <Figure label="Agents" value={String(data.agents_generated)} note={`${data.successful_builds} evaluated`} />
        <Figure label="Test cases" value={String(data.total_eval_cases)} note="generated, never hand written" />
        <Figure label="Iterations" value={String(data.total_iterations)} note="critic and optimizer rounds" />
        <Figure label="Guard flags" value={String(flags)} note="raised before generation" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        <section className="card p-6 lg:col-span-3">
          <div className="mb-4 flex items-baseline justify-between"><h2 className="serif text-[17px] text-ink-100">Pass rate by agent</h2><span className="text-[12px] text-ink-500">iteration 0 → shipped, with holdout</span></div>
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={chart} barGap={4} barCategoryGap="28%">
                <CartesianGrid stroke={c.grid} vertical={false} />
                <XAxis dataKey="name" stroke={c.axis} fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke={c.axis} fontSize={11} tickLine={false} axisLine={false} unit="%" domain={[0, 100]} width={40} />
                <Tooltip contentStyle={c.tooltip} cursor={{ fill: c.cursor }} formatter={(v) => `${v}%`} />
                <Bar dataKey="Iteration 0" fill={c.muted} radius={[6, 6, 0, 0]} animationDuration={700} />
                <Bar dataKey="Shipped" fill={c.strong} radius={[6, 6, 0, 0]} animationDuration={900} />
                <Bar dataKey="Holdout" fill={c.info} radius={[6, 6, 0, 0]} animationDuration={1100} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 flex flex-wrap gap-5 text-[12px] text-ink-400">
            <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-ink-600" />Iteration 0</span>
            <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-ink-100" />Shipped</span>
            <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-ink-400" />Holdout, never seen by the optimizer</span>
          </div>
        </section>
        <section className="card p-6 lg:col-span-2">
          <div className="mb-4 flex items-baseline justify-between"><h2 className="serif text-[17px] text-ink-100">What still fails</h2><span className="num text-[12px] text-ink-500">{totalFails} cases</span></div>
          <div className="space-y-5">
            {Object.entries(CATEGORY_LABEL).map(([k, label]) => (
              <div key={k}>
                <div className="mb-1.5 flex items-baseline justify-between text-[13px]"><span className="text-ink-300">{label}</span><span className="num text-ink-100">{failTotals[k] ?? 0}</span></div>
                <ScoreBar value={totalFails ? (failTotals[k] ?? 0) / totalFails : 0} tone={k === "hallucination" ? "fail" : "warn"} />
              </div>
            ))}
          </div>
          <p className="mt-6 text-[12px] leading-relaxed text-ink-500">Each failure is classified by a deterministic critic from what the agent retrieved, cited and stated. Failures stay visible; nothing is filtered out to flatter the score.</p>
        </section>
      </div>

      <section className="card mt-6 overflow-hidden">
        <h2 className="serif border-b border-ink-700 px-6 py-4 text-[17px] text-ink-100">Factory runs</h2>
        <div>
          {runs.map((r) => (
            <Link key={r.name} to={`/evaluation?run=${r.name}`} className="group grid grid-cols-2 items-center gap-4 border-b border-ink-700 px-6 py-4 transition-colors last:border-0 hover:bg-ink-950/60 sm:grid-cols-12">
              <div className="col-span-2 sm:col-span-4">
                <div className="text-[15px] font-medium capitalize text-ink-100">{r.name.replace(/_/g, " ")}</div>
                <div className="mt-1 text-[12px] text-ink-500">{r.agent_name} v{r.agent_version} · {r.model?.split("/").pop()} · judged by {r.judge_model?.split("/").pop()}</div>
              </div>
              <div className="sm:col-span-3">
                <div className="num text-[13px] text-ink-400">{pct(r.initial_pass_rate)} → <span className={`text-${tone(r.final_pass_rate)}`}>{pct(r.final_pass_rate)}</span> <span className="text-ink-500">· holdout {pct(r.holdout_pass_rate)}</span></div>
                <div className="mt-2"><ScoreBar value={r.final_pass_rate} /></div>
              </div>
              <div className="flex flex-wrap gap-1 sm:col-span-2">{r.tools.length ? r.tools.map((t) => <Badge key={t}>{t}</Badge>) : <span className="text-[12px] text-ink-500">no tools</span>}</div>
              <div className="sm:col-span-2"><Badge tone={readinessTone(r.readiness)}>{(r.readiness || "not evaluated").toLowerCase()}</Badge></div>
              <div className="hidden justify-end text-ink-500 transition-colors group-hover:text-accent sm:col-span-1 sm:flex"><ArrowUpRight className="h-4 w-4" /></div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
