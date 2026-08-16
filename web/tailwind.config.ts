import type { Config } from "tailwindcss";

/**
 * Two temperatures, one system.
 *   fam-*  → the Family surface: warm light, a kitchen-table product
 *   con-*  → the Clinician Console: dense dark, an ops room
 * Agent colors are shared across both so an agent is recognisable anywhere.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        fam: {
          bg: "#FAF7F2",
          surface: "#FFFFFF",
          surface2: "#F3EEE6",
          ink: "#26332B",
          ink2: "#6B7A70",
          line: "#E5DED2",
          accent: "#3E7C59",
          accentSoft: "#E7F0EA",
          warm: "#C97B4A",
          attn: "#B8860B",
          danger: "#A63D3D",
        },
        con: {
          bg: "#10141A",
          surface: "#171C24",
          surface2: "#1E242E",
          ink: "#E8EAED",
          ink2: "#8B94A3",
          line: "#2A313D",
          accent: "#57A47B",
          warn: "#D9A441",
          danger: "#D96C6C",
          info: "#6B9BD1",
        },
        agent: {
          parser: "#6B9BD1",
          reconciler: "#9B7BD1",
          scheduler: "#57A47B",
          pharmacist: "#D1A15B",
          watchman: "#D9A441",
          coach: "#C97B4A",
          escalator: "#D96C6C",
        },
      },
      fontFamily: {
        display: ["Fraunces", "ui-serif", "Georgia", "serif"],
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: { fam: "16px", con: "10px" },
      boxShadow: { fam: "0 2px 16px rgba(38,51,43,0.07)" },
      keyframes: {
        lift: {
          "0%":   { transform: "translateY(0) scale(1)", boxShadow: "0 0 0 rgba(0,0,0,0)" },
          "100%": { transform: "translateY(-8px) scale(1.02)", boxShadow: "0 8px 24px rgba(38,51,43,0.12)" },
        },
        breathe: { "0%,100%": { opacity: "0.55" }, "50%": { opacity: "1" } },
        gapGrow: { "0%": { height: "0px", opacity: "0" }, "100%": { height: "var(--gap-h,44px)", opacity: "1" } },
        odometer: { "0%": { transform: "translateY(60%)", opacity: "0" }, "100%": { transform: "translateY(0)", opacity: "1" } },
      },
      animation: {
        lift: "lift 280ms cubic-bezier(0.2,0.8,0.2,1) forwards",
        breathe: "breathe 1.4s ease-in-out infinite",
        gapGrow: "gapGrow 420ms cubic-bezier(0.2,0.8,0.2,1) forwards",
        odometer: "odometer 180ms ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
