"""Citizen-facing environmental narratives from filtered water quality data."""

from __future__ import annotations

import pandas as pd

from analytics.ai_insights import _chem, _pick, norm_lang
from analytics.public_facts import public_facts


def _wqi_band(wqi: float, lang: str) -> str:
    if wqi <= 25:
        return _pick(lang, "excellent", "отличное", "өте жақсы")
    if wqi <= 50:
        return _pick(lang, "good", "хорошее", "жақсы")
    if wqi <= 75:
        return _pick(lang, "moderate", "умеренное", "орташа")
    if wqi <= 100:
        return _pick(lang, "poor", "плохое", "нашар")
    return _pick(lang, "critical", "критическое", "сыни")


def generate_stories(df: pd.DataFrame, lang: str = "kk") -> dict:
    """Structured storytelling payload for the national platform UI."""
    lang = norm_lang(lang)
    facts = public_facts(df)
    if not facts or not facts.get("records"):
        return {
            "national_status": _pick(
                lang,
                "No monitoring records match your current view. Widen regions or years to explore Kazakhstan's waters.",
                "Нет записей для текущего выбора. Расширьте регионы или годы, чтобы исследовать воды Казахстана.",
                "Ағымдағы көрініс бойынша жазбалар жоқ. Қазақстан суын зерттеу үшін аудандарды немесе жылдарды кеңейтіңіз.",
            ),
            "pollution_story": "",
            "region_stories": {},
            "basin_highlights": [],
            "journey": [],
            "compare_teaser": "",
            "cleanest_region": None,
            "worst_region": None,
        }

    chem = _chem(df)
    base = chem if not chem.empty else df
    mean_wqi = float(base["WQI_Score"].mean()) if "WQI_Score" in base.columns else 0
    band = _wqi_band(mean_wqi, lang)

    cleanest = facts.get("cleanest_region", "—")
    clean_wqi = facts.get("cleanest_wqi", "—")
    worst = facts.get("most_polluted_region", "—")
    worst_wqi = facts.get("most_polluted_wqi", "—")
    pollutant = facts.get("dangerous_pollutant", "—")
    pratio = facts.get("dangerous_ratio", "—")
    within = facts.get("within_limits_pct", 0)
    hr_count = facts.get("high_risk_count", 0)
    delta = facts.get("trend_delta")
    y0 = facts.get("trend_year_from")
    y1 = facts.get("trend_year_to")

    trend_phrase = ""
    if delta is not None and y0 and y1:
        if delta > 0.5:
            trend_phrase = _pick(
                lang,
                f"Between {y0} and {y1}, national water quality shows signs of stress (WQI +{delta:.1f}).",
                f"С {y0} по {y1} качество воды демонстрирует признаки напряжения (WQI +{delta:.1f}).",
                f"{y0}–{y1} жылдары ұлттық су сапасы шамамен нашарлаған (WQI +{delta:.1f}).",
            )
        elif delta < -0.5:
            trend_phrase = _pick(
                lang,
                f"From {y0} to {y1}, conditions improved modestly (WQI {delta:.1f}).",
                f"С {y0} по {y1} показатели умеренно улучшились (WQI {delta:.1f}).",
                f"{y0}–{y1} аралығында жағдай жақсарған (WQI {delta:.1f}).",
            )
        else:
            trend_phrase = _pick(
                lang,
                f"Between {y0} and {y1}, national WQI remained relatively stable.",
                f"С {y0} по {y1} национальный WQI оставался относительно стабильным.",
                f"{y0}–{y1} жылдары ұлттық WQI салыстырмалы тұрақты болды.",
            )

    national_status = _pick(
        lang,
        f"Kazakhstan's monitored waters average in the **{band}** range. "
        f"**{cleanest}** maintains relatively calmer conditions (WQI {clean_wqi}), "
        f"while **{worst}** carries the heaviest burden (WQI {worst_wqi}). "
        f"{within}% of records stay within MPC limits. {trend_phrase}".strip(),
        f"Контролируемые воды Казахстана в среднем в категории **{band}**. "
        f"**{cleanest}** — относительно спокойнее (WQI {clean_wqi}), "
        f"**{worst}** — наибольшая нагрузка (WQI {worst_wqi}). "
        f"{within}% записей в пределах ПДК. {trend_phrase}".strip(),
        f"Қазақстанның бақыланатын сулары орташа **{band}** санатында. "
        f"**{cleanest}** — салыстырмалы тұрақты (WQI {clean_wqi}), "
        f"**{worst}** — ең ауыр жүктеме (WQI {worst_wqi}). "
        f"Жазбалардың {within}% ШРК шегінде. {trend_phrase}".strip(),
    )

    pollution_story = _pick(
        lang,
        f"**{pollutant}** leads pollution pressure at **{pratio}× MPC** on average. "
        f"**{hr_count:,}** high-risk readings (>2× MPC) appear in the current view — "
        f"these are the places where rivers and communities need the closest attention.",
        f"**{pollutant}** создаёт главное давление — в среднем **{pratio}× ПДК**. "
        f"**{hr_count:,}** записей высокого риска (>2× ПДК) в текущей выборке — "
        f"именно там рекам и сообществам нужен пристальный контроль.",
        f"**{pollutant}** ластану қысымының алдында — орташа **{pratio}× ШРК**. "
        f"Ағымдағы көріністе **{hr_count:,}** жоғары тәуекел жазбасы (>2× ШРК) — "
        f"өзендер мен елді мекендерге мұнда ерекше назар керек.",
    )

    region_stories: dict[str, str] = {}
    if "Region" in base.columns:
        for region, grp in base.groupby("Region"):
            rwqi = float(grp["WQI_Score"].mean())
            rratio = float(grp["Ratio"].mean())
            hr = int((grp["Ratio"] > 2).sum())
            rb = _wqi_band(rwqi, lang)
            region_stories[str(region)] = _pick(
                lang,
                f"**{region}**: {rb} water quality (WQI {rwqi:.1f}). "
                f"Average pollution {rratio:.2f}× MPC; {hr} high-risk records in view.",
                f"**{region}**: {rb} качество (WQI {rwqi:.1f}). "
                f"Среднее загрязнение {rratio:.2f}× ПДК; {hr} записей высокого риска.",
                f"**{region}**: {rb} сапа (WQI {rwqi:.1f}). "
                f"Орташа ластану {rratio:.2f}× ШРК; {hr} жоғары тәуекел жазбасы.",
            )

    basin_highlights: list[dict] = []
    if "Basin" in df.columns:
        for basin, grp in df.groupby("Basin"):
            if grp.empty:
                continue
            basin_highlights.append({
                "id": str(basin).lower().replace(" ", "-"),
                "name": str(basin),
                "records": int(len(grp)),
                "mean_wqi": round(float(grp["WQI_Score"].mean()), 1) if "WQI_Score" in grp.columns else None,
                "teaser": _pick(
                    lang,
                    f"The {basin} basin connects {int(len(grp)):,} observations across Kazakhstan's hydrography.",
                    f"Бассейн {basin} — {int(len(grp)):,} наблюдений в гидрографии Казахстана.",
                    f"{basin} бассейні — Қазақстан гидрографиясында {int(len(grp)):,} бақылау.",
                ),
            })

    journey = [
        {
            "id": "sources",
            "title": _pick(lang, "Where the data flows from", "Откуда приходят данные", "Деректер қайдан келеді"),
            "body": _pick(
                lang,
                "Kazhydromet river levels and chemical monitoring merge into one national picture.",
                "Уровни рек Казгидромета и химический мониторинг формируют единую национальную картину.",
                "Казгидромет өзен деңгейлері мен химиялық мониторинг бір ұлттық суретті құрайды.",
            ),
        },
        {
            "id": "pressure",
            "title": _pick(lang, "Pollution pressure", "Давление загрязнения", "Ластану қысымы"),
            "body": pollution_story,
        },
        {
            "id": "regions",
            "title": _pick(lang, "Regional contrast", "Контраст регионов", "Аймақтар контрасты"),
            "body": _pick(
                lang,
                f"From {cleanest} to {worst}, Kazakhstan's waters are not uniform — each oblast tells its own story.",
                f"От {cleanest} до {worst} воды Казахстана неоднородны — каждая область рассказывает свою историю.",
                f"{cleanest} мен {worst} арасында Қазақстан сулары біркелкі емес — әр облыс өз тарихын айтады.",
            ),
        },
        {
            "id": "future",
            "title": _pick(lang, "Looking ahead", "Взгляд вперёд", "Алға қарай"),
            "body": _pick(
                lang,
                "Forecast models project next-year WQI — explore the Forecast Lab with scientific caution on small samples.",
                "Модели прогнозируют WQI на следующий год — изучите лабораторию прогноза с учётом малых выборок.",
                "Болжам модельдері келесі жылдың WQI-сын болжайды — шағын таңдауда ғылыми сақтықпен зерттеңіз.",
            ),
        },
    ]

    compare_teaser = _pick(
        lang,
        "Compare any two regions and years to see how water quality shifted.",
        "Сравните два региона и года, чтобы увидеть сдвиг качества воды.",
        "Су сапасының өзгерісін көру үшін екі аудан мен жылды салыстырыңыз.",
    )

    return {
        "national_status": national_status,
        "pollution_story": pollution_story,
        "region_stories": region_stories,
        "basin_highlights": basin_highlights[:8],
        "journey": journey,
        "compare_teaser": compare_teaser,
        "cleanest_region": cleanest,
        "worst_region": worst,
    }
