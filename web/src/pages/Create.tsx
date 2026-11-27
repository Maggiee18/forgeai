import clsx from "clsx";
import { ArrowRight, FileSpreadsheet, FileText, Info, MessagesSquare, Sparkles, Upload, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api, type Question, type Workspace } from "../api";
import { JobLog, useJob } from "../components/JobLog";
import { Badge, Card, ErrorBox, PageHeader, Spinner } from "../components/ui";

const ACCEPT = ".pdf,.csv,.txt,.md,.docx";

function Steps({ at }: { at: number }) {
  const steps = ["Brief and documents", "Inspect", "Interview", "Requirements review", "Build"];
  return (
    <ol className="mb-6 flex flex-wrap items-center gap-2 text-[12px]">
      {steps.map((s, i) => (
        <li key={s} className="flex items-center gap-2">
          <span className={clsx("flex h-5 w-5 items-center justify-center rounded-full border num text-[10px]",
            i < at ? "border-pass bg-pass-dim text-pass" : i === at ? "border-ink-300 text-ink-100" : "border-ink-700 text-ink-500")}>{i + 1}</span>
          <span className={i === at ? "text-ink-100" : "text-ink-500"}>{s}</span>
          {i < steps.length - 1 && <span className="mx-1 h-px w-6 bg-ink-700" />}
        </li>
      ))}
    </ol>
  );
}

export default function Create() {
  const { wid } = useParams();
  const nav = useNavigate();
  const [brief, setBrief] = useState("");
  const [drag, setDrag] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [ws, setWs] = useState<Workspace | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const loc = useLocation();
  const [notice, setNotice] = useState<string | null>((loc.state as { notice?: string } | null)?.notice ?? null);
  const [qs, setQs] = useState<Question[] | null>(null);
  const [answers, setAnswers] = useState<string[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const { lines, job } = useJob(jobId, (j) => {
    if (j.state === "done" && ws) nav(`/requirements?ws=${ws.id}`);
  });

  useEffect(() => {
    if (wid) api.workspace(wid).then((w) => { setWs(w); if (w.questions) { setQs(w.questions); setAnswers(w.questions.map((q) => q.default_answer)); } }).catch((e) => {
      if (String(e.message).includes("workspace not found")) {
        // free hosting wipes its disk when it sleeps: start a fresh workspace instead of showing an error
        setWs(null); setQs(null); setJobId(null);
        const msg = "This session was cleared. The free server restarts after about 15 minutes without visitors and forgets unfinished work. Start again below; the demonstration runs are always kept.";
        setNotice(msg);
        nav("/create", { replace: true, state: { notice: msg } });
      } else setErr(e.message);
    });
  }, [wid]);

  const step = !ws ? 0 : !qs ? 1 : !jobId ? 2 : 3;

  async function inspect() {
    setErr(null); setNotice(null);
    if (brief.trim().length < 20) return setErr("Write at least one full sentence describing the assistant you need.");
    if (!files.length) return setErr("Add at least one document for the agent to answer from.");
    setBusy("Reading documents…");
    try {
      const w = await api.createWorkspace(brief, files);
      setWs(w);
      nav(`/create/${w.id}`, { replace: true });
    } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  }

  async function demo(name: string) {
    setErr(null); setNotice(null);
    setBusy("Loading demo…");
    try {
      const w = await api.demoWorkspace(name);
      setWs(w);
      nav(`/create/${w.id}`, { replace: true });
    } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  }

  async function interview() {
    if (!ws) return;
    setErr(null);
    setBusy("The interviewer is reading your brief and documents…");
    try {
      const q = await api.questions(ws.id);
      setQs(q);
      setAnswers(q.map((x) => x.default_answer));
    } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  }

  async function requirements() {
    if (!ws) return;
    setErr(null);
    try {
      const r = await api.requirements(ws.id, answers);
      setJobId(r.job_id);
    } catch (e) { setErr((e as Error).message); }
  }

  return (
    <div>
      {ws && <PageHeader title="Create agent" subtitle="A one paragraph brief plus the documents the agent must answer from." />}
      <div className={clsx(!ws && "flex justify-center")}><Steps at={step} /></div>
      {notice && !ws && (
        <div className="card mb-4 flex items-start gap-3 px-4 py-3 text-[13px]">
          <Info size={16} className="mt-0.5 shrink-0 text-ink-500" />
          <div className="flex-1 text-ink-500">{notice}</div>
          <button className="text-ink-500 hover:text-ink-100" onClick={() => setNotice(null)} aria-label="Dismiss"><X size={14} /></button>
        </div>
      )}
      {err && <div className="mb-4"><ErrorBox error={err} /></div>}

      {!ws && (
        <div className="mx-auto max-w-[760px] pt-4">
          <h2 className="serif text-center text-[30px] leading-tight text-ink-100 sm:text-[36px]">What should your agent do?</h2>
          <p className="mx-auto mt-3 max-w-lg text-center text-[14px] leading-relaxed text-ink-400">Describe it in a paragraph and attach the documents it must answer from. ForgeAI interviews you, checks the documents can support the brief, then builds and tests the agent.</p>
          <div className={clsx("mt-8 rounded-[22px] border bg-ink-850 p-3 transition-colors", drag ? "border-ink-100" : "border-ink-700 focus-within:border-ink-500")}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); setFiles((f) => [...f, ...Array.from(e.dataTransfer.files)]); }}>
            <textarea className="h-36 w-full resize-none bg-transparent px-2 py-1.5 text-[15px] leading-relaxed text-ink-100 placeholder:text-ink-500 focus:outline-none" value={brief} onChange={(e) => setBrief(e.target.value)}
              placeholder="I need an assistant that answers HR policy questions for our shore staff about leave, travel claims and the code of conduct." aria-label="Brief" />
            {files.length > 0 && (
              <div className="flex flex-wrap gap-1.5 px-1 pb-2">
                {files.map((f, i) => (
                  <span key={i} className="flex items-center gap-1.5 rounded-full border border-ink-700 bg-ink-950 py-1 pl-2.5 pr-1.5 text-[12px] text-ink-300">
                    {/\.csv$/i.test(f.name) ? <FileSpreadsheet className="h-3.5 w-3.5" /> : <FileText className="h-3.5 w-3.5" />}{f.name}<span className="text-ink-500">{(f.size / 1024).toFixed(0)} KB</span>
                    <button aria-label={`Remove ${f.name}`} onClick={() => setFiles(files.filter((_, j) => j !== i))} className="rounded-full p-0.5 hover:bg-ink-800"><X className="h-3 w-3" /></button>
                  </span>
                ))}
              </div>
            )}
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-ink-700 pt-3">
              <div className="flex items-center gap-2">
                <label className="btn cursor-pointer"><Upload className="h-4 w-4" /> Attach documents<input type="file" multiple accept={ACCEPT} className="hidden" onChange={(e) => setFiles((f) => [...f, ...Array.from(e.target.files || [])])} /></label>
                <span className="hidden text-[12px] text-ink-500 sm:inline">PDF, CSV, TXT, MD, DOCX · or drop them here</span>
              </div>
              <button className="btn btn-primary" onClick={inspect} disabled={!!busy}>{busy ? <Spinner label="" /> : <ArrowRight className="h-4 w-4" />} Inspect documents</button>
            </div>
          </div>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-2 text-[13px] text-ink-500">
            Or start from a demonstration
            <button className="btn" onClick={() => demo("hr_policy")} disabled={!!busy}>HR policy assistant</button>
            <button className="btn" onClick={() => demo("ship_spares")} disabled={!!busy}>Ship spares procurement</button>
          </div>
          {busy && <div className="mt-4 flex justify-center"><Spinner label={busy} /></div>}
        </div>
      )}

      {ws && (
        <div className="space-y-4">
          <Card title="Brief"><p className="text-[13px] leading-relaxed text-ink-300">{ws.brief}</p></Card>
          <Card title={`What ForgeAI extracted from ${ws.inventory.length} document${ws.inventory.length === 1 ? "" : "s"}`}>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {ws.inventory.map((d) => (
                <div key={d.doc} className="rounded-md border border-ink-700 bg-ink-900 p-3">
                  <div className="flex items-center gap-2 text-[13px] text-ink-100">
                    {d.kind === "csv" ? <FileSpreadsheet className="h-4 w-4 text-info" /> : <FileText className="h-4 w-4 text-ink-400" />}
                    <span className="truncate">{d.doc}</span>
                  </div>
                  <div className="mt-1 text-[11px] text-ink-500">
                    {d.kind === "csv" ? `${d.rows} rows · ${d.columns?.length} columns` : `${d.pages} pages · ${d.words} words · ${d.sections?.length ?? 0} sections`}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {(d.kind === "csv" ? d.columns : d.sections?.slice(1))?.slice(0, 10).map((s) => <Badge key={s}>{s.replace(/^\d+(\.\d+)*\.?\s*/, "")}</Badge>)}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {!qs && (
            <div className="flex items-center gap-3">
              <button className="btn btn-primary" onClick={interview} disabled={!!busy}><MessagesSquare className="h-4 w-4" /> Start intake interview</button>
              {busy && <Spinner label={busy} />}
            </div>
          )}

          {qs && !jobId && (
            <Card title={`Clarifying questions (${qs.length} of at most 5)`}>
              <p className="mb-3 text-[12px] text-ink-500">Edit any answer. Questions the documents already answer are removed automatically in the next step. Unchanged defaults are recorded as assumptions.</p>
              <div className="space-y-4">
                {qs.map((q, i) => (
                  <div key={i}>
                    <div className="text-[13px] text-ink-100">{i + 1}. {q.question}</div>
                    {q.why && <div className="mb-1.5 text-[11px] text-ink-500">Why it matters: {q.why}</div>}
                    <input className="input" value={answers[i] ?? ""} onChange={(e) => setAnswers(answers.map((a, j) => (j === i ? e.target.value : a)))} />
                  </div>
                ))}
              </div>
              <button className="btn btn-primary mt-4" onClick={requirements}><Sparkles className="h-4 w-4" /> Write requirements and check groundability</button>
            </Card>
          )}

          {jobId && <JobLog title="Writing requirements · checking groundability and conflicts" lines={lines} job={job} />}
        </div>
      )}
    </div>
  );
}
