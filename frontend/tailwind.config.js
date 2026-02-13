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
        primary: '#F8FAFC',
        secondary: '#FFFFFF',
        accent: '#2563EB',
        neutral: {
          800: '#111827',
          600: '#4B5563',
          500: '#6B7280',
          400: '#9CA3AF',
        },
        border: '#E5E7EB',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        work: ['Work Sans', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
