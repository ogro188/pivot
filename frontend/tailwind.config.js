/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        base: { bg: '#0B0E14', panel: '#141922', panel2: '#191F2A', line: '#232936' },
        text: { primary: '#E4E7EC', secondary: '#7A8699', muted: '#4B5563' },
        signal: { long: '#2FBF71', short: '#D64550' },
        brand: { cyan: '#37E0C4' },
      },
      fontFamily: {
        mono: ['"IBM Plex Mono"', 'monospace'],
        sans: ['"IBM Plex Sans"', 'sans-serif'],
        condensed: ['"IBM Plex Sans Condensed"', 'sans-serif'],
      },
      keyframes: {
        'radar-sweep': { '0%': { transform: 'rotate(0deg)' }, '100%': { transform: 'rotate(360deg)' } },
        'pulse-dot': { '0%, 100%': { opacity: '1' }, '50%': { opacity: '0.3' } },
      },
      animation: {
        'radar-sweep': 'radar-sweep 3s linear infinite',
        'pulse-dot': 'pulse-dot 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}