import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { useLanguage } from '../i18n/LanguageContext.jsx'

function renderMarkdownLight(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br/>')
    .replace(/_(.*?)_/g, '<em>$1</em>')
}

export function ChatPanel({ filters, open, onToggle, experience = false }) {
  const { t, lang } = useLanguage()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [suggestions, setSuggestions] = useState([])
  const [modeLabel, setModeLabel] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => {
    if (!open) return
    setMessages([{ role: 'assistant', text: t('analyst.welcome') }])
    setSuggestions([])
  }, [lang, open, t])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const send = async (text) => {
    const msg = (text || input).trim()
    if (!msg || loading) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: msg }])
    setLoading(true)
    try {
      const res = await api.chat({ ...filters, message: msg, lang })
      setMessages((m) => [...m, { role: 'assistant', text: res.reply }])
      if (res.suggestions?.length) setSuggestions(res.suggestions)
      if (res.source === 'ollama' && res.model) {
        setModeLabel(`${t('analyst.poweredByOllama')} · ${res.model}`)
      } else if (res.source === 'fallback') {
        setModeLabel(t('analyst.fallbackMode'))
      }
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', text: `${t('analyst.error')} ${e.message}` }])
    } finally {
      setLoading(false)
    }
  }

  if (!open) {
    return (
      <button type="button" className={`chat-fab ${experience ? 'chat-fab--experience' : ''}`} onClick={onToggle} aria-label={t('analyst.open')}>
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true">
          <path d="M12 3a9 9 0 00-9 9c0 1.5.4 2.9 1 4.1L3 21l4.9-1.1A9 9 0 1012 3z" stroke="currentColor" strokeWidth="1.5"/>
        </svg>
      </button>
    )
  }

  return (
    <aside className={`chat-dock ${experience ? 'chat-dock--experience' : ''}`} aria-label={t('analyst.title')}>
      <header className="chat-dock__head">
        <div>
          <div className="chat-dock__title">{t('analyst.title')}</div>
          <div className="chat-dock__sub">
            {modeLabel || t('analyst.subtitle')}
          </div>
        </div>
        <button type="button" className="icon-btn" onClick={onToggle} aria-label={t('analyst.close')}>×</button>
      </header>

      <div className="chat-messages">
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble chat-bubble--${m.role}`}>
            {m.role === 'assistant' ? (
              <div dangerouslySetInnerHTML={{ __html: renderMarkdownLight(m.text) }} />
            ) : (
              m.text
            )}
          </div>
        ))}
        {loading && (
          <div className="chat-bubble chat-bubble--assistant chat-bubble--typing">
            {t('analyst.thinking')}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {suggestions.length > 0 && (
        <div className="chat-suggestions">
          {suggestions.slice(0, 3).map((s) => (
            <button key={s} type="button" className="chat-suggest-btn" onClick={() => send(s)}>
              {s}
            </button>
          ))}
        </div>
      )}

      <form
        className="chat-input-row"
        onSubmit={(e) => {
          e.preventDefault()
          send()
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t('analyst.placeholder')}
          maxLength={500}
        />
        <button type="submit" className="chat-send" disabled={loading || !input.trim()}>
          {t('analyst.send')}
        </button>
      </form>
    </aside>
  )
}
