"""Tests for context-aware chat assistant."""

from __future__ import annotations

import pandas as pd

from analytics.chat_assistant import FALLBACK_NOTICE, build_context, chat


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame({
        "Region": ["Almaty", "Almaty", "VKO", "VKO"],
        "Basin": ["Balkash-Alakol", "Balkash-Alakol", "Ertis", "Ertis"],
        "Year": [2020, 2021, 2020, 2021],
        "Pollutant": ["Nitrates", "Copper", "Nitrates", "Copper"],
        "Concentration": [10.0, 0.002, 50.0, 0.003],
        "MPC": [45.0, 0.001, 45.0, 0.001],
        "WQI_Score": [11.1, 100.0, 55.6, 150.0],
        "Ratio": [0.22, 2.0, 1.11, 3.0],
        "data_source": ["observed", "reconstructed", "observed", "reconstructed"],
    })


def test_build_context_not_empty():
    ctx = build_context(_sample_df(), filters={"regions": ["Almaty"]})
    assert ctx["empty"] is False
    assert ctx["records"] == 4
    assert "mean_wqi" in ctx
    assert ctx["active_filters"]["regions"] == ["Almaty"]
    assert "basin_analytics" in ctx
    assert "forecast" in ctx


def test_chat_wqi_question_en():
    res = chat("What is the mean WQI?", _sample_df(), lang="en")
    assert res["confidence"] in ("high", "low")
    assert res["source"] in ("ollama", "fallback")
    assert "VKO" in res["reply"] or "Almaty" in res["reply"]
    assert res["suggestions"]
    if res["source"] == "fallback":
        assert FALLBACK_NOTICE in res["reply"]


def test_chat_wqi_question_ru():
    res = chat("Какой средний WQI?", _sample_df(), lang="ru")
    assert res["confidence"] in ("high", "low")
    assert "VKO" in res["reply"] or "Almaty" in res["reply"]
    if res["source"] == "fallback":
        assert FALLBACK_NOTICE in res["reply"]


def test_chat_wqi_question_kk():
    res = chat("Орташа WQI қандай?", _sample_df(), lang="kk")
    assert res["confidence"] in ("high", "low")
    assert "VKO" in res["reply"] or "Almaty" in res["reply"]
    assert "аудан" in res["reply"].lower() or "қысым" in res["reply"].lower() or FALLBACK_NOTICE in res["reply"]


def test_chat_includes_context_fields():
    ctx = build_context(
        _sample_df(),
        filters={"regions": ["Almaty"], "years": [2020, 2021]},
        hotspots=[{"name": "Test station", "basin": "Ertis", "intensity": 2.5, "status": "high", "high_risk_pct": 10}],
        forecast={"ok": True, "target": "WQI_Score", "years": [2020, 2021], "forecast_year": 2022,
                  "models": [{"name": "Linear Regression", "pred_next": 55.0, "cv": {"mae": 1.0}}]},
        risk_alerts={"high_risk_pct": 25.0, "moderate_risk_pct": 30.0, "top_regions": []},
    )
    assert ctx["pollution_hotspots"]
    assert ctx["forecast"]["available"] is True
    assert ctx["risk_summary"]["high_risk_pct"] == 25.0


def test_chat_trend_uses_chemical_not_all_rows():
    """Trend must not mix water-level rows with chemical years incorrectly."""
    df = pd.DataFrame({
        "Region": ["A", "A", "A", "A"],
        "Year": [2020, 2021, 2020, 2021],
        "Pollutant": ["Water_Level_cm", "Water_Level_cm", "Nitrates", "Nitrates"],
        "Concentration": [100.0, 100.0, 90.0, 45.0],
        "MPC": [100.0, 100.0, 45.0, 45.0],
        "WQI_Score": [50.0, 50.0, 100.0, 50.0],
        "Ratio": [1.0, 1.0, 2.0, 1.0],
        "data_source": ["observed", "observed", "reconstructed", "reconstructed"],
    })
    ctx = build_context(df)
    assert ctx["trend_direction"] == "improving"
    assert ctx["wqi_trend_delta"] == -50.0


def test_high_risk_region_by_count_not_mean_ratio():
    df = pd.DataFrame({
        "Region": ["Almaty", "Almaty", "Karaganda"],
        "Year": [2020, 2021, 2020],
        "Pollutant": ["Nitrates", "Copper", "Nitrates"],
        "Concentration": [100.0, 0.003, 50.0],
        "MPC": [45.0, 0.001, 45.0],
        "WQI_Score": [111.0, 150.0, 55.0],
        "Ratio": [2.2, 3.0, 1.1],
        "data_source": ["reconstructed"] * 3,
    })
    ctx = build_context(df)
    assert ctx["high_risk_leader_region"] == "Almaty"
    assert ctx["high_risk_leader_count"] == 2
    res = chat("Which region has the most high-risk records?", df, lang="en")
    assert "Almaty" in res["reply"]
    assert "2" in res["reply"]




def test_chat_empty_df():
    res = chat("help", pd.DataFrame(), lang="en")
    assert "filter" in res["reply"].lower() or "selection" in res["reply"].lower()
