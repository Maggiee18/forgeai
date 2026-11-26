import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { api, pct } from "../api";
import { useAsync } from "../lib/hooks";

/** Selected run lives in the URL (?run=name) so every per-run page is linkable. */
export function useSelectedRun(): [string | null, (r: string) => void, { name: string; final_pass_rate: number | null }[]] {
  const [params, setParams] = useSearchParams();
  const { data } = useAsync(api.runs, []);
  const runs = data ?? [];
  const current = params.get("run");
  useEffect(() => {
    if (!current && runs.length) setParams({ run: runs[0].name }, { replace: true });
  }, [current, runs, setParams]);
  return [current, (r: string) => setParams({ run: r }), runs];
}

export function RunPicker({ value, onChange, runs }: { value: string | null; onChange: (r: string) => void; runs: { name: string; final_pass_rate: number | null }[] }) {
  if (!runs.length) return null;
  return (
    <label className="flex items-center gap-2 text-xs text-ink-400">
      Run
      <select className="input w-56 py-1.5" value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
        {runs.map((r) => (
          <option key={r.name} value={r.name}>
            {r.name} · {pct(r.final_pass_rate)}
          </option>
        ))}
      </select>
    </label>
  );
}
