import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'
import type { Message } from '../hooks/useChat'
import { WidgetBlock } from './WidgetBlock'
import './MessageBubble.css'

interface MessageBubbleProps {
  message: Message
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const variant = isUser ? 'user' : 'assistant'
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    navigator.clipboard.writeText(message.content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div className={`message-bubble message-bubble--${variant}`}>
      <div className={`message-bubble__col message-bubble__col--${variant}`}>
        <p className={`message-bubble__label message-bubble__label--${variant}`}>
          {isUser ? 'You' : 'Assistant'}
        </p>

        {!isUser && message.progressUpdates.length > 0 && (
          <div className="message-bubble__progress">
            {message.progressUpdates.map((step, i) => {
              const isLast = i === message.progressUpdates.length - 1
              const active = !message.isComplete && isLast && message.content === ''
              return (
                <div key={i}>
                  <div className="message-bubble__progress-step">
                    <span
                      className={
                        active
                          ? 'message-bubble__progress-dot message-bubble__progress-dot--active'
                          : 'message-bubble__progress-dot'
                      }
                    />
                    {step.content}
                  </div>
                  {step.sql && (
                    <details className="message-bubble__sql">
                      <summary className="message-bubble__sql-summary">View SQL</summary>
                      <pre className="message-bubble__sql-code">{step.sql}</pre>
                    </details>
                  )}
                  {step.error && <p className="message-bubble__sql-error">{step.error}</p>}
                </div>
              )
            })}
          </div>
        )}

        <div className={`message-bubble__body message-bubble__body--${variant}`}>
          {isUser ? (
            <p className="message-bubble__text">{message.content}</p>
          ) : (
            <div className="message-bubble__markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
                {message.content}
              </ReactMarkdown>
              {!message.isComplete && <span className="message-bubble__cursor" />}
            </div>
          )}
        </div>

        {!isUser && message.widgets.length > 0 && (
          <div>
            {[...message.widgets]
              .sort((a, b) => a.index - b.index)
              .map(w => (
                <WidgetBlock key={w.id} block={w} />
              ))}
          </div>
        )}

        {!isUser && message.isComplete && message.content && (
          <button onClick={handleCopy} className="message-bubble__copy">
            {copied ? 'Copied' : 'Copy'}
          </button>
        )}
      </div>
    </div>
  )
}
