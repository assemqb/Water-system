import React, { useEffect, useRef, useState } from 'react'
import { useLanguage } from '../../i18n/LanguageContext.jsx'
import { asArray } from '../../utils/array.js'

function FilterDropdown({ id, label, summary, openId, setOpenId, children }) {
  const ref = useRef(null)
  const isOpen = openId === id

  useEffect(() => {
    if (!isOpen) return undefined
    const close = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpenId(null)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [isOpen, setOpenId])

  return (
    <div className="sfr-item" ref={ref}>
      <button
        type="button"
        className={`sfr-trigger ${isOpen ? 'sfr-trigger--open' : ''}`}
        onClick={() => setOpenId(isOpen ? null : id)}
      >
        <span className="sfr-trigger__label">{label}</span>
        <span className="sfr-trigger__value">{summary}</span>
      </button>
      {isOpen && <div className="sfr-menu">{children}</div>}
    </div>
  )
}

function MultiList({ options, selected, onChange, labels = {}, allLabel, clearLabel }) {
  const opts = asArray(options)
  const sel = asArray(selected)

  return (
    <div className="sfr-list">
      <div className="sfr-list__actions">
        <button type="button" onClick={() => onChange([...opts])}>{allLabel}</button>
        <button type="button" onClick={() => onChange([])}>{clearLabel}</button>
      </div>
      <ul>
        {opts.map((o) => (
          <li key={o}>
            <label>
              <input
                type="checkbox"
                checked={sel.includes(o)}
                onChange={() => {
                  if (sel.includes(o)) onChange(sel.filter((x) => x !== o))
                  else onChange([...sel, o])
                }}
              />
              <span>{labels[o] || o}</span>
            </label>
          </li>
        ))}
      </ul>
      {!opts.length && <p className="sfr-list__empty">—</p>}
    </div>
  )
}

export function SmartFilterRail({ options, filters, onChange, onReset, expanded = false }) {
  const { t } = useLanguage()
  const [openId, setOpenId] = useState(null)

  const sourceLabels = {
    observed: t('sources.observed'),
    observed_chemical: t('sources.observed_chemical'),
    reference: t('sources.reference'),
  }

  const summarize = (key, total) => {
    const n = asArray(filters[key]).length
    if (!total) return '—'
    if (n === 0) return t('filters.none')
    if (n === total) return t('filters.all')
    return t('filters.of', { n, total })
  }

  return (
    <div className={`sfr ${expanded ? 'sfr--expanded' : ''}`}>
      <FilterDropdown
        id="region"
        label={t('filters.region')}
        summary={summarize('regions', options.regions?.length)}
        openId={openId}
        setOpenId={setOpenId}
      >
        <MultiList
          options={options.regions}
          selected={filters.regions}
          onChange={(v) => onChange('regions', v)}
          allLabel={t('filters.all')}
          clearLabel={t('filters.clear')}
        />
      </FilterDropdown>

      {asArray(options.basins).length > 0 && (
        <FilterDropdown
          id="basin"
          label={t('filters.basin')}
          summary={summarize('basins', options.basins?.length)}
          openId={openId}
          setOpenId={setOpenId}
        >
          <MultiList
            options={options.basins}
            selected={filters.basins}
            onChange={(v) => onChange('basins', v)}
            allLabel={t('filters.all')}
            clearLabel={t('filters.clear')}
          />
        </FilterDropdown>
      )}

      <FilterDropdown
        id="year"
        label={t('filters.year')}
        summary={summarize('years', options.years?.length)}
        openId={openId}
        setOpenId={setOpenId}
      >
        <MultiList
          options={options.years}
          selected={filters.years}
          onChange={(v) => onChange('years', v)}
          allLabel={t('filters.all')}
          clearLabel={t('filters.clear')}
        />
      </FilterDropdown>

      <FilterDropdown
        id="pollutant"
        label={t('filters.pollutant')}
        summary={summarize('pollutants', options.pollutants?.length)}
        openId={openId}
        setOpenId={setOpenId}
      >
        <MultiList
          options={options.pollutants}
          selected={filters.pollutants}
          onChange={(v) => onChange('pollutants', v)}
          allLabel={t('filters.all')}
          clearLabel={t('filters.clear')}
        />
      </FilterDropdown>

      <FilterDropdown
        id="source"
        label={t('filters.source')}
        summary={summarize('sources', options.sources?.length)}
        openId={openId}
        setOpenId={setOpenId}
      >
        <MultiList
          options={options.sources}
          selected={filters.sources}
          onChange={(v) => onChange('sources', v)}
          labels={sourceLabels}
          allLabel={t('filters.all')}
          clearLabel={t('filters.clear')}
        />
      </FilterDropdown>

      <button type="button" className="sfr-reset" onClick={onReset}>
        {t('filters.resetAll')}
      </button>
    </div>
  )
}
