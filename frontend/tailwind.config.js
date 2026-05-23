/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        /* shadcn tokens */
        border:     'hsl(var(--border))',
        input:      'hsl(var(--input))',
        ring:       'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary:    { DEFAULT: 'hsl(var(--primary))', foreground: 'hsl(var(--primary-foreground))' },
        secondary:  { DEFAULT: 'hsl(var(--secondary))', foreground: 'hsl(var(--secondary-foreground))' },
        destructive:{ DEFAULT: 'hsl(var(--destructive))', foreground: 'hsl(var(--destructive-foreground))' },
        muted:      { DEFAULT: 'hsl(var(--muted))', foreground: 'hsl(var(--muted-foreground))' },
        accent:     { DEFAULT: 'hsl(var(--accent))', foreground: 'hsl(var(--accent-foreground))' },
        popover:    { DEFAULT: 'hsl(var(--popover))', foreground: 'hsl(var(--popover-foreground))' },
        card:       { DEFAULT: 'hsl(var(--card))', foreground: 'hsl(var(--card-foreground))' },

        /* App surface scale — light mode */
        s0: '#F8FAFC',
        s1: '#FFFFFF',
        s2: '#FFFFFF',
        s3: '#F1F5F9',
        s4: '#EFF6FF',

        /* Semantic */
        gain:   '#16A34A',
        loss:   '#DC2626',
        info:   '#1D4ED8',
        warn:   '#D97706',
        purple: '#7C3AED',
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
      },
      fontSize: {
        '2xs': ['10px', { lineHeight: '14px' }],
        xs:    ['11px', { lineHeight: '16px' }],
        sm:    ['12px', { lineHeight: '18px' }],
        base:  ['13px', { lineHeight: '20px' }],
        md:    ['14px', { lineHeight: '20px' }],
        lg:    ['16px', { lineHeight: '24px' }],
        xl:    ['18px', { lineHeight: '28px' }],
      },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-400px 0' },
          '100%': { backgroundPosition: '400px 0' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.25s ease-out',
        shimmer:   'shimmer 1.6s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
