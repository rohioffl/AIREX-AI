import { useEffect } from 'react'

/**
 * Keyboard shortcuts hook for power-user navigation.
 * 
 * Shortcuts:
 * - / : Focus search bar
 * - a : Approve selected incident (if on incident detail page)
 * - r : Reject selected incident (if on incident detail page)
 * - ? : Show keyboard shortcuts help modal
 * - Esc : Close modals/dropdowns
 * - n : New incident (if on alerts page)
 * - u : User management (if admin)
 */
export function useKeyboardShortcuts({
  onSearchFocus = null,
  onApprove = null,
  onReject = null,
  onShowHelp = null,
  onClose = null,
  onNewIncident = null,
  onUserManagement = null,
  enabled = true,
}) {
  useEffect(() => {
    if (!enabled) return

    function handleKeyDown(e) {
      // Ignore if typing in input/textarea
      if (
        e.target.tagName === 'INPUT' ||
        e.target.tagName === 'TEXTAREA' ||
        e.target.isContentEditable
      ) {
        // Allow Esc to close modals even when typing
        if (e.key === 'Escape' && onClose) {
          onClose()
        }
        return
      }

      // Modifier keys
      const isCtrl = e.ctrlKey || e.metaKey
      const isShift = e.shiftKey
      const isAlt = e.altKey

      // / - Focus search
      if (e.key === '/' && !isCtrl && !isShift && !isAlt && onSearchFocus) {
        e.preventDefault()
        onSearchFocus()
        return
      }

      // ? - Show help
      if (e.key === '?' && !isCtrl && !isShift && !isAlt && onShowHelp) {
        e.preventDefault()
        onShowHelp()
        return
      }

      // Esc - Close
      if (e.key === 'Escape' && onClose) {
        e.preventDefault()
        onClose()
        return
      }

      // a - Approve (if on incident detail)
      if (e.key === 'a' && !isCtrl && !isShift && !isAlt && onApprove) {
        e.preventDefault()
        onApprove()
        return
      }

      // r - Reject (if on incident detail)
      if (e.key === 'r' && !isCtrl && !isShift && !isAlt && onReject) {
        e.preventDefault()
        onReject()
        return
      }

      // n - New incident
      if (e.key === 'n' && !isCtrl && !isShift && !isAlt && onNewIncident) {
        e.preventDefault()
        onNewIncident()
        return
      }

      // u - User management (admin only)
      if (e.key === 'u' && !isCtrl && !isShift && !isAlt && onUserManagement) {
        e.preventDefault()
        onUserManagement()
        return
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [enabled, onSearchFocus, onApprove, onReject, onShowHelp, onClose, onNewIncident, onUserManagement])
}
