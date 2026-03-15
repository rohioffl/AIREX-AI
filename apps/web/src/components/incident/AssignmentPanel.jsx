import { useState, useEffect } from 'react'
import { User, UserCheck, X } from 'lucide-react'
import { assignIncident, unassignIncident, fetchUsers } from '../../services/api'

export default function AssignmentPanel({ incident }) {
  const [users, setUsers] = useState([])
  const [assigning, setAssigning] = useState(false)
  const [showDropdown, setShowDropdown] = useState(false)

  const assignedToId = incident?.meta?.assigned_to
  const assignedUser = users.find(u => u.id === assignedToId)

  useEffect(() => {
    loadUsers()
  }, [])

  const loadUsers = async () => {
    try {
      const data = await fetchUsers()
      setUsers(data?.items || data || [])
    } catch (err) {
      console.error('Failed to load users:', err)
    }
  }

  const handleAssign = async (userId) => {
    setAssigning(true)
    try {
      await assignIncident(incident.id, userId)
      setShowDropdown(false)
      window.location.reload() // Refresh to show updated assignment
    } catch (err) {
      console.error('Failed to assign incident:', err)
      alert('Failed to assign incident: ' + (err.message || 'Unknown error'))
    } finally {
      setAssigning(false)
    }
  }

  const handleUnassign = async () => {
    setAssigning(true)
    try {
      await unassignIncident(incident.id)
      window.location.reload() // Refresh to show updated assignment
    } catch (err) {
      console.error('Failed to unassign incident:', err)
      alert('Failed to unassign incident: ' + (err.message || 'Unknown error'))
    } finally {
      setAssigning(false)
    }
  }

  return (
    <div className="glass rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <UserCheck size={18} style={{ color: 'var(--neon-indigo)' }} />
          <h3 className="font-semibold" style={{ color: 'var(--text-heading)' }}>
            Assignment
          </h3>
        </div>
      </div>

      {assignedUser ? (
        <div className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--bg-input)' }}>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'var(--glow-indigo)' }}>
              <User size={16} style={{ color: 'var(--neon-indigo)' }} />
            </div>
            <div>
              <div className="font-medium text-sm" style={{ color: 'var(--text-heading)' }}>
                {assignedUser.display_name || assignedUser.email}
              </div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                {assignedUser.email}
              </div>
            </div>
          </div>
          <button
            onClick={handleUnassign}
            disabled={assigning}
            className="p-1.5 rounded transition-colors disabled:opacity-50"
            style={{ 
              color: 'var(--color-accent-red)',
              background: 'var(--glow-rose)'
            }}
            title="Unassign"
          >
            <X size={14} />
          </button>
        </div>
      ) : (
        <div className="relative">
          <button
            onClick={() => setShowDropdown(!showDropdown)}
            disabled={assigning}
            className="w-full px-4 py-2 rounded-lg transition-all disabled:opacity-50 flex items-center justify-between"
            style={{ 
              background: 'var(--bg-input)',
              border: '1px solid var(--border)',
              color: 'var(--text-primary)',
              fontSize: 14,
              fontWeight: 500
            }}
          >
            <span>Assign to user...</span>
            <User size={16} style={{ color: 'var(--text-muted)' }} />
          </button>

          {showDropdown && (
            <>
              <div 
                className="fixed inset-0 z-10"
                onClick={() => setShowDropdown(false)}
              />
              <div 
                className="absolute top-full left-0 right-0 mt-2 glass rounded-lg shadow-lg z-20 max-h-64 overflow-y-auto"
                style={{ border: '1px solid var(--border)' }}
              >
                {users.map(user => (
                  <button
                    key={user.id}
                    onClick={() => handleAssign(user.id)}
                    className="w-full px-4 py-2 text-left hover:bg-input transition-colors flex items-center gap-2"
                    style={{ fontSize: 13 }}
                  >
                    <div className="w-6 h-6 rounded-full flex items-center justify-center" style={{ background: 'var(--glow-indigo)' }}>
                      <User size={12} style={{ color: 'var(--neon-indigo)' }} />
                    </div>
                    <div>
                      <div className="font-medium" style={{ color: 'var(--text-heading)' }}>
                        {user.display_name || user.email}
                      </div>
                      <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                        {user.email}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
