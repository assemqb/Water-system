import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from './api.js'
import { useLanguage } from './i18n/LanguageContext.jsx'
import { useTheme } from './i18n/ThemeContext.jsx'
import { ErrorBoundary } from './components/ErrorBoundary.jsx'
import { ChatPanel } from './components/ChatPanel.jsx'
import { WaterExperience } from './components/experience/WaterExperience.jsx'
import { useMapSelection } from './hooks/useMapSelection.js'
import {
  buildFilterPayload,
  normalizeFilterOptions,
  normalizeFilters,
  safeRegions,
  safeYears,
} from './utils/array.js'

const DEFAULT_SOURCES = ['observed', 'reconstructed']

const PLOT_LAYOUT_BASE = {
  paper_bgcolor: 'transparent',
  margin: { t: 0, r: 0, b: 0, l: 0 },
  colorway: ['#2dd4bf', '#14b8a6', '#f59e0b', '#ef4444', '#6366f1'],
}

function LoadingScreen({ message, error, hint, onRetry, retryLabel }) {
  return (
    <div className="platform" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
      <div style={{ textAlign: 'center', padding: '2rem', maxWidth: 480 }}>
        <div className="page-skeleton__map" style={{ height: 120, marginBottom: '1.5rem', borderRadius: 16 }} />
        <p className="empty-state">{message}</p>
        {error && <div className="alert-error" style={{ marginTop: '1rem' }}>{error}</div>}
        {hint && <p className="empty-state" style={{ marginTop: '0.75rem', fontSize: '0.8125rem' }}>{hint}</p>}
        {onRetry && (
          <button type="button" className="btn-primary" style={{ marginTop: '1.25rem' }} onClick={onRetry}>
            {retryLabel}
          </button>
        )}
      </div>
    </div>
  )
}

export default function App() {
  const { t, lang, locale } = useLanguage()
  const { isDark } = useTheme()
  const mapSel = useMapSelection()

  const [meta, setMeta] = useState(null)
  const [options, setOptions] = useState({ regions: [], years: [], pollutants: [], sources: [], basins: [] })
  const [filters, setFilters] = useState({ sources: DEFAULT_SOURCES, regions: [], years: [], pollutants: [], basins: [] })
  const [summary, setSummary] = useState(null)
  const [charts, setCharts] = useState(null)
  const [loading, setLoading] = useState(true)
  const [ready, setReady] = useState(false)
  const [bootstrapError, setBootstrapError] = useState(null)
  const [dataError, setDataError] = useState(null)
  const [filterEmpty, setFilterEmpty] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)
  const [mapMode, setMapMode] = useState('wqi')
  const [yearFocus, setYearFocus] = useState(null)
  const [bootstrapped, setBootstrapped] = useState(false)
  const [retryKey, setRetryKey] = useState(0)

  const plotLayout = useMemo(() => ({
    ...PLOT_LAYOUT_BASE,
    plot_bgcolor: 'transparent',
    font: { family: 'Inter, sans-serif', color: isDark ? '#8eb4c9' : '#0f766e', size: 10 },
    gridColor: isDark ? 'rgba(94, 184, 212, 0.12)' : 'rgba(8, 145, 178, 0.12)',
  }), [isDark])

  const filterPayload = useMemo(() => buildFilterPayload(filters, lang), [filters, lang])

  useEffect(() => {
    api.meta(lang).then(setMeta).catch((e) => setBootstrapError(e.message))
  }, [lang])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setBootstrapError(null)
    setBootstrapped(false)
    api.health()
      .then(() => api.filterOptions({ sources: DEFAULT_SOURCES, lang }))
      .then((raw) => {
        if (cancelled) return
        const opts = normalizeFilterOptions(raw)
        const years = opts.years
        setOptions(opts)
        setFilters(normalizeFilters({
          sources: DEFAULT_SOURCES.filter((s) => opts.sources.includes(s)),
          regions: opts.regions,
          years,
          pollutants: opts.pollutants,
          basins: opts.basins,
        }, opts))
        setYearFocus(years[years.length - 1] ?? null)
        setBootstrapped(true)
      })
      .catch((e) => { if (!cancelled) setBootstrapError(e.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [lang, retryKey])

  useEffect(() => {
    if (!bootstrapped) return
    const years = safeYears(filters.years)
    if (years.length && (yearFocus == null || !years.includes(yearFocus))) {
      setYearFocus(years[years.length - 1])
    }
  }, [filters.years, bootstrapped, yearFocus])

  useEffect(() => {
    if (!bootstrapped || !safeRegions(filters.regions).length) return undefined
    let cancelled = false
    setLoading(true)
    setDataError(null)
    setFilterEmpty(false)
    Promise.all([api.summary(filterPayload), api.charts(filterPayload)])
      .then(([sum, ch]) => {
        if (!cancelled) {
          setSummary(sum)
          setCharts(ch)
          setFilterEmpty(false)
          setReady(true)
        }
      })
      .catch((e) => {
        if (cancelled) return
        const noData = String(e.message || '').includes('No data for selected filters')
        if (noData) {
          setSummary({
            record_count: 0,
            kpi: null,
            insights: [],
            public_facts: {},
            risk_alerts: null,
            region_stats: [],
            gis: { stations: [], basin_stats: [], lake_stats: [], hotspots: [], basins: [], lakes: [], rivers: [] },
            stories: {},
            chart_narratives: {},
          })
          setCharts(null)
          setFilterEmpty(true)
          setDataError(null)
          setReady(true)
        } else {
          setDataError(e.message)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [filterPayload, bootstrapped])

  const updateFilter = (key, val) => {
    setFilters((f) => {
      const next = normalizeFilters({ ...f, [key]: val }, options)
      if (key === 'sources') {
        api.filterOptions({ sources: next.sources, lang })
          .then((raw) => setOptions(normalizeFilterOptions(raw)))
          .catch(() => {})
      }
      return next
    })
  }

  const resetFilters = () => {
    const years = safeYears(options.years)
    setFilters(normalizeFilters({
      sources: DEFAULT_SOURCES.filter((s) => options.sources?.includes(s)),
      regions: options.regions,
      years,
      pollutants: options.pollutants,
      basins: options.basins,
    }, options))
    setYearFocus(years[years.length - 1] ?? null)
    mapSel.selectRegion(null)
    mapSel.selectBasin(null)
    mapSel.clearGeo()
  }

  const selectRegion = useCallback((region) => {
    const name = region ? String(region) : null
    mapSel.selectRegion(name)
    if (name) {
      setFilters((f) => normalizeFilters({ ...f, regions: [name] }, options))
    } else {
      setFilters((f) => normalizeFilters({ ...f, regions: options.regions }, options))
    }
  }, [mapSel, options])

  const selectBasin = useCallback((basinId) => {
    mapSel.selectBasin(basinId)
    if (basinId) {
      setMapMode('basins')
      setFilters((f) => normalizeFilters({ ...f, basins: [basinId] }, options))
    } else {
      setFilters((f) => normalizeFilters({ ...f, basins: options.basins }, options))
    }
  }, [mapSel, options])

  const handleGeoSelect = useCallback((sel) => {
    mapSel.selectGeo(sel)
    if (sel?.type === 'basin' && sel.id) {
      selectBasin(sel.id)
    } else if (sel?.type === 'station' && sel.basin) {
      setMapMode('pollution')
    }
  }, [mapSel, selectBasin])

  const hotspotRegions = useMemo(
    () => (Array.isArray(summary?.risk_alerts?.top_regions)
      ? summary.risk_alerts.top_regions.slice(0, 4).map((r) => r.Region)
      : []),
    [summary]
  )

  const hasData = Boolean(summary && charts)
  const recordCount = summary?.record_count ?? meta?.total_records

  const exportCsv = async () => {
    const blob = await api.exportCsv(filterPayload)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'water_quality_export.csv'
    a.click()
  }

  if (!ready) {
    return (
      <LoadingScreen
        message={loading ? t('status.loading') : t('empty.noData')}
        error={bootstrapError || dataError ? `${t('errors.loadFailed')} ${bootstrapError || dataError}` : null}
        hint={bootstrapError || dataError ? t('errors.backendHint') : null}
        retryLabel={t('errors.retry')}
        onRetry={() => {
          setReady(false)
          setSummary(null)
          setCharts(null)
          setRetryKey((k) => k + 1)
        }}
      />
    )
  }

  return (
    <ErrorBoundary>
      <WaterExperience
        refreshing={loading}
        charts={charts}
        summary={summary}
        stories={summary?.stories}
        narratives={summary?.chart_narratives}
        plotLayout={plotLayout}
        meta={meta}
        options={options}
        filters={filters}
        onFilterChange={updateFilter}
        onFilterReset={resetFilters}
        mapSel={mapSel}
        mapMode={mapMode}
        onMapModeChange={setMapMode}
        onRegionSelect={selectRegion}
        onBasinSelect={selectBasin}
        onGeoSelect={handleGeoSelect}
        onGeoClose={mapSel.clearGeo}
        onBasinFocus={selectBasin}
        hotspotRegions={hotspotRegions}
        gis={summary?.gis}
        onAnalystOpen={() => setChatOpen(true)}
        onExport={exportCsv}
        recordCount={recordCount != null ? String(recordCount.toLocaleString(locale)) : '—'}
        locale={locale}
        yearFocus={yearFocus}
        onYearFocusChange={setYearFocus}
        filterPayload={filterPayload}
        filterEmpty={filterEmpty}
      />
      <ChatPanel filters={filterPayload} open={chatOpen} onToggle={() => setChatOpen((o) => !o)} experience />
    </ErrorBoundary>
  )
}
