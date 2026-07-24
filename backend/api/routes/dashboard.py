"""Dashboard REST routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from backend.schemas.models import ChatRequest, CompareRequest, FilterRequest, MLRequest
from backend.services.dashboard_service import dashboard_service

from analytics.chart_narratives import chart_narratives
from analytics.gis_layers import gis_bundle
from analytics.public_facts import public_facts
from analytics.story_engine import generate_stories

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _filtered(body: FilterRequest):
    df = dashboard_service.load_dataset()
    filtered = dashboard_service.apply_filters(
        df,
        sources=body.sources,
        regions=body.regions,
        basins=body.basins,
        years=body.years,
        pollutants=body.pollutants,
    )
    if filtered.empty:
        raise HTTPException(status_code=404, detail="No data for selected filters.")
    return filtered


@router.get("/meta")
def get_meta(lang: str = Query("en")):
    return dashboard_service.meta(lang)


@router.get("/geojson")
def get_geojson():
    return dashboard_service.load_geojson()


@router.get("/gis/static")
def get_gis_static():
    """Static hydrology geometry (rivers, lakes, basins)."""
    from analytics.gis_layers import load_basins, load_lakes, load_rivers
    return {
        "rivers": load_rivers(),
        "lakes": load_lakes(),
        "basins": load_basins(),
    }


@router.post("/gis")
def get_gis(body: FilterRequest):
    """Data-driven GIS layers: stations, basin stats, pollution hotspots."""
    filtered = _filtered(body)
    return gis_bundle(filtered)


@router.post("/filter-options")
def filter_options(body: FilterRequest):
    df = dashboard_service.load_dataset()
    return dashboard_service.filter_options(df, sources=body.sources)


@router.post("/summary")
def dashboard_summary(body: FilterRequest):
    filtered = _filtered(body)
    lang = body.lang or "en"
    return {
        "kpi": dashboard_service.kpi(filtered),
        "data_quality": dashboard_service.data_quality(filtered),
        "risk_alerts": dashboard_service.risk_alerts(filtered),
        "insights": dashboard_service.insights(filtered, lang=lang),
        "public_facts": public_facts(filtered),
        "chart_narratives": chart_narratives(filtered, lang=lang),
        "stories": generate_stories(filtered, lang=lang),
        "region_stats": dashboard_service.region_stats(filtered),
        "record_count": len(filtered),
        "gis": gis_bundle(filtered),
    }


@router.post("/charts")
def dashboard_charts(body: FilterRequest):
    filtered = _filtered(body)
    return dashboard_service.charts(filtered, lang=body.lang or "en")


@router.post("/ml")
def dashboard_ml(body: MLRequest):
    filtered = _filtered(body)
    return dashboard_service.ml_forecast(filtered, target=body.target)


@router.post("/compare")
def dashboard_compare(body: CompareRequest):
    df = dashboard_service.load_dataset()
    filtered = dashboard_service.apply_filters(
        df,
        sources=body.sources,
        regions=body.regions,
        basins=body.basins,
        years=body.years,
        pollutants=body.pollutants,
    )
    return dashboard_service.compare(
        filtered, body.region_a, body.year_a, body.region_b, body.year_b
    )


@router.get("/analyst/status")
def analyst_status():
    """Ollama availability for the Environmental Intelligence Analyst."""
    from analytics.ollama_client import is_available, list_models, resolve_model

    available = is_available()
    return {
        "ollama_available": available,
        "model": resolve_model() if available else None,
        "installed_models": list_models(),
    }


@router.post("/chat")
def dashboard_chat(body: ChatRequest):
    """Environmental Intelligence Analyst — Ollama LLM with AquaMonitor context."""
    df = dashboard_service.load_dataset()
    filtered = dashboard_service.apply_filters(
        df,
        sources=body.sources,
        regions=body.regions,
        basins=body.basins,
        years=body.years,
        pollutants=body.pollutants,
    )
    return dashboard_service.chat(
        filtered,
        body.message,
        lang=body.lang or "en",
        sources=body.sources,
        regions=body.regions,
        basins=body.basins,
        years=body.years,
        pollutants=body.pollutants,
    )


@router.post("/export/csv")
def export_csv(body: FilterRequest):
    filtered = _filtered(body)
    csv_text = dashboard_service.export_csv(filtered)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=filtered_water_quality_data.csv"},
    )
