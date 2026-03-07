import { useEffect } from 'react'

export function useKeyboardShortcuts({ searchRef, onEscape }) {
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === '/') {
        const activeTag = document.activeElement?.tagName
        if (activeTag === 'INPUT' || activeTag === 'TEXTAREA' || activeTag === 'SELECT') {
          return
        }
        e.preventDefault()
        if (searchRef?.current) {
          searchRef.current.focus()
        }
      } else if (e.key === 'Escape') {
        if (searchRef?.current) {
          searchRef.current.blur()
        }
        if (onEscape) {
          onEscape()
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [searchRef, onEscape])
}
