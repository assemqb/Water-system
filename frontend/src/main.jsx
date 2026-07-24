import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import { ErrorBoundary } from './components/ErrorBoundary.jsx'
import { LanguageProvider } from './i18n/LanguageContext.jsx'
import { ThemeProvider } from './i18n/ThemeContext.jsx'
import './styles/tokens.css'
import './styles/chat.css'
import './styles/story.css'
import './styles/dashboard.css'
import './styles/experience.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <ThemeProvider>
        <LanguageProvider>
          <App />
        </LanguageProvider>
      </ThemeProvider>
    </ErrorBoundary>
  </React.StrictMode>,
)
