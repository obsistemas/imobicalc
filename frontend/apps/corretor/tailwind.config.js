/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        // --color-primary é "R G B" (sem vírgula) definido em src/style.css — formato exigido
        // pelo Tailwind pra suportar modificadores de opacidade (bg-primary/10, border-primary/30
        // etc.); um valor hex direto aqui não funcionaria com esses modificadores. Fallback
        // (raro — só se a variável não carregar) é a cor de marca da obsistemas.com.br.
        primary: "rgb(var(--color-primary, 0 159 227) / <alpha-value>)",
      },
    },
  },
  plugins: [],
};
