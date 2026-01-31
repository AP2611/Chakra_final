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
        // Saffron Gold palette
        gold: {
          50: '#FFFAF0',
          100: '#FFF3E0',
          200: '#FFE0B2',
          300: '#FFCC80',
          400: '#FFB74D',
          500: '#FFA726',
          600: '#FF9800',
          700: '#F57C00',
          800: '#EF6C00',
          900: '#E65100',
          glow: '#FFD700',
          shimmer: '#FFECB3',
        },
        // Deep Charcoal palette
        charcoal: {
          50: '#F5F5F5',
          100: '#EEEEEE',
          200: '#E0E0E0',
          300: '#BDBDBD',
          400: '#9E9E9E',
          500: '#757575',
          600: '#616161',
          700: '#424242',
          800: '#303030',
          900: '#1A1A1A',
          base: '#0D0D0D',
          glass: 'rgba(26, 26, 26, 0.8)',
        },
        // Warm Ivory palette
        ivory: {
          50: '#FFFFF0',
          100: '#FFFDE7',
          200: '#FFF9C4',
          300: '#FFF59D',
          400: '#FFF176',
          500: '#FFEE58',
          soft: '#F5F0E6',
          glow: '#FFF8E1',
        },
        // Sacred geometry accent
        saffron: {
          DEFAULT: '#FF6B35',
          light: '#FF8A5C',
          dark: '#CC5529',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Playfair Display', 'serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      backgroundImage: {
        'chakra-gradient': 'radial-gradient(ellipse at center, #1A1A1A 0%, #0D0D0D 100%)',
        'gold-shimmer': 'linear-gradient(90deg, transparent 0%, rgba(255, 215, 0, 0.3) 50%, transparent 100%)',
        'glass-gradient': 'linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%)',
        'mandala-pattern': "url(\"data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23FFA726' fill-opacity='0.05'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E\")",
      },
      animation: {
        'spin-slow': 'spin 20s linear infinite',
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'float': 'float 6s ease-in-out infinite',
        'shimmer': 'shimmer 2s linear infinite',
        'rotate-chakra': 'rotate-chakra 30s linear infinite',
        'particle-float': 'particle-float 8s ease-in-out infinite',
        'light-ray': 'light-ray 10s ease-in-out infinite',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 20px rgba(255, 215, 0, 0.3)' },
          '50%': { boxShadow: '0 0 40px rgba(255, 215, 0, 0.6)' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-20px)' },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'rotate-chakra': {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
        'particle-float': {
          '0%, 100%': { transform: 'translateY(0) translateX(0)' },
          '25%': { transform: 'translateY(-30px) translateX(20px)' },
          '50%': { transform: 'translateY(-10px) translateX(-10px)' },
          '75%': { transform: 'translateY(-40px) translateX(15px)' },
        },
        'light-ray': {
          '0%, 100%': { opacity: '0.3', transform: 'translateX(0) translateY(0)' },
          '50%': { opacity: '0.6', transform: 'translateX(50px) translateY(20px)' },
        },
      },
      boxShadow: {
        'gold-glow': '0 0 30px rgba(255, 215, 0, 0.3)',
        'gold-glow-lg': '0 0 60px rgba(255, 215, 0, 0.4)',
        'inner-gold': 'inset 0 0 20px rgba(255, 215, 0, 0.1)',
        'glass': '0 8px 32px 0 rgba(0, 0, 0, 0.37)',
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
}
