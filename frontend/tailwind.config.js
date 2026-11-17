import {
  BASE_BG,
  BASE_PANEL,
  BASE_PANEL2,
  BASE_LINE,
  BASE_EDGE,
  TEXT_PRIMARY,
  TEXT_SECONDARY,
  TEXT_MUTED,
  SIGNAL_LONG,
  SIGNAL_SHORT,
  BRAND_CYAN,
  STATE_OK,
  STATE_WARN,
  STATE_ERROR,
} from './src/theme'

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Los hex viven en src/theme.ts (fuente unica; scripts/check_contrast.py la lee).
        //   line = hairline decorativo (divisores, grilla) — sin requisito WCAG 1.4.11
        //   edge = borde de CONTROLES interactivos (input, button, select) — exige 3:1
        base: { bg: BASE_BG, panel: BASE_PANEL, panel2: BASE_PANEL2, line: BASE_LINE, edge: BASE_EDGE },
        // Texto: escalera validada WCAG AA (>=4.5:1 sobre bg, panel y panel2)
        text: { primary: TEXT_PRIMARY, secondary: TEXT_SECONDARY, muted: TEXT_MUTED },
        // SEMANTICA DE MERCADO. NUNCA usar fuera de direccion real LONG/SHORT.
        signal: { long: SIGNAL_LONG, short: SIGNAL_SHORT },
        // Marca de PIVOT: estados activos, foco, radar. Nunca direccion de mercado.
        brand: { cyan: BRAND_CYAN },
        // ESTADO DE SISTEMA (UI generica: guardado, advertencia, fallo).
        // Distinto de signal.* para no confundir "el sistema fallo" con "el mercado bajo".
        state: { ok: STATE_OK, warn: STATE_WARN, error: STATE_ERROR },
      },
      fontFamily: {
        mono: ['"IBM Plex Mono"', 'monospace'],
        sans: ['"IBM Plex Sans"', 'sans-serif'],
        condensed: ['"IBM Plex Sans Condensed"', 'sans-serif'],
      },
      keyframes: {
        'radar-sweep': { '0%': { transform: 'rotate(0deg)' }, '100%': { transform: 'rotate(360deg)' } },
        'pulse-dot': { '0%, 100%': { opacity: '1' }, '50%': { opacity: '0.3' } },
        'toast-in': {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'skeleton-sweep': { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
      },
      animation: {
        'radar-sweep': 'radar-sweep 3s linear infinite',
        'pulse-dot': 'pulse-dot 2s ease-in-out infinite',
        'toast-in': 'toast-in 160ms ease-out',
        'skeleton-sweep': 'skeleton-sweep 1.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
