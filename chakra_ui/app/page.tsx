'use client'

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Code2, FileText, BarChart3, Settings, Sparkles, 
  ChevronRight, Brain, Cpu, Layers, ArrowRight, MessageCircle
} from 'lucide-react'
import Chakra3DScene from '@/components/Chakra3DScene'
import ParticleSystem from '@/components/ParticleSystem'
import CodeAssistant from '@/components/CodeAssistant'
import DocumentAssistant from '@/components/DocumentAssistant'
import Analytics from '@/components/Analytics'
import SettingsPanel from '@/components/Settings'
import Chatbot from '@/components/Chatbot'

const navItems = [
  { id: 'code', label: 'Code Assistant', icon: Code2 },
  { id: 'documents', label: 'Document Assistant', icon: FileText },
  { id: 'chatbot', label: 'Chatbot', icon: MessageCircle },
  { id: 'analytics', label: 'Analytics', icon: BarChart3 },
  { id: 'settings', label: 'Settings', icon: Settings },
]

export default function Home() {
  const [activeSection, setActiveSection] = useState('hero')
  const [showApp, setShowApp] = useState(false)
  const [particles, setParticles] = useState<{x: number, y: number, size: number, speed: number, delay: number}[]>([])

  useEffect(() => {
    const newParticles = Array.from({ length: 50 }, () => ({
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 3 + 1,
      speed: Math.random() * 20 + 10,
      delay: Math.random() * 5,
    }))
    setParticles(newParticles)
  }, [])

  const handleEnterApp = () => {
    setShowApp(true)
    setTimeout(() => setActiveSection('code'), 500)
  }

  return (
    <div className="min-h-screen bg-charcoal-base relative overflow-hidden">
      <div className="light-rays" />
      <ParticleSystem />

      <AnimatePresence mode="wait">
        {!showApp ? (
          <motion.div
            key="hero"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, y: -50 }}
            transition={{ duration: 0.8 }}
            className="relative z-10 flex flex-col items-center justify-center min-h-screen"
          >
            <div className="absolute inset-0 z-0">
              <Chakra3DScene />
            </div>

            <div className="relative z-10 text-center px-6 max-w-4xl mx-auto">
              <motion.div
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5, duration: 0.8 }}
                className="mb-8"
              >
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass mb-6">
                  <Sparkles className="w-4 h-4 text-gold-glow" />
                  <span className="text-sm text-ivory-100">Refined Intelligence</span>
                </div>
              </motion.div>

              <motion.h1
                initial={{ opacity: 0, y: 50 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.7, duration: 0.8 }}
                className="text-6xl md:text-8xl font-bold mb-6"
              >
                <span className="gradient-text">Chakra</span>
              </motion.h1>

              <motion.p
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.9, duration: 0.8 }}
                className="text-xl md:text-2xl text-ivory-200 mb-8 max-w-2xl mx-auto"
              >
                Where ancient wisdom meets <span className="text-gold-400">future intelligence</span>
              </motion.p>

              <motion.button
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 1.1, duration: 0.5 }}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={handleEnterApp}
                className="group relative px-8 py-4 bg-gradient-to-r from-gold-500 to-saffron rounded-full text-charcoal-base font-semibold text-lg overflow-hidden btn-premium"
              >
                <span className="relative z-10 flex items-center gap-2">
                  Enter Chakra
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </span>
                <div className="absolute inset-0 bg-gradient-to-r from-gold-glow to-gold-400 opacity-0 group-hover:opacity-100 transition-opacity" />
              </motion.button>
            </div>

            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1.5, duration: 1 }}
              className="absolute bottom-10 left-1/2 -translate-x-1/2 flex items-center gap-8 text-ivory-400"
            >
              <div className="flex items-center gap-2">
                <Brain className="w-5 h-5" />
                <span className="text-sm">Neural</span>
              </div>
              <div className="w-px h-6 bg-gold-500/30" />
              <div className="flex items-center gap-2">
                <Cpu className="w-5 h-5" />
                <span className="text-sm">Quantum</span>
              </div>
              <div className="w-px h-6 bg-gold-500/30" />
              <div className="flex items-center gap-2">
                <Layers className="w-5 h-5" />
                <span className="text-sm">Sacred</span>
              </div>
            </motion.div>
          </motion.div>
        ) : (
          <motion.div
            key="app"
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="relative z-10 flex h-screen"
          >
            <motion.aside
              initial={{ x: -100, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              transition={{ delay: 0.2, duration: 0.5 }}
              className="w-72 glass-dark h-full flex flex-col py-6"
            >
              <div className="px-6 mb-8">
                <div className="flex items-center gap-3">
                  <img 
                    src="/bg_removed.png" 
                    alt="Chakra Logo" 
                    className="w-12 h-12 object-contain"
                  />
                  <span className="text-xl font-bold gold-text">Chakra</span>
                </div>
              </div>

              <nav className="flex-1 px-4">
                <ul className="space-y-2">
                  {navItems.map((item, index) => (
                    <motion.li
                      key={item.id}
                      initial={{ x: -20, opacity: 0 }}
                      animate={{ x: 0, opacity: 1 }}
                      transition={{ delay: 0.3 + index * 0.1 }}
                    >
                      <button
                        onClick={() => setActiveSection(item.id)}
                        className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 ${
                          activeSection === item.id
                            ? 'bg-gold-500/10 text-gold-glow border border-gold-500/20'
                            : 'text-ivory-300 hover:bg-white/5 hover:text-gold-glow'
                        }`}
                      >
                        <item.icon className="w-5 h-5" />
                        <span className="font-medium">{item.label}</span>
                        {activeSection === item.id && (
                          <motion.div
                            layoutId="activeIndicator"
                            className="ml-auto w-2 h-2 rounded-full bg-gold-glow"
                          />
                        )}
                      </button>
                    </motion.li>
                  ))}
                </ul>
              </nav>

              <div className="px-4 mt-auto">
                <div className="p-4 rounded-xl glass border border-gold-500/10">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-gold-400 to-saffron flex items-center justify-center text-charcoal-base font-semibold">
                      <span className="text-sm font-bold">A</span>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-ivory-100">Admin User</p>
                      <p className="text-xs text-ivory-400">Pro Plan</p>
                    </div>
                  </div>
                </div>
              </div>
            </motion.aside>

            <main className="flex-1 overflow-auto p-8">
              <AnimatePresence mode="wait">
                {activeSection === 'code' && (
                  <motion.div
                    key="code"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    transition={{ duration: 0.3 }}
                  >
                    <CodeAssistant />
                  </motion.div>
                )}
                {activeSection === 'documents' && (
                  <motion.div
                    key="documents"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    transition={{ duration: 0.3 }}
                  >
                    <DocumentAssistant />
                  </motion.div>
                )}
                {activeSection === 'chatbot' && (
                  <motion.div
                    key="chatbot"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    transition={{ duration: 0.3 }}
                  >
                    <Chatbot />
                  </motion.div>
                )}
                {activeSection === 'analytics' && (
                  <motion.div
                    key="analytics"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    transition={{ duration: 0.3 }}
                  >
                    <Analytics />
                  </motion.div>
                )}
                {activeSection === 'settings' && (
                  <motion.div
                    key="settings"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    transition={{ duration: 0.3 }}
                  >
                    <SettingsPanel />
                  </motion.div>
                )}
              </AnimatePresence>
            </main>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
