"""Structured public-facing facts from filtered data."""

from __future__ import annotations

import pandas as pd

from analytics.ai_insights import NON_CHEMICAL, _chem
from analytics.water_body import only_lakes
from analytics.table_type import only_worst_parameter, restrict_to_full_panel


def _facts_for(base: pd.DataFrame) -> dict:
    facts: dict = {"records": int(len(base))}
    if base.empty:
        return facts

    # Primary ranking is by MEDIAN WQI, not mean: a handful of real extreme
    # readings (e.g. mining-affected Ertis-basin rivers) can drag a region's
    # mean into the thousands while every other reading sits near the MPC
    # line — the median is what "typical" means for this heavy-tailed data.
    # Mean is kept alongside as an explicitly-labeled secondary figure.
    if "Region" in base.columns and "WQI_Score" in base.columns:
        by_wqi = base.groupby("Region")["WQI_Score"].median().sort_values()
        by_wqi_mean = base.groupby("Region")["WQI_Score"].mean()
        if not by_wqi.empty:
            facts["cleanest_region"] = str(by_wqi.index[0])
            facts["cleanest_wqi"] = round(float(by_wqi.iloc[0]), 1)
            facts["cleanest_wqi_mean"] = round(float(by_wqi_mean[by_wqi.index[0]]), 1)
            facts["most_polluted_region"] = str(by_wqi.index[-1])
            facts["most_polluted_wqi"] = round(float(by_wqi.iloc[-1]), 1)
            facts["most_polluted_wqi_mean"] = round(float(by_wqi_mean[by_wqi.index[-1]]), 1)

    if "Pollutant" in base.columns and "Ratio" in base.columns:
        by_p = base.groupby("Pollutant")["Ratio"].median().sort_values(ascending=False)
        if not by_p.empty:
            facts["dangerous_pollutant"] = str(by_p.index[0])
            facts["dangerous_ratio"] = round(float(by_p.iloc[0]), 2)

    if "Ratio" in base.columns:
        facts["within_limits_pct"] = round(float((base["Ratio"] < 1).mean() * 100), 1)
        facts["over_mpc_pct"] = round(float((base["Ratio"] > 1).mean() * 100), 1)
        facts["high_risk_count"] = int((base["Ratio"] > 2).sum())

    if "Year" in base.columns and "WQI_Score" in base.columns:
        yearly = base.groupby("Year")["WQI_Score"].median().dropna().sort_index()
        if len(yearly) >= 2:
            facts["trend_delta"] = round(float(yearly.iloc[-1] - yearly.iloc[0]), 2)
            facts["trend_year_from"] = int(yearly.index[0])
            facts["trend_year_to"] = int(yearly.index[-1])

    if "Region" in base.columns and "WQI_Score" in base.columns:
        by_region_median = base.groupby("Region")["WQI_Score"].median()
        by_region_mean = base.groupby("Region")["WQI_Score"].mean()
        facts["regional_wqi"] = {
            str(k): round(float(v), 1) for k, v in by_region_median.items() if pd.notna(v)
        }
        facts["regional_wqi_mean"] = {
            str(k): round(float(v), 1) for k, v in by_region_mean.items() if pd.notna(v)
        }

    return facts


def public_facts(df: pd.DataFrame) -> dict:
    """River-default facts (see analytics.water_body) — the main dashboard view."""
    if df.empty:
        return {}
    chem = _chem(df)
    base = chem if not chem.empty else df
    return _facts_for(base)


def lake_facts(df: pd.DataFrame) -> dict:
    """Same shape as public_facts, computed for lake water bodies only.

    Shown as a separate panel rather than blended into public_facts, since
    lakes' natural mineralization (Alakol, Balkhash, Tengiz, ...) is not
    comparable to river pollution on the same ranking (see L7).
    """
    if df.empty or "Pollutant" not in df.columns:
        return {}
    chem = df[~df["Pollutant"].isin(NON_CHEMICAL)]
    lakes = only_lakes(chem)
    return _facts_for(lakes)


def worst_parameter_facts(df: pd.DataFrame) -> dict:
    """Same shape as public_facts, computed for worst_parameter readings only
    (river + lake — NOT lake-excluded; see full_panel_facts docstring for why).

    A worst_parameter table only ever reports the substance that exceeded a
    threshold that month — never a "normal" reading — so it is a biased
    sample of typical concentration. Shown separately from public_facts
    rather than blended into the same ranking (see analytics.table_type).
    """
    if df.empty or "Pollutant" not in df.columns:
        return {}
    chem = df[~df["Pollutant"].isin(NON_CHEMICAL)]
    worst = only_worst_parameter(chem)
    return _facts_for(worst)


def full_panel_facts(df: pd.DataFrame) -> dict:
    """Same shape as public_facts, computed for full_panel readings only
    (river + lake — NOT lake-excluded).

    In this dataset the full_panel table layout is ~all lakes/seas —
    Kazhydromet reports rivers via the worst_parameter table instead (see
    analytics.table_type and dashboard_service.kpi's docstring) — so
    rivers ∩ full_panel is ~empty and public_facts (the river-default view)
    is deliberately NOT also restricted to full_panel. This is the
    comprehensive-panel counterpart to worst_parameter_facts, not a
    "cleaner" version of public_facts.
    """
    if df.empty or "Pollutant" not in df.columns:
        return {}
    chem = df[~df["Pollutant"].isin(NON_CHEMICAL)]
    full = restrict_to_full_panel(chem)
    return _facts_for(full)
