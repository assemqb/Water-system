import React from 'react'
import { KazakhstanMap } from '../map/KazakhstanMap.jsx'
import { MapLayerControl } from '../map/MapLayerControl.jsx'
import { BasinExplorer } from './BasinExplorer.jsx'
import { GeoStoryPanel } from './GeoStoryPanel.jsx'

export function MapStage({
  charts,
  plotLayout,
  mapMode,
  onMapModeChange,
  gis,
  regionStats,
  hotspotRegions,
  selectedRegion,
  selectedBasin,
  geoSelection,
  onRegionSelect,
  onHoverRegion,
  onGeoSelect,
  onGeoClose,
  onBasinSelect,
  onBasinFocus,
  onAnalystOpen,
  children,
}) {
  return (
    <section className="map-stage" id="kz-map">
      <div className="map-stage__canvas">
        <KazakhstanMap
          figure={charts?.map}
          plotLayout={plotLayout}
          mapMode={mapMode}
          gis={gis}
          regionStats={regionStats}
          hotspotRegions={hotspotRegions}
          selectedRegion={selectedRegion}
          selectedBasin={selectedBasin}
          onRegionSelect={onRegionSelect}
          onHoverRegion={onHoverRegion}
          onGeoSelect={onGeoSelect}
          height="100%"
        />
      </div>

      <div className="map-stage__basins">
        <BasinExplorer
          basinStats={gis?.basin_stats}
          activeBasin={selectedBasin}
          onSelect={onBasinSelect}
        />
      </div>

      <div className="map-stage__layers">
        <MapLayerControl mapMode={mapMode} onMapModeChange={onMapModeChange} />
      </div>

      {geoSelection && (
        <GeoStoryPanel
          selection={geoSelection}
          gis={gis}
          onClose={onGeoClose}
          onBasinFocus={onBasinFocus}
          onAnalystOpen={onAnalystOpen}
        />
      )}

      <div className="map-stage__overlays">{children}</div>
    </section>
  )
}
