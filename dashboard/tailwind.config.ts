import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        background: "#0f172a",
        surface: "#1e293b",
        border: "#334155",
        primary: {
          DEFAULT: "#3b82f6",
          foreground: "#ffffff",
        },
        warning: {
          DEFAULT: "#f59e0b",
          foreground: "#ffffff",
        },
        critical: {
          DEFAULT: "#f43f5e",
          foreground: "#ffffff",
        },
        success: {
          DEFAULT: "#10b981",
          foreground: "#ffffff",
        },
        "text-primary": "#f8fafc",
        "text-secondary": "#94a3b8",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      animation: {
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
        "fade-in": "fade-in 200ms ease-out",
        "slide-in": "slide-in 250ms ease-out",
      },
      keyframes: {
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(245, 158, 11, 0)" },
          "50%": { boxShadow: "0 0 20px 4px rgba(245, 158, 11, 0.3)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "slide-in": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
