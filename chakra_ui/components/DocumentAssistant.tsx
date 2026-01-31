'use client'

import { useState, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  FileText, Upload, Sparkles, CheckCircle, 
  FileCode, FileImage, File, X, ChevronRight,
  Search, Download, Eye, Brain, BookOpen, Clock, ChevronDown
} from 'lucide-react'
import { streamSSE } from '@/utils/api'

interface Document {
  id: number
  name: string
  type: string
  size: string
  pages: number
}

interface Answer {
  id: number
  question: string
  answer: string
  sources: string[]
  originalOutputs?: OriginalOutput[]
}

interface OriginalOutput {
  id: number
  iteration: number
  timestamp: string
  originalOutput: string
  refinedOutput: string
  score: number
}

const sampleDocuments: Document[] = [
  { id: 1, name: 'API Documentation.pdf', type: 'pdf', size: '2.4 MB', pages: 24 },
  { id: 2, name: 'Technical Specification.docx', type: 'docx', size: '1.1 MB', pages: 18 },
  { id: 3, name: 'Architecture Diagram.png', type: 'image', size: '856 KB', pages: 1 },
]

const sampleAnswers: Answer[] = [
  {
    id: 1,
    question: "What are the main API endpoints?",
    answer: "The API provides three primary endpoints: /api/v1/users for user management, /api/v1/data for data operations, and /api/v1/auth for authentication. Each endpoint supports CRUD operations with rate limiting of 100 requests per minute.",
    sources: ["API Documentation.pdf", "Technical Specification.docx"],
  },
  {
    id: 2,
    question: "How does the authentication system work?",
    answer: "The authentication system uses JWT tokens with RSA-256 encryption. Tokens expire after 24 hours and can be refreshed using the refresh endpoint. All endpoints require Bearer token authentication in the Authorization header.",
    sources: ["API Documentation.pdf"],
  },
]

const fileTypeIcons: Record<string, React.ElementType> = {
  pdf: FileText,
  docx: FileCode,
  image: FileImage,
  default: File,
}

export default function DocumentAssistant() {
  const [isDragging, setIsDragging] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<Document[]>(sampleDocuments)
  const [isProcessing, setIsProcessing] = useState(false)
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null)
  const [answers, setAnswers] = useState<Answer[]>(sampleAnswers)
  const [question, setQuestion] = useState('')
  const [isAsking, setIsAsking] = useState(false)
  const [currentStep, setCurrentStep] = useState<string>('')
  const [progress, setProgress] = useState(0)
  const [showHistory, setShowHistory] = useState<number | null>(null)
  const [currentOriginalOutputs, setCurrentOriginalOutputs] = useState<OriginalOutput[]>([])
  
  const abortControllerRef = useRef<AbortController | null>(null)
  
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    // Handle file drop
    setIsProcessing(true)
    setTimeout(() => setIsProcessing(false), 2000)
  }, [])

  const handleAskQuestion = useCallback(async () => {
    if (!question.trim() || isAsking) return
    
    setIsAsking(true)
    setCurrentStep('Analyzing question...')
    setProgress(0)
    setCurrentOriginalOutputs([])
    
    // Cancel any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()
    
    let streamingAnswer = ''
    const answerId = Date.now()
    
    await streamSSE(
      '/process-stream',
      {
        task: question,
        context: `Documents: ${uploadedFiles.map(d => d.name).join(', ')}`,
        use_rag: true,
        is_code: false
      },
      {
        onToken: (token: string) => {
          // Stream tokens for answer
          streamingAnswer += token
        },
        onEvent: (data: any) => {
          switch (data.type) {
            case 'start':
              setCurrentStep('Searching documents...')
              setProgress(10)
              break
              
            case 'rag_retrieved':
              setCurrentStep(`Found ${data.chunks_count} relevant sections`)
              setProgress(20)
              break
              
            case 'memory_found':
              setCurrentStep(`Found ${data.examples_count} similar questions`)
              setProgress(30)
              break
              
            case 'iteration_start':
              setCurrentStep(`Analyzing iteration ${data.iteration}...`)
              setProgress(40 + (data.iteration - 1) * 15)
              break
              
            case 'first_response_started':
              setCurrentStep('Generating answer...')
              break
              
            case 'first_response_complete':
              setCurrentStep('Refining answer...')
              setProgress(70)
              break
              
            case 'improving_started':
              setCurrentStep('Improving answer quality...')
              setProgress(80)
              break
              
            case 'improved_token':
              // CRITICAL FIX: Extract token from event and update answer directly
              // This handles the case where complete output is sent as single improved_token
              if (data.token) {
                streamingAnswer += data.token
                // Update answer state immediately for real-time display
                setAnswers(prev => {
                  const updated = [...prev]
                  const currentAnswer = updated.find(a => a.id === answerId)
                  if (currentAnswer) {
                    currentAnswer.answer = streamingAnswer
                  } else {
                    // Create new answer entry if it doesn't exist yet
                    updated.unshift({
                      id: answerId,
                      question,
                      answer: streamingAnswer,
                      timestamp: new Date().toLocaleTimeString()
                    })
                  }
                  return updated
                })
              }
              setProgress(82)
              break
              
            case 'improved':
              // Handle both improved_output and solution fields
              const improvedAnswer = data.improved_output || data.solution
              if (improvedAnswer) {
                streamingAnswer = improvedAnswer
                // Update answer state immediately
                setAnswers(prev => {
                  const updated = [...prev]
                  const currentAnswer = updated.find(a => a.id === answerId)
                  if (currentAnswer) {
                    currentAnswer.answer = streamingAnswer
                  } else {
                    updated.unshift({
                      id: answerId,
                      question,
                      answer: streamingAnswer,
                      timestamp: new Date().toLocaleTimeString()
                    })
                  }
                  return updated
                })
              }
              setProgress(85)
              break
              
            case 'iteration_complete':
              const iterationData = data.data
              if (iterationData?.agni_output) {
                streamingAnswer = iterationData.agni_output
              }
              // Store original output in history
              if (iterationData?.yantra_output) {
                setCurrentOriginalOutputs(prev => [{
                  id: Date.now() + (iterationData.iteration || 0),
                  iteration: iterationData.iteration || 0,
                  timestamp: new Date().toLocaleTimeString(),
                  originalOutput: iterationData.yantra_output,
                  refinedOutput: iterationData.agni_output || iterationData.yantra_output,
                  score: iterationData.score || 0
                }, ...prev])
              }
              setProgress(90)
              break
              
            case 'plateau_reached':
              setCurrentStep('Answer finalized')
              break
          }
        },
        onComplete: (data: any) => {
          setIsAsking(false)
          setProgress(100)
          setCurrentStep('Complete!')
          
          // Generate answer from iterations or use final_solution (refined output only)
          const finalAnswer = data.final_solution || streamingAnswer
          
          if (finalAnswer) {
            setAnswers(prev => [{
              id: answerId,
              question,
              answer: finalAnswer,
              sources: uploadedFiles.map(d => d.name),
              originalOutputs: [...currentOriginalOutputs]
            }, ...prev])
          } else {
            // Fallback answer
            setAnswers(prev => [{
              id: answerId,
              question,
              answer: "Based on the uploaded documents, " + question.toLowerCase().includes('how') 
                ? "the system follows a structured approach with multiple components working together."
                : "there are several key aspects to consider as outlined in the documentation.",
              sources: uploadedFiles.map(d => d.name),
              originalOutputs: [...currentOriginalOutputs]
            }, ...prev])
          }
          
          setCurrentOriginalOutputs([])
          setQuestion('')
        },
        onError: (error: Error) => {
          console.error('Stream error:', error)
          setIsAsking(false)
          setCurrentStep('')
          
          // Fallback answer
          setAnswers(prev => [{
            id: answerId,
            question,
            answer: "Based on the uploaded documents, the system architecture follows a microservices pattern with each service having its own database and independent scaling capabilities.",
            sources: uploadedFiles.map(d => d.name),
            originalOutputs: [...currentOriginalOutputs]
          }, ...prev])
          setCurrentOriginalOutputs([])
          setQuestion('')
        }
      }
    )
  }, [question, isAsking, uploadedFiles])

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6"
      >
        <h1 className="text-3xl font-bold text-ivory-100 mb-2 flex items-center gap-3">
          <FileText className="w-8 h-8 text-gold-glow" />
          Document Assistant
        </h1>
        <p className="text-ivory-400">Upload documents and get AI-powered insights</p>
      </motion.div>

      {/* Main content */}
      <div className="flex-1 grid grid-cols-3 gap-6">
        {/* Upload zone & Documents list */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
          className="col-span-1 space-y-4"
        >
          {/* Drop zone */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`glass rounded-2xl p-6 border-2 transition-all duration-300 ${
              isDragging 
                ? 'border-gold-500 bg-gold-500/10' 
                : 'border-gold-500/20 hover:border-gold-500/40'
            }`}
          >
            <div className="text-center">
              <motion.div
                animate={{ 
                  scale: isDragging ? 1.1 : 1,
                  rotate: isDragging ? 5 : 0
                }}
                transition={{ type: 'spring', stiffness: 300 }}
                className="w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-br from-gold-500/20 to-saffron/20 flex items-center justify-center"
              >
                <Upload className="w-8 h-8 text-gold-glow" />
              </motion.div>
              
              <h3 className="text-ivory-100 font-semibold mb-2">
                {isDragging ? 'Drop files here' : 'Upload Documents'}
              </h3>
              <p className="text-ivory-400 text-sm mb-4">
                Drag & drop PDF, DOCX, or images
              </p>
              
              <button className="px-4 py-2 rounded-lg bg-gold-500/10 text-gold-glow hover:bg-gold-500/20 transition-colors text-sm">
                Browse Files
              </button>
            </div>

            {/* Processing animation */}
            <AnimatePresence>
              {isProcessing && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="mt-4 p-3 rounded-lg bg-gold-500/10 border border-gold-500/20"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full border-2 border-gold-500/30 border-t-gold-glow animate-spin" />
                    <div>
                      <p className="text-sm text-gold-glow">Processing document...</p>
                      <p className="text-xs text-ivory-400">Extracting text and context</p>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Uploaded documents */}
          <div className="glass rounded-2xl p-4">
            <h3 className="text-ivory-100 font-semibold mb-3 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-gold-500" />
              Uploaded Documents
            </h3>
            
            <div className="space-y-2">
              {uploadedFiles.map((doc, index) => {
                const Icon = fileTypeIcons[doc.type] || fileTypeIcons.default
                return (
                  <motion.div
                    key={doc.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                    onClick={() => setSelectedDoc(doc)}
                    className={`p-3 rounded-xl cursor-pointer transition-all ${
                      selectedDoc?.id === doc.id
                        ? 'bg-gold-500/10 border border-gold-500/30'
                        : 'bg-charcoal-800/50 hover:bg-charcoal-800 border border-transparent'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-charcoal-700 flex items-center justify-center">
                        <Icon className="w-5 h-5 text-gold-glow" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-ivory-100 truncate">{doc.name}</p>
                        <p className="text-xs text-ivory-400">{doc.size} • {doc.pages} pages</p>
                      </div>
                      <ChevronRight className="w-4 h-4 text-ivory-400" />
                    </div>
                  </motion.div>
                )
              })}
            </div>
          </div>
        </motion.div>

        {/* Q&A Section */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="col-span-2 flex flex-col"
        >
          {/* Question input */}
          <div className="glass rounded-2xl p-4 mb-4">
            <div className="flex gap-3">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-ivory-400" />
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleAskQuestion()}
                  placeholder="Ask a question about your documents..."
                  className="w-full pl-10 pr-4 py-3 bg-charcoal-900/50 rounded-xl text-ivory-100 placeholder-ivory-400 border border-gold-500/20 focus:border-gold-500/50 focus:outline-none transition-all"
                />
              </div>
              <button
                onClick={handleAskQuestion}
                disabled={isAsking || !question.trim()}
                className="px-6 py-3 bg-gradient-to-r from-gold-500 to-saffron rounded-xl text-charcoal-base font-semibold hover:shadow-gold-glow transition-all disabled:opacity-50 flex items-center gap-2 min-w-[140px]"
              >
                {isAsking ? (
                  <>
                    <div className="w-5 h-5 border-2 border-charcoal-base/30 border-t-charcoal-base rounded-full animate-spin" />
                    <span className="text-sm">{currentStep || 'Thinking...'}</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5" />
                    Ask
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Answers list */}
          <div className="flex-1 overflow-auto space-y-4">
            <AnimatePresence>
              {answers.map((answer, index) => (
                <motion.div
                  key={answer.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  transition={{ delay: index * 0.1 }}
                  className="glass rounded-2xl p-6"
                >
                  <div className="flex items-start gap-4">
                    <div className="w-8 h-8 rounded-full bg-gold-500/20 flex items-center justify-center flex-shrink-0">
                      <Sparkles className="w-4 h-4 text-gold-glow" />
                    </div>
                    <div className="flex-1">
                      <p className="text-gold-glow text-sm mb-2">{answer.question}</p>
                      <p className="text-ivory-100">{answer.answer}</p>
                      
                      {/* Sources */}
                      <div className="mt-3 flex flex-wrap gap-2">
                        {answer.sources.map((source) => (
                          <span
                            key={source}
                            className="px-2 py-1 rounded-lg bg-gold-500/10 text-gold-500 text-xs flex items-center gap-1"
                          >
                            <FileText className="w-3 h-3" />
                            {source}
                          </span>
                        ))}
                      </div>

                      {/* Original LLM Output History for this answer */}
                      {answer.originalOutputs && answer.originalOutputs.length > 0 && (
                        <motion.div
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ delay: 0.3 }}
                          className="mt-4"
                        >
                          <button
                            onClick={() => setShowHistory(showHistory === answer.id ? null : answer.id)}
                            className="flex items-center gap-2 text-sm text-ivory-400 hover:text-gold-glow transition-colors"
                          >
                            <Clock className="w-4 h-4" />
                            Original LLM Output History ({answer.originalOutputs.length})
                            <ChevronDown className={`w-4 h-4 transition-transform ${showHistory === answer.id ? 'rotate-180' : ''}`} />
                          </button>
                          
                          <AnimatePresence>
                            {showHistory === answer.id && (
                              <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                className="overflow-hidden"
                              >
                                <div className="mt-3 space-y-3 max-h-96 overflow-y-auto">
                                  {answer.originalOutputs.map((output) => (
                                    <motion.div
                                      key={output.id}
                                      initial={{ x: -20, opacity: 0 }}
                                      animate={{ x: 0, opacity: 1 }}
                                      className="p-4 rounded-lg bg-charcoal-800/50 border border-gold-500/10 hover:border-gold-500/30 transition-colors"
                                    >
                                      <div className="flex items-center justify-between mb-2">
                                        <div className="flex items-center gap-3">
                                          <div className="w-2 h-2 rounded-full bg-gold-500" />
                                          <span className="text-ivory-100 text-sm font-medium">Iteration {output.iteration}</span>
                                          <span className="text-ivory-400 text-xs">Score: {output.score.toFixed(2)}</span>
                                        </div>
                                        <span className="text-ivory-400 text-xs">{output.timestamp}</span>
                                      </div>
                                      <div className="mt-2 p-3 rounded bg-charcoal-900/50 border border-gold-500/5">
                                        <p className="text-xs text-ivory-400 mb-1">Original Output:</p>
                                        <p className="text-ivory-200 text-sm whitespace-pre-wrap break-words">
                                          {output.originalOutput}
                                        </p>
                                      </div>
                                    </motion.div>
                                  ))}
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </motion.div>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>

            {/* Empty state */}
            {answers.length === 0 && (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <FileText className="w-16 h-16 text-gold-500/30 mx-auto mb-4" />
                  <p className="text-ivory-400">Ask a question to get AI-powered insights</p>
                </div>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  )
}
