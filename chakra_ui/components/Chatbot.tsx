'use client'

import { useState, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  MessageCircle, Send, Sparkles, Copy, Check, Brain, User
} from 'lucide-react'
import { streamSSE } from '@/utils/api'

interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

export default function Chatbot() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [currentStep, setCurrentStep] = useState<string>('')
  const [progress, setProgress] = useState(0)
  const [iterations, setIterations] = useState<number[]>([])
  const [tokenCount, setTokenCount] = useState(0)
  const [currentIteration, setCurrentIteration] = useState(0)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleSend = useCallback(async () => {
    if (!input.trim() || isProcessing) return

    const userMessage: Message = {
      id: Date.now(),
      role: 'user',
      content: input,
      timestamp: new Date().toLocaleTimeString()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsProcessing(true)
    setCurrentStep('Processing your prompt...')
    setProgress(0)
    setIterations([])
    setTokenCount(0)
    setCurrentIteration(0)

    // Cancel any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()

    // Create assistant message placeholder for streaming
    const assistantMessageId = Date.now()
    let assistantResponse = ''

    setMessages(prev => [...prev, {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toLocaleTimeString()
    }])

    await streamSSE(
      '/process-stream',
      {
        task: userMessage.content,
        context: '',
        use_rag: false,
        is_code: false
      },
      {
        onToken: (token: string) => {
          // Update assistant message with streaming tokens
          assistantResponse += token
          setTokenCount(prev => prev + 1)
          setMessages(prev => prev.map(msg => 
            msg.id === assistantMessageId 
              ? { ...msg, content: assistantResponse }
              : msg
          ))
          scrollToBottom()
        },
        onEvent: (data: any) => {
          switch (data.type) {
            case 'start':
              setCurrentStep('Starting analysis...')
              setProgress(10)
              break

            case 'memory_found':
              setCurrentStep(`Found ${data.examples_count} similar examples from memory`)
              setProgress(20)
              break

            case 'iteration_start':
              setCurrentIteration(data.iteration)
              setIterations(prev => {
                if (!prev.includes(data.iteration)) {
                  return [...prev, data.iteration]
                }
                return prev
              })
              setCurrentStep(`Generating response (Iteration ${data.iteration})...`)
              setProgress(30 + (data.iteration - 1) * 20)
              break

            case 'first_response_started':
              setCurrentStep('Generating response...')
              break

            case 'first_response_complete':
              setCurrentStep('Refining response...')
              setProgress(60)
              break

            case 'improving_started':
              setCurrentStep('Improving response quality...')
              setProgress(70)
              break

            case 'improved_token':
              // Extract token from event and update message directly
              // This handles the case where complete output is sent as single improved_token
              if (data.token) {
                assistantResponse += data.token
                // Update token count if provided
                if (data.token_count) {
                  setTokenCount(data.token_count)
                }
                setMessages(prev => prev.map(msg => 
                  msg.id === assistantMessageId 
                    ? { ...msg, content: assistantResponse }
                    : msg
                ))
                scrollToBottom()
              }
              setProgress(75)
              break

            case 'improved':
              // Handle both improved_output and solution fields
              const improvedContent = data.improved_output || data.solution
              if (improvedContent) {
                assistantResponse = improvedContent
                // Update token count if provided
                if (data.token_count) {
                  setTokenCount(data.token_count)
                }
                setMessages(prev => prev.map(msg => 
                  msg.id === assistantMessageId 
                    ? { ...msg, content: assistantResponse }
                    : msg
                ))
                scrollToBottom()
              }
              setProgress(80)
              break

            case 'iteration_complete':
              const iterationData = data.data
              if (iterationData?.agni_output && !assistantResponse) {
                assistantResponse = iterationData.agni_output
                setMessages(prev => prev.map(msg => 
                  msg.id === assistantMessageId 
                    ? { ...msg, content: assistantResponse }
                    : msg
                ))
              }
              // Track completed iteration
              if (data.iteration) {
                setIterations(prev => {
                  if (!prev.includes(data.iteration)) {
                    return [...prev, data.iteration]
                  }
                  return prev
                })
              }
              setProgress(90)
              break
          }
        },
        onComplete: (data: any) => {
          setIsProcessing(false)
          setProgress(100)
          setCurrentStep('')

          // Update with final response if we have one
          const finalResponse = data.final_solution || assistantResponse || 'I apologize, but I could not generate a response. Please try again.'
          
          // Log completion stats
          if (data.total_iterations) {
            console.log(`[Chatbot] Completed: ${data.total_iterations} iterations, ${tokenCount} tokens`)
          }
          
          setMessages(prev => prev.map(msg => 
            msg.id === assistantMessageId 
              ? { ...msg, content: finalResponse }
              : msg
          ))
          scrollToBottom()
        },
        onError: (error: Error) => {
          console.error('[Chatbot] Stream error:', error)
          setIsProcessing(false)
          setCurrentStep('')
          setProgress(0)

          // Show detailed error message
          const errorMessage = error.message || 'An error occurred. Please try again.'
          const detailedError = `Error: ${errorMessage}${tokenCount > 0 ? ` (Generated ${tokenCount} tokens before error)` : ''}${iterations.length > 0 ? ` (Completed ${iterations.length} iterations)` : ''}`
          
          setMessages(prev => prev.map(msg => 
            msg.id === assistantMessageId 
              ? { ...msg, content: detailedError }
              : msg
          ))
          scrollToBottom()
        }
      }
    )
  }, [input, isProcessing])

  const handleCopy = (text: string, messageId: number) => {
    navigator.clipboard.writeText(text)
    // You could add a visual feedback here if needed
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
          <MessageCircle className="w-8 h-8 text-gold-glow" />
          Chatbot
        </h1>
        <p className="text-ivory-400">AI-powered conversational assistant</p>
      </motion.div>

      {/* Messages area */}
      <div className="flex-1 glass rounded-2xl p-6 mb-6 overflow-hidden flex flex-col">
        <div className="flex-1 overflow-y-auto space-y-4 pr-2">
          <AnimatePresence>
            {messages.length === 0 ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex-1 flex items-center justify-center"
              >
                <div className="text-center">
                  <MessageCircle className="w-16 h-16 text-gold-500/30 mx-auto mb-4" />
                  <p className="text-ivory-400">Start a conversation by typing a message below</p>
                </div>
              </motion.div>
            ) : (
              messages.map((message) => (
                <motion.div
                  key={message.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className={`flex gap-4 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {message.role === 'assistant' && (
                    <div className="w-8 h-8 rounded-full bg-gold-500/20 flex items-center justify-center flex-shrink-0">
                      <Brain className="w-4 h-4 text-gold-glow" />
                    </div>
                  )}
                  
                  <div
                    className={`max-w-[70%] rounded-2xl p-4 ${
                      message.role === 'user'
                        ? 'bg-gold-500/10 border border-gold-500/20 text-ivory-100'
                        : 'bg-charcoal-800/50 border border-gold-500/10 text-ivory-100'
                    }`}
                  >
                    <p className="whitespace-pre-wrap break-words">{message.content}</p>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-xs text-ivory-400">{message.timestamp}</span>
                      {message.role === 'assistant' && (
                        <button
                          onClick={() => handleCopy(message.content, message.id)}
                          className="ml-2 text-ivory-400 hover:text-gold-glow transition-colors"
                        >
                          <Copy className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  </div>

                  {message.role === 'user' && (
                    <div className="w-8 h-8 rounded-full bg-gold-500/20 flex items-center justify-center flex-shrink-0">
                      <User className="w-4 h-4 text-gold-glow" />
                    </div>
                  )}
                </motion.div>
              ))
            )}
          </AnimatePresence>

          {/* Processing indicator */}
          {isProcessing && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex gap-4 justify-start"
            >
              <div className="w-8 h-8 rounded-full bg-gold-500/20 flex items-center justify-center flex-shrink-0">
                <Brain className="w-4 h-4 text-gold-glow animate-pulse" />
              </div>
              <div className="bg-charcoal-800/50 border border-gold-500/10 rounded-2xl p-4 flex-1">
                <div className="flex items-center gap-3">
                  <div className="relative w-6 h-6">
                    <div className="absolute inset-0 rounded-full border-2 border-gold-500/20" />
                    <motion.div
                      className="absolute inset-0 rounded-full border-2 border-transparent border-t-gold-glow"
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                    />
                  </div>
                  <div className="flex-1">
                    <p className="text-gold-glow text-sm font-medium">{currentStep || 'Thinking...'}</p>
                    {progress > 0 && (
                      <div className="w-full h-1 bg-charcoal-700 rounded-full overflow-hidden mt-1">
                        <motion.div
                          className="h-full bg-gradient-to-r from-gold-500 to-saffron"
                          initial={{ width: 0 }}
                          animate={{ width: `${progress}%` }}
                          transition={{ duration: 0.3 }}
                        />
                      </div>
                    )}
                    {/* Iteration and Token Count Display */}
                    <div className="flex items-center gap-4 mt-2 text-xs text-ivory-400">
                      {currentIteration > 0 && (
                        <span className="flex items-center gap-1">
                          <span className="text-gold-glow">Iteration:</span>
                          <span>{currentIteration}</span>
                        </span>
                      )}
                      {iterations.length > 0 && (
                        <span className="flex items-center gap-1">
                          <span className="text-gold-glow">Attempts:</span>
                          <span>{iterations.length}</span>
                        </span>
                      )}
                      {tokenCount > 0 && (
                        <span className="flex items-center gap-1">
                          <span className="text-gold-glow">Tokens:</span>
                          <span>{tokenCount}</span>
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input area */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass rounded-2xl p-4"
      >
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Sparkles className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-ivory-400" />
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              placeholder="Type your message here... (Press Enter to send, Shift+Enter for new line)"
              className="w-full pl-10 pr-4 py-3 bg-charcoal-900/50 rounded-xl text-ivory-100 placeholder-ivory-400 border border-gold-500/20 focus:border-gold-500/50 focus:outline-none transition-all resize-none"
              rows={1}
            />
          </div>
          <button
            onClick={handleSend}
            disabled={isProcessing || !input.trim()}
            className="px-6 py-3 bg-gradient-to-r from-gold-500 to-saffron rounded-xl text-charcoal-base font-semibold hover:shadow-gold-glow transition-all disabled:opacity-50 flex items-center gap-2"
          >
            {isProcessing ? (
              <>
                <div className="w-5 h-5 border-2 border-charcoal-base/30 border-t-charcoal-base rounded-full animate-spin" />
                Sending...
              </>
            ) : (
              <>
                <Send className="w-5 h-5" />
                Send
              </>
            )}
          </button>
        </div>
      </motion.div>
    </div>
  )
}

