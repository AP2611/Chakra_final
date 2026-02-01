/**
 * API utility functions for backend communication
 */

const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

/**
 * Check if backend is healthy
 */
export async function checkHealth(): Promise<boolean> {
  try {
    // Create timeout manually for better compatibility
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 5000)
    
    const response = await fetch(`${API_URL}/health`, {
      method: 'GET',
      signal: controller.signal,
    })
    
    clearTimeout(timeoutId)
    const data = await response.json()
    return data.status === 'healthy'
  } catch (error) {
    console.error('Health check failed:', error)
    return false
  }
}

/**
 * Stream SSE events using ReadableStream API with token batching
 */
export async function streamSSE(
  endpoint: string,
  body: any,
  callbacks: {
    onToken?: (token: string) => void
    onEvent?: (event: any) => void
    onComplete?: (data: any) => void
    onError?: (error: Error) => void
  }
): Promise<void> {
  // Check health first
  const isHealthy = await checkHealth()
  if (!isHealthy) {
    callbacks.onError?.(new Error('Backend is not available. Please ensure the server is running.'))
    return
  }

  try {
    const response = await fetch(`${API_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    if (!response.body) {
      throw new Error('Response body is null')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let tokenBuffer = ''
    let lastUpdateTime = Date.now()
    const BATCH_SIZE = 1  // Smaller batch for faster updates
    const BATCH_INTERVAL = 5 // ms - faster updates

    const flushTokens = () => {
      if (tokenBuffer) {
        callbacks.onToken?.(tokenBuffer)
        tokenBuffer = ''
        lastUpdateTime = Date.now()
      }
    }

    const processLine = (line: string) => {
      if (line.startsWith('data: ')) {
        const jsonStr = line.slice(6) // Remove 'data: ' prefix
        try {
          const data = JSON.parse(jsonStr)
          
          if (data.type === 'token' && data.token) {
            // Regular token - batch and send to onToken
            tokenBuffer += data.token
            const now = Date.now()
            if (tokenBuffer.length >= BATCH_SIZE || (now - lastUpdateTime) >= BATCH_INTERVAL) {
              flushTokens()
            }
          } else if (data.type === 'improved_token' && data.token) {
            // CRITICAL FIX: improved_token should ONLY go to onEvent, NOT onToken
            // This prevents improved tokens from being routed to firstGeneratedCode
            // Call onEvent first to set phase flags
            callbacks.onEvent?.(data)
            // Do NOT route to onToken - onEvent handler will update refinedCode directly
          } else {
            // Flush any pending tokens before processing other events
            flushTokens()
            
            // Handle other event types
            callbacks.onEvent?.(data)
            
            if (data.type === 'end' || data.type === 'complete') {
              callbacks.onComplete?.(data)
            } else if (data.type === 'error') {
              // Handle both 'message' and 'error' fields for compatibility
              const errorMsg = data.message || data.error || 'Unknown error'
              callbacks.onError?.(new Error(errorMsg))
            }
          }
        } catch (e) {
          console.error('Failed to parse SSE data:', e, jsonStr)
        }
      }
    }

    while (true) {
      const { done, value } = await reader.read()
      
      if (done) {
        // Flush any remaining tokens
        flushTokens()
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || '' // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.trim()) {
          processLine(line.trim())
        }
      }
    }
  } catch (error) {
    callbacks.onError?.(error instanceof Error ? error : new Error('Unknown error'))
  }
}

/**
 * Analytics API functions
 */
export async function getAnalyticsMetrics() {
  try {
    const response = await fetch(`${API_URL}/analytics/metrics`)
    if (!response.ok) throw new Error('Failed to fetch metrics')
    return await response.json()
  } catch (error) {
    console.error('Error fetching metrics:', error)
    return {
      avg_improvement: 0.0,
      avg_latency: 0.0,
      avg_accuracy: 0.0,
      avg_iterations: 0.0,
      total_tasks: 0
    }
  }
}

export async function getQualityImprovementData(limit: number = 20) {
  try {
    const response = await fetch(`${API_URL}/analytics/quality-improvement?limit=${limit}`)
    if (!response.ok) throw new Error('Failed to fetch quality data')
    const data = await response.json()
    return data.data || []
  } catch (error) {
    console.error('Error fetching quality data:', error)
    return []
  }
}

export async function getPerformanceHistory(hours: number = 24) {
  try {
    const response = await fetch(`${API_URL}/analytics/performance-history?hours=${hours}`)
    if (!response.ok) throw new Error('Failed to fetch performance data')
    const data = await response.json()
    return data.data || []
  } catch (error) {
    console.error('Error fetching performance data:', error)
    return []
  }
}

export async function getRecentTasks(limit: number = 10) {
  try {
    const response = await fetch(`${API_URL}/analytics/recent-tasks?limit=${limit}`)
    if (!response.ok) throw new Error('Failed to fetch recent tasks')
    const data = await response.json()
    return data.tasks || []
  } catch (error) {
    console.error('Error fetching recent tasks:', error)
    return []
  }
}

/**
 * RAG Document Upload API functions
 */
export async function uploadDocument(file: File): Promise<{ success: boolean; filename: string; message: string }> {
  try {
    const formData = new FormData()
    formData.append('file', file)
    
    const response = await fetch(`${API_URL}/rag/upload`, {
      method: 'POST',
      body: formData,
    })
    
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to upload document')
    }
    
    return await response.json()
  } catch (error) {
    console.error('Error uploading document:', error)
    throw error
  }
}

export async function listDocuments(): Promise<{ documents: string[]; total_chunks: number; count: number }> {
  try {
    const response = await fetch(`${API_URL}/rag/documents`)
    if (!response.ok) throw new Error('Failed to fetch documents')
    return await response.json()
  } catch (error) {
    console.error('Error fetching documents:', error)
    return { documents: [], total_chunks: 0, count: 0 }
  }
}

export async function deleteDocument(source: string): Promise<{ success: boolean; message: string }> {
  try {
    const response = await fetch(`${API_URL}/rag/documents/${encodeURIComponent(source)}`, {
      method: 'DELETE',
    })
    
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to delete document')
    }
    
    return await response.json()
  } catch (error) {
    console.error('Error deleting document:', error)
    throw error
  }
}

export { API_URL }

