"""Tests for rule-based insights."""

from __future__ import annotations

import pandas as pd

from analytics.ai_insights import generate_insights
from analytics.i18n_content import INSIGHT_DISCLAIMERS


def test_empty_dataframe_returns_disclaimer():
    insights = generate_insights(pd.DataFrame(), lang="en")
    assert len(insights) >= 1
    assert INSIGHT_DISCLAIMERS["en"] in insights[-1]


def test_generates_region_insight():
    df = pd.DataFrame(
        {
            "Region": ["Almaty", "Almaty", "VKO"],
            "Pollutant": ["Nitrates", "Copper", "Nitrates"],
            "Ratio": [2.5, 1.8, 0.5],
            "WQI_Score": [120, 90, 25],
            "Year": [2023, 2023, 2023],
            "data_source": ["reconstructed"] * 3,
        }
    )
    insights = generate_insights(df, lang="en")
    assert any("Almaty" in i for i in insights)
    assert INSIGHT_DISCLAIMERS["en"] in insights[-1]


def test_insights_ru():
    insights = generate_insights(pd.DataFrame(), lang="ru")
    assert "фильтр" in insights[0].lower() or "запис" in insights[0].lower()
