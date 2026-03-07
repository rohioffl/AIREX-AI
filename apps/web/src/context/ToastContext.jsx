import { createContext, useContext, useState, useCallback } from 'react'

const ToastContext = createContext()

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismissToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const addToast = useCallback((toast) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
    const entry = { id, ...toast, createdAt: Date.now() }
    setToasts(prev => [...prev, entry])
    setTimeout(() => dismissToast(id), 6000)
    return id
  }, [dismissToast])

  const dismissAll = useCallback(() => setToasts([]), [])

  return (
    <ToastContext.Provider value={{ toasts, addToast, dismissToast, dismissAll }}>
      {children}
    </ToastContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components -- useToasts hook must co-locate with ToastProvider
export function useToasts() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToasts must be used within ToastProvider')
  return ctx
}
