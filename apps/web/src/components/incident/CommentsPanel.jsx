import { useState, useEffect, useCallback } from 'react'
import { MessageSquare, Send, User } from 'lucide-react'
import { fetchComments, createComment } from '../../services/api'
import { formatRelativeTime } from '../../utils/formatters'

export default function CommentsPanel({ incident }) {
  const [comments, setComments] = useState([])
  const [loading, setLoading] = useState(false)
  const [newComment, setNewComment] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const loadComments = useCallback(async () => {
    if (!incident?.id) return
    setLoading(true)
    try {
      const data = await fetchComments(incident.id)
      setComments(data || [])
    } catch (err) {
      console.error('Failed to load comments:', err)
    } finally {
      setLoading(false)
    }
  }, [incident?.id])

  useEffect(() => {
    loadComments()
  }, [loadComments])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!newComment.trim() || submitting) return

    setSubmitting(true)
    try {
      const comment = await createComment(incident.id, newComment.trim())
      setComments([...comments, comment])
      setNewComment('')
    } catch (err) {
      console.error('Failed to create comment:', err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="glass rounded-xl p-6">
      <div className="flex items-center gap-2 mb-4">
        <MessageSquare size={18} style={{ color: '#6366f1' }} />
        <h3 className="font-semibold" style={{ color: 'var(--text-heading)' }}>
          Comments
        </h3>
        <span className="px-2 py-0.5 rounded-full text-xs" style={{ background: 'var(--bg-input)', color: 'var(--text-muted)' }}>
          {comments.length}
        </span>
      </div>

      {loading ? (
        <div className="text-sm text-muted">Loading comments...</div>
      ) : comments.length === 0 ? (
        <div className="text-sm text-muted text-center py-8">
          No comments yet. Be the first to comment!
        </div>
      ) : (
        <div className="space-y-4 mb-4 max-h-96 overflow-y-auto">
          {comments.map((comment) => (
            <div key={comment.id} className="flex gap-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'rgba(99, 102, 241, 0.1)' }}>
                <User size={16} style={{ color: '#6366f1' }} />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-sm" style={{ color: 'var(--text-heading)' }}>
                    {comment.user_display_name || comment.user_email}
                  </span>
                  <span className="text-xs text-muted">
                    {formatRelativeTime(comment.created_at)}
                  </span>
                </div>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                  {comment.content}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={newComment}
          onChange={(e) => setNewComment(e.target.value)}
          placeholder="Add a comment..."
          className="flex-1 px-3 py-2 rounded-lg border border-border bg-input text-sm"
          disabled={submitting}
        />
        <button
          type="submit"
          disabled={!newComment.trim() || submitting}
          className="px-4 py-2 rounded-lg transition-all disabled:opacity-50"
          style={{ 
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', 
            color: '#fff',
            fontSize: 14,
            fontWeight: 600
          }}
        >
          <Send size={16} />
        </button>
      </form>
    </div>
  )
}
