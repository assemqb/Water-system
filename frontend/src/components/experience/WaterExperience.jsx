import React, { useMemo } from 'react'
import { useLanguage } from '../../i18n/LanguageContext.jsx'
import { LanguageSwitcher } from '../../i18n/LanguageSwitcher.jsx'
import { ThemeToggle } from '../../i18n/ThemeToggle.jsx'
import { EnvironmentalExplorer } from '../filters/EnvironmentalExplorer.jsx'
import { MapStage } from './MapStage.jsx'
import { NationalStatusPanel } from './NationalStatusPanel.jsx'
import { StorySection } from './StorySection.jsx'
import { JourneyNav } from './JourneyNav.jsx'
import { BasinStoryGrid } from './BasinStoryGrid.jsx'
import { LakeStoryGrid } from './LakeStoryGrid.jsx'
import { MonitoringNetwork } from './MonitoringNetwork.jsx'
import { FlowTimeline } from './FlowTimeline.jsx'
import { ChartPanel } from '../charts/ChartStory.jsx'
import { PeriodCompare } from '../story/PeriodCompare.jsx'
import { ForecastLab } from '../forecast/ForecastLab.jsx'
import { WqiEducation } from '../education/WqiEducation.jsx'
import { RiskDashboard } from '../dashboard/RiskDashboard.jsx'
import { maxOf, minOf, safeRegions, safeYears } from '../../utils/array.js'
import { focusTrendByYear } from '../../utils/chartFocus.js'

function renderMd(text) {
  if (text == null) return ''
  return String(text).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
}

export function WaterExperience({
  charts,
  summary,
  stories,
  narratives,
  plotLayout,
  meta,
  options,
  filters,
  onFilterChange,
  onFilterReset,
  mapSel,
  mapMode,
  onMapModeChange,
  onRegionSelect,
  onBasinSelect,
  onGeoSelect,
  onGeoClose,
  onBasinFocus,
  gis,
  hotspotRegions,
  onAnalystOpen,
  onExport,
  recordCount,
  filterPayload,
  filterEmpty = false,
  refreshing = false,
  yearFocus,
  onYearFocusChange,
}) {
  const { t } = useLanguage()
  const kpi = summary?.kpi
  const facts = summary?.public_facts || {}
  const insights = Array.isArray(summary?.insights) ? summary.insights.filter(Boolean) : []
  const regions = safeRegions(options?.regions)
  const regionStats = summary?.region_stats
  const yearMin = minOf(filters?.years)
  const yearMax = maxOf(filters?.years)

  const displayRegion = mapSel.hoverRegion || mapSel.selectedRegion
  const displayStats = mapSel.hoverStats
    || (displayRegion && Array.isArray(regionStats)
      ? regionStats.find((r) => r.region === displayRegion)
      : null)

  const trendFigure = useMemo(
    () => (charts?.trend && yearFocus != null ? focusTrendByYear(charts.trend, yearFocus) : charts?.trend),
    [charts?.trend, yearFocus]
  )

  const visibleChapterIds = useMemo(() => {
    const ids = new Set(['journey-overview', 'journey-basins', 'journey-lakes', 'journey-network'])
    if (charts?.heatmap) ids.add('journey-pollution')
    if (charts?.trend) ids.add('journey-time')
    if (charts?.regions || charts?.yoy_delta) ids.add('journey-regions')
    ids.add('journey-compare', 'journey-forecast', 'journey-wqi', 'journey-data')
    return ids
  }, [charts])

  let chapter = 0

  return (
    <div className="platform">
      {refreshing && <div className="platform__refresh" aria-live="polite">{t('status.updating')}</div>}
      {filterEmpty && (
        <div className="alert-error platform__filter-empty" role="alert">
          {t('empty.noData')}
        </div>
      )}

      <header className="platform__chrome">
        <div className="platform__brand">
          <span className="platform__name">{t('platform.name')}</span>
          <span className="platform__tag">{t('platform.tagline')}</span>
        </div>
        <div className="platform__tools">
          <ThemeToggle />
          <LanguageSwitcher />
          <button type="button" className="platform__analyst" onClick={onAnalystOpen}>
            {t('analyst.openShort')}
          </button>
        </div>
      </header>

      <EnvironmentalExplorer
        options={options}
        filters={filters}
        onChange={onFilterChange}
        onReset={onFilterReset}
      />

      <MapStage
        charts={charts}
        plotLayout={plotLayout}
        mapMode={mapMode}
        onMapModeChange={onMapModeChange}
        gis={gis}
        regionStats={regionStats}
        hotspotRegions={hotspotRegions}
        selectedRegion={mapSel.selectedRegion}
        selectedBasin={mapSel.selectedBasin}
        geoSelection={mapSel.geoSelection}
        onRegionSelect={onRegionSelect}
        onHoverRegion={mapSel.setHoverRegion}
        onGeoSelect={onGeoSelect}
        onGeoClose={onGeoClose}
        onBasinSelect={onBasinSelect}
        onBasinFocus={onBasinFocus}
        onAnalystOpen={onAnalystOpen}
      >
        {!mapSel.geoSelection && (
          <NationalStatusPanel kpi={kpi} facts={facts} nationalStory={stories?.national_status} />
        )}

        {displayRegion && !mapSel.geoSelection && (
          <div className={`region-probe ${mapSel.selectedRegion === displayRegion ? 'region-probe--on' : ''}`}>
            <strong>{displayRegion}</strong>
            {displayStats && (
              <span>
                {t('map.hoverWqi')} {displayStats.mean_wqi} · {t('map.hoverRisk')} {displayStats.high_risk_pct}% · {displayStats.top_pollutant}
              </span>
            )}
            <em>{t('map.clickFilter')}</em>
          </div>
        )}

        <a href="#journey-overview" className="platform__scroll-cue">{t('hero.scrollHint')}</a>
      </MapStage>

      <div className="platform__journey-wrap">
        <JourneyNav visibleIds={visibleChapterIds} />

        <main id="analytics" className="platform__depth">
          <StorySection
            id="journey-overview"
            chapter={++chapter}
            variant="overview"
            eyebrow={t('journey.chapters.overviewEyebrow')}
            title={t('journey.chapters.overviewTitle')}
            lead={stories?.national_status || t('journey.chapters.overviewLead')}
          >
            {kpi && (
              <div className="journey-kpi-strip">
                <div className="journey-kpi"><span>{t('national.avgWqi')}</span><strong>{kpi.mean_wqi}</strong></div>
                <div className="journey-kpi"><span>{t('national.highRisk')}</span><strong>{kpi.high_risk_share}%</strong></div>
                <div className="journey-kpi"><span>{t('national.records')}</span><strong>{kpi.records?.toLocaleString()}</strong></div>
              </div>
            )}
            {insights.length > 0 && (
              <ul className="insight-stream">
                {insights.slice(0, 4).map((line, i) => (
                  <li key={i} dangerouslySetInnerHTML={{ __html: renderMd(line) }} />
                ))}
              </ul>
            )}
          </StorySection>

          {gis?.basin_stats?.length > 0 && (
            <StorySection
              id="journey-basins"
              chapter={++chapter}
              variant="water"
              eyebrow={t('journey.chapters.basinsEyebrow')}
              title={t('journey.chapters.basinsTitle')}
              lead={t('journey.chapters.basinsLead')}
            >
              <BasinStoryGrid
                basinStats={gis.basin_stats}
                activeBasin={mapSel.selectedBasin}
                onSelect={onBasinFocus}
              />
            </StorySection>
          )}

          {gis?.lake_stats?.length > 0 && (
            <StorySection
              id="journey-lakes"
              chapter={++chapter}
              variant="water"
              eyebrow={t('journey.chapters.lakesEyebrow')}
              title={t('journey.chapters.lakesTitle')}
              lead={t('journey.chapters.lakesLead')}
            >
              <LakeStoryGrid lakeStats={gis.lake_stats} onSelect={onGeoSelect} />
            </StorySection>
          )}

          {gis?.stations?.length > 0 && (
            <StorySection
              id="journey-network"
              chapter={++chapter}
              variant="water"
              eyebrow={t('journey.chapters.networkEyebrow')}
              title={t('journey.chapters.networkTitle')}
              lead={t('journey.chapters.networkLead')}
            >
              <MonitoringNetwork
                stations={gis.stations}
                activeCode={mapSel.geoSelection?.type === 'station' ? mapSel.geoSelection.id : null}
                onSelect={onGeoSelect}
              />
            </StorySection>
          )}

          {charts?.heatmap && (
            <StorySection
              id="journey-pollution"
              chapter={++chapter}
              variant="risk"
              eyebrow={t('experience.chapters.pollution.eyebrow')}
              title={t('experience.chapters.pollution.title')}
              lead={t('experience.chapters.pollution.body', {
                pollutant: facts.dangerous_pollutant || '—',
                region: facts.most_polluted_region || '—',
              })}
              insight={narratives?.heatmap}
            >
              <ChartPanel
                title={t('analytics.matrixTitle')}
                subtitle={t('analytics.matrixSub')}
                figure={charts.heatmap}
                plotLayout={plotLayout}
                tall
              />
              <RiskDashboard riskAlerts={summary?.risk_alerts} inline />
            </StorySection>
          )}

          {charts?.trend && (
            <StorySection
              id="journey-time"
              chapter={++chapter}
              variant="water"
              eyebrow={t('experience.chapters.time.eyebrow')}
              title={t('experience.chapters.time.title')}
              lead={t('experience.chapters.time.body')}
              insight={narratives?.trend}
            >
              <FlowTimeline
                yearMin={yearMin}
                yearMax={yearMax}
                yearFocus={yearFocus}
                onChange={onYearFocusChange}
                narrative={narratives?.trend}
              />
              <ChartPanel
                title={t('analytics.trendTitle')}
                subtitle={t('analytics.trendSub')}
                figure={trendFigure}
                plotLayout={plotLayout}
                chartKey={`trend-${yearFocus}`}
                tall
              />
            </StorySection>
          )}

          {(charts?.regions || charts?.yoy_delta) && (
            <StorySection
              id="journey-regions"
              chapter={++chapter}
              variant="default"
              eyebrow={t('experience.chapters.regions.eyebrow')}
              title={t('experience.chapters.regions.title')}
              insight={narratives?.yoy}
            >
              {charts.regions && (
                <ChartPanel title={t('analytics.rankTitle')} subtitle={t('analytics.rankSub')} figure={charts.regions} plotLayout={plotLayout} narrative={narratives?.map} />
              )}
              {charts.yoy_delta && (
                <ChartPanel title={t('analytics.yoyTitle')} subtitle={t('analytics.yoySub')} figure={charts.yoy_delta} plotLayout={plotLayout} tall narrative={narratives?.yoy} />
              )}
            </StorySection>
          )}

          <StorySection id="journey-compare" chapter={++chapter} variant="default" eyebrow={t('sections.compare.eyebrow')} title={t('sections.compare.title')} lead={stories?.compare_teaser || t('sections.compare.lead')}>
            <PeriodCompare filters={filterPayload} regions={regions} years={safeYears(filters?.years)} inline />
          </StorySection>

          <StorySection id="journey-forecast" chapter={++chapter} variant="future" eyebrow={t('experience.chapters.future.eyebrow')} title={t('experience.chapters.future.title')} lead={meta?.ml_disclaimer}>
            <ForecastLab filters={filterPayload} meta={meta} plotLayout={plotLayout} inline />
          </StorySection>

          <StorySection id="journey-wqi" chapter={++chapter} variant="default" title={t('wqi.title')} lead={t('wqi.desc')}>
            <WqiEducation embedded />
          </StorySection>

          <StorySection id="journey-data" chapter={++chapter} variant="default" eyebrow={t('sections.data.eyebrow')} title={t('sections.data.title')} lead={t('sections.data.lead')}>
            <button type="button" className="platform__export" onClick={onExport}>{t('exportCsv')}</button>
            <p className="story-section__meta">{t('footer.records', { count: recordCount ?? '—' })} · {meta?.last_updated}</p>
            {Array.isArray(meta?.limitations) && meta.limitations.length > 0 && (
              <ul className="limitations-list">
                {meta.limitations.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            )}
          </StorySection>
        </main>
      </div>
    </div>
  )
}
