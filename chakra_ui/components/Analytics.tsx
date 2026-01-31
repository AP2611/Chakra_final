'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { BarChart3, TrendingUp, Clock, Target, Zap, Activity, History, RefreshCw } from 'lucide-react'
import { getAnalyticsMetrics, getQualityImprovementData, getPerformanceHistory, getRecentTasks } from '@/utils/api'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from 'recharts'

interface Metrics {
  avg_improvement: number
  avg_latency: number
  avg_accuracy: number
  avg_iterations: number
  total_tasks: number
}

interface QualityData {
  iteration: string
  before: number
  after: number
  improvement: number
}

interface PerformanceData {
  time: string
  latency: number
  accuracy: number
}

interface RecentTask {
  id: number
  task: string
  improvement: string
  duration: string
  iterations: number
  date: string
}

function MetricCard({ title, value, change, icon: Icon, delay, color = 'gold' }: { 
  title: string
  value: string
  change: string
  icon: any
  delay: number
  color?: string
}) {
  const isPositive = change.startsWith('+') || parseFloat(change) > 0
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className="glass rounded-2xl p-6 card-premium"
      style={{ backgroundColor: 'var(--bg-glass)' }}
    >
      <div className="flex items-start justify-between mb-4">
        <div className={`w-12 h-12 rounded-xl bg-gradient-to-br from-[var(--accent-${color})]/20 to-[var(--accent-saffron)]/20 flex items-center justify-center`}>
          <Icon className="w-6 h-6" style={{ color: `var(--accent-${color})` }} />
        </div>
        <span className={`text-sm font-medium ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
          {change}
        </span>
      </div>
      <h3 className="text-sm mb-1" style={{ color: 'var(--text-secondary)' }}>{title}</h3>
      <p className="text-3xl font-bold" style={{ color: 'var(--text-primary)' }}>{value}</p>
      <p className="text-xs mt-2" style={{ color: 'var(--text-secondary)' }}>vs last session</p>
    </motion.div>
  )
}

export default function Analytics() {
  const [mounted, setMounted] = useState(false)
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date())
  const [metrics, setMetrics] = useState<Metrics>({
    avg_improvement: 0.0,
    avg_latency: 0.0,
    avg_accuracy: 0.0,
    avg_iterations: 0.0,
    total_tasks: 0
  })
  const [qualityData, setQualityData] = useState<QualityData[]>([])
  const [performanceData, setPerformanceData] = useState<PerformanceData[]>([])
  const [recentTasks, setRecentTasks] = useState<RecentTask[]>([])

  useEffect(() => {
    setMounted(true)
  }, [])

  const fetchAnalytics = async () => {
    try {
      setLoading(true)
      const [metricsData, qualityDataResult, performanceDataResult, recentTasksResult] = await Promise.all([
        getAnalyticsMetrics(),
        getQualityImprovementData(20),
        getPerformanceHistory(24),
        getRecentTasks(10)
      ])

      setMetrics(metricsData)
      setQualityData(qualityDataResult)
      setPerformanceData(performanceDataResult)
      setRecentTasks(recentTasksResult)
      setLastUpdate(new Date())
    } catch (error) {
      console.error('Error fetching analytics:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!mounted) return

    // Fetch immediately
    fetchAnalytics()

    // Then fetch every 3 seconds
    const interval = setInterval(fetchAnalytics, 3000)

    return () => clearInterval(interval)
  }, [mounted])

  if (!mounted) return null

  const formattedQualityData = qualityData.map(item => ({
    iteration: item.iteration,
    before: item.before,
    after: item.after,
    improvement: item.improvement
  }))

  return (
    <div className="h-full flex flex-col">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6 flex items-center justify-between"
      >
        <div>
          <h1 className="text-3xl font-bold mb-2 flex items-center gap-3" style={{ color: 'var(--text-primary)' }}>
            <BarChart3 className="w-8 h-8" style={{ color: 'var(--accent-gold)' }} />
            Analytics
          </h1>
          <p style={{ color: 'var(--text-secondary)' }}>
            Real-time agent performance metrics and improvements
            {lastUpdate && (
              <span className="ml-2 text-xs">
                Last updated: {lastUpdate.toLocaleTimeString()}
                {loading && <RefreshCw className="inline-block w-3 h-3 ml-1 animate-spin" />}
              </span>
            )}
          </p>
        </div>
      </motion.div>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <MetricCard
          title="Avg Improvement"
          value={`${metrics.avg_improvement.toFixed(1)}%`}
          change={metrics.avg_improvement > 0 ? `+${metrics.avg_improvement.toFixed(1)}%` : `${metrics.avg_improvement.toFixed(1)}%`}
          icon={TrendingUp}
          delay={0}
          color="gold"
        />
        <MetricCard
          title="Avg Latency"
          value={`${metrics.avg_latency.toFixed(1)}s`}
          change={metrics.avg_latency > 0 ? `${metrics.avg_latency.toFixed(1)}s` : 'N/A'}
          icon={Clock}
          delay={0.1}
          color="saffron"
        />
        <MetricCard
          title="Accuracy"
          value={`${metrics.avg_accuracy.toFixed(1)}%`}
          change={metrics.avg_accuracy > 0 ? `+${metrics.avg_accuracy.toFixed(1)}%` : `${metrics.avg_accuracy.toFixed(1)}%`}
          icon={Target}
          delay={0.2}
          color={metrics.avg_accuracy > 80 ? 'gold' : metrics.avg_accuracy > 60 ? 'saffron' : 'red'}
        />
        <MetricCard
          title="Total Tasks"
          value={metrics.total_tasks.toString()}
          change={metrics.total_tasks > 0 ? `${metrics.total_tasks} tasks` : 'No tasks yet'}
          icon={Zap}
          delay={0.3}
          color="gold"
        />
      </div>

      <div className="flex-1 grid grid-cols-3 gap-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="col-span-2 glass rounded-2xl p-6"
          style={{ backgroundColor: 'var(--bg-glass)' }}
        >
          <div className="flex items-center gap-3 mb-6 pb-4 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--accent-gold)]/20 to-[var(--accent-saffron)]/20 flex items-center justify-center">
              <Activity className="w-5 h-5" style={{ color: 'var(--accent-gold)' }} />
            </div>
            <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Quality Improvement</h2>
          </div>
          
          {formattedQualityData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={formattedQualityData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis 
                  dataKey="iteration" 
                  angle={-45}
                  textAnchor="end"
                  height={80}
                  stroke="var(--text-secondary)"
                />
                <YAxis stroke="var(--text-secondary)" domain={[0, 100]} />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'var(--bg-secondary)',
                    border: '1px solid var(--border-medium)',
                    borderRadius: '8px'
                  }}
                />
                <Legend />
                <Bar dataKey="before" fill="#666" name="Before" />
                <Bar dataKey="after" fill="var(--accent-gold)" name="After" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-64" style={{ color: 'var(--text-secondary)' }}>
              No data yet. Process some tasks to see quality improvements.
            </div>
          )}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="glass rounded-2xl p-6"
          style={{ backgroundColor: 'var(--bg-glass)' }}
        >
          <div className="flex items-center gap-3 mb-6 pb-4 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--accent-gold)]/20 to-[var(--accent-saffron)]/20 flex items-center justify-center">
              <History className="w-5 h-5" style={{ color: 'var(--accent-gold)' }} />
            </div>
            <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Learning History</h2>
          </div>

          <div className="space-y-3 max-h-96 overflow-auto">
            {recentTasks.length > 0 ? (
              recentTasks.map((task, index) => (
                <motion.div
                  key={task.id}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.4 + index * 0.05 }}
                  className="p-4 rounded-xl hover:bg-white/5 transition-all"
                  style={{ backgroundColor: 'rgba(0,0,0,0.2)' }}
                >
                  <div className="flex items-start justify-between mb-2">
                    <p className="font-medium text-sm line-clamp-2" style={{ color: 'var(--text-primary)' }}>
                      {task.task}
                    </p>
                    <span className="text-xs flex-shrink-0 ml-2" style={{ color: 'var(--text-secondary)' }}>
                      {task.date}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--text-secondary)' }}>
                      <span>{task.duration}</span>
                      <span>{task.iterations} iter</span>
                    </div>
                    <span className="text-sm font-medium" style={{ color: 'var(--accent-gold)' }}>
                      {task.improvement}
                    </span>
                  </div>
                </motion.div>
              ))
            ) : (
              <div className="text-center py-8" style={{ color: 'var(--text-secondary)' }}>
                No tasks processed yet. Start using the Code Assistant or Document Assistant to see analytics.
              </div>
            )}
          </div>
        </motion.div>
      </div>

      {performanceData.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="mt-6 glass rounded-2xl p-6"
          style={{ backgroundColor: 'var(--bg-glass)' }}
        >
          <div className="flex items-center gap-3 mb-6 pb-4 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--accent-gold)]/20 to-[var(--accent-saffron)]/20 flex items-center justify-center">
              <Activity className="w-5 h-5" style={{ color: 'var(--accent-gold)' }} />
            </div>
            <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Performance Over Time</h2>
          </div>
          
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={performanceData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis dataKey="time" stroke="var(--text-secondary)" />
              <YAxis yAxisId="left" stroke="#ff9800" />
              <YAxis yAxisId="right" orientation="right" stroke="var(--accent-gold)" domain={[0, 100]} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border-medium)',
                  borderRadius: '8px'
                }}
              />
              <Legend />
              <Line 
                yAxisId="left" 
                type="monotone" 
                dataKey="latency" 
                stroke="#ff9800" 
                name="Latency (s)" 
                strokeWidth={2}
              />
              <Line 
                yAxisId="right" 
                type="monotone" 
                dataKey="accuracy" 
                stroke="var(--accent-gold)" 
                name="Accuracy (%)" 
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </motion.div>
      )}
    </div>
  )
}
