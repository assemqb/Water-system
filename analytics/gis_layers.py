"""Real GIS layers — rivers, lakes, basins, monitoring stations from project data."""

from __future__ import annotations

import json
from typing import Any, Optional

import pandas as pd

from config.settings import (
    BASINS_GEOJSON_PATH,
    LAKES_GEOJSON_PATH,
    RIVERS_GEOJSON_PATH,
    STATION_COORDS,
    STATION_MAP,
)


def _load_geojson(path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_rivers() -> dict:
    return _load_geojson(RIVERS_GEOJSON_PATH)


def load_lakes() -> dict:
    return _load_geojson(LAKES_GEOJSON_PATH)


def load_basins() -> dict:
    return _load_geojson(BASINS_GEOJSON_PATH)


def _station_status(high_risk_pct: float, max_ratio: float) -> str:
    if high_risk_pct >= 15 or max_ratio >= 2.0:
        return "high"
    if high_risk_pct >= 5 or max_ratio >= 1.0:
        return "moderate"
    return "normal"


def station_stats(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Aggregate filtered data per Kazhydromet station code with real coordinates."""
    if df.empty or "station_code" not in df.columns:
        return []

    observed = df[df["station_code"].notna()].copy()
    if observed.empty:
        return []

    rows: list[dict[str, Any]] = []
    for code_raw, grp in observed.groupby("station_code"):
        code = int(code_raw)
        if code not in STATION_MAP or code not in STATION_COORDS:
            continue
        basin, region, description = STATION_MAP[code]
        lon, lat = STATION_COORDS[code]
        top_row = grp.loc[grp["Ratio"].idxmax()] if grp["Ratio"].notna().any() else None
        high_risk_pct = float((grp["Ratio"] > 2).mean() * 100)
        max_ratio = float(grp["Ratio"].max())
        trend = None
        if "Year" in grp.columns and len(grp["Year"].dropna().unique()) >= 2:
            yearly = grp.groupby("Year")["WQI_Score"].mean().sort_index()
            if len(yearly) >= 2:
                trend = round(float(yearly.iloc[-1] - yearly.iloc[0]), 2)

        pollutants = (
            grp.groupby("Pollutant")["Ratio"]
            .max()
            .sort_values(ascending=False)
            .head(5)
            .reset_index()
            .rename(columns={"Ratio": "max_ratio"})
        )

        rows.append({
            "code": code,
            "name": description,
            "basin": basin,
            "region": region,
            "lon": lon,
            "lat": lat,
            "median_wqi": round(float(grp["WQI_Score"].median()), 2),
            "over_mpc_pct": round(float((grp["Ratio"] > 1).mean() * 100), 1),
            "mean_wqi": round(float(grp["WQI_Score"].mean()), 2),
            "max_ratio": round(max_ratio, 2),
            "high_risk_pct": round(high_risk_pct, 1),
            "records": int(len(grp)),
            "status": _station_status(high_risk_pct, max_ratio),
            "top_pollutant": str(top_row["Pollutant"]) if top_row is not None else "—",
            "trend_wqi_delta": trend,
            "pollutants": pollutants.to_dict(orient="records"),
            "years": sorted(int(y) for y in grp["Year"].dropna().unique()) if "Year" in grp.columns else [],
        })
    return rows


def basin_stats(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Per-basin statistics for basin explorer.

    NOT restricted to full_panel: that table layout is ~all lakes/seas in
    this dataset (Kazhydromet reports rivers via the worst_parameter table
    instead — see analytics.table_type), so restricting here would silently
    drop river-chemical exceedances from a basin's stats while keeping its
    water-level data, understating basins with only worst_parameter
    chemical coverage. See dashboard_service.kpi_full_panel/
    kpi_worst_parameter for where that split is applied without this
    geography confound.
    """
    if df.empty or "Basin" not in df.columns:
        return []

    rows: list[dict[str, Any]] = []
    for basin, grp in df.groupby("Basin"):
        if str(basin) == "Global_Reference":
            continue
        top_row = grp.loc[grp["Ratio"].idxmax()] if grp["Ratio"].notna().any() else None
        trend = None
        if "Year" in grp.columns and len(grp["Year"].dropna().unique()) >= 2:
            yearly = grp.groupby("Year")["WQI_Score"].mean().sort_index()
            if len(yearly) >= 2:
                trend = round(float(yearly.iloc[-1] - yearly.iloc[0]), 2)

        rows.append({
            "id": str(basin),
            "records": int(len(grp)),
            # Primary: median WQI + share of measurements above MPC.
            "median_wqi": round(float(grp["WQI_Score"].median()), 2),
            "over_mpc_pct": round(float((grp["Ratio"] > 1).mean() * 100), 1),
            # Secondary — mean, explicitly labeled wherever rendered.
            "mean_wqi": round(float(grp["WQI_Score"].mean()), 2),
            "max_ratio": round(float(grp["Ratio"].max()), 2),
            "high_risk_pct": round(float((grp["Ratio"] > 2).mean() * 100), 1),
            "top_pollutant": str(top_row["Pollutant"]) if top_row is not None else "—",
            "top_region": str(grp.groupby("Region")["Ratio"].median().idxmax()) if "Region" in grp.columns else "—",
            "trend_wqi_delta": trend,
            "stations": sorted(int(c) for c in grp["station_code"].dropna().unique()) if "station_code" in grp.columns else [],
        })
    rows.sort(key=lambda r: r["max_ratio"], reverse=True)
    return rows


def lake_stats(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Lake metrics derived from basin/region data linked to lake GeoJSON properties."""
    lakes = load_lakes()
    basin_stats_map = {b["id"]: b for b in basin_stats(df)}

    rows: list[dict[str, Any]] = []
    for feat in lakes.get("features", []):
        props = feat.get("properties", {})
        lake_id = props.get("id")
        basin = props.get("basin")
        stats = basin_stats_map.get(basin, {})
        rows.append({
            "id": lake_id,
            "name": props.get("name"),
            "basin": basin,
            "area_km2": props.get("area_km2"),
            "type": props.get("type"),
            "mean_wqi": stats.get("mean_wqi"),
            "max_ratio": stats.get("max_ratio"),
            "high_risk_pct": stats.get("high_risk_pct"),
            "top_pollutant": stats.get("top_pollutant"),
            "trend_wqi_delta": stats.get("trend_wqi_delta"),
            "records": stats.get("records", 0),
        })
    return rows


def pollution_hotspots(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Data-derived pollution clusters at station coordinates."""
    stations = station_stats(df)
    return [
        {
            "code": s["code"],
            "lon": s["lon"],
            "lat": s["lat"],
            "intensity": s["max_ratio"],
            "high_risk_pct": s["high_risk_pct"],
            "status": s["status"],
            "name": s["name"],
            "basin": s["basin"],
        }
        for s in stations
        if s["max_ratio"] >= 1.0 or s["high_risk_pct"] >= 5
    ]


def gis_bundle(df: pd.DataFrame) -> dict[str, Any]:
    """Full GIS payload for the hydrology map."""
    return {
        "rivers": load_rivers(),
        "lakes": load_lakes(),
        "basins": load_basins(),
        "stations": station_stats(df),
        "basin_stats": basin_stats(df),
        "lake_stats": lake_stats(df),
        "hotspots": pollution_hotspots(df),
    }
