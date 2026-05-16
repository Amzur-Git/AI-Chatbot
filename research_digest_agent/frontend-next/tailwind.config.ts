import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f172a",
        fog: "#e2e8f0",
        signal: "#0ea5e9",
      },
    },
  },
  plugins: [],
};

export default config;
