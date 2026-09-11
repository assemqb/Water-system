import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../../api.js'
import { useLanguage } from '../../i18n/LanguageContext.jsx'
import { useSectionReveal } from '../../hooks/useSectionReveal.js'
import { LazyPlot } from '../LazyPlot.jsx'
import { asArray, asNumberArray } from '../../utils/array.js'

const MODEL_I18N_KEYS = {
  'Linear Regression': 'ml.modelLinearRegression',
  'Decision Tree': 'ml.modelDecisionTree',
  'Random Forest': 'ml.modelRandomForest',
  'Extra Trees': 'ml.modelExtraTrees',
  'ElasticNet': 'ml.modelElasticNet',
  'XGBoost': 'ml.modelXGBoost',
  'LightGBM': 'ml.modelLightGBM',
  'CatBoost': 'ml.modelCatBoost',
}

export function ForecastLab({ filters, meta, plotLayout, inline = false }) {
  const { t } = useLanguage()
  const { ref, className } = useSectionReveal()
  const [mlTarget, setMlTarget] = useState('WQI_Score')
  const [ml, setMl] = useState(null)

  const modelLabel = useCallback((name) => {
    const key = MODEL_I18N_KEYS[name]
    return key ? t(key) : name
  }, [t])

  const filterKey = JSON.stringify(filters ?? {})

  useEffect(() => {
    let cancelled = false
    api.ml(filters, mlTarget)
      .then((res) => { if (!cancelled) setMl(res) })
      .catch(() => { if (!cancelled) setMl(null) })
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- keyed by serialized filters
  }, [filterKey, mlTarget])

  const forecastFigure = useMemo(() => {
    if (!ml?.ok || !Array.isArray(ml.models) || !ml.models.length) return null
    const best = ml.models.find((m) => m.name === 'Linear Regression') || ml.models[0]
    const mlYears = asNumberArray(ml.years)
    const mlActual = asNumberArray(ml.actual)
    const yhat = asNumberArray(best.yhat)
    if (!mlYears.length || !mlActual.length) return null
    const years = [...mlYears, ml.forecast_year]
    const forecast = [...yhat, best.pred_next]
    return {
      data: [
        { x: mlYears, y: mlActual, type: 'scatter', mode: 'lines+markers', name: t('ml.actual'), line: { color: '#2dd4bf' } },
        { x: years, y: forecast, type: 'scatter', mode: 'lines', name: t('ml.forecastLine', { model: modelLabel(best.name) }), line: { dash: 'dot', color: '#fbbf24' } },
      ],
      layout: { xaxis: { title: t('filters.year') }, yaxis: { title: mlTarget === 'WQI_Score' ? t('ml.targetWqi') : t('ml.targetConc') } },
    }
  }, [ml, mlTarget, t, modelLabel])

  const inner = (
      <div className="forecast-lab" style={inline ? { padding: 0, background: 'transparent' } : undefined}>
        <div className="map-toolbar" style={{ marginBottom: '1rem' }}>
          {['WQI_Score', 'Concentration'].map((target) => (
            <button
              key={target}
              type="button"
              className={`basin-chip ${mlTarget === target ? 'basin-chip--on' : ''}`}
              onClick={() => setMlTarget(target)}
            >
              {target === 'WQI_Score' ? t('ml.targetWqi') : t('ml.targetConc')}
            </button>
          ))}
        </div>

        {ml?.ok ? (
          <>
            {forecastFigure && (
              <div className="chart-panel__body" style={{ marginBottom: '1.5rem' }}>
                <LazyPlot
                  data={forecastFigure.data}
                  layout={{ ...forecastFigure.layout, ...plotLayout, autosize: true, paper_bgcolor: 'transparent' }}
                  config={{ responsive: true, displayModeBar: true, displaylogo: false }}
                  style={{ width: '100%', height: 340 }}
                  useResizeHandler
                />
                <p className="chart-narrative">
                  {t('ml.forecastExplain', { year: ml.forecast_year, model: modelLabel(ml.comparison_table?.[0]?.Model) || '—' })}
                </p>
              </div>
            )}
            {ml.any_overfitting && <p className="chart-narrative">{t('ml.overfitWarn')}</p>}
            <div className="forecast-table-wrap">
              <table className="forecast-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>{t('ml.thModel')}</th>
                    <th>{t('ml.thForecast', { year: ml.forecast_year })}</th>
                    <th>{t('ml.cvMae')}</th>
                    <th>{t('ml.cvR2')}</th>
                    <th>{t('ml.cvMape')}</th>
                    <th>{t('ml.thOverfit')}</th>
                  </tr>
                </thead>
                <tbody>
                  {(Array.isArray(ml.comparison_table) ? ml.comparison_table : []).map((row) => (
                    <tr key={row.Model} className={row.Rank === 1 ? 'row-best' : ''}>
                      <td>{row.Rank}</td>
                      <td>{modelLabel(row.Model)}</td>
                      <td>{row[`Pred ${ml.forecast_year}`]}</td>
                      <td>{row['CV MAE']}</td>
                      <td>{row['CV R²']}</td>
                      <td>{row['CV MAPE %']}%</td>
                      <td>{row['Overfit ⚠'] === 'Yes' ? t('ml.yes') : t('ml.no')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {meta?.why_not_deep_learning && (
              <p className="map-hint" style={{ marginTop: '1rem' }}>{meta.why_not_deep_learning}</p>
            )}
          </>
        ) : ml?.chemical_yoy?.ok ? (
          <>
            <p className="chart-narrative">
              {t('ml.yoyExplain', { yearA: ml.chemical_yoy.year_a, yearB: ml.chemical_yoy.year_b })}
            </p>
            <div className="forecast-table-wrap">
              <table className="forecast-table">
                <thead>
                  <tr>
                    <th>{t('ml.yoyWaterBody')}</th>
                    <th>{t('ml.yoyType')}</th>
                    <th>{t('ml.yoyPollutant')}</th>
                    <th>{t('ml.yoyRatio', { year: ml.chemical_yoy.year_a })}</th>
                    <th>{t('ml.yoyRatio', { year: ml.chemical_yoy.year_b })}</th>
                    <th>{t('ml.yoyDelta')}</th>
                  </tr>
                </thead>
                <tbody>
                  {ml.chemical_yoy.rows.slice(0, 25).map((row, idx) => (
                    <tr key={`${row.water_body}-${row.pollutant}-${idx}`}>
                      <td>{row.water_body}</td>
                      <td>{row.water_body_type === 'lake' ? t('waterBodyType.lake') : t('waterBodyType.river')}</td>
                      <td>{row.pollutant}</td>
                      <td>{row.mean_ratio_a}</td>
                      <td>{row.mean_ratio_b}</td>
                      <td style={{ color: row.ratio_delta > 0 ? '#fca5a5' : '#6ee7b7' }}>
                        {row.ratio_delta > 0 ? '+' : ''}{row.ratio_delta}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <p className="empty-state">{ml?.message || t('ml.unavailableDesc')}</p>
        )}
      </div>
  )

  if (inline) return inner

  return (
    <section id="forecast" ref={ref} className={className}>
      <p className="section__eyebrow">{t('sections.forecast.eyebrow')}</p>
      <h2 className="section__title">{t('sections.forecast.title')}</h2>
      <p className="section__lead">{meta?.ml_disclaimer || t('sections.forecast.lead')}</p>
      {inner}
    </section>
  )
}
