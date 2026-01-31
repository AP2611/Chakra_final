'use client'

import { useState, useEffect, useCallback, useRef } from 'react'

export interface SSEEvent {
  type: string
  [key: string]: any
}

export interface UseSSEOptions {
  url: string
  enabled?: boolean
  onMessage?: (event: SSEEvent) => void
  onError?: (error: Event) => void
  onComplete?: () => void
  retryInterval?: number
  maxRetries?: number
}

export interface UseSSEReturn {
  isConnected: boolean
  isConnecting: boolean
  error: Error | null
  lastEvent: SSEEvent | null
  events: SSEEvent[]
  connect: () => void
  disconnect: () => void
  clearEvents: () => void
}

export function useSSE(options: UseSSEOptions): UseSSEReturn {
  const {
    url,
    enabled = true,
    onMessage,
    onError,
    onComplete,
    retryInterval = 3000,
    maxRetries = 5,
  } = options

  const [isConnected, setIsConnected] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [lastEvent, setLastEvent] = useState<SSEEvent | null>(null)
  const [events, setEvents] = useState<SSEEvent[]>([])

  const eventSourceRef = useRef<EventSource | null>(null)
  const retryCountRef = useRef(0)
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const clearEvents = useCallback(() => {
    setEvents([])
    setLastEvent(null)
  }, [])

  const disconnect = useCallback(() => {
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current)
      retryTimeoutRef.current = null
    }

    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }

    setIsConnected(false)
    setIsConnecting(false)
    retryCountRef.current = 0
  }, [])

  const connect = useCallback(() => {
    if (!enabled) return

    disconnect()

    try {
      setIsConnecting(true)
      setError(null)

      const eventSource = new EventSource(url)
      eventSourceRef.current = eventSource

      eventSource.onopen = () => {
        setIsConnected(true)
        setIsConnecting(false)
        setError(null)
        retryCountRef.current = 0
      }

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as SSEEvent
          setLastEvent(data)
          setEvents((prev) => [...prev, data])
          onMessage?.(data)
        } catch (parseError) {
          console.error('Failed to parse SSE event:', parseError)
        }
      }

      eventSource.onerror = (errorEvent) => {
        setIsConnected(false)
        setIsConnecting(false)
        setError(new Error('SSE connection error'))

        onError?.(errorEvent)

        // Attempt to reconnect
        if (retryCountRef.current < maxRetries) {
          retryCountRef.current++
          setIsConnecting(true)

          retryTimeoutRef.current = setTimeout(() => {
            connect()
          }, retryInterval)
        } else {
          eventSource.close()
          eventSourceRef.current = null
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to create SSE connection'))
      setIsConnecting(false)
    }
  }, [url, enabled, disconnect, onMessage, onError, retryInterval, maxRetries])

  useEffect(() => {
    if (enabled) {
      connect()
    }

    return () => {
      disconnect()
    }
  }, [enabled, connect, disconnect])

  // Complete callback when we receive a 'complete' event
  useEffect(() => {
    if (lastEvent?.type === 'complete') {
      onComplete?.()
    }
  }, [lastEvent, onComplete])

  return {
    isConnected,
    isConnecting,
    error,
    lastEvent,
    events,
    connect,
    disconnect,
    clearEvents,
  }
}

// Hook for making POST requests with SSE streaming
export function useSSEPost<T = any>(baseUrl: string) {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const postAndStream = useCallback(
    async (
      endpoint: string,
      data: any,
      options: {
        onMessage?: (event: SSEEvent) => void
        onError?: (error: Error) => void
        onComplete?: () => void
      } = {}
    ): Promise<SSEEvent[]> => {
      setIsLoading(true)
      setError(null)

      const collectedEvents: SSEEvent[] = []

      return new Promise((resolve, reject) => {
        const url = `${baseUrl}${endpoint}`
        
        try {
          const eventSource = new EventSource(url)

          eventSource.onmessage = (event) => {
            try {
              const parsedEvent = JSON.parse(event.data) as SSEEvent
              collectedEvents.push(parsedEvent)
              options.onMessage?.(parsedEvent)

              if (parsedEvent.type === 'complete') {
                eventSource.close()
                setIsLoading(false)
                options.onComplete?.()
                resolve(collectedEvents)
              }
            } catch (parseError) {
              console.error('Failed to parse SSE event:', parseError)
            }
          }

          eventSource.onerror = (errorEvent) => {
            eventSource.close()
            setIsLoading(false)
            const err = new Error('SSE connection error')
            setError(err)
            options.onError?.(err)
            reject(err)
          }
        } catch (err) {
          setIsLoading(false)
          const error = err instanceof Error ? err : new Error('Failed to initiate SSE')
          setError(error)
          options.onError?.(error)
          reject(error)
        }
      })
    },
    [baseUrl]
  )

  const postJSON = useCallback(
    async <T = any>(
      endpoint: string,
      data: any,
      signal?: AbortSignal
    ): Promise<T> => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch(`${baseUrl}${endpoint}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(data),
          signal,
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const result = await response.json()
        setIsLoading(false)
        return result as T
      } catch (err) {
        setIsLoading(false)
        const error = err instanceof Error ? err : new Error('Request failed')
        setError(error)
        throw error
      }
    },
    [baseUrl]
  )

  return {
    postAndStream,
    postJSON,
    isLoading,
    error,
  }
}
