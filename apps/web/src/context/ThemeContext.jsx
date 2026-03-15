import { createContext, useContext, useState, useEffect } from 'react'
import { flushSync } from 'react-dom'

const ThemeContext = createContext()

export function ThemeProvider({ children }) {
  const [isDark, setIsDark] = useState(() => {
    const saved = localStorage.getItem('airex-theme')
    return saved ? saved === 'dark' : true
  })

  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDark)
    document.body.classList.toggle('light-mode', !isDark)
    localStorage.setItem('airex-theme', isDark ? 'dark' : 'light')
  }, [isDark])

  const toggle = (e) => {
    // Grab click coordinates to anchor the ripple; fall back to center
    const x = e?.clientX ?? window.innerWidth / 2
    const y = e?.clientY ?? window.innerHeight / 2

    // No View Transitions support → instant swap
    if (!document.startViewTransition) {
      setIsDark(prev => !prev)
      return
    }

    const endRadius = Math.hypot(
      Math.max(x, window.innerWidth - x),
      Math.max(y, window.innerHeight - y)
    )

    const transition = document.startViewTransition(() => {
      // flushSync forces React to apply the DOM update synchronously
      // so the view transition snapshot captures the new theme
      flushSync(() => setIsDark(prev => !prev))
    })

    // Once the transition pseudo-elements are ready, drive the clip-path.
    // Always expand the NEW snapshot as a circle — works for both directions.
    transition.ready.then(() => {
      document.documentElement.animate(
        {
          clipPath: [
            `circle(0px at ${x}px ${y}px)`,
            `circle(${endRadius}px at ${x}px ${y}px)`,
          ],
        },
        { duration: 500, easing: 'ease-in-out', pseudoElement: '::view-transition-new(root)' }
      )
    })
  }

  return (
    <ThemeContext.Provider value={{ isDark, toggle }}>
      {children}
    </ThemeContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components -- useTheme hook must co-locate with ThemeProvider
export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
