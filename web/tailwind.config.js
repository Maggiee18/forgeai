/** @type {import('tailwindcss').Config} */
// Every colour is a CSS variable (see src/index.css) so the light/dark toggle flips the whole UI, charts included.
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // "ink" is a neutral ramp from page (950) to strongest text (100) in BOTH themes
        ink: { 950: v("ink-950"), 900: v("ink-900"), 850: v("ink-850"), 800: v("ink-800"), 700: v("ink-700"), 600: v("ink-600"), 500: v("ink-500"), 400: v("ink-400"), 300: v("ink-300"), 100: v("ink-100") },
        accent: { DEFAULT: v("accent"), dim: v("accent-dim") },   // near-black in light, white in dark
        pass: { DEFAULT: v("pass"), dim: v("pass-dim") },         
        warn: { DEFAULT: v("warn"), dim: v("warn-dim") },         
        fail: { DEFAULT: v("fail"), dim: v("fail-dim") },         
        info: { DEFAULT: v("info"), dim: v("info-dim") },
        canvas: v("canvas"),
      },
      fontFamily: {
        display: ["'Instrument Serif'", "Georgia", "serif"],
        sans: ["'Geist Sans'", "Geist", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["'Geist Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: { DEFAULT: "6px", md: "8px", lg: "10px", xl: "12px", "2xl": "16px" },
      keyframes: {
        fadein: { from: { opacity: 0, transform: "translateY(6px)" }, to: { opacity: 1, transform: "none" } },
        grow: { from: { transform: "scaleX(0)" }, to: { transform: "scaleX(1)" } },
      },
      animation: { fadein: "fadein .35s cubic-bezier(.2,.7,.2,1) both", grow: "grow .8s cubic-bezier(.2,.7,.2,1) both" },
    },
  },
  safelist: ["text-pass", "text-warn", "text-fail", "bg-pass", "bg-warn", "bg-fail"],
  plugins: [],
};
