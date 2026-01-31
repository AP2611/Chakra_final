'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

type Theme = 'deep-space' | 'golden-dawn' | 'saffron-nights' | 'ivory-light'

interface ThemeContextType {
  theme: Theme
  setTheme: (theme: Theme) => void
  themes: { id: Theme; name: string; description: string }[]
}

const themes: { id: Theme; name: string; description: string }[] = [
  { id: 'deep-space', name: 'Deep Space', description: 'Classic dark theme with golden accents' },
  { id: 'golden-dawn', name: 'Golden Dawn', description: 'Warm golden sunrise atmosphere' },
  { id: 'saffron-nights', name: 'Saffron Nights', description: 'Deep saffron and purple hues' },
  { id: 'ivory-light', name: 'Ivory Light', description: 'Clean light theme with warm accents' },
]

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>('deep-space')
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    const savedTheme = localStorage.getItem('chakra-theme') as Theme
    if (savedTheme && themes.some(t => t.id === savedTheme)) {
      setTheme(savedTheme)
    }
  }, [])

  useEffect(() => {
    if (mounted) {
      localStorage.setItem('chakra-theme', theme)
      document.documentElement.setAttribute('data-theme', theme)
      
      // Update CSS custom properties based on theme
      const root = document.documentElement
      
      switch (theme) {
        case 'deep-space':
          root.style.setProperty('--bg-primary', '#0D0D0D')
          root.style.setProperty('--bg-secondary', '#1A1A1A')
          root.style.setProperty('--bg-glass', 'rgba(26, 26, 26, 0.8)')
          root.style.setProperty('--text-primary', '#FFFFF0')
          root.style.setProperty('--text-secondary', '#F5F0E6')
          root.style.setProperty('--accent-gold', '#FFD700')
          root.style.setProperty('--accent-saffron', '#FF6B35')
          root.style.setProperty('--accent-glow', 'rgba(255, 215, 0, 0.3)')
          break
        case 'golden-dawn':
          root.style.setProperty('--bg-primary', '#1A120B')
          root.style.setProperty('--bg-secondary', '#2D1F14')
          root.style.setProperty('--bg-glass', 'rgba(45, 31, 20, 0.8)')
          root.style.setProperty('--text-primary', '#FFF8E7')
          root.style.setProperty('--text-secondary', '#FFE4B5')
          root.style.setProperty('--accent-gold', '#FFD700')
          root.style.setProperty('--accent-saffron', '#FF8C42')
          root.style.setProperty('--accent-glow', 'rgba(255, 215, 0, 0.4)')
          break
        case 'saffron-nights':
          root.style.setProperty('--bg-primary', '#0F0A1A')
          root.style.setProperty('--bg-secondary', '#1A1030')
          root.style.setProperty('--bg-glass', 'rgba(26, 16, 48, 0.8)')
          root.style.setProperty('--text-primary', '#F5E6F5')
          root.style.setProperty('--text-secondary', '#E8D4E8')
          root.style.setProperty('--accent-gold', '#FFD700')
          root.style.setProperty('--accent-saffron', '#FF6B35')
          root.style.setProperty('--accent-glow', 'rgba(255, 107, 53, 0.4)')
          break
        case 'ivory-light':
          root.style.setProperty('--bg-primary', '#FFFEF5')
          root.style.setProperty('--bg-secondary', '#FFF8E7')
          root.style.setProperty('--bg-glass', 'rgba(255, 255, 245, 0.8)')
          root.style.setProperty('--text-primary', '#2D1F14')
          root.style.setProperty('--text-secondary', '#4A3728')
          root.style.setProperty('--accent-gold', '#CC8800')
          root.style.setProperty('--accent-saffron', '#CC5529')
          root.style.setProperty('--accent-glow', 'rgba(204, 136, 0, 0.3)')
          break
      }
    }
  }, [theme, mounted])

  return (
    <ThemeContext.Provider value={{ theme, setTheme, themes }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
