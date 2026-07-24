"""
Context-aware water quality chat assistant powered by Ollama.

Primary mode: Ollama local LLM with structured AquaMonitor analytics context.
Fallback mode: rule-based answers when Ollama is unavailable.

Metrics align with the dashboard: chemical pollutants for pollution/risk/trend;
high-risk region = most records with ratio > 2 (not highest mean ratio alone).
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from analytics.ai_insights import generate_insights
from analytics.i18n_content import INSIGHT_DISCLAIMERS
from analytics.chat_nlu import extract_regions, extract_year
from analytics.ollama_client import generate as ollama_generate, is_available as ollama_available

NON_CHEMICAL_POLLUTANTS = frozenset({"Water_Level_cm", "Mixed_Chemicals"})

CHAT_DISCLAIMER_EN = (
    "This assistant uses your current dashboard filters. "
    "Pollution metrics use chemical indicators only (excludes water-level proxies). "
    "Not regulatory advice."
)
CHAT_DISCLAIMER_RU = (
    "Ответы основаны на текущих фильтрах. "
    "Показатели загрязнения — только химические индикаторы (без уровня воды). "
    "Не нормативная рекомендация."
)

CHAT_DISCLAIMER_KK = (
    "Жауаптар ағымдағы сүзгілерге негізделген. "
    "Ластану көрсеткіштері — тек химиялық индикаторлар (су деңгейі емес). "
    "Нормативтік ұсыныс емес."
)

SUGGESTIONS_EN = [
    "Which region faces the highest pollution pressure?",
    "Is water quality improving or getting worse?",
    "What is the main pollutant in the current view?",
    "Which areas need monitoring priority?",
]
SUGGESTIONS_RU = [
    "Какой регион испытывает наибольшее давление загрязнения?",
    "Улучшается или ухудшается качество воды?",
    "Какой загрязнитель доминирует в текущей выборке?",
    "Каким районам нужен приоритетный мониторинг?",
]
SUGGESTIONS_KK = [
    "Қай ауданда ластану қысымы ең жоғары?",
    "Су сапасы жақсарып жатыр ма, әлде нашарлап жатыр ма?",
    "Ағымдағы көруде басым ластаушы қандай?",
    "Қай аудандарға бақылау басымдығы керек?",
]


def _pick(lang: str, en: str, ru: str, kk: str) -> str:
    if lang == "kk":
        return kk
    if lang == "ru":
        return ru
    return en


def _disclaimer(lang: str) -> str:
    return _pick(lang, CHAT_DISCLAIMER_EN, CHAT_DISCLAIMER_RU, CHAT_DISCLAIMER_KK)


def _suggestions(lang: str) -> list[str]:
    if lang == "kk":
        return list(SUGGESTIONS_KK)
    if lang == "ru":
        return list(SUGGESTIONS_RU)
    return list(SUGGESTIONS_EN)


def _chemical_df(df: pd.DataFrame) -> pd.DataFrame:
    if "Pollutant" not in df.columns:
        return df
    return df[~df["Pollutant"].isin(NON_CHEMICAL_POLLUTANTS)]


def _stats_block(sub: pd.DataFrame) -> dict[str, Any]:
    if sub.empty:
        return {}
    return {
        "records": int(len(sub)),
        "mean_wqi": round(float(sub["WQI_Score"].mean()), 2),
        "mean_ratio": round(float(sub["Ratio"].mean()), 2),
        "high_risk_pct": round(float((sub["Ratio"] > 2).mean() * 100), 1),
        "moderate_risk_pct": round(float(((sub["Ratio"] >= 1) & (sub["Ratio"] <= 2)).mean() * 100), 1),
    }


def _high_risk_leader(sub: pd.DataFrame) -> tuple[str | None, int, float | None]:
    """Region with the most ratio > 2 records (matches dashboard risk table)."""
    high = sub[sub["Ratio"] > 2]
    if high.empty or "Region" not in high.columns:
        return None, 0, None
    counts = high.groupby("Region").size().sort_values(ascending=False)
    region = str(counts.index[0])
    count = int(counts.iloc[0])
    share = round(count / len(sub[sub["Region"] == region]) * 100, 1) if len(sub[sub["Region"] == region]) else None
    return region, count, share


def _mean_ratio_leader(sub: pd.DataFrame) -> tuple[str | None, float | None]:
    if sub.empty or "Region" not in sub.columns:
        return None, None
    regional = sub.groupby("Region")["Ratio"].mean().sort_values(ascending=False)
    if regional.empty:
        return None, None
    return str(regional.index[0]), round(float(regional.iloc[0]), 2)


def _wqi_extremes(sub: pd.DataFrame) -> dict[str, Any]:
    if sub.empty or "Region" not in sub.columns:
        return {}
    by_region = sub.groupby("Region")["WQI_Score"].mean().sort_values()
    if by_region.empty:
        return {}
    return {
        "best_wqi_region": str(by_region.index[0]),
        "best_wqi": round(float(by_region.iloc[0]), 2),
        "worst_wqi_region": str(by_region.index[-1]),
        "worst_wqi": round(float(by_region.iloc[-1]), 2),
    }


def _trend_block(sub: pd.DataFrame) -> dict[str, Any]:
    if sub.empty or "Year" not in sub.columns:
        return {}
    yearly = sub.groupby("Year")["WQI_Score"].mean().dropna().sort_index()
    if len(yearly) < 2:
        return {"trend_years": len(yearly)}
    delta = float(yearly.iloc[-1] - yearly.iloc[0])
    return {
        "year_range": [int(yearly.index[0]), int(yearly.index[-1])],
        "wqi_trend_delta": round(delta, 2),
        "trend_direction": "deteriorating" if delta > 0 else ("stable" if abs(delta) < 0.5 else "improving"),
        "trend_start_wqi": round(float(yearly.iloc[0]), 2),
        "trend_end_wqi": round(float(yearly.iloc[-1]), 2),
    }


def _summarize_forecast(forecast: dict[str, Any] | None) -> dict[str, Any]:
    if not forecast or not forecast.get("ok"):
        return {"available": False, "reason": forecast.get("message") if forecast else "not computed"}
    models = forecast.get("models") or []
    linear = next((m for m in models if m.get("name") == "Linear Regression"), None)
    best = linear or (min(models, key=lambda m: m.get("cv", {}).get("mae", 1e9)) if models else None)
    return {
        "available": True,
        "target": forecast.get("target"),
        "years_observed": forecast.get("years"),
        "forecast_year": forecast.get("forecast_year"),
        "recommended_model": best.get("name") if best else None,
        "predicted_next": best.get("pred_next") if best else None,
        "any_overfitting": forecast.get("any_overfitting"),
    }


def _summarize_hotspots(hotspots: list[dict[str, Any]] | None, limit: int = 5) -> list[dict[str, Any]]:
    if not hotspots:
        return []
    ranked = sorted(hotspots, key=lambda h: h.get("intensity", 0), reverse=True)
    return [
        {
            "station": h.get("name"),
            "basin": h.get("basin"),
            "intensity": h.get("intensity"),
            "high_risk_pct": h.get("high_risk_pct"),
            "status": h.get("status"),
        }
        for h in ranked[:limit]
    ]


def _summarize_basins(basin_stats: list[dict[str, Any]] | None, limit: int = 8) -> list[dict[str, Any]]:
    if not basin_stats:
        return []
    return [
        {
            "basin": b.get("id"),
            "mean_wqi": b.get("mean_wqi"),
            "max_ratio": b.get("max_ratio"),
            "high_risk_pct": b.get("high_risk_pct"),
            "top_pollutant": b.get("top_pollutant"),
            "top_region": b.get("top_region"),
            "trend_wqi_delta": b.get("trend_wqi_delta"),
        }
        for b in basin_stats[:limit]
    ]


def build_context(
    df: pd.DataFrame,
    *,
    filters: dict[str, Any] | None = None,
    hotspots: list[dict[str, Any]] | None = None,
    basin_stats: list[dict[str, Any]] | None = None,
    forecast: dict[str, Any] | None = None,
    risk_alerts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarise filtered data and dashboard analytics for the LLM."""
    ctx: dict[str, Any] = {
        "platform": "AquaMonitor Kazakhstan Water Quality Intelligence",
        "active_filters": filters or {},
    }

    if df.empty:
        ctx.update({"empty": True, "records": 0})
        ctx["forecast"] = _summarize_forecast(forecast)
        return ctx

    chem = _chemical_df(df)
    ctx.update({
        "empty": False,
        "records_total": int(len(df)),
        "records_chemical": int(len(chem)),
        "observed_pct": round(float((df["data_source"] == "observed").mean() * 100), 1)
        if "data_source" in df.columns else None,
    })

    # Primary pollution stats = chemical only (consistent with heatmap / hazard logic)
    poll = _stats_block(chem if not chem.empty else df)
    ctx.update(poll)
    ctx["records"] = ctx.get("records", ctx["records_total"])
    ctx["using_chemical_subset"] = not chem.empty and len(chem) < len(df)

    analysis = chem if not chem.empty else df
    hr_region, hr_count, _ = _high_risk_leader(analysis)
    ctx["high_risk_leader_region"] = hr_region
    ctx["high_risk_leader_count"] = hr_count
    mr_region, mr_ratio = _mean_ratio_leader(analysis)
    ctx["top_mean_ratio_region"] = mr_region
    ctx["top_mean_ratio"] = mr_ratio
    ctx.update(_wqi_extremes(analysis))
    ctx.update(_trend_block(analysis))

    if "Pollutant" in analysis.columns:
        by_poll = analysis.groupby("Pollutant")["Ratio"].mean().sort_values(ascending=False)
        if not by_poll.empty:
            ctx["worst_pollutant"] = str(by_poll.index[0])
            ctx["worst_pollutant_ratio"] = round(float(by_poll.iloc[0]), 2)

    if "data_source" in df.columns and "Region" in analysis.columns:
        high = analysis[analysis["Ratio"] > 2]
        if not high.empty:
            src = high["data_source"].value_counts(normalize=True).mul(100).round(1)
            ctx["high_risk_source_mix"] = src.to_dict()

    if "Region" in analysis.columns:
        stats = {}
        for reg, grp in analysis.groupby("Region"):
            stats[str(reg)] = {
                "mean_wqi": round(float(grp["WQI_Score"].mean()), 2),
                "mean_ratio": round(float(grp["Ratio"].mean()), 2),
                "high_risk": int((grp["Ratio"] > 2).sum()),
                "n": int(len(grp)),
            }
        ctx["region_stats"] = stats
        ctx["available_regions"] = list(stats.keys())

    if "data_source" in df.columns:
        shares = (df["data_source"].value_counts(normalize=True) * 100).round(1)
        ctx["source_mix"] = shares.to_dict()

    if "Basin" in df.columns:
        ctx["available_basins"] = sorted(df["Basin"].dropna().unique().tolist())
    if "Year" in df.columns:
        ctx["selected_years"] = sorted(int(y) for y in df["Year"].dropna().unique())
    if "Pollutant" in df.columns:
        ctx["selected_pollutants"] = sorted(df["Pollutant"].dropna().unique().tolist())

    ctx["basin_analytics"] = _summarize_basins(basin_stats)
    ctx["pollution_hotspots"] = _summarize_hotspots(hotspots)
    ctx["forecast"] = _summarize_forecast(forecast)

    if risk_alerts:
        ctx["risk_summary"] = {
            "high_risk_pct": risk_alerts.get("high_risk_pct"),
            "moderate_risk_pct": risk_alerts.get("moderate_risk_pct"),
            "top_regions": (risk_alerts.get("top_regions") or [])[:5],
        }

    return ctx


def _match_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, re.I) for p in patterns)


def _detect_intent(message: str) -> str:
    """Priority-ordered intent — avoids 'risk' swallowing trend/region questions."""
    m = message.lower()
    if _match_any(m, [r"what is wqi", r"explain wqi", r"что такое wqi", r"wqi деген", r"wqi нет", r"wqi деген не"]):
        return "explain_wqi"
    if _match_any(m, [r"compare", r"сравни", r"салыстыр", r"vs\b", r"versus"]):
        return "compare_regions"
    if _match_any(m, [r"why.*risk", r"почему.*риск", r"неге.*тәуекел", r"why is"]):
        return "why_region"
    if _match_any(m, [r"cleanest", r"самый чист", r"ең таза", r"best region", r"лучший регион"]):
        return "cleanest"
    if _match_any(m, [r"\btrend\b", r"тренд", r"динамик", r"улучш", r"ухудш", r"improv", r"deterior", r"год к году",
                      r"жақсар", r"нашарла", r"динамика"]):
        return "trend"
    if _match_any(m, [
        r"which region.*risk", r"highest risk region", r"most high.risk", r"riskiest region",
        r"какой регион.*риск", r"самый рискован", r"больше всего.*риск", r"где больше.*риск",
        r"қай аудан.*тәуекел", r"жоғары тәуекел.*аудан", r"ауданда.*жоғары тәуекел",
    ]):
        return "risk_region"
    if _match_any(m, [r"priorit", r"actionable", r"комбинац", r"рекоменд", r"summarize.*3", r"три приоритет",
                      r"басымдық", r"ұсыныс", r"үш приоритет"]):
        return "priorities"
    if _match_any(m, [r"\bwqi\b", r"индекс", r"качеств", r"сапа", r"индекс"]):
        return "wqi"
    if _match_any(m, [r"\brisk\b", r"риск", r"опасн", r"threshold", r"порог", r"high.risk share", r"дол[яи]",
                      r"тәуекел", r"қауіп", r"порог"]):
        return "risk"
    if _match_any(m, [r"\bregion\b", r"регион", r"област", r"аудан", r"аймақ"]):
        return "region"
    if _match_any(m, [r"pollut", r"загрязн", r"nitrat", r"copper", r"нитрат", r"медь", r"ластауш"]):
        return "pollutant"
    if _match_any(m, [r"\bml\b", r"forecast", r"прогноз", r"model", r"модел", r"болжам"]):
        return "ml"
    if _match_any(m, [r"\bdata\b", r"dataset", r"источник", r"данн", r"source", r"observed", r"reconstructed",
                      r"дерек", r"көз", r"дереккөз"]):
        return "data"
    if _match_any(m, [r"\bhelp\b", r"что ты", r"что умеешь", r"помощь", r"help me",
                      r"көмек", r"не білесің", r"не айта"]):
        return "help"
    return "general"


def _subset_note(ctx: dict[str, Any], lang: str) -> str:
    if not ctx.get("using_chemical_subset"):
        return ""
    if lang == "ru":
        return " Анализ основан на химических показателях в текущей выборке."
    if lang == "kk":
        return " Талдау ағымдағы таңдаудағы химиялық көрсеткіштерге негізделген."
    return " Analysis uses chemical indicators in your current selection."


def _wqi_label(wqi: float | None, lang: str) -> str:
    if wqi is None:
        return "—"
    if lang == "ru":
        if wqi < 50:
            return "ниже нормы (хорошая ситуация)"
        if wqi <= 100:
            return "умеренное давление на экосистему"
        return "значительное загрязнение относительно ПДК"
    if lang == "kk":
        if wqi < 50:
            return "нормадан төмен (жақсы жағдай)"
        if wqi <= 100:
            return "орташа экологиялық қысым"
        return "ШРК-ға қатысты айтарлықтай ластану"
    if wqi < 50:
        return "below the regulatory threshold (favourable)"
    if wqi <= 100:
        return "moderate environmental pressure"
    return "significantly worse than the regulatory limit"


def _trend_phrase(direction: str | None, lang: str) -> str:
    mapping_en = {
        "deteriorating": "water quality is worsening over the selected period",
        "improving": "water quality is improving over the selected period",
        "stable": "water quality is broadly stable",
    }
    mapping_ru = {
        "deteriorating": "качество воды ухудшается в выбранном периоде",
        "improving": "качество воды улучшается в выбранном периоде",
        "stable": "качество воды в целом стабильно",
    }
    mapping_kk = {
        "deteriorating": "таңдалған кезеңде су сапасы нашарлап барады",
        "improving": "таңдалған кезеңде су сапасы жақсарып барады",
        "stable": "таңдалған кезеңде су сапасы тұрақты",
    }
    if lang == "ru":
        return mapping_ru.get(direction or "", "динамика неоднозначна")
    if lang == "kk":
        return mapping_kk.get(direction or "", "динамика анық емес")
    return mapping_en.get(direction or "", "the trend is unclear")


def _national_wqi(ctx: dict[str, Any]) -> float | None:
    wqi = ctx.get("mean_wqi")
    return float(wqi) if wqi is not None else None


def _rule_reply(message: str, ctx: dict[str, Any], lang: str) -> str | None:
    if ctx.get("empty"):
        return _pick(
            lang,
            "No data for the current filters. Try widening your selection.",
            "Нет данных для текущих фильтров. Расширьте выборку.",
            "Ағымдағы сүзгілер үшін деректер жоқ. Таңдауды кеңейтіңіз.",
        )

    intent = _detect_intent(message)
    n = ctx.get("records_chemical") or ctx["records"]
    note = _subset_note(ctx, lang)
    regions_in_msg = extract_regions(message, ctx.get("available_regions", []))
    year_q = extract_year(message)
    rs = ctx.get("region_stats", {})

    if intent == "explain_wqi":
        return _pick(
            lang,
            "**WQI** = (Concentration / MPC) × 50. Below 50 = cleaner than MPC; 50 = at limit; above 100 = >2× MPC (high risk). Lower is better.",
            "**WQI** = (Концентрация / ПДК) × 50. Ниже 50 — чище ПДК; 50 — на границе; выше 100 — >2× ПДК (высокий риск). Меньше = лучше.",
            "**WQI** = (Концентрация / ШРК) × 50. 50-ден төмен — таза; 50 — шекте; 100-ден жоғары — жоғары тәуекел. Төмен = жақсы.",
        )

    if intent == "compare_regions" and len(regions_in_msg) >= 2:
        a, b = regions_in_msg[0], regions_in_msg[1]
        sa, sb = rs.get(a, {}), rs.get(b, {})
        if sa and sb:
            wqi_a, wqi_b = sa.get("mean_wqi"), sb.get("mean_wqi")
            return _pick(
                lang,
                f"**{a}** shows {_wqi_label(wqi_a, lang)}, while **{b}** shows {_wqi_label(wqi_b, lang)}. "
                f"**{a}** has **{sa.get('high_risk', 0)}** critical exceedances vs **{sb.get('high_risk', 0)}** in **{b}**.{note}",
                f"**{a}** — {_wqi_label(wqi_a, lang)}, **{b}** — {_wqi_label(wqi_b, lang)}. "
                f"Критических превышений: **{sa.get('high_risk', 0)}** в **{a}** и **{sb.get('high_risk', 0)}** в **{b}**.{note}",
                f"**{a}** — {_wqi_label(wqi_a, lang)}, **{b}** — {_wqi_label(wqi_b, lang)}. "
                f"Шектеуден асу: **{a}** — **{sa.get('high_risk', 0)}**, **{b}** — **{sb.get('high_risk', 0)}**.{note}",
            )

    if intent == "why_region" and regions_in_msg:
        reg = regions_in_msg[0]
        st = rs.get(reg, {})
        wp = ctx.get("worst_pollutant", "—")
        nat = _national_wqi(ctx)
        wqi = st.get("mean_wqi")
        if st:
            vs_nat = ""
            if nat is not None and wqi is not None:
                if wqi > nat + 5:
                    vs_nat = _pick(
                        lang,
                        " Water quality here is worse than the national average in this view.",
                        " Качество воды здесь хуже среднего по стране в текущей выборке.",
                        " Бұл ауданда су сапасы ағымдағы көруде республика орташа көрсеткішінен нашар.",
                    )
                elif wqi < nat - 5:
                    vs_nat = _pick(
                        lang,
                        " This region performs better than the national average in this view.",
                        " Этот регион лучше среднего по стране в текущей выборке.",
                        " Бұл аудан ағымдағы көруде республика орташа көрсеткішінен жақсы.",
                    )
            return _pick(
                lang,
                f"**{reg}** faces elevated environmental pressure in the current selection.{vs_nat} "
                f"**{wp}** is the dominant pollutant, with **{st.get('high_risk', 0)}** critical exceedances recorded.{note}",
                f"**{reg}** испытывает повышенное экологическое давление в текущей выборке.{vs_nat} "
                f"Доминирует **{wp}**, зафиксировано **{st.get('high_risk', 0)}** критических превышений.{note}",
                f"**{reg}** ағымдағы таңдауда жоғары экологиялық қысымға тап болуда.{vs_nat} "
                f"**{wp}** басым ластаушы, **{st.get('high_risk', 0)}** шектеуден асу тіркелген.{note}",
            )

    if intent == "cleanest":
        best = ctx.get("best_wqi_region", "—")
        worst = ctx.get("worst_wqi_region", "—")
        return _pick(
            lang,
            f"**{best}** has the most favourable conditions in your selection. "
            f"**{worst}** currently shows the highest environmental pressure.{note}",
            f"**{best}** — наиболее благоприятная ситуация в выборке. "
            f"**{worst}** испытывает наибольшее экологическое давление.{note}",
            f"**{best}** — таңдаудағы ең қолайлы жағдай. "
            f"**{worst}** — ең жоғары экологиялық қысым.{note}",
        )

    if regions_in_msg and intent in ("trend", "region", "general", "wqi"):
        reg = regions_in_msg[0]
        st = rs.get(reg, {})
        if st:
            yr_note = f" ({year_q})" if year_q else ""
            return _pick(
                lang,
                f"**{reg}**{yr_note} shows {_wqi_label(st.get('mean_wqi'), lang)}. "
                f"**{ctx.get('worst_pollutant', '—')}** is the main concern, with **{st.get('high_risk', 0)}** critical exceedances.{note}",
                f"**{reg}**{yr_note}: {_wqi_label(st.get('mean_wqi'), lang)}. "
                f"Основная проблема — **{ctx.get('worst_pollutant', '—')}**, **{st.get('high_risk', 0)}** критических превышений.{note}",
                f"**{reg}**{yr_note}: {_wqi_label(st.get('mean_wqi'), lang)}. "
                f"Негізгі мәселе — **{ctx.get('worst_pollutant', '—')}**, **{st.get('high_risk', 0)}** шектеуден асу.{note}",
            )

    if intent == "help":
        return _pick(
            lang,
            f"I answer using **chemical pollution** indicators for your current filters.{note}",
            f"Я отвечаю по **химическим показателям** загрязнения (WQI, риск, регионы, тренды) "
            f"на основе текущих фильтров.{note}",
            f"Мен ағымдағы сүзгілер бойынша **химиялық ластану** көрсеткіштері (WQI, тәуекел, аудандар, тренд) "
            f"бойынша жауап беремін.{note}",
        )

    if intent == "trend":
        direction = ctx.get("trend_direction")
        delta = ctx.get("wqi_trend_delta")
        yr = ctx.get("year_range", [])
        if direction and delta is not None and len(yr) == 2:
            phrase = _trend_phrase(direction, lang)
            return _pick(
                lang,
                f"In your selection, {phrase} between **{yr[0]}** and **{yr[1]}** "
                f"(overall index shift {delta:+.1f} points).{note}",
                f"В вашей выборке {phrase} с **{yr[0]}** по **{yr[1]}** "
                f"(изменение индекса {delta:+.1f} пунктов).{note}",
                f"Сіздің таңдауыңызда **{yr[0]}**–**{yr[1]}** аралығында {phrase} "
                f"(индекс {delta:+.1f} пунктқа өзгерген).{note}",
            )
        return _pick(
            lang,
            f"Not enough years in the current selection to assess a clear trend.{note}",
            f"Недостаточно лет в выборке для оценки тренда.{note}",
            f"Анық тренд бағалау үшін таңдаудағы жылдар жеткіліксіз.{note}",
        )

    if intent == "risk_region":
        leader = ctx.get("high_risk_leader_region")
        count = ctx.get("high_risk_leader_count", 0)
        mean_r = ctx.get("top_mean_ratio_region")
        if leader:
            extra = ""
            if mean_r and mean_r != leader:
                extra = _pick(
                    lang,
                    f" **{mean_r}** shows the highest average concentration relative to limits — a different measure of pressure.",
                    f" **{mean_r}** имеет наибольшее среднее превышение относительно ПДК — другой показатель давления.",
                    f" **{mean_r}** — орташа концентрация бойынша ең жоғары қысым (басқа метрика).",
                )
            return _pick(
                lang,
                f"**{leader}** concentrates the most critical pollution events in your selection "
                f"(**{count}** exceedances above twice the regulatory limit).{extra}{note}",
                f"**{leader}** — больше всего критических превышений в выборке "
                f"(**{count}** случаев выше двойного ПДК).{extra}{note}",
                f"**{leader}** — таңдаудағы ең көп шектеуден асу "
                f"(**{count}** екі есе ШРК-дан жоғары).{extra}{note}",
            )
        return _pick(
            lang,
            f"No critical exceedances (above twice the regulatory limit) appear in the current selection.{note}",
            f"В текущей выборке нет критических превышений (выше двойного ПДК).{note}",
            f"Ағымдағы таңдауда шектеуден екі есе асатын критикалық жағдайлар жоқ.{note}",
        )

    if intent == "wqi":
        worst = ctx.get("worst_wqi_region", "—")
        best = ctx.get("best_wqi_region", "—")
        return _pick(
            lang,
            f"Overall water quality in your selection reflects {_wqi_label(ctx.get('mean_wqi'), lang)}. "
            f"**{worst}** faces the highest pressure; **{best}** is in the best condition.{note}",
            f"Общая картина в выборке: {_wqi_label(ctx.get('mean_wqi'), lang)}. "
            f"Наибольшее давление — **{worst}**, лучшая ситуация — **{best}**.{note}",
            f"Таңдаудағы жалпы жағдай: {_wqi_label(ctx.get('mean_wqi'), lang)}. "
            f"Ең жоғары қысым — **{worst}**, ең қолайлы — **{best}**.{note}",
        )

    if intent == "risk":
        leader = ctx.get("high_risk_leader_region", "—")
        return _pick(
            lang,
            f"**{ctx['high_risk_pct']}%** of records show critical exceedances (above twice the limit), "
            f"and **{ctx['moderate_risk_pct']}%** are in the moderate range. "
            f"**{leader}** needs the closest attention.{note}",
            f"**{ctx['high_risk_pct']}%** записей — критические превышения, "
            f"**{ctx['moderate_risk_pct']}%** — умеренный риск. "
            f"Приоритет мониторинга — **{leader}**.{note}",
            f"**{ctx['high_risk_pct']}%** жазба — критикалық асу, "
            f"**{ctx['moderate_risk_pct']}%** — орташа тәуекел. "
            f"**{leader}** — бақылау басымдығы.{note}",
        )

    if intent == "region":
        leader = ctx.get("high_risk_leader_region", "—")
        mean_r = ctx.get("top_mean_ratio_region", "—")
        worst = ctx.get("worst_wqi_region", "—")
        best = ctx.get("best_wqi_region", "—")
        return _pick(
            lang,
            f"**{leader}** has the most critical pollution events. "
            f"**{mean_r}** shows the strongest average concentration pressure. "
            f"Best overall conditions: **{best}**; highest pressure: **{worst}**.{note}",
            f"Больше всего критических случаев — **{leader}**. "
            f"Наибольшее среднее давление — **{mean_r}**. "
            f"Лучшие условия — **{best}**, наибольшее давление — **{worst}**.{note}",
            f"Ең көп критикалық жағдай — **{leader}**. "
            f"Орташа концентрация бойынша қысым — **{mean_r}**. "
            f"Ең қолайлы — **{best}**, ең нашар — **{worst}**.{note}",
        )

    if intent == "pollutant":
        wp = ctx.get("worst_pollutant", "—")
        return _pick(
            lang,
            f"**{wp}** is the dominant pollutant in your current selection and drives most of the environmental pressure.{note}",
            f"**{wp}** — главный загрязнитель в текущей выборке и основной источник экологического давления.{note}",
            f"**{wp}** — ағымдағы таңдауда басым ластаушы және экологиялық қысымның негізгі көзі.{note}",
        )

    if intent == "priorities":
        if ctx.get("observed_pct", 0) > 90:
            data_en = (
                f"3. **Data:** {ctx['observed_pct']}% is water-level (Kazhydromet); "
                "direct chemical sampling needed for regulatory conclusions."
            )
            data_ru = (
                f"3. **Данные:** {ctx['observed_pct']}% — уровень воды (Kazhydromet); "
                "для нормативных выводов нужны прямые хим. замеры."
            )
            data_kk = (
                f"3. **Деректер:** {ctx['observed_pct']}% — су деңгейі (Kazhydromet); "
                "нормативтік қорытынды үшін тікелей химиялық өлшеу керек."
            )
        else:
            data_en = "3. **Data:** expand observed chemical measurement coverage."
            data_ru = "3. **Данные:** расширить долю наблюдаемых химических измерений."
            data_kk = "3. **Деректер:** бақыланатын химиялық өлшеулерді кеңейту."
        return _pick(
            lang,
            "\n\n".join([
                f"1. **Region:** intensify monitoring in **{ctx.get('high_risk_leader_region', '—')}** (most high-risk records).",
                f"2. **Pollutant:** prioritize **{ctx.get('worst_pollutant', '—')}** (mean {ctx.get('worst_pollutant_ratio', '—')}× MPC).",
                data_en,
            ]) + note,
            "\n\n".join([
                f"1. **Регион:** усилить контроль в **{ctx.get('high_risk_leader_region', '—')}** (лидер по high-risk записям).",
                f"2. **Загрязнитель:** приоритет **{ctx.get('worst_pollutant', '—')}** (ср. {ctx.get('worst_pollutant_ratio', '—')}× ПДК).",
                data_ru,
            ]) + note,
            "\n\n".join([
                f"1. **Аудан:** **{ctx.get('high_risk_leader_region', '—')}** ауданында бақылауды күшейту (high-risk лидері).",
                f"2. **Ластаушы:** **{ctx.get('worst_pollutant', '—')}** басым (орт. {ctx.get('worst_pollutant_ratio', '—')}× ШРК).",
                data_kk,
            ]) + note,
        )

    if intent == "ml":
        return _pick(
            lang,
            "Open the **Forecast Lab** section: 8 models with TimeSeriesSplit CV. "
            "With n≈5 annual points, **Linear Regression** is most reliable.",
            "Раздел **Лаборатория прогноза**: 8 моделей, TimeSeriesSplit CV. "
            "При n≈5 годовых точек надёжнее **линейная регрессия**.",
            "**Болжам зертханасы** бөлімі: 8 модель, TimeSeriesSplit CV. "
            "n≈5 жылдық нүктеде **сызықты регрессия** сенімдірек.",
        )

    if intent == "data":
        mix = ctx.get("source_mix", {})
        mix_str = ", ".join(f"{k}: {v}%" for k, v in mix.items()) if mix else "—"
        hr_mix = ctx.get("high_risk_source_mix", {})
        hr_str = ", ".join(f"{k}: {v}%" for k, v in hr_mix.items()) if hr_mix else "—"
        return _pick(
            lang,
            f"Full selection: {mix_str}. High-risk records by source: {hr_str}. "
            f"Total {ctx['records_total']:,} records.{note}",
            f"Вся выборка: {mix_str}. High-risk записи по источникам: {hr_str}. "
            f"Всего {ctx['records_total']:,} записей.{note}",
            f"Барлық таңдау: {mix_str}. High-risk жазбалар көздер бойынша: {hr_str}. "
            f"Барлығы {ctx['records_total']:,} жазба.{note}",
        )

    return None


def _rule_reply_with_insights(message: str, ctx: dict[str, Any], insights: list[str], lang: str) -> str:
    specific = _rule_reply(message, ctx, lang)
    if specific:
        return specific

    skip = set(INSIGHT_DISCLAIMERS.values())
    chem_insights = [
        i for i in insights
        if i not in skip and "algorithmically" not in i.lower() and "алгоритм" not in i.lower()
    ][:2]
    if chem_insights:
        body = "\n\n".join(f"• {b.replace('**', '')}" for b in chem_insights)
        return _pick(
            lang,
            f"For your filters:\n\n{body}\n\nTry asking about: WQI, risk, region, trend, or priorities?",
            f"По текущим фильтрам:\n\n{body}\n\nУточните: WQI, риск, регион, тренд или приоритеты?",
            f"Ағымдағы сүзгілер бойынша:\n\n{body}\n\nСұраңыз: WQI, тәуекел, аудан, тренд немесе басымдықтар?",
        )

    worst = ctx.get("worst_wqi_region", "—")
    wp = ctx.get("worst_pollutant", "—")
    return _pick(
        lang,
        f"In your current view, water quality reflects {_wqi_label(ctx.get('mean_wqi'), lang)}. "
        f"**{worst}** faces the highest pressure and **{wp}** is the main pollutant of concern.",
        f"В текущей выборке — {_wqi_label(ctx.get('mean_wqi'), lang)}. "
        f"Наибольшее давление — **{worst}**, главный загрязнитель — **{wp}**.",
        f"Ағымдағы көруде — {_wqi_label(ctx.get('mean_wqi'), lang)}. "
        f"Ең жоғары қысым **{worst}** ауданында, басым ластаушы — **{wp}**.",
    )


def _ollama_system_prompt(lang: str) -> str:
    lang_name = {"en": "English", "ru": "Russian", "kk": "Kazakh (Cyrillic)"}.get(lang, "English")
    return (
        "You are the Environmental Intelligence Analyst for AquaMonitor — a Kazakhstan surface-water "
        "quality intelligence platform used by environmental officers and policymakers.\n\n"
        "Voice and style:\n"
        "- Write as a senior environmental analyst, not a generic chatbot.\n"
        "- Lead with the environmental finding, then supporting evidence from the context.\n"
        "- Use region, basin, pollutant, and trend language appropriate for policy briefings.\n"
        "- Prefer short paragraphs and bullet points when comparing regions or risks.\n"
        "- Do NOT say you are ChatGPT, an AI assistant, or a language model.\n\n"
        "Rules:\n"
        "- Use ONLY facts from the JSON analytics context (filters, WQI, trends, hotspots, forecast).\n"
        "- Higher WQI = worse pollution. Ratio > 2 = critical exceedance (high risk).\n"
        "- If data is empty for the filters, say so and suggest widening the selection.\n"
        "- Do not invent numbers, regions, or pollutants not present in the context.\n"
        "- This is analytical guidance, not regulatory or legal advice.\n"
        f"- Reply entirely in {lang_name}. Never switch language."
    )


def _format_context_for_prompt(ctx: dict[str, Any]) -> str:
    """Human-readable structured context block for the LLM."""
    import json

    lines = ["=== AquaMonitor Analytics Context ==="]
    filters = ctx.get("active_filters") or {}
    if filters:
        lines.append("Active filters:")
        for key in ("regions", "basins", "years", "pollutants", "sources"):
            val = filters.get(key)
            if val:
                lines.append(f"  - {key}: {val}")

    if ctx.get("empty"):
        lines.append("Dataset: no records match the current filters.")
    else:
        lines.append(f"Records: {ctx.get('records_total', 0)} total, {ctx.get('records_chemical', 0)} chemical")
        if ctx.get("mean_wqi") is not None:
            lines.append(f"Mean WQI: {ctx['mean_wqi']} | High-risk share: {ctx.get('high_risk_pct')}%")
        if ctx.get("worst_pollutant"):
            lines.append(
                f"Dominant pollutant: {ctx['worst_pollutant']} "
                f"(ratio {ctx.get('worst_pollutant_ratio', '—')}× MPC)"
            )
        if ctx.get("trend_direction"):
            yr = ctx.get("year_range", [])
            lines.append(
                f"Trend: {ctx['trend_direction']} (ΔWQI {ctx.get('wqi_trend_delta', '—')} "
                f"from {yr[0] if yr else '?'} to {yr[-1] if yr else '?'})"
            )
        if ctx.get("high_risk_leader_region"):
            lines.append(
                f"High-risk leader: {ctx['high_risk_leader_region']} "
                f"({ctx.get('high_risk_leader_count', 0)} critical exceedances)"
            )
        if ctx.get("best_wqi_region"):
            lines.append(
                f"Best WQI region: {ctx['best_wqi_region']} | "
                f"Worst: {ctx.get('worst_wqi_region')}"
            )

    hotspots = ctx.get("pollution_hotspots") or []
    if hotspots:
        lines.append("Pollution hotspots:")
        for h in hotspots[:3]:
            lines.append(
                f"  - {h.get('station')} ({h.get('basin')}): "
                f"intensity {h.get('intensity')}, status {h.get('status')}"
            )

    basins = ctx.get("basin_analytics") or []
    if basins:
        lines.append("Basin summary (top pressure):")
        for b in basins[:3]:
            lines.append(
                f"  - {b.get('basin')}: WQI {b.get('mean_wqi')}, "
                f"max ratio {b.get('max_ratio')}, trend Δ {b.get('trend_wqi_delta')}"
            )

    fc = ctx.get("forecast") or {}
    if fc.get("available"):
        lines.append(
            f"Forecast ({fc.get('target')}): {fc.get('recommended_model')} predicts "
            f"{fc.get('predicted_next')} for {fc.get('forecast_year')}"
        )
    elif fc:
        lines.append(f"Forecast: not available ({fc.get('reason', 'insufficient data')})")

    lines.append("\nFull JSON context:")
    lines.append(json.dumps(ctx, ensure_ascii=False, indent=2))
    return "\n".join(lines)


def _try_ollama(message: str, ctx: dict[str, Any], lang: str) -> tuple[str | None, str | None]:
    """Returns (reply_text, model_name)."""
    system = _ollama_system_prompt(lang)
    user = f"{_format_context_for_prompt(ctx)}\n\nUser question:\n{message}"
    return ollama_generate(system, user, lang=lang)


FALLBACK_NOTICE = "Ollama model unavailable"


def _dynamic_suggestions(ctx: dict[str, Any], lang: str) -> list[str]:
    base = _suggestions(lang)
    if ctx.get("empty"):
        return base[:3]
    extra: list[str] = []
    wr = ctx.get("worst_wqi_region")
    hr = ctx.get("high_risk_leader_region")
    if wr:
        extra.append(
            _pick(lang, f"Why is {wr} stressed?", f"Почему {wr} под нагрузкой?", f"Неге {wr} ауыр жағдайда?")
        )
    if hr:
        extra.append(
            _pick(lang, f"Explain risk in {hr}", f"Объясни риск в {hr}", f"{hr} тәуекелін түсіндір")
        )
    extra.append(
        _pick(lang, "Is water quality improving?", "Улучшается ли качество воды?", "Су сапасы жақсарып жатыр ма?")
    )
    return (extra + base)[:3]


def chat(
    message: str,
    df: pd.DataFrame,
    lang: str = "kk",
    *,
    filters: dict[str, Any] | None = None,
    hotspots: list[dict[str, Any]] | None = None,
    basin_stats: list[dict[str, Any]] | None = None,
    forecast: dict[str, Any] | None = None,
    risk_alerts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Answer a user message using Ollama + AquaMonitor context, with rule-based fallback."""
    message = (message or "").strip()
    if not message:
        empty_msg = _pick(
            lang,
            "Ask a question about water quality.",
            "Задайте вопрос о качестве воды.",
            "Су сапасы туралы сұрақ қойыңыз.",
        )
        return {
            "reply": empty_msg,
            "suggestions": _suggestions(lang),
            "confidence": "low",
            "source": "fallback",
            "model": None,
            "ollama_available": ollama_available(),
        }

    ctx = build_context(
        df,
        filters=filters,
        hotspots=hotspots,
        basin_stats=basin_stats,
        forecast=forecast,
        risk_alerts=risk_alerts,
    )
    chem = _chemical_df(df)
    insights = generate_insights(chem if not chem.empty else df, lang=lang) if not ctx.get("empty") else []
    suggestions = _dynamic_suggestions(ctx, lang)

    ollama_reply, model = _try_ollama(message, ctx, lang)
    if ollama_reply:
        reply = f"{ollama_reply}\n\n_{_disclaimer(lang)}_"
        return {
            "reply": reply,
            "suggestions": suggestions,
            "confidence": "high",
            "source": "ollama",
            "model": model,
            "ollama_available": True,
        }

    rule_body = _rule_reply_with_insights(message, ctx, insights, lang)
    reply = f"**{FALLBACK_NOTICE}**\n\n{rule_body}\n\n_{_disclaimer(lang)}_"
    return {
        "reply": reply,
        "suggestions": suggestions,
        "confidence": "high" if ctx.get("records") else "low",
        "source": "fallback",
        "model": None,
        "ollama_available": False,
    }
