/**
 * Extract error message from API error responses.
 * 
 * Handles different FastAPI error formats:
 * - Simple: { detail: "Error message" }
 * - Validation: { detail: [{ type, loc, msg, ... }] }
 * - Array of strings: { detail: ["Error 1", "Error 2"] }
 */
export function extractErrorMessage(error) {
  if (!error) return 'An unknown error occurred'
  
  // If it's already a string, return it
  if (typeof error === 'string') return error
  
  // Try to get error from response data
  const detail = error?.response?.data?.detail || error?.detail || error?.message || error
  
  // If detail is a string, return it
  if (typeof detail === 'string') return detail
  
  // If detail is an array, extract messages
  if (Array.isArray(detail)) {
    return detail
      .map(item => {
        if (typeof item === 'string') return item
        if (item?.msg) return item.msg
        if (item?.message) return item.message
        return JSON.stringify(item)
      })
      .filter(Boolean)
      .join(', ')
  }
  
  // If detail is an object, try to extract message
  if (typeof detail === 'object' && detail !== null) {
    if (detail.msg) return detail.msg
    if (detail.message) return detail.message
    if (detail.error) return detail.error
  }
  
  // Fallback: stringify the error
  try {
    return JSON.stringify(detail)
  } catch {
    return 'An unknown error occurred'
  }
}
