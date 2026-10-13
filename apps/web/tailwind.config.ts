import type { Config } from "tailwindcss";

export default {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        td: {
          accent: "var(--td-accent)",
          ink: "var(--td-accent-ink)",
          amber: "var(--td-amber)",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
