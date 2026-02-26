import { useState } from 'react'
import { Brain, Copy, ChevronDown } from 'lucide-react'

// Helper to get a preview of the analysis
function getAnalysisPreview(text, maxChars = 150) {
  if (!text) return 'No analysis available'
  const lines = text.split('\n').filter(l => l.trim() && !l.startsWith('===') && !l.startsWith('---'))
  const preview = lines.slice(0, 3).join(' ')
  if (preview.length <= maxChars) return preview
  return preview.substring(0, maxChars - 3) + '...'
}

export default function AIAnalysisPanel({ ragContext, recommendation }) {
  const [expanded, setExpanded] = useState(false)
  
  // Extract analysis text, excluding pattern analysis (which is shown separately in AIRecommendationApproval)
  let analysisText = null
  if (ragContext) {
    let filtered = ragContext
    
    // Check if pattern analysis exists in the context
    const hasPatternAnalysis = filtered.includes('=== Pattern Analysis') || 
                                filtered.includes('Pattern Analysis') ||
                                (filtered.includes('Historical Context:') && 
                                 (filtered.includes('Alert Type Patterns:') || filtered.includes('Temporal Patterns:')))
    
    if (hasPatternAnalysis) {
      // Find where pattern analysis section ends (look for section headers that come after pattern analysis)
      // Pattern analysis ends before "Similar Incidents:" or "Relevant Runbooks:"
      const sectionMarkers = [
        '\n\nSimilar Incidents:',
        '\n\nRelevant Runbooks:',
        'Similar Incidents:',
        'Relevant Runbooks:',
      ]
      
      let patternEndIndex = -1
      
      for (const marker of sectionMarkers) {
        const index = filtered.indexOf(marker)
        if (index > 0) {
          patternEndIndex = index
          break
        }
      }
      
      if (patternEndIndex > 0) {
        // Take everything after pattern analysis (including the section header)
        filtered = filtered.substring(patternEndIndex).trim()
      } else {
        // Pattern analysis is the only content, show nothing (it's in the other panel)
        filtered = null
      }
    }
    
    analysisText = filtered && filtered.length > 0 ? filtered : null
  }
  
  // Fallback to root_cause if no filtered analysis text
  if (!analysisText && recommendation?.root_cause) {
    analysisText = `Root Cause Analysis:\n\n${recommendation.root_cause}`
  }

  if (!analysisText) {
    return (
      <div className="glass rounded-xl overflow-hidden" style={{ width: '100%', boxSizing: 'border-box', borderLeft: '4px solid #818cf8' }}>
        <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: '1px solid var(--border)' }}>
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-md flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(129,140,248,0.1)', color: '#818cf8' }}>
              <Brain size={16} />
            </div>
            <div>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                AI Investigation
              </h3>
              <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                Analysis in progress...
              </p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="glass rounded-xl overflow-hidden" style={{ width: '100%', boxSizing: 'border-box', borderLeft: '4px solid #818cf8' }}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between px-5 py-4 w-full text-left transition-colors"
        style={{ 
          background: 'transparent',
          borderBottom: expanded ? '1px solid var(--border)' : 'none'
        }}
        onMouseEnter={(e) => e.currentTarget.style.opacity = '0.9'}
        onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div className="h-8 w-8 rounded-md flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(129,140,248,0.1)', color: '#818cf8' }}>
            <Brain size={16} />
          </div>
          <div className="flex-1 min-w-0">
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              AI Investigation
            </h3>
            {!expanded && (
              <p style={{ 
                fontSize: 11, 
                color: 'var(--text-muted)', 
                marginTop: 4,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}>
                {getAnalysisPreview(analysisText)}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', padding: '2px 6px', borderRadius: 4, background: 'var(--bg-input)' }}>
            {analysisText.length.toLocaleString()} chars
          </span>
          <ChevronDown 
            size={16} 
            style={{ 
              color: 'var(--text-muted)', 
              transform: expanded ? 'rotate(180deg)' : 'none', 
              transition: 'transform 0.2s' 
            }} 
          />
        </div>
      </button>

      {expanded && (
        <div className="p-5" style={{ borderTop: '1px solid var(--border)' }}>
          <div className="flex justify-between items-center mb-3">
            <div className="flex items-center gap-2">
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Full Analysis</span>
            </div>
            <button
              onClick={(ev) => {
                ev.stopPropagation()
                navigator.clipboard.writeText(analysisText)
              }}
              className="flex items-center gap-1 px-2 py-1 rounded transition-colors"
              style={{ fontSize: 11, fontWeight: 600, color: '#818cf8', background: 'var(--bg-input)' }}
              onMouseEnter={(e) => e.currentTarget.style.opacity = '0.8'}
              onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
            >
              <Copy size={11} /> Copy
            </button>
          </div>
          <div className="relative rounded" style={{ 
            maxHeight: '600px', 
            overflow: 'auto',
            background: 'var(--bg-input)',
            padding: '12px',
            border: '1px solid var(--border)'
          }}>
            <pre style={{ 
              fontFamily: 'var(--font-mono)', 
              fontSize: 11, 
              color: 'var(--terminal-text)', 
              whiteSpace: 'pre-wrap', 
              wordBreak: 'break-word', 
              lineHeight: 1.5,
              margin: 0,
              padding: 0
            }}>
              {analysisText}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
