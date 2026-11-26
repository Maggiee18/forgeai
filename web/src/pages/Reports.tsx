import clsx from "clsx";
import { Download, FileArchive } from "lucide-react";
import { marked } from "marked";
import { useEffect, useState } from "react";
import { api } from "../api";
import { RunPicker, useSelectedRun } from "../components/RunPicker";
import { Empty, ErrorBox, PageHeader, Skeleton } from "../components/ui";

const ARTIFACTS = [
  { file: "REPORT.md", label: "Quality report", kind: "md" },
  { file: "requirements.md", label: "Requirements document", kind: "md" },
  { file: "scorecard.md", label: "Final scorecard", kind: "md" },
  { file: "iteration_log.md", label: "Iteration log", kind: "md" },
  { file: "requirements.json", label: "Requirements JSON", kind: "json" },
  { file: "agent_definition.json", label: "Agent definition JSON", kind: "json" },
  { file: "evalset.jsonl", label: "Evaluation dataset", kind: "json" },
  { file: "final_results.jsonl", label: "Evaluation results", kind: "json" },
  { file: "iteration_log.json", label: "Iteration log JSON", kind: "json" },
  { file: "scorecard.json", label: "Scorecard JSON", kind: "json" },
  { file: "judge_selftest.json", label: "Judge self test", kind: "json" },
  { file: "budget.json", label: "Token and time budget", kind: "json" },
];

export default function Reports() {
  const [run, setRun, runs] = useSelectedRun();
  const [file, setFile] = useState("REPORT.md");
  const [text, setText] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!run) return;
    setText(null);
    setErr(null);
    fetch(api.fileUrl(run, file)).then(async (r) => { if (!r.ok) throw new Error(`${file} is not in this run`); setText(await r.text()); }).catch((e) => setErr(e.message));
  }, [run, file]);
  if (!runs.length) return <Empty title="No reports yet" body="Every build writes its requirements, definition, eval set, iteration log, scorecard and report here." />;
  const art = ARTIFACTS.find((a) => a.file === file)!;
  let body: string | null = text;
  if (text && art.kind === "json") {
    try { body = file.endsWith(".jsonl") ? text.trim().split("\n").map((l) => JSON.stringify(JSON.parse(l), null, 2)).join("\n\n") : JSON.stringify(JSON.parse(text), null, 2); } catch { body = text; }
  }
  const md = ARTIFACTS.filter((a) => a.kind === "md");
  const data = ARTIFACTS.filter((a) => a.kind === "json");
  const Pill = ({ a }: { a: (typeof ARTIFACTS)[number] }) => (
    <button onClick={() => setFile(a.file)} className={clsx("rounded-full border px-3 py-1.5 text-[12.5px] transition-colors", file === a.file ? "border-ink-100 bg-ink-100 text-ink-850" : "border-ink-700 bg-ink-850 text-ink-400 hover:text-ink-100")}>{a.label}</button>
  );
  return (
    <div>
      <PageHeader title="Reports and artifacts" subtitle="Everything the factory produced for this run, exactly as committed."
        actions={<>{run && <a className="btn btn-primary" href={api.zipUrl(run)}><FileArchive className="h-4 w-4" /> Download all</a>}<RunPicker value={run} onChange={setRun} runs={runs} /></>} />
      <div className="mb-2 flex flex-wrap items-center gap-2"><span className="mr-1 text-[12px] text-ink-500">Documents</span>{md.map((a) => <Pill key={a.file} a={a} />)}</div>
      <div className="mb-6 flex flex-wrap items-center gap-2"><span className="mr-1 text-[12px] text-ink-500">Data</span>{data.map((a) => <Pill key={a.file} a={a} />)}</div>
      <article className="mx-auto max-w-[820px] rounded-2xl border border-ink-700 bg-ink-850 shadow-sm">
        <header className="flex items-center justify-between border-b border-ink-700 px-8 py-4 sm:px-12">
          <span className="font-mono text-[12px] text-ink-500">{run} / {file}</span>
          {run && <a href={api.fileUrl(run, file)} download className="btn py-1 text-[12px]"><Download className="h-3.5 w-3.5" /> Download</a>}
        </header>
        <div className="px-8 py-10 sm:px-12 sm:py-12">
          {err ? <ErrorBox error={err} /> : body === null ? <div className="space-y-3"><Skeleton className="h-8 w-2/3" /><Skeleton className="h-4 w-1/2" /><Skeleton className="h-48" /></div>
            : art.kind === "md" ? <div className="prose-md" dangerouslySetInnerHTML={{ __html: marked.parse(body, { async: false }) as string }} />
            : <pre className="max-h-[70vh] overflow-auto font-mono text-[12px] leading-relaxed text-ink-300">{body}</pre>}
        </div>
      </article>
    </div>
  );
}
