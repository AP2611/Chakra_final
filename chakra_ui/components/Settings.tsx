'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Settings as SettingsIcon, User, Bell, Shield, Palette, Globe, Zap, Save, ToggleLeft, ToggleRight, Sun, Moon, Star } from 'lucide-react'
import { useTheme } from '@/context/ThemeContext'

const themeOptions = [
  { id: 'deep-space', name: 'Deep Space', icon: Star, desc: 'Classic dark theme' },
  { id: 'golden-dawn', name: 'Golden Dawn', icon: Sun, desc: 'Warm golden sunrise' },
  { id: 'saffron-nights', name: 'Saffron Nights', icon: Moon, desc: 'Deep saffron hues' },
  { id: 'ivory-light', name: 'Ivory Light', icon: Sun, desc: 'Clean light theme' },
]

const sections = [
  { id: 'profile', title: 'Profile', icon: User },
  { id: 'appearance', title: 'Appearance', icon: Palette },
  { id: 'notifications', title: 'Notifications', icon: Bell },
  { id: 'privacy', title: 'Privacy', icon: Shield },
  { id: 'api', title: 'API', icon: Globe },
]

export default function Settings() {
  const { theme, setTheme } = useTheme()
  const [activeSection, setActiveSection] = useState('appearance')
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    setIsSaving(true)
    setTimeout(() => {
      setIsSaving(false)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    }, 1000)
  }

  return (
    <div className="h-full flex flex-col">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="mb-6">
        <h1 className="text-3xl font-bold mb-2 flex items-center gap-3" style={{ color: 'var(--text-primary)' }}>
          <SettingsIcon className="w-8 h-8" style={{ color: 'var(--accent-gold)' }} />
          Settings
        </h1>
        <p style={{ color: 'var(--text-secondary)' }}>Manage your Chakra experience</p>
      </motion.div>

      <div className="flex-1 grid grid-cols-5 gap-6">
        <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} className="col-span-1 space-y-2">
          {sections.map((section, i) => (
            <motion.button
              key={section.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              onClick={() => setActiveSection(section.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 ${
                activeSection === section.id
                  ? 'bg-[var(--accent-gold)]/10 border border-[var(--border-medium)]'
                  : 'hover:bg-white/5'
              }`}
              style={{ color: activeSection === section.id ? 'var(--accent-gold)' : 'var(--text-secondary)' }}
            >
              <section.icon className="w-5 h-5" />
              <span className="font-medium">{section.title}</span>
            </motion.button>
          ))}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          className="col-span-4 glass rounded-2xl p-6"
          style={{ backgroundColor: 'var(--bg-glass)' }}
        >
          {activeSection === 'appearance' && (
            <>
              <div className="flex items-center gap-3 mb-6 pb-4 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--accent-gold)]/20 to-[var(--accent-saffron)]/20 flex items-center justify-center">
                  <Palette className="w-5 h-5" style={{ color: 'var(--accent-gold)' }} />
                </div>
                <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Theme</h2>
              </div>

              <div className="grid grid-cols-2 gap-4 mb-6">
                {themeOptions.map((opt, i) => {
                  const Icon = opt.icon
                  const isActive = theme === opt.id
                  return (
                    <motion.button
                      key={opt.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.1 }}
                      onClick={() => setTheme(opt.id as any)}
                      className={`p-4 rounded-xl border transition-all duration-300 text-left ${
                        isActive ? 'border-[var(--border-medium)] bg-[var(--accent-gold)]/5' : 'border-[var(--border-subtle)]'
                      }`}
                      style={{ backgroundColor: isActive ? 'var(--bg-secondary)' : 'transparent' }}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                          isActive ? 'bg-[var(--accent-gold)]/20' : 'bg-[var(--bg-secondary)]'
                        }`}>
                          <Icon className="w-6 h-6" style={{ color: isActive ? 'var(--accent-gold)' : 'var(--text-secondary)' }} />
                        </div>
                        <div>
                          <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>{opt.name}</h3>
                          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{opt.desc}</p>
                        </div>
                      </div>
                    </motion.button>
                  )
                })}
              </div>

              <div className="mb-6">
                <h3 className="font-medium mb-3" style={{ color: 'var(--text-primary)' }}>Theme Preview</h3>
                <div className="grid grid-cols-4 gap-3">
                  <div className="p-3 rounded-lg" style={{ background: 'linear-gradient(135deg, #0D0D0D 0%, #1A1A1A 100%)' }}>
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-3 h-3 rounded-full" style={{ background: 'var(--accent-gold)' }} />
                      <span className="text-xs text-gray-300">Deep Space</span>
                    </div>
                    <div className="h-2 rounded" style={{ background: 'var(--bg-secondary)' }} />
                  </div>
                  <div className="p-3 rounded-lg" style={{ background: 'linear-gradient(135deg, #1A120B 0%, #2D1F14 100%)' }}>
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-3 h-3 rounded-full" style={{ background: '#FF8C42' }} />
                      <span className="text-xs text-yellow-100">Golden Dawn</span>
                    </div>
                    <div className="h-2 rounded" style={{ background: 'rgba(255,140,66,0.3)' }} />
                  </div>
                  <div className="p-3 rounded-lg" style={{ background: 'linear-gradient(135deg, #0F0A1A 0%, #1A1030 100%)' }}>
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-3 h-3 rounded-full" style={{ background: 'var(--accent-saffron)' }} />
                      <span className="text-xs text-purple-200">Saffron Nights</span>
                    </div>
                    <div className="h-2 rounded" style={{ background: 'rgba(255,107,53,0.3)' }} />
                  </div>
                  <div className="p-3 rounded-lg" style={{ background: 'linear-gradient(135deg, #FFFEF5 0%, #FFF8E7 100%)' }}>
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-3 h-3 rounded-full" style={{ background: '#CC8800' }} />
                      <span className="text-xs text-brown-700">Ivory Light</span>
                    </div>
                    <div className="h-2 rounded" style={{ background: 'rgba(204,136,0,0.2)' }} />
                  </div>
                </div>
              </div>

              <div className="flex justify-end">
                <button
                  onClick={handleSave}
                  disabled={isSaving}
                  className="px-6 py-3 rounded-xl font-semibold hover:shadow-lg transition-all flex items-center gap-2"
                  style={{ background: 'linear-gradient(135deg, var(--accent-gold), var(--accent-saffron))', color: '#000' }}
                >
                  {isSaving ? (
                    <>
                      <div className="w-5 h-5 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                      Saving...
                    </>
                  ) : saved ? (
                    <>
                      <Zap className="w-5 h-5" />
                      Saved!
                    </>
                  ) : (
                    <>
                      <Save className="w-5 h-5" />
                      Save Changes
                    </>
                  )}
                </button>
              </div>
            </>
          )}

          {activeSection === 'profile' && (
            <>
              <div className="flex items-center gap-3 mb-6 pb-4 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--accent-gold)]/20 to-[var(--accent-saffron)]/20 flex items-center justify-center">
                  <User className="w-5 h-5" style={{ color: 'var(--accent-gold)' }} />
                </div>
                <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Profile</h2>
              </div>
              <div className="space-y-4">
                {['Admin User', 'admin@chakra.ai', 'IST (UTC+5:30)'].map((val, i) => (
                  <motion.div key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
                    className="flex items-center justify-between p-4 rounded-xl" style={{ backgroundColor: 'rgba(0,0,0,0.2)' }}>
                    <div>
                      <p className="font-medium" style={{ color: 'var(--text-primary)' }}>{['Name', 'Email', 'Timezone'][i]}</p>
                      <p style={{ color: 'var(--text-secondary)' }}>{val}</p>
                    </div>
                    <button className="text-sm hover:underline" style={{ color: 'var(--accent-gold)' }}>Edit</button>
                  </motion.div>
                ))}
              </div>
            </>
          )}

          {activeSection === 'notifications' && (
            <>
              <div className="flex items-center gap-3 mb-6 pb-4 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--accent-gold)]/20 to-[var(--accent-saffron)]/20 flex items-center justify-center">
                  <Bell className="w-5 h-5" style={{ color: 'var(--accent-gold)' }} />
                </div>
                <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Notifications</h2>
              </div>
              <div className="space-y-4">
                {['Email Notifications', 'Push Notifications', 'AI Updates', 'Marketing Emails'].map((label, i) => {
                  const isActive = i % 2 === 0
                  return (
                    <motion.div key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
                      className="flex items-center justify-between p-4 rounded-xl" style={{ backgroundColor: 'rgba(0,0,0,0.2)' }}>
                      <p className="font-medium" style={{ color: 'var(--text-primary)' }}>{label}</p>
                      <button style={{ color: isActive ? 'var(--accent-gold)' : 'var(--text-secondary)' }}>
                        {isActive ? <ToggleRight className="w-10 h-6" /> : <ToggleLeft className="w-10 h-6" />}
                      </button>
                    </motion.div>
                  )
                })}
              </div>
            </>
          )}

          {activeSection === 'privacy' && (
            <>
              <div className="flex items-center gap-3 mb-6 pb-4 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--accent-gold)]/20 to-[var(--accent-saffron)]/20 flex items-center justify-center">
                  <Shield className="w-5 h-5" style={{ color: 'var(--accent-gold)' }} />
                </div>
                <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Privacy</h2>
              </div>
              <div className="space-y-4">
                {['Two-Factor Authentication', 'End-to-End Encryption'].map((label, i) => {
                  const isActive = i % 2 === 0
                  return (
                    <motion.div key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
                      className="flex items-center justify-between p-4 rounded-xl" style={{ backgroundColor: 'rgba(0,0,0,0.2)' }}>
                      <p className="font-medium" style={{ color: 'var(--text-primary)' }}>{label}</p>
                      <button style={{ color: isActive ? 'var(--accent-gold)' : 'var(--text-secondary)' }}>
                        {isActive ? <ToggleRight className="w-10 h-6" /> : <ToggleLeft className="w-10 h-6" />}
                      </button>
                    </motion.div>
                  )
                })}
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
                  className="flex items-center justify-between p-4 rounded-xl" style={{ backgroundColor: 'rgba(0,0,0,0.2)' }}>
                  <div>
                    <p className="font-medium" style={{ color: 'var(--text-primary)' }}>Data Retention</p>
                    <p style={{ color: 'var(--text-secondary)' }}>30 Days</p>
                  </div>
                  <select className="px-3 py-1 rounded-lg text-sm" style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}>
                    {['7 Days', '30 Days', '90 Days', '1 Year', 'Forever'].map(opt => <option key={opt}>{opt}</option>)}
                  </select>
                </motion.div>
              </div>
            </>
          )}

          {activeSection === 'api' && (
            <>
              <div className="flex items-center gap-3 mb-6 pb-4 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--accent-gold)]/20 to-[var(--accent-saffron)]/20 flex items-center justify-center">
                  <Globe className="w-5 h-5" style={{ color: 'var(--accent-gold)' }} />
                </div>
                <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>API</h2>
              </div>
              <div className="space-y-4">
                {['ck_xxxxxxxxxxxxxxxx', '', '1000 req/min'].map((val, i) => (
                  <motion.div key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
                    className="p-4 rounded-xl" style={{ backgroundColor: 'rgba(0,0,0,0.2)' }}>
                    <p className="font-medium mb-2" style={{ color: 'var(--text-primary)' }}>{['API Key', 'Webhook URL', 'Rate Limit'][i]}</p>
                    <input type="text" value={val} readOnly className="w-full px-3 py-2 rounded-lg text-sm"
                      style={{ background: 'var(--bg-primary)', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }} />
                  </motion.div>
                ))}
              </div>
            </>
          )}
        </motion.div>
      </div>
    </div>
  )
}
