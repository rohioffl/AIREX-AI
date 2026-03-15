import { Component } from 'react'
import { AlertTriangle } from 'lucide-react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          className="flex items-center justify-center min-h-[400px] p-8"
          style={{ background: 'var(--bg-body)' }}
        >
          <div
            className="glass rounded-xl p-8 max-w-md w-full text-center"
            style={{ border: '1px solid rgba(244,63,94,0.2)' }}
          >
            <div
              className="mx-auto mb-4 flex items-center justify-center w-12 h-12 rounded-full"
              style={{ background: 'var(--glow-rose)' }}
            >
              <AlertTriangle size={24} style={{ color: 'var(--color-accent-red)' }} />
            </div>
            <h2
              className="text-lg font-bold mb-2"
              style={{ color: 'var(--text-heading)' }}
            >
              Something went wrong
            </h2>
            <p
              className="text-sm mb-4"
              style={{ color: 'var(--text-secondary)' }}
            >
              {this.state.error?.message || 'An unexpected error occurred.'}
            </p>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="px-4 py-2 rounded-lg text-sm font-semibold transition-all"
              style={{ background: 'var(--gradient-primary)', color: '#fff' }}
            >
              Try again
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
