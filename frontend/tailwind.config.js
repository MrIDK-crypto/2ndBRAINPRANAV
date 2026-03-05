/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#FAF9F7',
        secondary: '#FFFFFF',
        accent: '#C9A598',
        neutral: {
          800: '#2D2D2D',
          600: '#6B6B6B',
          500: '#9A9A9A',
          400: '#9A9A9A',
        },
        border: '#F0EEEC',
      },
      fontFamily: {
        sans: ['Avenir', 'Avenir Next', 'DM Sans', 'system-ui', 'sans-serif'],
        display: ['Instrument Serif', 'Georgia', 'serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
