import { AlertTriangle, CheckCircle2, CircleSlash, FileText, GitCompare, HelpCircle, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, type Requirements } from "../api";
import { JobLog, useJob } from "../components/JobLog";
import { RunPicker, useSelectedRun } from "../components/RunPicker";
import { Badge, Card, Empty, ErrorBox, LoadingGrid, PageHeader } from "../components/ui";

const SRC_TONE = { requester: "pass", answers_file: "pass", documents: "info", assumed: "warn" } as const;
const SRC_LABEL = { requester: "you answered", answers_file: "recorded answer", documents: "answered by documents", assumed: "assumption" };

function ListEditor({ label, value, onChange, editable }: { label: string; value: string[]; onChange: (v: string[]) => void; editable: boolean }) {
  if (!editable)
    return (
      <div>
        <div className="label mb-1.5">{label}</div>
        <div className="flex flex-wrap gap-1.5">{value.length ? value.map((t) => <Badge key={t}>{t}</Badge>) : <span className="text-[12px] text-ink-500">none</span>}</div>
      </div>
    );
  return (
    <div>
      <div className="label mb-1.5">{label} <span className="text-ink-500">(one per line)</span></div>
      <textarea className="input h-28 font-mono text-[12px]" value={value.join("\n")} onChange={(e) => onChange(e.target.value.split("\n").map((s) => s.trim()).filter(Boolean))} />
    </div>
  );
}

function Field({ label, value, onChange, editable }: { label: string; value: string; onChange: (v: string) => void; editable: boolean }) {
  return (
    <div>
      <div className="label mb-1">{label}</div>
      {editable ? <input className="input" value={value} onChange={(e) => onChange(e.target.value)} /> : <div className="text-[13px] text-ink-100">{value}</div>}
    </div>
  );
}

export function RequirementsView({ req, setReq, editable }: { req: Requirements; setReq?: (r: Requirements) => void; editable: boolean }) {
  const set = <K extends keyof Requirements>(k: K, v: Requirements[K]) => setReq?.({ ...req, [k]: v });
  const unsupported = req.groundability.filter((g) => g.status === "unsupported").length;
  const partial = req.groundability.filter((g) => g.status === "partial").length;
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Agent" className="lg:col-span-2">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Name" value={req.agent_name} onChange={(v) => set("agent_name", v)} editable={editable} />
            <Field label="Audience" value={req.audience} onChange={(v) => set("audience", v)} editable={editable} />
            <Field label="Purpose" value={req.purpose} onChange={(v) => set("purpose", v)} editable={editable} />
            <Field label="Tone" value={req.tone} onChange={(v) => set("tone", v)} editable={editable} />
            <div className="md:col-span-2"><Field label="Scope" value={req.scope} onChange={(v) => set("scope", v)} editable={editable} /></div>
          </div>
        </Card>
        <Card title="Groundability at a glance">
          <div className="space-y-2 text-[13px]">
            <div className="flex justify-between"><span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-pass" /> Supported topics</span><span className="num">{req.groundability.length - unsupported - partial}</span></div>
            <div className="flex justify-between"><span className="flex items-center gap-2"><HelpCircle className="h-4 w-4 text-warn" /> Partly supported</span><span className="num">{partial}</span></div>
            <div className="flex justify-between"><span className="flex items-center gap-2"><CircleSlash className="h-4 w-4 text-fail" /> Not in documents</span><span className="num">{unsupported}</span></div>
            <div className="flex justify-between"><span className="flex items-center gap-2"><GitCompare className="h-4 w-4 text-fail" /> Contradictions</span><span className="num">{req.conflicts.length}</span></div>
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card><ListEditor label="Must answer" value={req.must_answer_topics} onChange={(v) => set("must_answer_topics", v)} editable={editable} /></Card>
        <Card><ListEditor label="Must refuse" value={req.must_refuse_topics} onChange={(v) => set("must_refuse_topics", v)} editable={editable} /></Card>
        <Card><ListEditor label="Tool needs" value={req.tool_needs} onChange={(v) => set("tool_needs", v)} editable={editable} /></Card>
      </div>

      {(req.flags.length > 0 || req.conflicts.length > 0) && (
        <Card title={<span className="flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-warn" /> Raised before generation</span>}>
          {req.conflicts.map((c) => (
            <div key={c.about} className="mb-3 rounded-md border border-fail/30 bg-fail-dim/40 p-3 text-[13px]">
              <div className="text-ink-100">Documents contradict each other on <span className="text-fail">{c.about}</span></div>
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                <blockquote className="rounded border border-ink-700 bg-ink-900 p-2 text-[12px]"><div className="mb-1 font-mono text-[11px] text-ink-500">{c.doc_a}</div>"{c.quote_a}"</blockquote>
                <blockquote className="rounded border border-ink-700 bg-ink-900 p-2 text-[12px]"><div className="mb-1 font-mono text-[11px] text-ink-500">{c.doc_b}</div>"{c.quote_b}"</blockquote>
              </div>
              {c.reason && <div className="mt-2 text-[11px] text-ink-500">Same subject because: {c.reason}</div>}
            </div>
          ))}
          <ul className="space-y-1.5 text-[13px]">
            {req.flags.filter((f) => !f.startsWith("Conflicting")).map((f) => <li key={f} className="flex gap-2"><span className="text-warn">⚠</span>{f}</li>)}
          </ul>
          {req.recommendations.length > 0 && (
            <div className="mt-3 border-t border-ink-700 pt-3">
              <div className="label mb-1">Recommended clarification or scope change</div>
              <ul className="list-disc space-y-1 pl-5 text-[13px]">{req.recommendations.map((r) => <li key={r}>{r}</li>)}</ul>
            </div>
          )}
        </Card>
      )}

      <Card title="Groundability check per topic" pad={false}>
        <div className="divide-y divide-ink-700">
          {req.groundability.map((g) => (
            <div key={g.topic} className="grid grid-cols-12 gap-3 px-4 py-2.5 text-[13px]">
              <div className="col-span-3 text-ink-100">{g.topic}</div>
              <div className="col-span-2"><Badge tone={g.status === "supported" ? "pass" : g.status === "partial" ? "warn" : "fail"}>{g.status}</Badge></div>
              <div className="col-span-5 text-[12px] text-ink-400">{g.evidence ? `"${g.evidence}"` : <span className="text-ink-500">no evidence found</span>}</div>
              <div className="col-span-2 text-[11px] text-ink-500">{g.sources.join(", ")}<div className="text-ink-600">{g.method}</div></div>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Intake interview">
          <ol className="space-y-3 text-[13px]">
            {req.clarifications.map((c, i) => (
              <li key={i}>
                <div className="flex items-start justify-between gap-2"><span className="text-ink-100">{c.question}</span><Badge tone={SRC_TONE[c.source]}>{SRC_LABEL[c.source]}</Badge></div>
                <div className="mt-0.5 text-[12px] text-ink-400">{c.answer}</div>
              </li>
            ))}
          </ol>
        </Card>
        <div className="space-y-4">
          <Card title="Knowledge sources">
            <ul className="space-y-2 text-[12px]">
              {req.knowledge_sources.map((k) => (
                <li key={k.doc}><span className="flex items-center gap-1.5 text-ink-100"><FileText className="h-3.5 w-3.5" />{k.doc}</span>
                  <span className="text-ink-500">{k.size} · {k.covers.slice(0, 8).join(", ")}</span></li>
              ))}
            </ul>
          </Card>
          <Card title="Known limitations, uncertainties and assumptions">
            <ul className="list-disc space-y-1 pl-5 text-[12px]">
              {[...req.known_limitations, ...req.uncertainties].map((x) => <li key={x}>{x}</li>)}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}

function WorkspaceRequirements({ wid }: { wid: string }) {
  const nav = useNavigate();
  const [req, setReq] = useState<Requirements | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [iters, setIters] = useState(3);
  const [tourn, setTourn] = useState(true);
  const [jobId, setJobId] = useState<string | null>(null);
  const [runName, setRunName] = useState("");
  const { lines, job } = useJob(jobId, (j) => { if (j.state === "done") setTimeout(() => nav(`/evaluation?run=${runName}`), 1200); });
  useEffect(() => {
    api.workspace(wid).then((w) => { setReq(w.requirements); setName((w.requirements?.agent_name || "agent").replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 40)); }).catch((e) => setErr(e.message));
  }, [wid]);
  if (err) return <ErrorBox error={err} />;
  if (!req) return <LoadingGrid />;
  async function build() {
    setErr(null);
    if (!/^[a-zA-Z0-9_-]{1,60}$/.test(name)) return setErr("Run names may only use letters, digits, - and _.");
    try {
      const r = await api.build(wid, { run_name: name, requirements: req!, max_iterations: iters, tournament: tourn });
      setRunName(r.run_name);
      setJobId(r.job_id);
    } catch (e) { setErr((e as Error).message); }
  }
  return (
    <div>
      <PageHeader title="Requirements review" subtitle="Human checkpoint: edit anything, then approve. Generation only starts after you approve." />
      {!jobId && <RequirementsView req={req} setReq={setReq} editable />}
      <Card className="mt-4" title="Approve and build">
        {!jobId ? (
          <div className="flex flex-wrap items-end gap-4">
            <label className="w-56"><div className="label mb-1">Run name</div><input className="input" value={name} onChange={(e) => setName(e.target.value)} /></label>
            <label><div className="label mb-1">Optimizer iterations (max 3)</div>
              <select className="input w-28" value={iters} onChange={(e) => setIters(+e.target.value)}>{[0, 1, 2, 3].map((n) => <option key={n}>{n}</option>)}</select></label>
            <label className="flex items-center gap-2 pb-2 text-[13px]"><input type="checkbox" checked={tourn} onChange={(e) => setTourn(e.target.checked)} /> Prompt tournament</label>
            <button className="btn btn-primary" onClick={build}><Play className="h-4 w-4" /> Approve requirements and build</button>
          </div>
        ) : (
          <JobLog title={`Building ${runName}: generate → eval → critic → optimizer`} lines={lines} job={job} />
        )}
        {err && <div className="mt-3"><ErrorBox error={err} /></div>}
      </Card>
    </div>
  );
}

export default function RequirementsPage() {
  const [params] = useSearchParams();
  const ws = params.get("ws");
  const [run, setRun, runs] = useSelectedRun();
  const [detail, setDetail] = useState<Requirements | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { if (!ws && run) api.run(run).then((d) => setDetail(d.requirements)).catch((e) => setErr(e.message)); }, [run, ws]);
  if (ws) return <WorkspaceRequirements wid={ws} />;
  return (
    <div>
      <PageHeader title="Requirements" subtitle="What the intake interviewer and groundability guard decided, before any agent was generated." actions={<RunPicker value={run} onChange={setRun} runs={runs} />} />
      {err ? <ErrorBox error={err} /> : !runs.length ? <Empty title="No runs yet" body="Create an agent to see its requirements here." /> : detail ? <RequirementsView req={detail} editable={false} /> : <LoadingGrid />}
    </div>
  );
}
