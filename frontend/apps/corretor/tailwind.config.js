/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        // Sobrescrito em runtime por CSS variables carregadas do branding do tenant.
        primary: "var(--color-primary, #2563eb)",
      },
    },
  },
  plugins: [],
};
