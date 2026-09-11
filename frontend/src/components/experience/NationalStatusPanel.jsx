import React from 'react'
import { useLanguage } from '../../i18n/LanguageContext.jsx'
import { AnimatedNumber } from '../ui/AnimatedNumber.jsx'

function renderMd(text) {
  if (text == null) return ''
  return String(text).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
}

export function NationalStatusPanel({ kpi, kpiLakes, facts, nationalStory, exceedanceCatalog = [] }) {
  const { t } = useLanguage()
  if (!kpi) return null

  return (
    <aside className="nsp" aria-label={t('national.title')}>
      <p className="nsp__eyebrow">{t('national.eyebrow')}</p>
      <h2 className="nsp__title">{t('national.title')}</h2>

      <div className="nsp__hero-metric">
        <span className="nsp__hero-label">{t('national.medianWqi')}</span>
        <span className="nsp__hero-value">
          <AnimatedNumber value={kpi.median_wqi} decimals={1} />
        </span>
        <span className="nsp__hero-unit">{t('map.legendTitle')}</span>
        {kpi.mean_wqi != null && (
          <span className="nsp__hero-secondary">
            {t('national.meanLabel')}: <AnimatedNumber value={kpi.mean_wqi} decimals={1} />
          </span>
        )}
      </div>

      <ul className="nsp__facts">
        {facts?.most_polluted_region && (
          <li className="nsp__fact nsp__fact--stress">
            <span>{t('national.mostPolluted')}</span>
            <strong>{facts.most_polluted_region}</strong>
          </li>
        )}
        {facts?.cleanest_region && (
          <li className="nsp__fact nsp__fact--calm">
            <span>{t('national.cleanest')}</span>
            <strong>{facts.cleanest_region}</strong>
          </li>
        )}
        {facts?.dangerous_pollutant && (
          <li className="nsp__fact nsp__fact--alert">
            <span>{t('national.topPollutant')}</span>
            <strong>{facts.dangerous_pollutant}</strong>
          </li>
        )}
        <li className="nsp__fact">
          <span>{t('national.records')}</span>
          <strong><AnimatedNumber value={kpi.records} decimals={0} /></strong>
        </li>
      </ul>

      {exceedanceCatalog.length > 0 && (
        <div className="nsp__exceedances" role="note">
          <p className="nsp__lakes-title">{t('national.exceedanceTitle')}</p>
          <p className="nsp__lakes-note">{t('national.exceedanceNote')}</p>
          <table className="nsp__exceedance-table">
            <thead>
              <tr>
                <th>{t('national.exceedanceRiver')}</th>
                <th>{t('national.exceedancePollutant')}</th>
                <th>{t('national.exceedanceMaxRatio')}</th>
                <th>{t('national.exceedanceMonths')}</th>
              </tr>
            </thead>
            <tbody>
              {exceedanceCatalog.slice(0, 8).map((row, idx) => (
                <tr key={`${row.water_body}-${row.pollutant}-${idx}`}>
                  <td>{row.water_body}</td>
                  <td>{row.pollutant}</td>
                  <td>{row.max_ratio}×</td>
                  <td>{row.months_exceeded}/{row.months_observed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {nationalStory && (
        <p
          className="nsp__story"
          dangerouslySetInnerHTML={{ __html: renderMd(nationalStory) }}
        />
      )}

      {kpiLakes && kpiLakes.records > 0 && (
        <div className="nsp__lakes" role="note">
          <p className="nsp__lakes-title">{t('national.lakesTitle')}</p>
          <p className="nsp__lakes-note">{t('national.lakesNote')}</p>
          <ul className="nsp__facts">
            <li className="nsp__fact">
              <span>{t('national.medianWqi')}</span>
              <strong><AnimatedNumber value={kpiLakes.median_wqi} decimals={1} /></strong>
            </li>
            <li className="nsp__fact">
              <span>{t('national.records')}</span>
              <strong><AnimatedNumber value={kpiLakes.records} decimals={0} /></strong>
            </li>
          </ul>
        </div>
      )}
    </aside>
  )
}
