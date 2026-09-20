import { useEffect, useRef } from 'react'
import { useChat } from '../hooks/useChat'
import { MessageBubble } from './MessageBubble'
import { ChatInput } from './ChatInput'
import './ChatWindow.css'

const SUGGESTED_PROMPTS = [
  'What are the top 5 product categories by revenue?',
  'Show the monthly number of orders in 2017 as a line chart',
  'Which customer states have the slowest average delivery time?',
  'What percentage of reviews are 5 stars?',
]

export function ChatWindow() {
  const { messages, isStreaming, error, sendMessage, stopStreaming } = useChat()
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="chat-window">
      <header className="chat-window__header">
        <div>
          <h1 className="chat-window__title">SQL Agent</h1>
          <p className="chat-window__subtitle">Olist Brazilian E-Commerce</p>
        </div>
        {/* Hidden until the conversation sidebar exists; newConversation only clears the screen.
        <button onClick={newConversation} className="chat-window__new-btn">
          + New chat
        </button>
        */}
      </header>

      <main className="chat-window__main">
        {messages.length === 0 && (
          <div className="chat-window__empty">
            <div>
              <h2 className="chat-window__empty-title">Ask your data</h2>
              <p className="chat-window__empty-text">
                Ask questions about orders, customers, products, sellers, payments and reviews.
                Answers are computed with SQL against the database.
              </p>
            </div>

            <div className="chat-window__prompts">
              {SUGGESTED_PROMPTS.map(prompt => (
                <button key={prompt} onClick={() => sendMessage(prompt)} className="chat-window__prompt">
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="chat-window__messages">
          {messages.map(message => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {isStreaming && messages[messages.length - 1]?.role === 'user' && (
            <div className="chat-window__thinking-row">
              <div className="chat-window__thinking-bubble">
                <div className="chat-window__thinking-dots">
                  <span className="chat-window__dot" style={{ animationDelay: '0ms' }} />
                  <span className="chat-window__dot" style={{ animationDelay: '150ms' }} />
                  <span className="chat-window__dot" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}

          {error && <div className="chat-window__error">{error}</div>}

          <div ref={messagesEndRef} />
        </div>
      </main>

      <div className="chat-window__input-dock">
        <ChatInput onSend={sendMessage} onStop={stopStreaming} isStreaming={isStreaming} />
      </div>
    </div>
  )
}
