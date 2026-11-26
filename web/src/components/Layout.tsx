import clsx from "clsx";
import { ClipboardCheck, FileText, Hammer, LayoutDashboard, Menu, MessageSquareText, MessagesSquare, Moon, Network, Plus, RefreshCcw, Sun, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useSearchParams } from "react-router-dom";
import { api, pct } from "../api";
import { useAsync } from "../lib/hooks";
import { useTheme } from "../lib/theme";

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/create", label: "Create agent", icon: Hammer },
  { to: "/requirements", label: "Requirements", icon: MessagesSquare },
  { to: "/architecture", label: "Architecture", icon: Network },
  { to: "/evaluation", label: "Evaluation", icon: ClipboardCheck },
  { to: "/optimization", label: "Optimization", icon: RefreshCcw },
  { to: "/playground", label: "Playground", icon: MessageSquareText },
  { to: "/reports", label: "Reports", icon: FileText },
];
const DEMOS = ["hr_policy", "ship_spares"];

function Logo() {
  return (
    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-ink-100 text-ink-850">
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M5 7h14M5 12h9M5 17h14" /></svg>
    </div>
  );
}

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button onClick={toggle} className="btn" aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}>
      {theme === "light" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
      <span className="hidden sm:inline">{theme === "light" ? "Dark" : "Light"}</span>
    </button>
  );
}

function Rail({ onNavigate }: { onNavigate?: () => void }) {
  const [params] = useSearchParams();
  const keep = params.get("run");
  return (
    <nav className="flex flex-col items-center gap-2">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={keep && to !== "/create" && to !== "/" ? `${to}?run=${keep}` : to} end={end} onClick={onNavigate} title={label} aria-label={label}
          className={({ isActive }) => clsx("group relative flex h-10 w-10 items-center justify-center rounded-full transition-all duration-150",
            isActive ? "bg-ink-100 text-ink-850" : "text-ink-400 hover:bg-ink-800 hover:text-ink-100")}>
          <Icon className="h-[17px] w-[17px]" strokeWidth={1.75} />
          <span className="pointer-events-none absolute left-12 z-50 whitespace-nowrap rounded-full bg-ink-100 px-2.5 py-1 text-[11px] text-ink-850 opacity-0 transition-opacity group-hover:opacity-100">{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

function RunsPanel({ onNavigate }: { onNavigate?: () => void }) {
  const { data: runs } = useAsync(api.runs, []);
  const [params] = useSearchParams();
  const current = params.get("run");
  const loc = useLocation();
  const target = ["/", "/create"].includes(loc.pathname) ? "/evaluation" : loc.pathname;
  const demos = (runs ?? []).filter((r) => DEMOS.includes(r.name));
  const others = (runs ?? []).filter((r) => !DEMOS.includes(r.name));
  const Item = ({ r }: { r: { name: string; final_pass_rate: number | null } }) => (
    <Link to={`${target}?run=${r.name}`} onClick={onNavigate}
      className={clsx("group flex items-center justify-between rounded-xl px-3 py-2 text-[13px] transition-colors", current === r.name ? "bg-ink-800 text-ink-100" : "text-ink-300 hover:bg-ink-800/70")}>
      <span className="flex min-w-0 items-center gap-2.5">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-ink-800 text-[10px] font-medium text-ink-400 group-hover:bg-ink-700">{r.name[0].toUpperCase()}</span>
        <span className="truncate">{r.name.replace(/_/g, " ")}</span>
      </span>
      <span className="num text-[11px] text-ink-500">{pct(r.final_pass_rate)}</span>
    </Link>
  );
  return (
    <div className="flex h-full flex-col">
      <div className="mb-4 flex items-center justify-between px-1"><span className="text-[15px] font-medium text-ink-100">ForgeAI</span><span className="text-[11px] text-ink-500">agent factory</span></div>
      <Link to="/create" onClick={onNavigate} className="btn btn-primary mb-6 w-full justify-center py-2.5"><Plus className="h-4 w-4" /> New agent</Link>
      {demos.length > 0 && (<>
        <div className="mb-1.5 px-1 text-[12px] text-ink-500">Demonstrations</div>
        <div className="mb-5 space-y-0.5">{demos.map((r) => <Item key={r.name} r={r} />)}</div>
      </>)}
      <div className="mb-1.5 border-t border-ink-700 px-1 pt-4 text-[12px] text-ink-500">Your runs</div>
      <div className="flex-1 space-y-0.5 overflow-y-auto">
        {others.length ? others.map((r) => <Item key={r.name} r={r} />) : <p className="px-1 text-[12px] leading-relaxed text-ink-500">Agents you build appear here.</p>}
      </div>
      <Status />
    </div>
  );
}

function Status() {
  const { data: s } = useAsync(api.status, []);
  if (!s) return null;
  return (
    <div className="mt-4 rounded-xl border border-ink-700 px-3 py-2.5 text-[11px] text-ink-400">
      <div className="flex items-center gap-2"><span className={clsx("h-1.5 w-1.5 rounded-full", s.mock_mode ? "bg-warn" : "bg-pass")} /><span className="text-ink-300">{s.mock_mode ? "Mock mode: no model reachable" : `agent ${s.agent_model.split("/").pop()} · judge ${s.judge_model.split("/").pop()}`}</span></div>
      {s.running_jobs > 0 && <div className="mt-1 flex items-center gap-2 text-ink-100"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink-100" /> build running</div>}
    </div>
  );
}

export default function Layout() {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const { data: s } = useAsync(api.status, []);
  useEffect(() => {
    setOpen(false);
  }, [loc.pathname, loc.search]);
  const page = NAV.find((n) => (n.end ? loc.pathname === n.to : loc.pathname.startsWith(n.to)))?.label ?? "ForgeAI";
  return (
    <div className="flex h-full bg-ink-900">
      <aside className="hidden w-[68px] shrink-0 flex-col items-center gap-6 border-r border-ink-700 bg-ink-950 py-4 xl:flex">
        <Logo />
        <Rail />
      </aside>
      <aside className="hidden w-64 shrink-0 border-r border-ink-700 bg-ink-900 px-3 py-4 xl:block">
        <RunsPanel />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-2">
            <button className="btn px-2.5 xl:hidden" onClick={() => setOpen(true)} aria-label="Open navigation"><Menu className="h-4 w-4" /></button>
            <span className="text-[15px] text-ink-100">{page}</span>
            {s && <span className="rounded-md border border-ink-700 px-1.5 py-0.5 text-[10.5px] text-ink-500">{s.mock_mode ? "mock" : s.backend}</span>}
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Link to="/create" className="btn btn-primary hidden sm:inline-flex"><Plus className="h-4 w-4" /> New agent</Link>
          </div>
        </header>
        <main className="mx-2 mb-2 min-h-0 flex-1 overflow-y-auto rounded-2xl border border-ink-700 bg-canvas sm:mx-3 sm:mb-3">
          <div key={loc.pathname} className="mx-auto max-w-[1200px] animate-fadein px-5 py-7 sm:px-8 lg:px-10 lg:py-9">
            <Outlet />
          </div>
        </main>
      </div>

      {open && (
        <div className="fixed inset-0 z-40 xl:hidden">
          <div className="absolute inset-0 bg-black/30" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-0 flex h-full animate-fadein">
            <div className="flex w-[68px] flex-col items-center gap-6 border-r border-ink-700 bg-ink-950 py-4"><Logo /><Rail onNavigate={() => setOpen(false)} /></div>
            <div className="relative w-64 bg-ink-900 px-3 py-4">
              <button className="btn absolute right-3 top-3 px-2" onClick={() => setOpen(false)} aria-label="Close navigation"><X className="h-4 w-4" /></button>
              <RunsPanel onNavigate={() => setOpen(false)} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
