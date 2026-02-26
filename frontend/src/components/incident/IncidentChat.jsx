import { useState, useRef, useEffect, useCallback } from 'react'
import { MessageSquare, Send, Loader, Trash2, ChevronDown } from 'lucide-react'
import { sendChatMessage, fetchChatHistory, clearChatHistory } from '../../services/api'

export default function IncidentChat({ incidentId }) {
  const [expanded, setExpanded] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  // Load history when first expanded
  useEffect(() => {
    if (expanded && !historyLoaded) {
      loadHistory()
    }
  }, [expanded]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (expanded) {
      scrollToBottom()
      inputRef.current?.focus()
    }
  }, [expanded, messages.length, scrollToBottom])

  async function loadHistory() {
    try {
      const history = await fetchChatHistory(incidentId)
      if (history && history.length > 0) {
        setMessages(history)
      }
      setHistoryLoaded(true)
    } catch {
      // Silently fail — empty chat is fine
      setHistoryLoaded(true)
    }
  }

  async function handleSend() {
    const msg = input.trim()
    if (!msg || loading) return

    setInput('')
    setError(null)
    setMessages(prev => [...prev, { role: 'user', content: msg }])
    setLoading(true)

    try {
      const response = await sendChatMessage(incidentId, msg)
      setMessages(prev => [...prev, { role: 'assistant', content: response.reply }])
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to get AI response'
      setError(errorMsg)
      // Remove the optimistic user message on failure
      setMessages(prev => prev.slice(0, -1))
      setInput(msg) // Restore input
    } finally {
      setLoading(false)
    }
  }

  async function handleClear() {
    try {
      await clearChatHistory(incidentId)
      setMessages([])
      setError(null)
    } catch {
      // Silently fail
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="glass rounded-xl overflow-hidden" style={{ borderLeft: '4px solid #06b6d4' }}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between px-5 py-4 w-full text-left transition-colors"
        style={{ background: 'transparent' }}
      >
        <div className="flex items-center gap-3">
          <div
            className="h-8 w-8 rounded-md flex items-center justify-center"
            style={{ background: 'rgba(6,182,212,0.1)', color: '#06b6d4' }}
          >
            <MessageSquare size={16} />
          </div>
          <div>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              AI Chat
            </h3>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              Ask questions about this incident
              {messages.length > 0 && ` \u2022 ${Math.floor(messages.length / 2)} exchange${Math.floor(messages.length / 2) !== 1 ? 's' : ''}`}
            </p>
          </div>
        </div>
        <ChevronDown
          size={16}
          style={{
            color: 'var(--text-muted)',
            transform: expanded ? 'rotate(180deg)' : 'none',
            transition: 'transform 0.2s',
          }}
        />
      </button>

      {expanded && (
        <div style={{ borderTop: '1px solid var(--border)' }}>
          {/* Messages area */}
          <div
            className="space-y-3 p-4"
            style={{ maxHeight: 400, overflowY: 'auto', minHeight: 120 }}
          >
            {messages.length === 0 && !loading && (
              <div className="text-center py-6">
                <MessageSquare size={24} style={{ color: 'var(--text-muted)', margin: '0 auto 8px' }} />
                <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  Ask about root cause, remediation steps, or historical patterns.
                </p>
                <div className="flex flex-wrap gap-2 justify-center mt-3">
                  {[
                    'What caused this incident?',
                    'Has this happened before?',
                    'Is the recommended action safe?',
                  ].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => {
                        setInput(suggestion)
                        inputRef.current?.focus()
                      }}
                      className="px-3 py-1.5 rounded-lg transition-colors"
                      style={{
                        fontSize: 11,
                        color: '#06b6d4',
                        background: 'rgba(6,182,212,0.06)',
                        border: '1px solid rgba(6,182,212,0.15)',
                      }}
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div
                key={idx}
                className="flex gap-3"
                style={{ justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}
              >
                <div
                  className="rounded-lg px-4 py-3"
                  style={{
                    maxWidth: '85%',
                    fontSize: 12,
                    lineHeight: 1.6,
                    color: msg.role === 'user' ? 'white' : 'var(--text-primary)',
                    background: msg.role === 'user'
                      ? 'linear-gradient(135deg, #6366f1, #818cf8)'
                      : 'var(--bg-input)',
                    border: msg.role === 'user'
                      ? 'none'
                      : '1px solid var(--border)',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {msg.content}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex gap-3">
                <div
                  className="rounded-lg px-4 py-3 flex items-center gap-2"
                  style={{
                    fontSize: 12,
                    color: 'var(--text-muted)',
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border)',
                  }}
                >
                  <Loader size={12} className="animate-spin" />
                  Thinking...
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Error */}
          {error && (
            <div className="mx-4 mb-2 px-3 py-2 rounded-md" style={{ fontSize: 11, color: '#fb7185', background: 'rgba(244,63,94,0.08)' }}>
              {error}
            </div>
          )}

          {/* Input */}
          <div
            className="flex items-center gap-2 px-4 py-3"
            style={{ borderTop: '1px solid var(--border)', background: 'var(--bg-input)' }}
          >
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about this incident..."
              disabled={loading}
              className="flex-1 rounded-lg px-3 py-2"
              style={{
                fontSize: 12,
                color: 'var(--text-primary)',
                background: 'var(--bg-card)',
                border: '1px solid var(--border)',
                outline: 'none',
              }}
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="flex items-center justify-center rounded-lg transition-colors disabled:opacity-40"
              style={{
                width: 36,
                height: 36,
                background: 'linear-gradient(135deg, #06b6d4, #0891b2)',
                color: 'white',
              }}
            >
              <Send size={14} />
            </button>
            {messages.length > 0 && (
              <button
                onClick={handleClear}
                className="flex items-center justify-center rounded-lg transition-colors"
                style={{
                  width: 36,
                  height: 36,
                  color: 'var(--text-muted)',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border)',
                }}
                title="Clear chat history"
              >
                <Trash2 size={14} />
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
