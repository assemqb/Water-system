const API_BASE = import.meta.env.VITE_API_URL || ''

const DEFAULT_TIMEOUT_MS = 45000

async function fetchWithTimeout(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(url, { ...options, signal: controller.signal })
    return res
  } catch (e) {
    if (e.name === 'AbortError') {
      throw new Error('Request timed out — is the API running on port 8001?')
    }
    if (e.message?.includes('Failed to fetch') || e.message?.includes('NetworkError')) {
      throw new Error('Cannot reach API — start backend: python3 -m uvicorn backend.main:app --port 8001')
    }
    throw e
  } finally {
    clearTimeout(timer)
  }
}

async function post(path, body, timeoutMs) {
  const res = await fetchWithTimeout(
    `${API_BASE}${path}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    timeoutMs
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `API error ${res.status}`)
  }
  return res.json()
}

async function get(path, timeoutMs = 15000) {
  const res = await fetchWithTimeout(`${API_BASE}${path}`, {}, timeoutMs)
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json()
}

export const api = {
  health: () => get('/api/health', 5000),
  meta: (lang = 'en') => get(`/api/dashboard/meta?lang=${encodeURIComponent(lang)}`),
  filterOptions: (filters) => post('/api/dashboard/filter-options', filters, 30000),
  summary: (filters) => post('/api/dashboard/summary', filters, 60000),
  charts: (filters) => post('/api/dashboard/charts', filters, 90000),
  ml: (filters, target) => post('/api/dashboard/ml', { ...filters, target }, 120000),
  compare: (payload) => post('/api/dashboard/compare', payload, 30000),
  chat: (payload) => post('/api/dashboard/chat', payload, 120000),
  geojson: () => get('/api/dashboard/geojson', 30000),
  exportCsv: async (filters) => {
    const res = await fetchWithTimeout(
      `${API_BASE}/api/dashboard/export/csv`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(filters),
      },
      120000
    )
    if (!res.ok) throw new Error('Export failed')
    return res.blob()
  },
}
