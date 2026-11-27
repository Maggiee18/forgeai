import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, type Job } from "../api";

/** Polls a background job and streams its log lines. Calls onDone once with the final job. */
export function useJob(jobId: string | null, onDone?: (j: Job) => void) {
  const [lines, setLines] = useState<string[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const since = useRef(0);
  const done = useRef(false);
  useEffect(() => {
    if (!jobId) return;
    since.current = 0;
    done.current = false;
    setLines([]);
    let timer: number;
    const tick = async () => {
      try {
        const j = await api.job(jobId, since.current);
        since.current = j.next;
        if (j.log.length) setLines((l) => [...l, ...j.log]);
        setJob(j);
        if (j.state !== "running") {
          if (!done.current) {
            done.current = true;
            onDone?.(j);
          }
          return;
        }
      } catch (e) {
        // the server restarted (free hosting sleeps when idle) and forgot this job: stop polling and say so
        if (String((e as Error)?.message || "").includes("job not found")) {
          const lost: Job = { id: jobId, state: "failed", kind: "", log: [], next: 0, result: null, elapsed_s: 0,
            error: "The server restarted while this ran (free hosting sleeps after about 15 minutes without visitors), so the job was lost. Please start it again." };
          setJob(lost);
          if (!done.current) { done.current = true; onDone?.(lost); }
          return;
        }
        /* transient network error: keep polling */
      }
      timer = window.setTimeout(tick, 1200);
    };
    tick();
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);
  return { lines, job };
}

export function JobLog({ lines, job, title }: { lines: string[]; job: Job | null; title: string }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [lines.length]);
  const state = job?.state ?? "running";
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-ink-700 px-4 py-2 text-[13px]">
        <span className="flex items-center gap-2 text-ink-100">
          {state === "running" && <Loader2 className="h-4 w-4 animate-spin text-pass" />}
          {state === "done" && <CheckCircle2 className="h-4 w-4 text-pass" />}
          {state === "failed" && <XCircle className="h-4 w-4 text-fail" />}
          {title}
        </span>
        <span className="num text-[11px] text-ink-500">{job ? `${job.elapsed_s.toFixed(0)} s` : ""}</span>
      </div>
      <pre className="max-h-80 overflow-y-auto bg-ink-900 px-4 py-3 font-mono text-[11.5px] leading-relaxed text-ink-400">
        {lines.map((l, i) => (
          <div key={i} className={l.includes("⚠") || l.startsWith("ERROR") ? "text-warn" : /PASS/.test(l) ? "text-ink-300" : /\bfail\b/.test(l) ? "text-fail/80" : undefined}>{l || " "}</div>
        ))}
        {state === "running" && <div className="animate-pulse text-pass">▍</div>}
        <div ref={end} />
      </pre>
      {job?.error && <div className="border-t border-fail/40 px-4 py-2 text-[13px] text-fail">{job.error}</div>}
    </div>
  );
}
