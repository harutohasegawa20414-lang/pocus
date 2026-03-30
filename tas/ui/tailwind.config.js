/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        gold: {
          50:  '#fdf8ec',
          100: '#faf0d0',
          200: '#f5dfa1',
          300: '#eec96a',
          400: '#e4af3a',
          500: '#C9A94D',
          600: '#a07830',
          700: '#7a5822',
          800: '#5a3e18',
          900: '#3e2a10',
        },
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Hiragino Sans"', '"Noto Sans JP"', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
