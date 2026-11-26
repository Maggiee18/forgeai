import clsx from "clsx";
import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import type { ReactNode } from "react";

export function Card({ title, actions, children, className, pad = true }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; pad?: boolean }) {
  return (
    <section className={clsx("card animate-fadein", className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-ink-700 px-5 py-3">
          <h3 className="text-[13px] font-medium text-ink-100">{title}</h3>
          <div className="flex items-center gap-2">{actions}</div>
        </header>
      )}
      <div className={clsx(pad && "p-5")}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, tone = "default", hint, serif = false }: { label: string; value: ReactNode; tone?: "default" | "pass" | "warn" | "fail"; hint?: string; serif?: boolean }) {
  const color = { default: "text-ink-100", pass: "text-pass", warn: "text-warn", fail: "text-fail" }[tone];
  return (
    <div className="card px-4 py-3.5 animate-fadein">
      <div className="label">{label}</div>
      <div className={clsx("mt-1.5", serif ? "serif text-[30px] leading-none" : "num text-[22px]", color)}>{value}</div>
      {hint && <div className="mt-1 text-[11px] text-ink-500">{hint}</div>}
    </div>
  );
}

const TONES = {
  pass: "bg-pass-dim text-pass border-pass/30",
  warn: "bg-warn-dim text-warn border-warn/30",
  fail: "bg-fail-dim text-fail border-fail/30",
  info: "bg-info-dim text-info border-info/30",
  muted: "bg-ink-800 text-ink-400 border-ink-700",
};
export function Badge({ tone = "muted", children, title }: { tone?: keyof typeof TONES; children: ReactNode; title?: string }) {
  return (
    <span title={title} className={clsx("inline-flex items-center gap-1 whitespace-nowrap rounded border px-1.5 py-0.5 text-[11px]", TONES[tone])}>
      {children}
    </span>
  );
}

export function PageHeader({ title, subtitle, actions, eyebrow }: { title: string; subtitle?: ReactNode; actions?: ReactNode; eyebrow?: string }) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-2xl">
        {eyebrow && <div className="eyebrow mb-2">{eyebrow}</div>}
        <h1 className="serif text-[26px] leading-tight text-ink-100 sm:text-[30px]">{title}</h1>
        {subtitle && <p className="mt-2 text-[14px] leading-relaxed text-ink-400">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-ink-400">
      <Loader2 className="h-4 w-4 animate-spin" /> {label}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("animate-pulse rounded-md bg-ink-800", className)} />;
}

export function LoadingGrid() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-20" />)}</div>
      <Skeleton className="h-64" />
    </div>
  );
}

export function ErrorBox({ error, retry }: { error: string; retry?: () => void }) {
  return (
    <div className="card flex items-start gap-3 border-fail/40 p-4 text-sm">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-fail" />
      <div className="flex-1">
        <div className="text-ink-100">Something went wrong</div>
        <div className="mt-1 text-ink-400">{error}</div>
      </div>
      {retry && <button className="btn" onClick={retry}>Try again</button>}
    </div>
  );
}

export function Empty({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center px-6 py-16 text-center">
      <Inbox className="h-6 w-6 text-ink-500" strokeWidth={1.5} />
      <div className="serif mt-4 text-[20px] text-ink-100">{title}</div>
      <p className="mt-1 max-w-md text-sm text-ink-400">{body}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ScoreBar({ value, tone }: { value: number | null; tone?: "pass" | "warn" | "fail" }) {
  const v = value ?? 0;
  const t = tone ?? (v >= 0.8 ? "pass" : v >= 0.6 ? "warn" : "fail");
  const bg = { pass: "bg-pass", warn: "bg-warn", fail: "bg-fail" }[t];
  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-ink-700">
      <div className={clsx("h-full origin-left animate-grow rounded-full", bg)} style={{ width: `${Math.round(v * 100)}%` }} />
    </div>
  );
}

export function tone(v: number | null | undefined): "pass" | "warn" | "fail" {
  const x = v ?? 0;
  return x >= 0.8 ? "pass" : x >= 0.6 ? "warn" : "fail";
}

export function Mono({ children }: { children: ReactNode }) {
  return <span className="num text-ink-100">{children}</span>;
}
