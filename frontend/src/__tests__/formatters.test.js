import { describe, it, expect } from 'vitest'
import { truncateId, formatDuration, formatTimestamp } from '../utils/formatters'

describe('truncateId', () => {
  it('truncates long IDs', () => {
    const id = '550e8400-e29b-41d4-a716-446655440000'
    expect(truncateId(id)).toBe('550e8400...')
  })

  it('returns short strings as-is', () => {
    expect(truncateId('abc')).toBe('abc')
  })

  it('handles empty string', () => {
    expect(truncateId('')).toBe('')
  })

  it('handles null/undefined', () => {
    expect(truncateId(null)).toBe('')
    expect(truncateId(undefined)).toBe('')
  })
})

describe('formatDuration', () => {
  it('formats seconds', () => {
    expect(formatDuration(5.3)).toBe('5.3s')
  })

  it('formats minutes and seconds', () => {
    expect(formatDuration(125)).toBe('2m 5s')
  })

  it('handles null', () => {
    expect(formatDuration(null)).toBe('—')
  })

  it('handles zero', () => {
    expect(formatDuration(0)).toBe('0.0s')
  })
})

describe('formatTimestamp', () => {
  it('formats ISO date', () => {
    const result = formatTimestamp('2026-02-16T12:30:00Z')
    expect(result).toContain('Feb')
    expect(result).toContain('16')
  })

  it('handles null', () => {
    expect(formatTimestamp(null)).toBe('—')
  })

  it('handles undefined', () => {
    expect(formatTimestamp(undefined)).toBe('—')
  })
})
