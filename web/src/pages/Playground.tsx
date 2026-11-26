import clsx from "clsx";
import { ArrowUp, FileText, Loader2, PanelRightClose, PanelRightOpen, RotateCcw, Wrench } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, type AgentOption, type ChatResponse } from "../api";
import { Badge, Empty, ErrorBox } from "../components/ui";

type Turn = { q: string; r?: ChatResponse; error?: string };

function Inspector({ r }: { r?: ChatResponse }) {
  if (!r) return <p className="text-[13px] leading-relaxed text-ink-500">Ask something. The passages the retriever handed to the model, any tool calls and the citations appear here, so you can see exactly where an answer came from.</p>;
  return (
    <div className="space-y-7">
      <section>
        <div className="label mb-2">Agent</div>
        <div className="text-[13px] text-ink-100">{r.agent.name} <span className="text-ink-500">v{r.agent.version}</span></div>
        <div className="mt-1 text-[12px] text-ink-400">{r.agent.retrieval.strategy} retrieval · top {r.agent.retrieval.top_k} · tools: {r.agent.tools.join(", ") || "none"}</div>
      </section>
      {r.refused && (
        <section>
          <div className="label mb-2">Why it declined</div>
          <p className="text-[13px] leading-relaxed text-ink-300">The agent set <code className="font-mono text-[12px]">refused: true</code>. Either the question is outside its scope, or none of the retrieved passages contain the answer. It is built never to fill a gap from memory.</p>
        </section>
      )}
      {r.tool_calls.length > 0 && (
        <section>
          <div className="label mb-2">Tool calls</div>
          {r.tool_calls.map((t, i) => (
            <div key={i} className="mb-3 border-l-2 border-accent pl-3 font-mono text-[11.5px] leading-relaxed">
              <div className="text-accent">{t.tool}<span className="text-ink-400">({JSON.stringify(t.args)})</span></div>
              <div className="text-ink-500">→ {JSON.stringify(t.result ?? t.error).slice(0, 260)}</div>
            </div>
          ))}
        </section>
      )}
      <section>
        <div className="label mb-2">Retrieved passages ({r.retrieved.length})</div>
        <div className="space-y-4">
          {r.retrieved.map((p, i) => (
            <div key={p.chunk_id} className={clsx("border-l-2 pl-3", r.citations.includes(p.doc) ? "border-pass" : "border-ink-700")}>
              <div className="mb-1 flex justify-between text-[11px] text-ink-500"><span>{i + 1}. {p.doc}{r.citations.includes(p.doc) ? " · cited" : ""}</span><span className="num">{p.score.toFixed(3)}</span></div>
              <p className="line-clamp-5 text-[12.5px] leading-relaxed text-ink-300">{p.text}</p>
            </div>
          ))}
        </div>
      </section>
      {!r.contract_ok && <section className="text-[12px] text-warn">Output contract warnings: {r.contract_errors.join("; ")}</section>}
    </div>
  );
}

export default function Playground() {
  const [agents, setAgents] = useState<AgentOption[] | null>(null);
  const [sel, setSel] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [focus, setFocus] = useState<number | null>(null);
  const [inspect, setInspect] = useState(() => window.innerWidth >= 1280);
  const [err, setErr] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    api.agents().then((a) => {
      setAgents(a);
      const want = new URLSearchParams(window.location.search).get("run");
      setSel((a.find((x) => x.run === want) || a[0])?.id ?? "");
    }).catch((e) => setErr(e.message));
  }, []);
  // block body on purpose: newer browsers return a Promise from scrollIntoView, which React would treat as a cleanup
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, busy]);
  const agent = agents?.find((a) => a.id === sel);
  const shown = focus !== null ? turns[focus]?.r : [...turns].reverse().find((t) => t.r)?.r;

  async function send(text?: string) {
    const q = (text ?? input).trim();
    if (!q || !agent || busy) return;
    setInput("");
    setBusy(true);
    const history = turns.filter((t) => t.r).slice(-4).map((t) => [t.q, t.r!.answer] as [string, string]);
    setTurns((t) => [...t, { q }]);
    setFocus(null);
    try {
      const r = await api.chat({ run: agent.run, baseline: agent.baseline, message: q, history });
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, r } : x)));
    } catch (e) {
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, error: (e as Error).message } : x)));
    } finally {
      setBusy(false);
      box.current?.focus();
    }
  }

  if (err) return <ErrorBox error={err} />;
  if (agents && !agents.length) return <Empty title="No agents to talk to yet" body="Every definition the factory produces can be loaded here. Build one first." />;
  const name = agent?.label.split(" (")[0] ?? "the agent";
  const suggestions = agent?.tools.includes("csv_lookup")
    ? ["What is the price and lead time of ME-FI-1021?", "Who must approve a USD 30,000 order?", "What are today's freight rates to Singapore?"]
    : ["How many days of annual leave do I get?", "Can I keep a gift worth INR 3,000 from a client?", "What is my salary band?"];

  return (
    <div className="-mx-5 -my-7 flex h-[calc(100vh-70px)] sm:-mx-8 lg:-mx-10 lg:-my-9">
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between gap-3 px-5 py-3 sm:px-8">
          <select className="btn max-w-[60vw] cursor-pointer appearance-none pr-8 text-[13px]" style={{ backgroundImage: "none" }} value={sel} onChange={(e) => { setSel(e.target.value); setTurns([]); }} aria-label="Agent">
            {agents?.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
          </select>
          <div className="flex items-center gap-1">
            {turns.length > 0 && <button className="btn border-transparent bg-transparent px-2" onClick={() => setTurns([])} aria-label="New conversation"><RotateCcw className="h-4 w-4" /></button>}
            <button className="btn border-transparent bg-transparent px-2" onClick={() => setInspect(!inspect)} aria-label={inspect ? "Hide inspector" : "Show inspector"}>{inspect ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}<span className="hidden text-[12px] sm:inline">Inspect</span></button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-[720px] px-5 py-10 sm:px-8">
            {!turns.length && (
              <div className="pt-[8vh] text-center">
                <h1 className="serif mt-3 text-[30px] leading-tight text-ink-100">Ask {name} anything.</h1>
                <p className="mx-auto mt-3 max-w-md text-[14px] leading-relaxed text-ink-400">Real retrieval, real tools, a real model. Nothing here is scripted, including the refusals.</p>
                <div className="mt-8 flex flex-wrap justify-center gap-2">{suggestions.map((s) => <button key={s} className="btn text-[13px]" onClick={() => send(s)}>{s}</button>)}</div>
              </div>
            )}
            <div className="space-y-10">
              {turns.map((t, i) => (
                <div key={i} className="animate-fadein">
                  <div className="flex justify-end"><div className="max-w-[85%] rounded-[22px] bg-ink-800 px-4 py-2.5 text-[14.5px] text-ink-100">{t.q}</div></div>
                  {t.r && (
                    <div className={clsx("mt-4 cursor-pointer rounded-2xl p-3 -mx-3 transition-colors hover:bg-ink-850", focus === i && "bg-ink-850")} onClick={() => { setFocus(i); setInspect(true); }}>
                      {t.r.refused && <div className="mb-2"><Badge tone="info">declined</Badge></div>}
                      <p className="whitespace-pre-wrap text-[15px] leading-[1.75] text-ink-300">{t.r.answer}</p>
                      <div className="mt-3 flex flex-wrap items-center gap-1.5">
                        {t.r.citations.map((c) => <Badge key={c}><FileText className="h-3 w-3" />{c}</Badge>)}
                        {t.r.tool_calls.map((c, k) => <Badge key={k} tone="warn"><Wrench className="h-3 w-3" />{c.tool}</Badge>)}
                        <span className="num ml-1 text-[11px] text-ink-500">{t.r.latency_s}s</span>
                      </div>
                    </div>
                  )}
                  {t.error && <div className="mt-3 text-[13px] text-fail">Couldn't get an answer: {t.error}</div>}
                </div>
              ))}
              {busy && <div className="flex items-center gap-2 text-[13px] text-ink-500"><Loader2 className="h-4 w-4 animate-spin" /> Retrieving passages and answering…</div>}
            </div>
            <div ref={end} />
          </div>
        </div>

        <form className="px-5 pb-5 pt-2 sm:px-8" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <div className="mx-auto flex max-w-[760px] flex-col gap-2 rounded-[22px] border border-ink-700 bg-ink-850 p-3 shadow-sm transition-colors focus-within:border-ink-500">
            <textarea ref={box} rows={1} className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-[15px] text-ink-100 placeholder:text-ink-500 focus:outline-none w-full" value={input} maxLength={2000}
              onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} placeholder={`Message ${name}`} />
            <div className="flex items-center justify-between"><span className="rounded-full border border-ink-700 px-3 py-1 text-[12px] text-ink-400">{agent?.tools.length ? `tools: ${agent.tools.join(", ")}` : "documents only"}</span><button className="btn btn-primary" disabled={busy || !input.trim()} aria-label="Send"><ArrowUp className="h-4 w-4" /> Send</button></div>
          </div>
        </form>
      </div>

      {inspect && (
        <aside className="fixed inset-y-0 right-0 z-30 w-[min(380px,90vw)] animate-fadein overflow-y-auto border-l border-ink-700 bg-ink-850 px-6 py-6 xl:static xl:z-auto xl:rounded-r-2xl">
          <div className="mb-6 flex items-center justify-between"><h2 className="serif text-[17px] text-ink-100">Inspect</h2><button className="btn border-transparent bg-transparent px-2 xl:hidden" onClick={() => setInspect(false)} aria-label="Close inspector"><PanelRightClose className="h-4 w-4" /></button></div>
          <Inspector r={shown} />
        </aside>
      )}
    </div>
  );
}
