import React from 'react'
import { useLanguage } from '../../i18n/LanguageContext.jsx'

export function BasinExplorer({ basinStats = [], activeBasin, onSelect }) {
  const { t } = useLanguage()
  if (!basinStats.length) return null

  return (
    <nav className="basin-explorer" aria-label={t('gis.basinNav')}>
      <span className="basin-explorer__label">{t('gis.exploreBasins')}</span>
      <div className="basin-explorer__list">
        {basinStats.map((b) => (
          <button
            key={b.id}
            type="button"
            className={`basin-explorer__item ${activeBasin === b.id ? 'basin-explorer__item--on' : ''}`}
            onClick={() => onSelect(b.id)}
          >
            <span className="basin-explorer__name">{b.id.replace(/-/g, ' ')}</span>
            <span className="basin-explorer__wqi">WQI {b.median_wqi}</span>
          </button>
        ))}
      </div>
    </nav>
  )
}
