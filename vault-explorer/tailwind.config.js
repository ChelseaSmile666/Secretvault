/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['JetBrains Mono', 'monospace'],
        sans: ['Space Grotesk', 'sans-serif'],
      },
      colors: {
        void: '#000008',
        surface: '#080818',
        panel: '#0d0d22',
        border: '#1a1a3a',
        cyan: { DEFAULT: '#00d4ff', dim: '#006680', glow: '#00d4ff44' },
        gold: { DEFAULT: '#ffd700', dim: '#806b00', glow: '#ffd70033' },
        crimson: { DEFAULT: '#ff2244', dim: '#801122', glow: '#ff224433' },
        violet: { DEFAULT: '#9944ff', dim: '#4c2280', glow: '#9944ff33' },
        emerald: { DEFAULT: '#00ff88', dim: '#006640', glow: '#00ff8833' },
        amber: { DEFAULT: '#ff8800', dim: '#804400', glow: '#ff880033' },
        ghost: { DEFAULT: '#8888aa', dim: '#444466' },
      },
      animation: {
        pulse_slow: 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        scanline: 'scanline 4s linear infinite',
        flicker: 'flicker 0.15s infinite',
        glow: 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        scanline: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100vh)' },
        },
        glow: {
          '0%': { textShadow: '0 0 5px currentColor' },
          '100%': { textShadow: '0 0 20px currentColor, 0 0 40px currentColor' },
        }
      }
    },
  },
  plugins: [],
}
