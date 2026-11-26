import { Background, Controls, MarkerType, Position, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import clsx from "clsx";
import { useEffect, useMemo, useState } from "react";
import { api, type AgentDefinition, type RunDetail } from "../api";
import { RunPicker, useSelectedRun } from "../components/RunPicker";
import { Badge, Card, Empty, ErrorBox, LoadingGrid, PageHeader } from "../components/ui";
import { useChartColors } from "../lib/theme";

const SECTION_ORDER = ["role", "scope", "grounding", "refusal", "tools", "style", "output_contract"];

function box(label: string, sub: string, tone: "base" | "pass" | "info" | "warn" | "fail" = "base") {
  return {
    data: {
      label: (
        <div>
          <div style={{ color: "rgb(var(--ink-100))", fontSize: 12.5, fontWeight: 500 }}>{label}</div>
          <div style={{ color: "rgb(var(--ink-400))", fontSize: 10.5, marginTop: 3, lineHeight: 1.45 }}>{sub}</div>
        </div>
      ),
    },
    className: `rf-${tone}`,
  };
}

function graph(d: AgentDefinition, sources: string[], arrow: string): { nodes: Node[]; edges: Edge[] } {
  const r = d.retrieval;
  const tools = d.tools.map((t) => t.name);
  const nodes: Node[] = [
    { id: "q", position: { x: 0, y: 110 }, ...box("User question", "plus last turn for follow ups") },
    { id: "kb", position: { x: 230, y: 0 }, ...box("Knowledge base", `${sources.length} documents · ${r.chunk_size} word chunks, ${r.chunk_overlap} overlap`, "info") },
    { id: "ret", position: { x: 230, y: 110 }, ...box("Hybrid retriever", `${r.strategy}: BM25 ×${r.bm25_weight ?? 1} + ${r.embedding?.provider ?? "none"} ×${r.dense_weight ?? 0} · RRF · top ${r.top_k}`, "info") },
    { id: "tools", position: { x: 460, y: 0 }, ...box("Tool planner", tools.length ? `attached: ${tools.join(", ") } · ≤2 rounds` : "no tools attached", tools.length ? "warn" : "base") },
    { id: "llm", position: { x: 460, y: 110 }, ...box("Agent model", `system prompt (${Object.keys(d.system_prompt_sections).length} sections) · temperature ${d.temperature}`, "pass") },
    { id: "contract", position: { x: 690, y: 110 }, ...box("Output contract", "JSON {answer, refused, citations} validated by the runtime", "pass") },
    { id: "ans", position: { x: 920, y: 60 }, ...box("Answer + citations", "citations limited to retrieved files") },
    { id: "ref", position: { x: 920, y: 170 }, ...box("Refusal", d.refusal_message.slice(0, 70), "fail") },
  ];
  nodes.forEach((n) => { n.sourcePosition = Position.Right; n.targetPosition = Position.Left; });
  const kb = nodes.find((n) => n.id === "kb")!; kb.sourcePosition = Position.Bottom;
  const ret = nodes.find((n) => n.id === "ret")!; ret.targetPosition = Position.Left;
  const e = (id: string, s: string, t: string, label?: string, dashed = false): Edge => ({
    id, source: s, target: t, label, animated: !dashed, markerEnd: { type: MarkerType.ArrowClosed, color: arrow },
    style: { stroke: "rgb(var(--ink-500))", strokeDasharray: dashed ? "4 3" : undefined }, labelStyle: { fill: "rgb(var(--ink-400))", fontSize: 10 }, labelBgStyle: { fill: "rgb(var(--ink-900))" },
  });
  const edges = [e("1", "q", "ret"), e("2", "kb", "ret", "chunks"), e("3", "ret", "llm", "excerpts"), e("6", "llm", "contract"), e("7", "contract", "ans"), e("8", "contract", "ref", "refused=true", true)];
  if (tools.length) edges.push(e("4", "ret", "tools", "context"), e("5", "tools", "llm", "tool results"));
  return { nodes, edges };
}

export default function Architecture() {
  const cc = useChartColors();
  const [run, setRun, runs] = useSelectedRun();
  const [d, setD] = useState<RunDetail | null>(null);
  const [ver, setVer] = useState<number | null>(null);
  const [def, setDef] = useState<AgentDefinition | null>(null);
  const [section, setSection] = useState("role");
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { if (run) api.run(run).then((x) => { setD(x); setDef(x.definition); setVer(x.definition.version); }).catch((e) => setErr(e.message)); }, [run]);
  useEffect(() => { if (run && d && ver !== null && ver !== d.definition.version) api.definitionVersion(run, ver).then(setDef).catch((e) => setErr(e.message)); else if (d) setDef(d.definition); }, [ver, run, d]);
  const g = useMemo(() => (def && d ? graph(def, d.requirements.knowledge_sources.map((k) => k.doc), cc.axis) : null), [def, d, cc.axis]);
  if (err) return <ErrorBox error={err} />;
  if (!runs.length) return <Empty title="No agents yet" body="Generated agents and their architecture appear here." />;
  if (!d || !def || !g) return <LoadingGrid />;
  const r = def.retrieval;
  const rejected = d.tool_selection.tools_rejected;
  return (
    <div>
      <PageHeader title="Agent architecture" subtitle="The declarative definition the factory generated, and why it chose what it chose."
        actions={<>
          <label className="flex items-center gap-2 text-xs text-ink-400">Version
            <select className="input w-20 py-1.5" value={ver ?? 0} onChange={(e) => setVer(+e.target.value)}>{d.versions.map((v) => <option key={v} value={v}>v{v}{v === d.definition.version ? " ✓" : ""}</option>)}</select></label>
          <RunPicker value={run} onChange={setRun} runs={runs} /></>} />
      <Card title={`${def.name} v${def.version}`} pad={false} actions={<span className="text-[11px] text-ink-500">drag to explore · ✓ marks the shipped version</span>}>
        <div className="h-72 bg-ink-900">
          <ReactFlow nodes={g.nodes} edges={g.edges} fitView proOptions={{ hideAttribution: true }} nodesConnectable={false}>
            <Background color={cc.grid} gap={20} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
      </Card>

      <div className="mt-4 grid items-start gap-4 lg:grid-cols-3">
        <Card title="System prompt" className="lg:col-span-2" pad={false}>
          <div className="flex gap-1 overflow-x-auto border-b border-ink-700 px-3 pt-2">
            {SECTION_ORDER.filter((s) => def.system_prompt_sections[s]).map((s) => (
              <button key={s} onClick={() => setSection(s)} className={clsx("rounded-t-md px-2.5 py-1.5 text-[12px]", section === s ? "bg-ink-800 text-ink-100" : "text-ink-400 hover:text-ink-300")}>{s.replace("_", " ")}</button>
            ))}
          </div>
          <pre className="max-h-80 overflow-y-auto whitespace-pre-wrap px-4 py-3 font-mono text-[12px] leading-relaxed text-ink-300">{def.system_prompt_sections[section]}</pre>
          <div className="border-t border-ink-700 px-4 py-2 text-[11px] text-ink-500">Variant: {def.provenance.variant}{d.tournament ? ` (won the prompt tournament)` : ""}. Sections are kept separate so the optimizer can patch one without regenerating the rest.</div>
        </Card>
        <div className="space-y-4">
          <Card title="Retrieval configuration">
            <dl className="grid grid-cols-2 gap-y-1.5 text-[12px]">
              {[["strategy", r.strategy], ["embedding", `${r.embedding?.provider}${r.embedding?.dim ? ` · ${r.embedding.dim}d` : ""}`], ["fusion", "RRF k=" + (r.rrf_k ?? 60)], ["weights", `bm25 ${r.bm25_weight} · dense ${r.dense_weight}`], ["chunk size", `${r.chunk_size} words`], ["overlap", `${r.chunk_overlap} words`], ["top k", r.top_k], ["min score", r.min_score], ["query expansions", Object.keys(r.query_expansion || {}).length]].map(([k, v]) => (
                <div key={String(k)} className="contents"><dt className="text-ink-500">{k}</dt><dd className="num text-ink-100">{String(v)}</dd></div>
              ))}
            </dl>
            {r.embedding?.note && <div className="mt-2 text-[11px] text-warn">{r.embedding.note}</div>}
            <p className="mt-3 text-[11px] leading-relaxed text-ink-500">Why: {r.derived_from}</p>
          </Card>
          <Card title="Output contract">
            <pre className="overflow-x-auto font-mono text-[11px] text-ink-300">{JSON.stringify(def.output_contract.properties, null, 1)}</pre>
          </Card>
        </div>
      </div>

      <Card title="Tool selection" className="mt-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {d.registry.map((t) => {
            const kept = def.tools.find((x) => x.name === t.name);
            const rej = rejected.find((x) => x.name === t.name);
            return (
              <div key={t.name} className={clsx("rounded-md border p-3", kept ? "border-pass/50 bg-pass-dim/30" : "border-ink-700 bg-ink-900")}>
                <div className="flex items-center justify-between"><span className="font-mono text-[12px] text-ink-100">{t.name}</span>{kept ? <Badge tone="pass">attached</Badge> : rej ? <Badge tone="fail">rejected</Badge> : <Badge>not needed</Badge>}</div>
                <p className="mt-1.5 text-[11px] text-ink-400">{t.description}</p>
                <p className="mt-2 text-[11px] text-ink-300">{kept ? `Why: ${kept.reason || "requirements need it"}${kept.evidence?.length ? ` (evidence: ${kept.evidence.slice(0, 4).join(", ")})` : ""}` : rej ? rej.reason : "Not proposed; nothing in the requirements calls for it."}</p>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
