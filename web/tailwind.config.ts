import type { Config } from "tailwindcss";

/**
 * Two temperatures, one system — "the chart, set properly".
 *
 *   fam-*  the family surface: warm paper, ink, serif display. A well-set
 *          clinical document, not a dashboard.
 *   con-*  the clinician console: near-black green, hairline rules, tabular
 *          numerals. An ops ledger, not a wall of glowing cards.
 *
 * Agent colors are shared across both surfaces so an agent is recognisable
 * anywhere it appears. No emoji anywhere in the UI — agents are identified by
 * two-letter monograms set in their color.
 */
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        fam: {
          bg: "#F7F3EA",
          surface: "#FFFDF8",
          surface2: "#EFE9DC",
          ink: "#232B22",
          ink2: "#68715F",
          line: "#DCD3C0",
          accent: "#2E6B4E",
          accentSoft: "#E4EEE6",
          warm: "#B85C38",
          attn: "#96731F",
          danger: "#A23B3B",
          hold: "#4A5A78",
        },
        con: {
          bg: "#0B0F0D",
          surface: "#11171310",
          panel: "#121814",
          panel2: "#1A231D",
          ink: "#DDE6DE",
          ink2: "#87988B",
          line: "#233028",
          accent: "#57A47B",
          warn: "#D2A03C",
          danger: "#C9604F",
          info: "#6B9BD1",
          hold: "#8FA3CC",
        },
        agent: {
          parser: "#6B9BD1",
          reconciler: "#C46A8A",
          scheduler: "#57A47B",
          pharmacist: "#C99A4B",
          watchman: "#D07B4A",
          coach: "#5FA9A0",
          escalator: "#C9604F",
        },
      },
      fontFamily: {
        display: ["Fraunces", "ui-serif", "Georgia", "serif"],
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: { fam: "6px", con: "4px" },
      boxShadow: {
        // A sheet of paper on a desk: one crisp edge, no blur cloud.
        sheet: "0 1px 0 rgba(35,43,34,0.10)",
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        breathe: { "0%,100%": { opacity: "0.45" }, "50%": { opacity: "1" } },
        gapGrow: {
          "0%": { height: "0px", opacity: "0" },
          "100%": { height: "var(--gap-h,44px)", opacity: "1" },
        },
        odometer: {
          "0%": { transform: "translateY(55%)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
      },
      animation: {
        rise: "rise 260ms cubic-bezier(0.2,0.8,0.2,1) both",
        breathe: "breathe 1.4s ease-in-out infinite",
        gapGrow: "gapGrow 420ms cubic-bezier(0.2,0.8,0.2,1) forwards",
        odometer: "odometer 180ms ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
