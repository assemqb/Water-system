"""
Kazakhstan Water Quality Dashboard.

Architecture: three-layer separation
  - Data layer:      data/loader.py, data/validator.py, db/kazakhstan_water_master.csv
  - Business logic:  analytics/wqi.py, analytics/hazard.py, config/settings.py
  - Presentation:    this Streamlit application

Streamlit enables rapid analytical dashboards for thesis defence; the SQLite/CSV
store supports a future migration path to PostgreSQL without changing business logic.
"""

from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.logging_config import get_logger
from config.settings import (
    DATASET_BANNER,
    DATA_PATH,
    GEOJSON_PATH,
    LIMITATIONS,
    ML_DISCLAIMER,
    MODEL_COLORS,
    REGION_NAME_MAP,
    TREE_MODEL_NAMES,
    WHY_NOT_DEEP_LEARNING,
)
from analytics.ai_insights import generate_insights
from analytics.ml_engine import (
    comparison_df_from_records,
    prepare_yearly_series,
    train_and_compare,
)
from analytics.shap_analysis import compute_shap_values
from data.loader import data_quality_summary, load_enriched
from data.validator import DataValidator
from visualization.charts import build_pollutant_region_heatmap, build_yoy_wqi_delta

logger = get_logger(__name__)

st.set_page_config(
    page_title="Kazakhstan Water Quality Dashboard",
    page_icon="💧",
    layout="wide",
)

KZ_GEOJSON_PATH = GEOJSON_PATH


@st.cache_data(show_spinner="Loading Kazakhstan map boundaries…")
def load_kz_geojson() -> dict:
    """
    Load kz.json (simplemaps.com, CC BY 4.0) and inject a 'region_key' id
    that matches our 8 dataset Region labels so choropleth_mapbox can join
    the WQI values to the correct polygon.

    Regions not in our dataset are retained but will appear grey (no data).
    """
    with open(KZ_GEOJSON_PATH, encoding="utf-8") as fh:
        raw = json.load(fh)

    # Build reverse map:  lowercase kz.json name  →  dataset label
    rev: dict[str, str] = {v.lower(): k for k, v in REGION_NAME_MAP.items()}

    for feat in raw["features"]:
        props = feat.setdefault("properties", {})
        raw_name: str = props.get("name", "")
        # Map to our dataset key if known, otherwise keep the original name
        region_key = rev.get(raw_name.lower(), raw_name)
        props["region_key"] = region_key
        feat["id"] = region_key          # used by featureidkey="id"

    return raw


@st.cache_data
def load_data() -> pd.DataFrame:
    df = load_enriched()
    report = DataValidator(strict=False).validate(df)
    if not report.passed:
        logger.error("Dataset validation failed: %s", report.errors)
    return df


def fit_linear_regression(year_series: pd.Series, value_series: pd.Series) -> Tuple[np.ndarray, np.ndarray]:
    x = year_series.astype(float).to_numpy()
    y = value_series.astype(float).to_numpy()
    coeffs = np.polyfit(x, y, 1)
    trend = np.polyval(coeffs, x)
    return coeffs, trend


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    residual = y_true - y_pred
    sse = float(np.sum(residual**2))
    sst = float(np.sum((y_true - float(np.mean(y_true))) ** 2))
    r2 = 1.0 - (sse / sst) if sst > 0 else 0.0
    mae = float(np.mean(np.abs(residual)))
    rmse = float(np.sqrt(np.mean(residual**2)))
    return {"r2": r2, "mae": mae, "rmse": rmse}


def build_kpi(df: pd.DataFrame) -> Dict[str, float]:
    return {
        "records": float(len(df)),
        "mean_wqi": float(df["WQI_Score"].mean()),
        "mean_ratio": float(df["Ratio"].mean()),
        "high_risk_share": float((df["Ratio"] > 2).mean() * 100),
    }


@st.cache_data
def _cached_ml_results(years_tuple: tuple, values_tuple: tuple, forecast_year: int) -> tuple:
    """Cache ML training keyed by yearly series (avoids retrain on every rerun)."""
    years = np.array(years_tuple, dtype=float)
    values = np.array(values_tuple, dtype=float)
    results = train_and_compare(years, values, forecast_year=forecast_year, n_cv_splits=3)
    serializable = []
    for r in results:
        serializable.append(
            {
                "name": r.name,
                "yhat": r.yhat.tolist(),
                "pred_next": r.pred_next,
                "insample": r.insample,
                "cv": r.cv,
                "n_samples": r.n_samples,
                "overfitting_warning": r.overfitting_warning,
            }
        )
    return tuple(serializable), forecast_year


def figure_to_png_bytes(fig: go.Figure) -> BytesIO | None:
    try:
        png_bytes = fig.to_image(format="png", width=1400, height=800, scale=2)
        return BytesIO(png_bytes)
    except Exception:
        logger.exception("PNG export failed")
        return None


def apply_theme(theme: str) -> str:
    if theme == "Dark":
        st.markdown(
            """
            <style>
            .block-container {
                padding-top: 4.8rem;
            }
            .stApp {
                background-color: #0e1117;
                color: #e6edf3;
            }
            .stApp, .stApp p, .stApp span, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3 {
                color: #e6edf3 !important;
            }
            [data-testid="stSidebar"] {
                background-color: #161b22;
            }
            [data-testid="stSidebar"] * {
                color: #e6edf3 !important;
            }
            [data-baseweb="select"] > div,
            [data-baseweb="tag"],
            [data-baseweb="input"] > div,
            .stTextInput input,
            .stSelectbox div[data-baseweb="select"] > div {
                background-color: #0d1117 !important;
                color: #e6edf3 !important;
                border-color: #30363d !important;
            }
            .top-nav {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                z-index: 999;
                height: 3.5rem;
                background: rgba(13, 17, 23, 0.95);
                border-bottom: 1px solid #30363d;
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0 1rem;
                backdrop-filter: blur(6px);
            }
            .top-nav-title {
                font-weight: 700;
                color: #e6edf3;
            }
            .top-nav-sub {
                color: #8b949e;
                font-size: 0.9rem;
            }
            .hero-card {
                background: linear-gradient(120deg, #1f6feb, #238636);
                color: #ffffff;
                padding: 1rem 1.2rem;
                border-radius: 12px;
                margin-bottom: 1rem;
            }
            [data-testid="stMetric"] {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 12px;
                padding: 0.6rem 0.8rem;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
            }
            .footer-muted {
                color: #8b949e;
                font-size: 0.9rem;
                text-align: center;
                padding-bottom: 0.5rem;
            }
            .section-title {
                margin-top: 1.1rem;
                margin-bottom: 0.45rem;
                font-size: 1.15rem;
                font-weight: 700;
                color: #f0f6fc;
                letter-spacing: 0.01em;
            }
            .section-block {
                margin-bottom: 1.25rem;
            }
            .chart-card {
                background: #111722;
                border: 1px solid #30363d;
                border-radius: 14px;
                padding: 0.55rem 0.55rem 0.2rem 0.55rem;
                box-shadow: 0 8px 22px rgba(0, 0, 0, 0.28);
            }
            .stButton > button, .stDownloadButton > button {
                background-color: #1f6feb;
                color: #ffffff !important;
                border: 1px solid #3b82f6;
            }
            .stButton > button:hover, .stDownloadButton > button:hover {
                background-color: #1a5fd0;
                border-color: #60a5fa;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        return "plotly_dark"

    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 4.8rem;
        }
        .stApp, .stApp p, .stApp span, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3 {
            color: #0f172a;
        }
        .top-nav {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 999;
            height: 3.5rem;
            background: rgba(255, 255, 255, 0.95);
            border-bottom: 1px solid #e5e7eb;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 1rem;
            backdrop-filter: blur(6px);
        }
        .top-nav-title {
            font-weight: 700;
            color: #0f172a;
        }
        .top-nav-sub {
            color: #64748b;
            font-size: 0.9rem;
        }
        .hero-card {
            background: linear-gradient(120deg, #1f77b4, #2ca02c);
            color: #ffffff;
            padding: 1rem 1.2rem;
            border-radius: 12px;
            margin-bottom: 1rem;
        }
        [data-testid="stMetric"] {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 0.6rem 0.8rem;
            box-shadow: 0 3px 12px rgba(15, 23, 42, 0.07);
        }
        .footer-muted {
            color: #6b7280;
            font-size: 0.9rem;
            text-align: center;
            padding-bottom: 0.5rem;
        }
        .section-title {
            margin-top: 1.1rem;
            margin-bottom: 0.45rem;
            font-size: 1.15rem;
            font-weight: 700;
            color: #0f172a;
            letter-spacing: 0.01em;
        }
        .section-block {
            margin-bottom: 1.25rem;
        }
        .chart-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 0.55rem 0.55rem 0.2rem 0.55rem;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
        }
        .stButton > button, .stDownloadButton > button {
            border-radius: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    return "plotly_white"


def section_header(text: str) -> None:
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)


def card_open() -> None:
    st.markdown('<div class="section-block"><div class="chart-card">', unsafe_allow_html=True)


def card_close() -> None:
    st.markdown("</div></div>", unsafe_allow_html=True)


def _parse_query_list(param_name: str) -> list[str]:
    raw_value = st.query_params.get(param_name)
    if not raw_value:
        return []
    return [item for item in str(raw_value).split(",") if item]


def _pick_valid_str(value: str | None, allowed: list[str], fallback: str) -> str:
    if value in allowed:
        return value
    return fallback


def main() -> None:
    section_options = ["Overview", "Map", "Trend", "Regions", "Prediction", "Export"]
    theme_options = ["Light", "Dark"]
    default_theme = _pick_valid_str(st.query_params.get("theme"), theme_options, "Light")
    default_section = _pick_valid_str(st.query_params.get("section"), section_options, "Overview")

    if "ui_theme" not in st.session_state:
        st.session_state["ui_theme"] = default_theme
    if "ui_section" not in st.session_state:
        st.session_state["ui_section"] = default_section

    with st.sidebar:
        st.header("Display Settings")
        theme_mode = st.radio(
            "Theme",
            theme_options,
            key="ui_theme",
            horizontal=True,
        )
        nav_focus = st.selectbox(
            "Active section",
            options=section_options,
            key="ui_section",
        )
    plot_template = apply_theme(theme_mode)

    st.markdown(
        f"""
        <div class="top-nav">
            <div class="top-nav-title">💧 Kazakhstan Water Quality</div>
            <div class="top-nav-sub">Frontend & Product Dashboard | {nav_focus}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="hero-card">
            <h2 style="margin:0;">💧 Kazakhstan Water Quality Dashboard</h2>
            <p style="margin:0.3rem 0 0 0;">
                Interactive analytics platform with trends, regional comparison, and baseline ML prediction.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.info(f"ℹ️ {DATASET_BANNER}")

    if not DATA_PATH.exists():
        st.error(f"Dataset not found: {DATA_PATH}. Run: python -m data.build_dataset")
        return

    df = load_data()

    with st.sidebar:
        st.header("Filters")
        all_sources = sorted(df["data_source"].dropna().unique()) if "data_source" in df.columns else ["reconstructed"]
        source_labels = {
            "observed": "Observed (Kazhydromet)",
            "reconstructed": "Reconstructed (chemical)",
            "reference": "Reference (international)",
        }
        default_sources = [s for s in ["observed", "reconstructed"] if s in all_sources] or all_sources

        if "selected_sources" not in st.session_state:
            st.session_state["selected_sources"] = default_sources

        selected_sources = st.multiselect(
            "Data source",
            options=all_sources,
            format_func=lambda x: source_labels.get(x, x),
            key="selected_sources",
        )

        df = df[df["data_source"].isin(selected_sources)] if "data_source" in df.columns else df

        all_regions = sorted(df["Region"].dropna().unique())
        all_years = sorted(df["Year"].dropna().unique())
        all_indicators = sorted(df["Pollutant"].dropna().unique())

        qp_regions = [v for v in _parse_query_list("regions") if v in all_regions]
        qp_years = []
        for v in _parse_query_list("years"):
            try:
                y = int(v)
                if y in all_years:
                    qp_years.append(y)
            except ValueError:
                continue
        qp_indicators = [v for v in _parse_query_list("indicators") if v in all_indicators]

        if "selected_regions" not in st.session_state:
            st.session_state["selected_regions"] = qp_regions or all_regions
        if "selected_years" not in st.session_state:
            st.session_state["selected_years"] = qp_years or all_years
        if "selected_indicators" not in st.session_state:
            st.session_state["selected_indicators"] = qp_indicators or all_indicators
        if st.button("Reset filters", use_container_width=True):
            st.session_state["selected_regions"] = all_regions
            st.session_state["selected_years"] = all_years
            st.session_state["selected_indicators"] = all_indicators
            st.rerun()
        selected_regions = st.multiselect(
            "Region",
            options=all_regions,
            key="selected_regions",
        )
        selected_years = st.multiselect(
            "Year",
            options=all_years,
            key="selected_years",
        )
        selected_indicators = st.multiselect(
            "Indicator (Pollutant)",
            options=all_indicators,
            key="selected_indicators",
        )

        with st.expander("About & Limitations"):
            st.markdown("**Dataset provenance**")
            dq = data_quality_summary(df)
            for src, pct in dq.get("sources", {}).items():
                st.write(f"- {source_labels.get(src, src)}: {pct}%")
            st.markdown("**Known limitations**")
            for lim in LIMITATIONS:
                st.caption(lim)

    filtered_df = df[
        df["Region"].isin(selected_regions)
        & df["Year"].isin(selected_years)
        & df["Pollutant"].isin(selected_indicators)
    ].copy()

    if filtered_df.empty:
        st.warning("No data for selected filters. Please widen your selection.")
        logger.warning("Empty DataFrame after filter application")
        return

    section_header("📋 Data Quality Summary")
    card_open()
    dq = data_quality_summary(filtered_df)
    dc1, dc2, dc3, dc4 = st.columns(4)
    dc1.metric("Records (n)", f"{dq['total']:,}")
    dc2.metric("Observed %", f"{dq.get('observed_pct', 0):.1f}%")
    dc3.metric("Reconstructed %", f"{dq.get('reconstructed_pct', 0):.1f}%")
    dc4.metric("Reference %", f"{dq.get('reference_pct', 0):.1f}%")
    card_close()

    section_header("🚨 Risk Alerts")
    card_open()
    high_risk_df = filtered_df[filtered_df["Ratio"] > 2].copy()
    moderate_risk_df = filtered_df[(filtered_df["Ratio"] >= 1) & (filtered_df["Ratio"] <= 2)].copy()
    if high_risk_df.empty:
        st.success("No high-risk records (Ratio > 2) found for current filters.")
    else:
        st.error(
            f"High-risk records: {len(high_risk_df)} "
            f"({len(high_risk_df) / len(filtered_df) * 100:.1f}% of filtered data)."
        )
    st.info(
        f"Moderate-risk records: {len(moderate_risk_df)} "
        f"({len(moderate_risk_df) / len(filtered_df) * 100:.1f}% of filtered data)."
    )
    top_risk_regions = (
        filtered_df.groupby("Region", as_index=False)
        .agg(
            Mean_Ratio=("Ratio", "mean"),
            High_Risk_Records=("Ratio", lambda x: int((x > 2).sum())),
            Total_Records=("Ratio", "size"),
            Mean_WQI=("WQI_Score", "mean"),
        )
        .sort_values(["High_Risk_Records", "Mean_Ratio"], ascending=[False, False])
    )
    top_risk_regions["High_Risk_Share_%"] = (
        top_risk_regions["High_Risk_Records"] / top_risk_regions["Total_Records"] * 100
    ).round(1)
    st.markdown("**Top risk regions (current filter view):**")
    st.dataframe(
        top_risk_regions[
            ["Region", "High_Risk_Records", "High_Risk_Share_%", "Mean_Ratio", "Mean_WQI"]
        ].head(8),
        use_container_width=True,
        hide_index=True,
    )
    card_close()

    kpi = build_kpi(filtered_df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Records", f"{int(kpi['records'])}")
    c2.metric("Mean WQI", f"{kpi['mean_wqi']:.2f}")
    c3.metric("Mean Ratio", f"{kpi['mean_ratio']:.2f}")
    c4.metric("High-Risk Share", f"{kpi['high_risk_share']:.1f}%")

    section_header("🗺️ Regional Choropleth (Kazakhstan)")
    regional_map = (
        filtered_df.groupby("Region", as_index=False)["WQI_Score"]
        .mean()
        .rename(columns={"WQI_Score": "Mean_WQI"})
    )
    kz_geojson = load_kz_geojson()
    fig_map = px.choropleth_mapbox(
        regional_map,
        geojson=kz_geojson,
        locations="Region",
        featureidkey="id",
        color="Mean_WQI",
        color_continuous_scale="YlOrRd",
        range_color=(regional_map["Mean_WQI"].min() * 0.95,
                     regional_map["Mean_WQI"].max() * 1.05),
        mapbox_style="carto-positron",   # free tile — no token required
        zoom=3.8,
        center={"lat": 48.0, "lon": 66.0},  # centre of Kazakhstan
        opacity=0.75,
        hover_name="Region",
        hover_data={"Mean_WQI": ":.2f"},
        title="Average WQI by Region",
        labels={"Mean_WQI": "WQI Score"},
    )
    fig_map.update_layout(
        margin={"l": 0, "r": 0, "t": 50, "b": 0},
        template=plot_template,
        coloraxis_colorbar=dict(
            title="WQI Score",
            tickfont=dict(size=11),
        ),
    )
    card_open()
    st.plotly_chart(fig_map, use_container_width=True)
    card_close()

    left, right = st.columns(2)

    with left:
        section_header("📈 Line Chart: WQI Trend")
        trend = filtered_df.groupby("Year", as_index=False)["WQI_Score"].mean()
        fig_line = px.line(
            trend,
            x="Year",
            y="WQI_Score",
            markers=True,
            title="Average WQI Over Time",
            template=plot_template,
        )
        card_open()
        st.plotly_chart(fig_line, use_container_width=True)
        card_close()

    with right:
        section_header("📊 Bar Chart: Regions Comparison")
        region_bar = filtered_df.groupby("Region", as_index=False)["WQI_Score"].mean()
        region_bar = region_bar.sort_values("WQI_Score", ascending=False)
        fig_bar = px.bar(
            region_bar,
            x="Region",
            y="WQI_Score",
            color="WQI_Score",
            color_continuous_scale="Blues",
            title="Average WQI by Region",
            template=plot_template,
        )
        card_open()
        st.plotly_chart(fig_bar, use_container_width=True)
        card_close()

    section_header("🗺️ Pollutant × Region Heatmap")
    fig_heatmap = build_pollutant_region_heatmap(
        filtered_df, template=plot_template, n_records=len(filtered_df)
    )
    card_open()
    st.plotly_chart(fig_heatmap, use_container_width=True)
    card_close()

    section_header("📉 Year-over-Year WQI Delta by Region")
    fig_yoy = build_yoy_wqi_delta(filtered_df, template=plot_template)
    card_open()
    st.plotly_chart(fig_yoy, use_container_width=True)
    card_close()

    section_header("💡 Insights (rule-based)")
    card_open()
    for line in generate_insights(filtered_df):
        st.markdown(line)
    card_close()

    section_header("🤖 ML Prediction — Comparative Study")
    st.caption(
        f"Validation: TimeSeriesSplit CV | Metrics: MAE, RMSE, R², MAPE | {ML_DISCLAIMER}"
    )
    st.caption(f"ℹ️ {WHY_NOT_DEEP_LEARNING}")
    pred_options = ["WQI_Score", "Concentration"]
    if "pred_target" not in st.session_state:
        st.session_state["pred_target"] = _pick_valid_str(
            st.query_params.get("pred_target"),
            pred_options,
            "WQI_Score",
        )
    pred_target = st.radio(
        "Prediction target",
        options=pred_options,
        key="pred_target",
        horizontal=True,
    )
    pred_data = prepare_yearly_series(filtered_df, pred_target)
    fig_pred = go.Figure()

    if len(pred_data) >= 2:
        _years = pred_data["Year"].astype(int).tolist()
        _y = pred_data[pred_target].tolist()
        _next = int(max(_years)) + 1

        _cached, _ = _cached_ml_results(tuple(_years), tuple(_y), _next)
        _colors = MODEL_COLORS

        _tab_names = ["📊 All Models (ranked)"] + [r["name"] for r in _cached]
        _tabs = st.tabs(_tab_names)

        with _tabs[0]:
            fig_pred = go.Figure()
            fig_pred.add_trace(go.Scatter(
                x=_years, y=_y,
                mode="lines+markers", name="Actual",
                line=dict(color="#1E40AF", width=2.5),
                marker=dict(size=8),
            ))
            for _res in _cached:
                _name = _res["name"]
                _color = _colors.get(_name, "#64748B")
                fig_pred.add_trace(go.Scatter(
                    x=_years, y=_res["yhat"],
                    mode="lines", name=f"{_name} fit",
                    line=dict(dash="dash", color=_color, width=1.8),
                ))
                fig_pred.add_trace(go.Scatter(
                    x=[_next], y=[_res["pred_next"]],
                    mode="markers+text",
                    text=[f"{_res['pred_next']:.1f}"],
                    textposition="top center",
                    marker=dict(size=11, symbol="triangle-up", color=_color),
                    name=f"{_name} → {_next}",
                ))
            fig_pred.update_layout(
                title=f"Model comparison — {pred_target} forecast to {_next} (n={len(_years)} years)",
                xaxis_title="Year",
                yaxis_title=pred_target,
                template=plot_template,
                legend=dict(orientation="h", y=-0.3),
            )
            st.plotly_chart(fig_pred, use_container_width=True)

            _cmp_df = comparison_df_from_records(list(_cached), _next)
            st.markdown(f"**Ranked comparison (n={len(_years)} annual observations)**")
            st.dataframe(_cmp_df, use_container_width=True, hide_index=True)

            if any(r["overfitting_warning"] for r in _cached):
                st.warning(
                    "Tree/boosting models show in-sample R² > 0.95 on n < 10 — overfitting likely. "
                    "Trust CV metrics and Linear Regression for trend interpretation."
                )

            with st.expander("SHAP feature importance (tree-based models)"):
                X = np.array(_years, dtype=float).reshape(-1, 1)
                live_results = train_and_compare(
                    np.array(_years, dtype=float), np.array(_y), _next
                )
                live_map = {r.name: r for r in live_results}
                for _res in _cached:
                    if _res["name"] not in TREE_MODEL_NAMES or _res["name"] not in live_map:
                        continue
                    shap_df = compute_shap_values(
                        live_map[_res["name"]].model,
                        _res["name"],
                        X,
                        feature_names=["Year"],
                    )
                    if shap_df is not None:
                        st.markdown(f"**{_res['name']}** — mean |SHAP|")
                        fig_shap = px.bar(
                            shap_df,
                            x="mean_abs_shap",
                            y="feature",
                            orientation="h",
                            template=plot_template,
                            title=f"SHAP — {_res['name']} (n={len(_years)})",
                        )
                        st.plotly_chart(fig_shap, use_container_width=True)

        for _idx, _res in enumerate(_cached, start=1):
            with _tabs[_idx]:
                _name = _res["name"]
                _color = _colors.get(_name, "#64748B")
                fig_single = go.Figure()
                fig_single.add_trace(go.Bar(
                    x=_years, y=_y,
                    name="Actual", marker_color="#1E40AF", opacity=0.8,
                ))
                fig_single.add_trace(go.Bar(
                    x=_years, y=_res["yhat"],
                    name="Predicted", marker_color=_color, opacity=0.8,
                ))
                fig_single.add_trace(go.Scatter(
                    x=[_next], y=[_res["pred_next"]],
                    mode="markers+text",
                    text=[f"{_next} forecast: {_res['pred_next']:.2f}"],
                    textposition="top center",
                    marker=dict(size=13, symbol="triangle-up", color=_color),
                    name=f"Forecast {_next}",
                ))
                fig_single.update_layout(
                    barmode="group",
                    title=f"{_name} — Actual vs Predicted ({pred_target}, n={len(_years)})",
                    xaxis_title="Year",
                    yaxis_title=pred_target,
                    template=plot_template,
                )
                card_open()
                st.plotly_chart(fig_single, use_container_width=True)
                mc1, mc2, mc3, mc4, mc5 = st.columns(5)
                mc1.metric("CV R²", f"{_res['cv']['r2']:.3f}" if _res['cv']['r2'] == _res['cv']['r2'] else "—")
                mc2.metric("CV MAE", f"{_res['cv']['mae']:.3f}" if _res['cv']['mae'] == _res['cv']['mae'] else "—")
                mc3.metric("CV RMSE", f"{_res['cv']['rmse']:.3f}" if _res['cv']['rmse'] == _res['cv']['rmse'] else "—")
                mc4.metric("CV MAPE %", f"{_res['cv']['mape']:.2f}" if _res['cv']['mape'] == _res['cv']['mape'] else "—")
                mc5.metric(f"Pred {_next}", f"{_res['pred_next']:.2f}")
                if _res["overfitting_warning"]:
                    st.warning("Overfitting warning: in-sample R² > 0.95 on small n.")
                card_close()
    else:
        st.info("Not enough yearly points for ML prediction (need ≥ 2 years).")

    section_header("⚖️ Compare Mode")
    card_open()
    compare_regions = sorted(filtered_df["Region"].dropna().unique())
    compare_years = sorted(filtered_df["Year"].dropna().unique())
    cmp_col1, cmp_col2 = st.columns(2)
    with cmp_col1:
        region_a = st.selectbox("Region A", options=compare_regions, key="cmp_region_a")
        year_range_a = st.selectbox(
            "Period A (Year)",
            options=compare_years,
            key="cmp_year_a",
        )
    with cmp_col2:
        region_b = st.selectbox(
            "Region B",
            options=compare_regions,
            index=1 if len(compare_regions) > 1 else 0,
            key="cmp_region_b",
        )
        year_range_b = st.selectbox(
            "Period B (Year)",
            options=compare_years,
            index=len(compare_years) - 1,
            key="cmp_year_b",
        )

    a_df = filtered_df[(filtered_df["Region"] == region_a) & (filtered_df["Year"] == year_range_a)]
    b_df = filtered_df[(filtered_df["Region"] == region_b) & (filtered_df["Year"] == year_range_b)]
    if a_df.empty or b_df.empty:
        st.warning("Comparison needs available data in both selected region-period combinations.")
    else:
        a_wqi = float(a_df["WQI_Score"].mean())
        b_wqi = float(b_df["WQI_Score"].mean())
        a_ratio = float(a_df["Ratio"].mean())
        b_ratio = float(b_df["Ratio"].mean())
        a_high = float((a_df["Ratio"] > 2).mean() * 100)
        b_high = float((b_df["Ratio"] > 2).mean() * 100)

        cm1, cm2, cm3 = st.columns(3)
        cm1.metric(
            "Mean WQI delta (B - A)",
            f"{(b_wqi - a_wqi):.2f}",
            delta=f"A: {a_wqi:.2f} | B: {b_wqi:.2f}",
        )
        cm2.metric(
            "Mean Ratio delta (B - A)",
            f"{(b_ratio - a_ratio):.2f}",
            delta=f"A: {a_ratio:.2f} | B: {b_ratio:.2f}",
        )
        cm3.metric(
            "High-Risk Share delta (pp)",
            f"{(b_high - a_high):.1f}",
            delta=f"A: {a_high:.1f}% | B: {b_high:.1f}%",
        )
    card_close()

    section_header("📦 Export")
    csv_bytes = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered data as CSV",
        data=csv_bytes,
        file_name="filtered_water_quality_data.csv",
        mime="text/csv",
    )

    export_options = {
        "map": fig_map,
        "trend": fig_line,
        "regions": fig_bar,
        "heatmap": fig_heatmap,
        "yoy_delta": fig_yoy,
        "prediction": fig_pred,
    }
    export_keys = list(export_options.keys())
    if "export_chart" not in st.session_state:
        st.session_state["export_chart"] = _pick_valid_str(
            st.query_params.get("export_chart"),
            export_keys,
            "map",
        )
    export_chart = st.selectbox("Choose chart to export as PNG", export_keys, key="export_chart")
    png_file = figure_to_png_bytes(export_options[export_chart])
    if png_file is not None:
        st.download_button(
            "Download chart as PNG",
            data=png_file,
            file_name=f"{export_chart}_chart.png",
            mime="image/png",
        )
    else:
        st.warning("PNG export requires 'kaleido'. Run: pip install kaleido")

    st.markdown("---")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.markdown(f'<div class="footer-muted">Last updated: {now_str}</div>', unsafe_allow_html=True)

    # Persist UI and filter state in URL so refresh keeps selections.
    st.query_params["theme"] = theme_mode
    st.query_params["section"] = nav_focus
    st.query_params["regions"] = ",".join(selected_regions)
    st.query_params["years"] = ",".join(str(int(y)) for y in selected_years)
    st.query_params["indicators"] = ",".join(selected_indicators)
    st.query_params["pred_target"] = pred_target
    st.query_params["export_chart"] = export_chart


if __name__ == "__main__":
    main()