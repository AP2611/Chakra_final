import type { Metadata } from 'next'
import './globals.css'
import { ThemeProvider } from '@/context/ThemeContext'

export const metadata: Metadata = {
  title: 'Chakra',
  description: 'A next-generation AI product inspired by Indian sacred geometry and futuristic technology.',
  icons: {
    icon: '/bg_removed.png',
    shortcut: '/bg_removed.png',
    apple: '/bg_removed.png',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="icon" href="/bg_removed.png" />
        <link rel="apple-touch-icon" href="/bg_removed.png" />
      </head>
      <body className="antialiased">
        <ThemeProvider>
          <div className="noise-overlay" />
          <div className="geo-pattern" />
          <div className="ambient-glow" style={{ width: '400px', height: '400px', top: '10%', left: '10%' }} />
          <div className="ambient-glow" style={{ width: '300px', height: '300px', top: '60%', right: '10%' }} />
          <div className="ambient-glow" style={{ width: '350px', height: '350px', bottom: '20%', left: '30%' }} />
          {children}
        </ThemeProvider>
      </body>
    </html>
  )
}
