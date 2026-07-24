import React from 'react'
import { useLanguage } from '../../i18n/LanguageContext.jsx'

const STATUS_LABEL = {
  normal: 'gis.statusNormal',
  moderate: 'gis.statusModerate',
  high: 'gis.statusHigh',
}

export function GeoStoryPanel({ selection, gis, onClose, onBasinFocus, onAnalystOpen }) {
  const { t } = useLanguage()
  if (!selection || !gis) return null

  const { type, id } = selection

  if (type === 'station') {
    const station = gis.stations?.find((s) => s.code === id)
    if (!station) return null
    return (
      <aside className="geo-story" aria-label={station.name}>
        <button type="button" className="geo-story__close" onClick={onClose} aria-label={t('gis.close')}>×</button>
        <p className="geo-story__type">{t('gis.station')}</p>
        <h3 className="geo-story__title">{station.name}</h3>
        <p className="geo-story__meta">{station.region} · {station.basin}</p>
        <span className={`geo-story__status geo-story__status--${station.status}`}>
          {t(STATUS_LABEL[station.status] || STATUS_LABEL.normal)}
        </span>
        <dl className="geo-story__facts">
          <div><dt>{t('map.hoverWqi')}</dt><dd>{station.mean_wqi}</dd></div>
          <div><dt>{t('gis.maxRatio')}</dt><dd>{station.max_ratio}× MPC</dd></div>
          <div><dt>{t('map.hoverRisk')}</dt><dd>{station.high_risk_pct}%</dd></div>
          <div><dt>{t('map.hoverPollutant')}</dt><dd>{station.top_pollutant}</dd></div>
          {station.trend_wqi_delta != null && (
            <div><dt>{t('gis.trend')}</dt><dd>{station.trend_wqi_delta > 0 ? '+' : ''}{station.trend_wqi_delta}</dd></div>
          )}
          <div><dt>{t('map.hoverRecords')}</dt><dd>{station.records.toLocaleString()}</dd></div>
        </dl>
        {station.pollutants?.length > 0 && (
          <div className="geo-story__pollutants">
            <h4>{t('gis.pollutantsMeasured')}</h4>
            <ul>
              {station.pollutants.slice(0, 5).map((p) => (
                <li key={p.Pollutant}>{p.Pollutant} — {p.max_ratio?.toFixed?.(2) ?? p.max_ratio}×</li>
              ))}
            </ul>
          </div>
        )}
        <button type="button" className="geo-story__action" onClick={() => onBasinFocus?.(station.basin)}>
          {t('gis.exploreBasin')}
        </button>
        <button type="button" className="geo-story__action geo-story__action--secondary" onClick={onAnalystOpen}>
          {t('analyst.openShort')}
        </button>
      </aside>
    )
  }

  if (type === 'lake') {
    const lake = gis.lake_stats?.find((l) => l.id === id)
    if (!lake) return null
    return (
      <aside className="geo-story" aria-label={lake.name}>
        <button type="button" className="geo-story__close" onClick={onClose} aria-label={t('gis.close')}>×</button>
        <p className="geo-story__type">{t('gis.lake')}</p>
        <h3 className="geo-story__title">{lake.name}</h3>
        <p className="geo-story__meta">{lake.basin} · {lake.area_km2?.toLocaleString()} km²</p>
        <dl className="geo-story__facts">
          {lake.mean_wqi != null && <div><dt>{t('map.hoverWqi')}</dt><dd>{lake.mean_wqi}</dd></div>}
          {lake.max_ratio != null && <div><dt>{t('gis.maxRatio')}</dt><dd>{lake.max_ratio}× MPC</dd></div>}
          {lake.top_pollutant && <div><dt>{t('map.hoverPollutant')}</dt><dd>{lake.top_pollutant}</dd></div>}
          {lake.trend_wqi_delta != null && (
            <div><dt>{t('gis.trend')}</dt><dd>{lake.trend_wqi_delta > 0 ? '+' : ''}{lake.trend_wqi_delta}</dd></div>
          )}
        </dl>
        <button type="button" className="geo-story__action" onClick={() => onBasinFocus?.(lake.basin)}>
          {t('gis.exploreBasin')}
        </button>
      </aside>
    )
  }

  if (type === 'basin' || type === 'river') {
    const basinId = type === 'river' ? selection.basin : id
    const basin = gis.basin_stats?.find((b) => b.id === basinId)
    const feat = gis.basins?.features?.find((f) => f.properties?.id === basinId)
    const title = feat?.properties?.display_name || basinId
    if (!basin) return null
    return (
      <aside className="geo-story geo-story--basin" aria-label={title}>
        <button type="button" className="geo-story__close" onClick={onClose} aria-label={t('gis.close')}>×</button>
        <p className="geo-story__type">{t('gis.basin')}</p>
        <h3 className="geo-story__title">{title}</h3>
        <dl className="geo-story__facts">
          <div><dt>{t('map.hoverWqi')}</dt><dd>{basin.mean_wqi}</dd></div>
          <div><dt>{t('gis.maxRatio')}</dt><dd>{basin.max_ratio}× MPC</dd></div>
          <div><dt>{t('map.hoverRisk')}</dt><dd>{basin.high_risk_pct}%</dd></div>
          <div><dt>{t('gis.topRegion')}</dt><dd>{basin.top_region}</dd></div>
          <div><dt>{t('map.hoverPollutant')}</dt><dd>{basin.top_pollutant}</dd></div>
          {basin.trend_wqi_delta != null && (
            <div><dt>{t('gis.trend')}</dt><dd>{basin.trend_wqi_delta > 0 ? '+' : ''}{basin.trend_wqi_delta}</dd></div>
          )}
          <div><dt>{t('gis.stations')}</dt><dd>{basin.stations?.length ?? 0}</dd></div>
        </dl>
        <button type="button" className="geo-story__action" onClick={() => onBasinFocus?.(basinId)}>
          {t('gis.focusBasin')}
        </button>
      </aside>
    )
  }

  return null
}
