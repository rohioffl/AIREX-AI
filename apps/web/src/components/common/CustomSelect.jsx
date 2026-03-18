import { useState, useRef, useEffect } from 'react'
import { ChevronDown, Check } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useTheme } from '../../context/ThemeContext'

const MotionDiv = motion.div

/**
 * CustomSelect — styled dropdown that matches the app's glass/neon design system.
 * Updated to match the frontend-patterns skill for Keyboard Navigation, Focus, and Animations.
 *
 * Props:
 *   value       – current selected value (string)
 *   onChange    – callback(newValue: string)
 *   options     – array of strings OR { value, label } objects
 *   placeholder – text shown when nothing is selected
 *   className   – extra wrapper className
 *   style       – extra wrapper style
 */
export default function CustomSelect({ value, onChange, options = [], placeholder = 'Select…', className = '', style = {} }) {
  const { isDark } = useTheme()
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const wrapperRef = useRef(null)
  const triggerRef = useRef(null)

  // Normalise option entries to { value, label }
  const normalised = options.map(o =>
    typeof o === 'string' ? { value: o, label: o } : o
  )

  // Include the placeholder as the first option for keyboard navigation
  const allOptions = [
    { value: '', label: placeholder, isPlaceholder: true },
    ...normalised
  ]
  const selectedIndex = allOptions.findIndex((option) => option.value === value)

  const selected = normalised.find(o => o.value === value)
  const displayLabel = selected ? selected.label : placeholder

  const closeDropdown = () => {
    setOpen(false)
    setActiveIndex(-1)
  }

  const openDropdown = () => {
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : 0)
    setOpen(true)
  }

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        closeDropdown()
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const handleKeyDown = (e) => {
    if (!open) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault()
        openDropdown()
      }
      return
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setActiveIndex(i => Math.min(i + 1, allOptions.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setActiveIndex(i => Math.max(i - 1, 0))
        break
      case 'Enter':
        e.preventDefault()
        if (activeIndex >= 0 && activeIndex < allOptions.length) {
          onChange(allOptions[activeIndex].value)
        }
        closeDropdown()
        triggerRef.current?.focus()
        break
      case 'Escape':
        e.preventDefault()
        closeDropdown()
        triggerRef.current?.focus()
        break
    }
  }

  const triggerStyle = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 6,
    padding: '6px 10px',
    borderRadius: 8,
    cursor: 'pointer',
    background: isDark ? 'var(--bg-elevated)' : '#FFFFFF',
    border: open
      ? `1px solid rgba(99,102,241,0.5)`
      : `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : '#E5E7EB'}`,
    color: value ? 'var(--text-primary)' : 'var(--text-muted)',
    fontSize: 13,
    fontWeight: 500,
    whiteSpace: 'nowrap',
    transition: 'border-color 0.15s, background 0.15s',
    boxShadow: isDark ? 'none' : '0 1px 2px rgba(0,0,0,0.05)',
    minWidth: 120,
    userSelect: 'none',
    ...style,
  }

  const dropdownStyle = {
    position: 'absolute',
    top: 'calc(100% + 4px)',
    left: 0,
    minWidth: '100%',
    zIndex: 9999,
    borderRadius: 10,
    padding: '4px',
    background: isDark ? 'rgba(15,18,28,0.98)' : '#FFFFFF',
    border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : '#E5E7EB'}`,
    boxShadow: isDark
      ? '0 8px 32px rgba(0,0,0,0.6), 0 0 0 1px rgba(99,102,241,0.1)'
      : '0 8px 24px rgba(0,0,0,0.12)',
    backdropFilter: 'blur(16px)',
    maxHeight: 260,
    overflowY: 'auto',
  }

  return (
    <div 
      ref={wrapperRef} 
      className={`relative ${className}`} 
      style={{ display: 'inline-block' }}
      onKeyDown={handleKeyDown}
    >
      <button
        ref={triggerRef}
        type="button"
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls="custom-select-listbox"
        onClick={() => {
          if (open) {
            closeDropdown()
          } else {
            openDropdown()
          }
        }}
        style={triggerStyle}
        onMouseEnter={(e) => {
          if (!open) e.currentTarget.style.borderColor = isDark ? 'rgba(255,255,255,0.15)' : '#D1D5DB'
        }}
        onMouseLeave={(e) => {
          if (!open) e.currentTarget.style.borderColor = isDark ? 'rgba(255,255,255,0.08)' : '#E5E7EB'
        }}
      >
        <span style={{ flex: 1, textAlign: 'left', color: value ? 'var(--text-primary)' : 'var(--text-muted)' }}>
          {displayLabel}
        </span>
        <ChevronDown
          size={13}
          style={{
            color: 'var(--text-muted)',
            transition: 'transform 0.2s',
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
            flexShrink: 0,
          }}
        />
      </button>

      <AnimatePresence>
        {open && (
          <MotionDiv
            id="custom-select-listbox"
            role="listbox"
            style={dropdownStyle}
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
          >
            {allOptions.map((opt, index) => {
              if (opt.isPlaceholder) {
                return (
                  <div key="placeholder-group">
                    <DropdownItem
                      label={opt.label}
                      isSelected={!value}
                      isActive={index === activeIndex}
                      isDark={isDark}
                      onClick={() => { onChange(''); closeDropdown(); triggerRef.current?.focus() }}
                      isMuted
                    />
                    {normalised.length > 0 && (
                      <div style={{ height: 1, background: isDark ? 'rgba(255,255,255,0.06)' : '#F3F4F6', margin: '3px 4px' }} role="separator" />
                    )}
                  </div>
                )
              }
              return (
                <DropdownItem
                  key={opt.value}
                  label={opt.label}
                  isSelected={opt.value === value}
                  isActive={index === activeIndex}
                  isDark={isDark}
                  onClick={() => { onChange(opt.value); closeDropdown(); triggerRef.current?.focus() }}
                />
              )
            })}
          </MotionDiv>
        )}
      </AnimatePresence>
    </div>
  )
}

function DropdownItem({ label, isSelected, isActive, isDark, onClick, isMuted }) {
  const [hovered, setHovered] = useState(false)
  const highlight = isActive || hovered

  return (
    <div
      role="option"
      aria-selected={isSelected}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '7px 10px',
        borderRadius: 7,
        cursor: 'pointer',
        fontSize: 13,
        fontWeight: isSelected ? 600 : 400,
        color: isSelected
          ? 'var(--neon-indigo)'
          : isMuted
          ? 'var(--text-muted)'
          : 'var(--text-primary)',
        background: highlight
          ? isDark ? 'rgba(99,102,241,0.12)' : 'rgba(99,102,241,0.06)'
          : isSelected
          ? isDark ? 'rgba(99,102,241,0.08)' : 'rgba(99,102,241,0.05)'
          : 'transparent',
        transition: 'background 0.1s',
      }}
    >
      <span>{label}</span>
      {isSelected && <Check size={13} style={{ color: 'var(--neon-indigo)', flexShrink: 0 }} />}
    </div>
  )
}
