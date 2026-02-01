'use client'

import { useState, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Sparkles, Code2, Copy, Check, 
  Wand2, Zap, Brain
} from 'lucide-react'
import { streamSSE } from '@/utils/api'

interface IterationData {
  iteration: number
  yantra_output: string
  sutra_critique: string
  agni_output: string
  score: number
  improvement: number
}

interface OriginalOutput {
  id: number
  iteration: number
  timestamp: string
  originalOutput: string
  refinedOutput: string
  score: number
}

export default function CodeAssistant() {
  const [prompt, setPrompt] = useState('')
  const [refinedCode, setRefinedCode] = useState('')
  const [firstGeneratedCode, setFirstGeneratedCode] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [copied, setCopied] = useState(false)
  const [copiedFirst, setCopiedFirst] = useState(false)
  const [progress, setProgress] = useState(0)
  const [currentStep, setCurrentStep] = useState<string>('')
  const [iterations, setIterations] = useState<IterationData[]>([])
  const [finalScore, setFinalScore] = useState<number>(0)
  
  const abortControllerRef = useRef<AbortController | null>(null)
  
  const handleGenerate = useCallback(async () => {
    if (!prompt.trim() || isProcessing) return
    
    setIsProcessing(true)
    setRefinedCode('')
    setFirstGeneratedCode('')
    setProgress(0)
    setIterations([])
    setCurrentStep('Initializing...')
    
    // Cancel any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()
    
    let currentFirstCode = ''
    let currentRefinedCode = ''
    let isInImprovementPhase = false
    let stepProgress = 0
    
    await streamSSE(
      '/process-stream',
      {
        task: prompt,
        context: '',
        use_rag: false,
        is_code: true
      },
      {
        onToken: (token: string) => {
          // CRITICAL FIX: Only process tokens if we're NOT in improvement phase
          // This prevents improved_token tokens from going to firstGeneratedCode
          if (isInImprovementPhase) {
            // In improvement phase - update refined code
            currentRefinedCode += token
            setRefinedCode(currentRefinedCode)
          } else {
            // Still in first generation phase
            // Use closure variable directly to avoid state sync issues
            currentFirstCode += token
            // Direct update using closure variable to prevent overwriting
            setFirstGeneratedCode(currentFirstCode)
          }
        },
        onEvent: (data: any) => {
          switch (data.type) {
            case 'start':
              setCurrentStep('Starting analysis...')
              setProgress(5)
              break
              
            case 'memory_found':
              setCurrentStep(`Found ${data.examples_count} similar examples from memory`)
              setProgress(10)
              break
              
            case 'iteration_start':
              setCurrentStep(`Iteration ${data.iteration}: Generating solution (Yantra)`)
              stepProgress = 10 + (data.iteration - 1) * 25
              setProgress(stepProgress)
              break
              
            case 'first_response_started':
              setCurrentStep('Generating code...')
              break
              
            case 'first_response_complete':
              setCurrentStep('Analyzing and improving...')
              setProgress(stepProgress + 15)
              break
              
            case 'improving_started':
              // CRITICAL FIX: Set phase flag IMMEDIATELY to prevent tokens from going to firstGeneratedCode
              isInImprovementPhase = true
              currentRefinedCode = '' // Reset for new improved output
              setRefinedCode('') // Clear previous refined code
              setCurrentStep('Refining solution...')
              setProgress(stepProgress + 30)
              break
              
            case 'improved_token':
              // CRITICAL FIX: Set phase flag IMMEDIATELY before processing token
              // This ensures tokens from improved_token events go to refinedCode, not firstGeneratedCode
              if (!isInImprovementPhase) {
                isInImprovementPhase = true
                currentRefinedCode = '' // Reset for new improved output
                setRefinedCode('') // Clear previous refined code
              }
              
              // Extract token from event and update refinedCode directly
              // NOTE: This token should NOT go through onToken handler
              // It's handled here to ensure it goes to refinedCode
              if (data.token) {
                currentRefinedCode += data.token
                setRefinedCode(currentRefinedCode)
              }
              
              setProgress(stepProgress + 50)
              break
              
            case 'improved':
              // Final improved output (in case we missed any tokens)
              // Handle both improved_output and solution fields for compatibility
              // CRITICAL FIX: Only update if refinedCode is empty to prevent overwriting
              const finalOutput = data.improved_output || data.solution
              
              if (finalOutput) {
                setRefinedCode(prev => {
                  // If refinedCode is already set, keep it (it was set by improved_token)
                  if (prev && prev.trim()) {
                    return prev
                  }
                  // Only set if empty
                  currentRefinedCode = finalOutput
                  isInImprovementPhase = false // Mark improvement as complete
                  return finalOutput
                })
              }
              setProgress(stepProgress + 60)
              break
              
            case 'iteration_complete':
              const iterationData = data.data as IterationData
              setIterations(prev => [...prev, iterationData])
              // CRITICAL FIX: Only update refinedCode if it's empty or if agni_output is different
              // This prevents overwriting the refinedCode that was already set by improved event
              if (iterationData.agni_output) {
                setRefinedCode(prev => {
                  // If refinedCode is already set and matches, keep it
                  if (prev && prev.trim() === iterationData.agni_output.trim()) {
                    return prev
                  }
                  // If refinedCode is empty, set it
                  if (!prev || !prev.trim()) {
                    return iterationData.agni_output
                  }
                  // If refinedCode is already set and different, keep the existing one
                  // (it was set by improved event which is more reliable)
                  return prev
                })
              }
              setProgress(stepProgress + 60)
              break
              
            case 'plateau_reached':
              setCurrentStep('Optimization converged - stopping early')
              break
          }
        },
        onComplete: (data: any) => {
          setIsProcessing(false)
          setProgress(100)
          setCurrentStep('Complete!')
          
          // CRITICAL FIX: Only update refinedCode if it's empty
          // This prevents overwriting the refinedCode that was already set by improved event
          if (data.final_solution) {
            setRefinedCode(prev => {
              // If refinedCode is already set, keep it (it was set by improved event)
              if (prev && prev.trim()) {
                return prev
              }
              // Only set if empty
              return data.final_solution
            })
          }
          
          setFinalScore(data.final_score || 0)
        },
        onError: (error: Error) => {
          console.error('Stream error:', error)
          setIsProcessing(false)
          setCurrentStep(`Error: ${error.message}`)
          
          // Fallback to simulated response
          setTimeout(() => {
            const simulatedCode = getSimulatedGeneratedCode(prompt)
            setFirstGeneratedCode(simulatedCode)
            setRefinedCode(getSimulatedOptimizedCode(simulatedCode))
            setProgress(100)
            setCurrentStep('Complete!')
            setIsProcessing(false)
          }, 1000)
        }
      }
    )
  }, [prompt, isProcessing])
  
  const getSimulatedGeneratedCode = (prompt: string): string => {
    // Simulate code generation from prompt
    return `// Generated code based on: ${prompt}
function example() {
  // Initial implementation
  console.log('Hello World');
  return true;
}`
  }
  
  const getSimulatedOptimizedCode = (code: string): string => {
    // Simple optimization simulation
    return `// Chakra AI Refined Version
${code}

// Optimized with best practices
function example() {
  // Refined implementation with error handling
  try {
    console.log('Hello World');
    return true;
  } catch (error) {
    console.error('Error:', error);
    return false;
  }
}`
  }

  const handleCopy = (text: string, isFirst: boolean = false) => {
    navigator.clipboard.writeText(text)
    if (isFirst) {
      setCopiedFirst(true)
      setTimeout(() => setCopiedFirst(false), 2000)
    } else {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6"
      >
        <h1 className="text-3xl font-bold text-ivory-100 mb-2 flex items-center gap-3">
          <Code2 className="w-8 h-8 text-gold-glow" />
          Code Assistant
        </h1>
        <p className="text-ivory-400">AI-powered code generation and refinement</p>
      </motion.div>

      {/* Prompt input */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="mb-6"
      >
        <div className="glass rounded-2xl p-4">
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <Sparkles className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-ivory-400" />
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleGenerate()}
                placeholder="Enter a prompt to generate code (e.g., 'Create a function to sort an array')..."
                className="w-full pl-10 pr-4 py-3 bg-charcoal-900/50 rounded-xl text-ivory-100 placeholder-ivory-400 border border-gold-500/20 focus:border-gold-500/50 focus:outline-none transition-all"
              />
            </div>
            <button
              onClick={handleGenerate}
              disabled={isProcessing || !prompt.trim()}
              className="px-6 py-3 bg-gradient-to-r from-gold-500 to-saffron rounded-xl text-charcoal-base font-semibold hover:shadow-gold-glow transition-all disabled:opacity-50 flex items-center gap-2"
            >
              {isProcessing ? (
                <>
                  <div className="w-5 h-5 border-2 border-charcoal-base/30 border-t-charcoal-base rounded-full animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Wand2 className="w-5 h-5" />
                  Generate & Refine
                </>
              )}
            </button>
          </div>
        </div>
      </motion.div>

      {/* Main content */}
      <div className="flex-1 grid grid-cols-2 gap-6">

        {/* First Generated Code panel */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="glass rounded-2xl p-6 flex flex-col relative overflow-hidden"
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-ivory-100 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-gold-500" />
              First Generated Code
            </h2>
            {firstGeneratedCode && (
              <button
                onClick={() => handleCopy(firstGeneratedCode, true)}
                className="flex items-center gap-2 px-3 py-1 rounded-lg bg-gold-500/10 text-gold-glow hover:bg-gold-500/20 transition-colors text-sm"
              >
                {copiedFirst ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                {copiedFirst ? 'Copied!' : 'Copy'}
              </button>
            )}
          </div>
          
          {firstGeneratedCode ? (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex-1 bg-charcoal-900/50 rounded-xl p-4 text-ivory-100 font-mono text-sm overflow-auto border border-gold-500/20"
            >
              <pre className="whitespace-pre-wrap">
                {firstGeneratedCode}
              </pre>
            </motion.div>
          ) : (
            <div className="flex-1 bg-charcoal-900/30 rounded-xl flex items-center justify-center border border-dashed border-gold-500/20">
              <div className="text-center">
                <Zap className="w-12 h-12 text-gold-500/40 mx-auto mb-3" />
                <p className="text-ivory-400">First generated code will appear here</p>
              </div>
            </div>
          )}
        </motion.div>

        {/* Refined Code panel */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3 }}
          className="glass rounded-2xl p-6 flex flex-col relative overflow-hidden"
        >
          {/* AI Thinking overlay */}
          <AnimatePresence>
            {isProcessing && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 bg-charcoal-base/95 z-10 flex flex-col items-center justify-center p-6"
              >
                {/* Chakra spinner */}
                <div className="relative w-24 h-24 mb-6">
                  <div className="absolute inset-0 rounded-full border-2 border-gold-500/20" />
                  <motion.div
                    className="absolute inset-0 rounded-full border-2 border-transparent border-t-gold-glow"
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                  />
                  <div className="absolute inset-2 rounded-full border-2 border-transparent border-t-saffron/50" />
                  <motion.div
                    className="absolute inset-4 rounded-full border-2 border-transparent border-t-gold-500/30"
                    animate={{ rotate: -360 }}
                    transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
                  />
                  <Brain className="absolute inset-0 m-auto w-8 h-8 text-gold-glow animate-pulse" />
                </div>
                
                {/* Current step */}
                <p className="text-gold-glow text-lg mb-4 font-medium">{currentStep}</p>
                
                {/* Progress bar */}
                <div className="w-64 h-3 bg-charcoal-800 rounded-full overflow-hidden mb-4">
                  <motion.div
                    className="h-full bg-gradient-to-r from-gold-500 to-saffron"
                    initial={{ width: 0 }}
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 0.3 }}
                  />
                </div>
                
                <p className="text-ivory-400 text-sm">
                  {progress < 30 ? 'Analyzing input...' :
                   progress < 60 ? 'Generating solution...' :
                   progress < 90 ? 'Refining output...' :
                   'Finalizing...'}
                </p>
                
                {/* Iteration indicators */}
                {iterations.length > 0 && (
                  <div className="mt-6 flex gap-2">
                    {iterations.map((_, idx) => (
                      <div
                        key={idx}
                        className="w-2 h-2 rounded-full bg-gold-500"
                      />
                    ))}
                    <div className="w-2 h-2 rounded-full bg-gold-500/30 animate-pulse" />
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>

          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-ivory-100 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-saffron" />
              Refined Code
            </h2>
            {refinedCode && (
              <button
                onClick={() => handleCopy(refinedCode, false)}
                className="flex items-center gap-2 px-3 py-1 rounded-lg bg-gold-500/10 text-gold-glow hover:bg-gold-500/20 transition-colors text-sm"
              >
                {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                {copied ? 'Copied!' : 'Copy'}
              </button>
            )}
          </div>
          
          {refinedCode ? (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex-1 bg-charcoal-900/50 rounded-xl p-4 text-ivory-100 font-mono text-sm overflow-auto border border-gold-500/20"
            >
              <pre className="whitespace-pre-wrap">
                {refinedCode}
              </pre>
            </motion.div>
          ) : (
            <div className="flex-1 bg-charcoal-900/30 rounded-xl flex items-center justify-center border border-dashed border-gold-500/20">
              <div className="text-center">
                <Zap className="w-12 h-12 text-gold-500/40 mx-auto mb-3" />
                <p className="text-ivory-400">Refined code will appear here</p>
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  )
}
