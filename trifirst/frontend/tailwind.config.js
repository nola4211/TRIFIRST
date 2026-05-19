/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#F97316',
        dark: {
          900: '#0F1117',
          800: '#1A1D27',
          700: '#232736',
          600: '#2D3148',
          500: '#3D4268',
        },
        swim: '#38BDF8',
        bike: '#FB923C',
        run: '#4ADE80',
      },
    },
  },
  plugins: [],
}
