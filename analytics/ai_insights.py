"""Rule-based localized insight generator."""

from __future__ import annotations

import pandas as pd

from analytics.i18n_content import INSIGHT_DISCLAIMERS, norm_lang
from analytics.water_body import exclude_lakes

NON_CHEMICAL = {"Water_Level_cm", "Mixed_Chemicals"}


def _chem(df: pd.DataFrame) -> pd.DataFrame:
    """Chemical-pollutant rows, rivers only (see analytics.water_body)."""
    if "Pollutant" not in df.columns:
        return df
    return exclude_lakes(df[~df["Pollutant"].isin(NON_CHEMICAL)])


def _pick(lang: str, en: str, ru: str, kk: str) -> str:
    if lang == "ru":
        return ru
    if lang == "kk":
        return kk
    return en


def generate_insights(df: pd.DataFrame, lang: str = "en") -> list[str]:
    lang = norm_lang(lang)
    if df.empty:
        return [
            _pick(
                lang,
                "No monitoring records match the selected region, years, or pollutants. Try expanding your filters.",
                "Нет записей для выбранных региона, годов или загрязнителей. Расширьте фильтры.",
                "Таңдалған аудан, жыл немесе ластаушылар бойынша жазба жоқ. Сүзгілерді кеңейтіңіз.",
            ),
            INSIGHT_DISCLAIMERS[lang],
        ]

    chem = _chem(df)
    base = chem if not chem.empty else df
    insights: list[str] = []
    n = len(base)

    # Ranked by MEDIAN, matching the KPI/region-stats/facts ranking
    # (dashboard_service, public_facts) — a handful of real extreme
    # readings can drag a mean far above what any "typical" reading looks
    # like; using mean here and median there could pick a different
    # "worst region" than the KPI panel shows for the same filtered view.
    if "Region" in base.columns and "Ratio" in base.columns:
        regional = base.groupby("Region")["Ratio"].median().sort_values(ascending=False)
        if not regional.empty:
            top = regional.index[0]
            ratio = regional.iloc[0]
            insights.append(
                _pick(
                    lang,
                    f"**{top}** shows the highest median pollution ratio ({ratio:.2f}× MPC) in the current view (n={n:,}).",
                    f"**{top}** — наибольшее медианное отношение к ПДК ({ratio:.2f}×) в текущей выборке (n={n:,}).",
                    f"**{top}** — ағымдағы көруде медиана ластану ({ratio:.2f}× ШРК) ең жоғары (n={n:,}).",
                )
            )
            clean = regional.index[-1]
            clean_r = regional.iloc[-1]
            insights.append(
                _pick(
                    lang,
                    f"**{clean}** is the cleanest region by median ratio ({clean_r:.2f}× MPC).",
                    f"**{clean}** — самый чистый регион по медианному отношению ({clean_r:.2f}× ПДК).",
                    f"**{clean}** — медиана қатынасы бойынша ең таза аудан ({clean_r:.2f}× ШРК).",
                )
            )

    if "Pollutant" in base.columns and "Ratio" in base.columns:
        by_poll = base.groupby("Pollutant")["Ratio"].median().sort_values(ascending=False)
        if not by_poll.empty:
            worst = by_poll.index[0]
            wr = by_poll.iloc[0]
            insights.append(
                _pick(
                    lang,
                    f"**{worst}** is the most critical pollutant (median {wr:.2f}× MPC).",
                    f"**{worst}** — самый проблемный загрязнитель (медиана {wr:.2f}× ПДК).",
                    f"**{worst}** — ең проблемалы ластаушы (медиана {wr:.2f}× ШРК).",
                )
            )

    if "Year" in base.columns and "WQI_Score" in base.columns:
        yearly = base.groupby("Year")["WQI_Score"].median().dropna().sort_index()
        if len(yearly) >= 2:
            delta = yearly.iloc[-1] - yearly.iloc[0]
            pct = (delta / yearly.iloc[0] * 100) if yearly.iloc[0] else 0
            if delta > 0:
                insights.append(
                    _pick(
                        lang,
                        f"Water quality **deteriorated** by {abs(pct):.0f}% (WQI {delta:+.1f}) from {int(yearly.index[0])} to {int(yearly.index[-1])}.",
                        f"Качество **ухудшилось** на {abs(pct):.0f}% (WQI {delta:+.1f}) с {int(yearly.index[0])} по {int(yearly.index[-1])}.",
                        f"Су сапасы **{int(yearly.index[0])}–{int(yearly.index[-1])}** аралығында {abs(pct):.0f}% нашарлады (WQI {delta:+.1f}).",
                    )
                )
            elif delta < -0.5:
                insights.append(
                    _pick(
                        lang,
                        f"Water quality **improved** by {abs(pct):.0f}% (WQI {delta:+.1f}) from {int(yearly.index[0])} to {int(yearly.index[-1])}.",
                        f"Качество **улучшилось** на {abs(pct):.0f}% (WQI {delta:+.1f}) с {int(yearly.index[0])} по {int(yearly.index[-1])}.",
                        f"Су сапасы **{int(yearly.index[0])}–{int(yearly.index[-1])}** аралығында {abs(pct):.0f}% жақсарды (WQI {delta:+.1f}).",
                    )
                )

    if "Ratio" in base.columns:
        safe_pct = (base["Ratio"] < 1).mean() * 100
        high = int((base["Ratio"] > 2).sum())
        insights.append(
            _pick(
                lang,
                f"**{safe_pct:.0f}%** of records are within MPC limits; **{high}** high-risk records detected (ratio > 2×).",
                f"**{safe_pct:.0f}%** записей в пределах ПДК; обнаружено **{high}** записей высокого риска (> 2×).",
                f"**{safe_pct:.0f}%** жазба ШРК шегінде; **{high}** жоғары тәуекел жазбасы (> 2×).",
            )
        )

    insights.append(INSIGHT_DISCLAIMERS[lang])
    return insights
