import { useRef, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export type WidgetBlock = {
  id: string
  index: number
  status: 'loading' | 'ready'
  html: string
}

export type ProgressStep = {
  content: string
  sql?: string
  error?: string
}

export type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  isComplete: boolean
  progressUpdates: ProgressStep[]
  widgets: WidgetBlock[]
}

type StreamEvent = Record<string, unknown> & { type: string }

function parseSseBuffer(buffer: string): { events: StreamEvent[]; remaining: string } {
  const parts = buffer.split('\n\n')
  const remaining = parts.pop() ?? ''
  const events: StreamEvent[] = []

  for (const part of parts) {
    for (const line of part.split('\n')) {
      if (!line.startsWith('data: ')) continue
      try {
        events.push(JSON.parse(line.slice(6)))
      } catch {
        // Ignore malformed lines.
      }
    }
  }
  return { events, remaining }
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const streamingContentRef = useRef('')
  const abortControllerRef = useRef<AbortController | null>(null)

  function updateMessage(id: string, update: (message: Message) => Message) {
    setMessages(prev => prev.map(m => (m.id === id ? update(m) : m)))
  }

  function handleEvent(event: StreamEvent, messageId: string | null): string | null {
    if (event.type === 'conversation_meta') {
      setConversationId(event.conversation_id as string)
      return messageId
    }

    if (event.type === 'message_start') {
      const id = event.message_id as string
      streamingContentRef.current = ''
      setMessages(prev => [
        ...prev,
        { id, role: 'assistant', content: '', isComplete: false, progressUpdates: [], widgets: [] },
      ])
      return id
    }

    if (event.type === 'error') {
      setError(event.message as string)
      return messageId
    }

    if (!messageId) return messageId

    switch (event.type) {
      case 'progress': {
        const step: ProgressStep = {
          content: event.content as string,
          sql: event.sql as string | undefined,
          error: event.error as string | undefined,
        }
        updateMessage(messageId, m => ({ ...m, progressUpdates: [...m.progressUpdates, step] }))
        break
      }

      case 'message_delta': {
        streamingContentRef.current += event.chunk as string
        const content = streamingContentRef.current
        updateMessage(messageId, m => ({ ...m, content }))
        break
      }

      case 'block_start': {
        const block: WidgetBlock = {
          id: event.block_id as string,
          index: event.index as number,
          status: 'loading',
          html: '',
        }
        updateMessage(messageId, m => ({ ...m, widgets: [...m.widgets, block] }))
        break
      }

      case 'block_delta':
        updateMessage(messageId, m => ({
          ...m,
          widgets: m.widgets.map(w =>
            w.id === event.block_id ? { ...w, html: w.html + (event.chunk as string) } : w,
          ),
        }))
        break

      case 'block_stop': {
        const failed = event.is_complete === false
        updateMessage(messageId, m => ({
          ...m,
          widgets: failed
            ? m.widgets.filter(w => w.id !== event.block_id)
            : m.widgets.map(w => (w.id === event.block_id ? { ...w, status: 'ready' } : w)),
        }))
        break
      }

      case 'message_stop':
        updateMessage(messageId, m => ({ ...m, isComplete: true }))
        setIsStreaming(false)
        break
    }
    return messageId
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim()
    if (isStreaming || !trimmed) return

    setError(null)
    setIsStreaming(true)
    setMessages(prev => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: 'user',
        content: trimmed,
        isComplete: true,
        progressUpdates: [],
        widgets: [],
      },
    ])

    const abortController = new AbortController()
    abortControllerRef.current = abortController

    try {
      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation_id: conversationId, message: trimmed }),
        signal: abortController.signal,
      })

      if (!response.ok) throw new Error(`Server error: ${response.status}`)
      if (!response.body) throw new Error('Streaming is not supported by this browser')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let messageId: string | null = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const { events, remaining } = parseSseBuffer(buffer)
        buffer = remaining

        for (const event of events) {
          messageId = handleEvent(event, messageId)
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setError((err as Error).message)
      }
    } finally {
      setIsStreaming(false)
    }
  }

  function stopStreaming() {
    abortControllerRef.current?.abort()
    setIsStreaming(false)
    setMessages(prev =>
      prev.map(m =>
        m.isComplete
          ? m
          : { ...m, isComplete: true, widgets: m.widgets.filter(w => w.status === 'ready') },
      ),
    )
  }

  function newConversation() {
    abortControllerRef.current?.abort()
    setMessages([])
    setConversationId(null)
    setIsStreaming(false)
    setError(null)
    streamingContentRef.current = ''
  }

  return {
    messages,
    conversationId,
    isStreaming,
    error,
    sendMessage,
    stopStreaming,
    newConversation,
  }
}
