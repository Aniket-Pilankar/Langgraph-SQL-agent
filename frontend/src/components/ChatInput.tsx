import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import { useVoice } from '../hooks/useVoice'
import './ChatInput.css'

interface ChatInputProps {
  onSend: (message: string) => void
  onStop: () => void
  isStreaming: boolean
}

const MAX_TEXTAREA_HEIGHT = 140

export function ChatInput({ onSend, onStop, isStreaming }: ChatInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { isSupported, isListening, transcript, start, stop } = useVoice()
  const baseValueRef = useRef('')

  useEffect(() => {
    if (!isListening) return
    const base = baseValueRef.current
    const separator = base && transcript ? ' ' : ''
    setValue(base + separator + transcript)
  }, [transcript, isListening])

  function handleMicClick() {
    if (isListening) {
      stop()
    } else {
      baseValueRef.current = value
      start()
    }
  }

  function handleSend() {
    if (!value.trim() || isStreaming) return
    if (isListening) stop()
    onSend(value.trim())
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function handleInput() {
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT)}px`
    }
  }

  return (
    <div className="chat-input">
      <div className="chat-input__field">
        {isSupported && (
          <button
            onClick={handleMicClick}
            disabled={isStreaming}
            className={isListening ? 'chat-input__mic chat-input__mic--on' : 'chat-input__mic'}
            title={isListening ? 'Stop listening' : 'Speak your question'}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"
              />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v4" />
            </svg>
          </button>
        )}

        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder={isListening ? 'Listening…' : 'Ask anything about the Olist e-commerce data…'}
          disabled={isStreaming}
          rows={1}
          className="chat-input__textarea"
        />

        {isStreaming ? (
          <button onClick={onStop} className="chat-input__stop-btn" title="Stop generating">
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
              <rect x="5" y="5" width="14" height="14" rx="2" />
            </svg>
          </button>
        ) : (
          <button onClick={handleSend} disabled={!value.trim()} className="chat-input__send-btn" title="Send (Enter)">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        )}
      </div>
      <p className="chat-input__hint">
        {isListening ? 'Listening — speak your question, then press send' : 'Enter to send · Shift+Enter for new line'}
      </p>
    </div>
  )
}
