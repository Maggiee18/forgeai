import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

type Theme = "light" | "dark";
const Ctx = createContext<{ theme: Theme; toggle: () => void }>({ theme: "light", toggle: () => {} });

function initial(): Theme {
  try {
    const saved = localStorage.getItem("forgeai-theme");
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* storage unavailable */
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initial);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("forgeai-theme", theme);
    } catch {
      /* storage unavailable */
    }
  }, [theme]);
  const value = useMemo(() => ({ theme, toggle: () => setTheme((t) => (t === "light" ? "dark" : "light")) }), [theme]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useTheme = () => useContext(Ctx);

const read = (name: string) => `rgb(${getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim().split(/\s+/).join(",")})`;

/** Chart colours resolved from the live theme (SVG attributes cannot use CSS variables directly). */
export function useChartColors() {
  const { theme } = useTheme();
  return useMemo(() => {
    void theme;
    return {
      grid: read("ink-700"), axis: read("ink-500"), text: read("ink-300"), strong: read("ink-100"), muted: read("ink-600"),
      accent: read("accent"), pass: read("pass"), warn: read("warn"), fail: read("fail"), info: read("info"),
      tooltip: { background: read("ink-850"), border: `1px solid ${read("ink-700")}`, borderRadius: 4, fontSize: 12, color: read("ink-300"), boxShadow: "none" },
      cursor: read("ink-800"),
    };
  }, [theme]);
}
