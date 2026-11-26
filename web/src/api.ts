// Typed client for the ForgeAI FastAPI backend. Every view reads real artifacts through these calls.

export type Scorecard = {
  n_cases: number;
  pass_rate: number | null;
  dev_pass_rate: number | null;
  holdout_pass_rate: number | null;
  by_type: Record<string, { n: number; pass_rate: number | null }>;
  answer_fact_recall: number | null;
  completeness: number | null;
  citation_precision: number | null;
  answer_relevance: number | null;
  refusal_accuracy: number | null;
  wrong_refusals_on_answerable: number;
  grounded_rate: number | null;
  contract_ok_rate: number | null;
  retrieval_hit_rate: number | null;
  failures_by_category: Record<"retrieval_miss" | "hallucination" | "wrong_refusal" | "prompt_defect", number>;
  suspected_eval_defects?: number;
  avg_latency_s: number | null;
};

export type IterationScore = { iteration: number; agent_version: number; scorecard: Scorecard; decision: string };

export type RunSummary = {
  name: string;
  agent_name: string;
  agent_version: number;
  description: string;
  tools: string[];
  n_cases: number;
  initial_pass_rate: number | null;
  final_pass_rate: number | null;
  dev_pass_rate: number | null;
  holdout_pass_rate: number | null;
  iterations: number;
  flags: number;
  conflicts: number;
  ungroundable: string[];
  tokens: number | null;
  elapsed_s: number | null;
  model: string;
  judge_model: string | null;
  backend: string;
  created: number | null;
  readiness: string | null;
};

export type Status = {
  backend: string;
  model: string;
  agent_model: string;
  judge_model: string;
  api_key_present: boolean;
  embedding: { provider: string; model?: string; dim?: number };
  mock_mode: boolean;
  running_jobs: number;
};

export type Overview = {
  agents_generated: number;
  successful_builds: number;
  avg_final_pass_rate: number | null;
  avg_initial_pass_rate: number | null;
  total_eval_cases: number;
  total_iterations: number;
  total_tokens: number;
  runs: RunSummary[];
  status: Status;
};

export type TopicCheck = { topic: string; status: "supported" | "partial" | "unsupported"; evidence: string; sources: string[]; method: string };
export type Conflict = { about: string; doc_a: string; quote_a: string; doc_b: string; quote_b: string; reason: string; values: string[] };
export type Clarification = { question: string; why: string; answer: string; source: "requester" | "assumed" | "answers_file" | "documents" };

export type Requirements = {
  agent_name: string;
  purpose: string;
  scope: string;
  audience: string;
  tone: string;
  must_answer_topics: string[];
  must_refuse_topics: string[];
  tool_needs: string[];
  clarifications: Clarification[];
  groundability: TopicCheck[];
  ungroundable_topics: string[];
  conflicts: Conflict[];
  knowledge_sources: { doc: string; kind: string; size: string; covers: string[] }[];
  known_limitations: string[];
  uncertainties: string[];
  flags: string[];
  recommendations: string[];
  approved: boolean;
  approval_note: string;
};

export type ToolRef = { name: string; reason?: string; evidence?: string[]; schema?: { input_schema: unknown; output_schema: unknown; description: string } };

export type AgentDefinition = {
  name: string;
  version: number;
  description: string;
  system_prompt_sections: Record<string, string>;
  retrieval: Record<string, any>;
  tools: ToolRef[];
  output_contract: Record<string, any>;
  refusal_message: string;
  docs_folder: string;
  temperature: number;
  provenance: Record<string, any>;
};

export type EvalCase = {
  id: string;
  type: string;
  question: string;
  expected_behavior: "answer" | "refuse";
  expected_sources: string[];
  key_facts: string[];
  evidence: { doc: string; quote: string }[];
  refusal_reason: string;
  split: "dev" | "holdout";
  origin: string;
  note: string;
};

export type CaseResult = {
  case_id: string;
  type: string;
  split: string;
  question: string;
  expected_behavior: string;
  answer: string;
  refused: boolean;
  citations: string[];
  retrieved_sources: string[];
  tool_calls: any[];
  contract_ok: boolean;
  refusal_ok: boolean;
  fact_recall: number;
  facts_matched: string[];
  facts_missing: string[];
  grounded: boolean;
  unsupported_numbers: string[];
  cited_expected: boolean;
  citation_precision: number;
  answer_relevance: number | null;
  retrieval_hit: boolean;
  passed: boolean;
  suspected_eval_defect: boolean;
  failure_category: string | null;
  diagnosis: string;
  judge_method: string;
  latency_s: number;
};

export type Change = {
  category: string;
  target: string;
  before?: any;
  after?: any;
  rationale?: string;
  skipped?: string;
  addressed_cases?: string[];
  fixed_cases?: string[];
  learned_expansions?: Record<string, string[]>;
};

export type IterationEntry = {
  iteration: number;
  from_version: number;
  to_version: number;
  dev_before: number | null;
  dev_after?: number | null;
  holdout_before?: number | null;
  holdout_after?: number | null;
  failures_in: Record<string, number>;
  changes: Change[];
  newly_broken?: string[];
  newly_fixed?: string[];
  decision?: string;
  stop_reason?: string;
};

export type RunDetail = {
  summary: RunSummary;
  brief: string;
  requirements: Requirements;
  definition: AgentDefinition;
  system_prompt: string;
  scorecard: IterationScore[];
  iteration_log: IterationEntry[];
  tournament: { winner: string; candidates: { variant: string; pass_rate: number; tokens: number; prompt_chars?: number }[]; note: string } | null;
  judge_selftest: { ran: boolean; accuracy?: number; trials?: number; decision?: string; details?: any[]; reason?: string };
  budget: { tokens_used: number; llm_calls: number; cached_calls: number; elapsed_seconds: number; by_stage: Record<string, { tokens: number; calls: number }> };
  config: Record<string, any>;
  eval_generation: { accepted: number; rejected: { type: string; candidate: any; reason: string }[] };
  versions: number[];
  stop_reason: string | null;
  tool_selection: { tools_kept: ToolRef[]; tools_rejected: { name: string; reason: string }[] };
  registry: { name: string; description: string; input_schema: any; output_schema: any }[];
};

export type DocInventory = { doc: string; kind: string; words: number; pages?: number; sections?: string[]; opening?: string; rows?: number; columns?: string[]; sample_rows?: Record<string, string>[] };
export type Workspace = { id: string; brief: string; inventory: DocInventory[]; requirements: Requirements | null; questions: Question[] | null };
export type Question = { question: string; why: string; default_answer: string };
export type Job = { id: string; state: "running" | "done" | "failed"; kind: string; log: string[]; next: number; result: any; error: string | null; elapsed_s: number };

export type ChatResponse = {
  answer: string;
  refused: boolean;
  citations: string[];
  retrieved: { chunk_id: string; doc: string; score: number; text: string }[];
  tool_calls: { tool: string; args?: any; result?: any; error?: string }[];
  contract_ok: boolean;
  contract_errors: string[];
  latency_s: number;
  agent: { name: string; version: number; tools: string[]; retrieval: Record<string, any> };
};
export type AgentOption = { id: string; label: string; run?: string; baseline?: string; tools: string[] };

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      if (j.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* not json */
    }
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  status: () => req<Status>("/api/status"),
  overview: () => req<Overview>("/api/overview"),
  runs: () => req<RunSummary[]>("/api/runs"),
  run: (name: string) => req<RunDetail>(`/api/runs/${encodeURIComponent(name)}`),
  evalset: (name: string) => req<EvalCase[]>(`/api/runs/${encodeURIComponent(name)}/evalset`),
  results: (name: string, iteration?: number) =>
    req<CaseResult[]>(`/api/runs/${encodeURIComponent(name)}/results${iteration === undefined ? "" : `?iteration=${iteration}`}`),
  definitionVersion: (name: string, v: number) => req<AgentDefinition>(`/api/runs/${encodeURIComponent(name)}/definition/${v}`),
  fileUrl: (name: string, file: string) => `/api/runs/${encodeURIComponent(name)}/file/${encodeURIComponent(file)}`,
  zipUrl: (name: string) => `/api/runs/${encodeURIComponent(name)}/zip`,
  createWorkspace: (brief: string, files: File[]) => {
    const f = new FormData();
    f.append("brief", brief);
    files.forEach((x) => f.append("files", x));
    return req<Workspace>("/api/workspaces", { method: "POST", body: f });
  },
  demoWorkspace: (demo: string) => req<Workspace>(`/api/workspaces/demo/${demo}`, { method: "POST" }),
  workspace: (id: string) => req<Workspace>(`/api/workspaces/${id}`),
  questions: (id: string) => req<Question[]>(`/api/workspaces/${id}/questions`, { method: "POST" }),
  requirements: (id: string, answers: string[]) => req<{ job_id: string }>(`/api/workspaces/${id}/requirements`, json({ answers })),
  build: (id: string, body: { run_name: string; requirements: Requirements; max_iterations: number; tournament: boolean }) =>
    req<{ job_id: string; run_name: string }>(`/api/workspaces/${id}/build`, json(body)),
  job: (id: string, since = 0) => req<Job>(`/api/jobs/${id}?since=${since}`),
  agents: () => req<AgentOption[]>("/api/agents"),
  chat: (body: { run?: string; baseline?: string; message: string; history: [string, string][] }) => req<ChatResponse>("/api/chat", json(body)),
};

export const pct = (x: number | null | undefined, digits = 0) => (x === null || x === undefined ? "n/a" : `${(x * 100).toFixed(digits)}%`);
export const CATEGORY_LABEL: Record<string, string> = {
  retrieval_miss: "Retrieval miss",
  prompt_defect: "Prompt defect",
  hallucination: "Hallucination",
  wrong_refusal: "Wrong refusal",
};

export type RunSummaryExtra = RunSummary & {
  failures: Record<string, number>;
  history: { iteration: number; dev: number | null; holdout: number | null; overall: number | null; decision: string }[];
};
export type ToolSelection = { tools_kept: ToolRef[]; tools_rejected: { name: string; reason: string }[] };
export type RegistryTool = { name: string; description: string; input_schema: any; output_schema: any };
