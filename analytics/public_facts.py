"""Structured public-facing facts from filtered data."""

from __future__ import annotations

import pandas as pd

from analytics.ai_insights import _chem


def public_facts(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    chem = _chem(df)
    base = chem if not chem.empty else df
    facts: dict = {"records": int(len(base))}

    if "Region" in base.columns and "WQI_Score" in base.columns:
        by_wqi = base.groupby("Region")["WQI_Score"].mean().sort_values()
        facts["cleanest_region"] = str(by_wqi.index[0])
        facts["cleanest_wqi"] = round(float(by_wqi.iloc[0]), 1)
        facts["most_polluted_region"] = str(by_wqi.index[-1])
        facts["most_polluted_wqi"] = round(float(by_wqi.iloc[-1]), 1)

    if "Pollutant" in base.columns and "Ratio" in base.columns:
        by_p = base.groupby("Pollutant")["Ratio"].mean().sort_values(ascending=False)
        if not by_p.empty:
            facts["dangerous_pollutant"] = str(by_p.index[0])
            facts["dangerous_ratio"] = round(float(by_p.iloc[0]), 2)

    if "Ratio" in base.columns:
        facts["within_limits_pct"] = round(float((base["Ratio"] < 1).mean() * 100), 1)
        facts["high_risk_count"] = int((base["Ratio"] > 2).sum())

    if "Year" in base.columns and "WQI_Score" in base.columns:
        yearly = base.groupby("Year")["WQI_Score"].mean().dropna().sort_index()
        if len(yearly) >= 2:
            facts["trend_delta"] = round(float(yearly.iloc[-1] - yearly.iloc[0]), 2)
            facts["trend_year_from"] = int(yearly.index[0])
            facts["trend_year_to"] = int(yearly.index[-1])

    if "Region" in base.columns and "Ratio" in base.columns:
        regional = base.groupby("Region")["Ratio"].mean()
        facts["regional_wqi"] = {
            str(k): round(float(base[base["Region"] == k]["WQI_Score"].mean()), 1)
            for k in regional.index
            if pd.notna(base[base["Region"] == k]["WQI_Score"].mean())
        }

    return facts
