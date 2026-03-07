import { StrictMode, Component } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  componentDidCatch(error, info) {
    console.error('AIREX ErrorBoundary:', error, info)
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, fontFamily: 'monospace', background: '#0f1117', color: '#f87171', minHeight: '100vh' }}>
          <h1 style={{ fontSize: 24, marginBottom: 16 }}>Something went wrong</h1>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 14, color: '#fbbf24' }}>
            {this.state.error?.message || 'Unknown error'}
          </pre>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, color: '#94a3b8', marginTop: 12 }}>
            {this.state.error?.stack || ''}
          </pre>
          <button
            onClick={() => window.location.reload()}
            style={{ marginTop: 24, padding: '8px 24px', background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer' }}
          >
            Reload
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
