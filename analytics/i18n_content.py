"""Localized copy for insights, meta, and narratives."""

from __future__ import annotations

META_BANNERS = {
    "en": "Open environmental data · Kazhydromet + chemical monitoring · SanPiN / MPC standards",
    "ru": "Открытые экоданные · Казгидромет + химический мониторинг · SanPiN / ПДК",
    "kk": "Ашық экожүйе деректері · Казгидромет + химиялық мониторинг · SanPiN / ШРК",
}

INSIGHT_DISCLAIMERS = {
    "en": "Insights are generated from your current filter selection. Not regulatory advice.",
    "ru": "Выводы сформированы по текущим фильтрам. Не нормативная рекомендация.",
    "kk": "Қорытындылар ағымдағы сүзгілер бойынша жасалған. Нормативтік ұсыныс емес.",
}

ML_DISCLAIMERS = {
    "en": "Annual sample size is small (n≈5). Prefer cross-validation and linear regression for trends.",
    "ru": "Малый годовой объём (n≈5). Для трендов надёжнее кросс-валидация и линейная регрессия.",
    "kk": "Жылдық выборка кіші (n≈5). Тренд үшін CV және сызықты регрессия сенімдірек.",
}

WHY_NOT_DL = {
    "en": "Deep learning needs n≥50 temporal points; with n≈5 annual means, simpler models are safer.",
    "ru": "Deep learning требует n≥50; при n≈5 годовых точек проще модели надёжнее.",
    "kk": "Deep learning n≥50 керек; n≈5 жылдық нүктеде қарапайым модельдер қауіпсізірек.",
}

LIMITATIONS_I18N = {
    "en": [
        "L1: Annual ML forecasting uses limited yearly aggregates (n≈5).",
        "L2: Chemical records are real measurements from official Kazhydromet monthly bulletins (2025).",
        "L3: Water-level data reflects hydrology, not chemical concentration.",
        "L4: International reference data is for methodology only.",
        "L5: Tree models overfit on small n; linear regression is primary for trends.",
        "L6: WQI uses MPC-anchored sub-indices (SanPiN fishery standards).",
    ],
    "ru": [
        "L1: Годовой ML-прогноз ограничен малым числом лет (n≈5).",
        "L2: Химические данные — реальные замеры из официальных ежемесячных бюллетеней Казгидромета (2025).",
        "L3: Уровень воды отражает гидрологию, не химию.",
        "L4: Международные данные — только для методологии.",
        "L5: Деревья переобучаются на малом n; для трендов — линейная регрессия.",
        "L6: WQI основан на суб-индексах относительно ПДК (SanPiN).",
    ],
    "kk": [
        "L1: Жылдық ML болжамы шектеулі (n≈5).",
        "L2: Химиялық деректер — Қазгидромет бюллетеньдерінен алынған нақты өлшемдер (2025).",
        "L3: Су деңгейі — гидрология, химия емес.",
        "L4: Халықаралық деректер — тек методология.",
        "L5: Ағаш модельдері кіші n-де артық оқиды; тренд — сызықты регрессия.",
        "L6: WQI ШРК-ға байланған суб-индекстер (SanPiN).",
    ],
}

CHART_LABELS = {
    "en": {
        "year": "Year",
        "wqi": "WQI Score",
        "region": "Region",
        "pollutant": "Pollutant",
        "mean_wqi": "Mean WQI",
        "ratio": "Ratio (C/MPC)",
        "wqi_delta": "Δ WQI (last − first year)",
        "improving": "Improving",
        "deteriorating": "Deteriorating",
        "map_hover": "WQI",
    },
    "ru": {
        "year": "Год",
        "wqi": "WQI",
        "region": "Регион",
        "pollutant": "Загрязнитель",
        "mean_wqi": "Ср. WQI",
        "ratio": "Отношение (C/ПДК)",
        "wqi_delta": "Δ WQI (посл. − перв. год)",
        "improving": "Улучшение",
        "deteriorating": "Ухудшение",
        "map_hover": "WQI",
    },
    "kk": {
        "year": "Жыл",
        "wqi": "WQI",
        "region": "Аудан",
        "pollutant": "Ластаушы",
        "mean_wqi": "Орт. WQI",
        "ratio": "Қатынас (C/ШРК)",
        "wqi_delta": "Δ WQI (соңғы − бірінші жыл)",
        "improving": "Жақсару",
        "deteriorating": "Нашарлау",
        "map_hover": "WQI",
    },
}


LAKE_CLASS_NOTE = {
    "en": (
        "Water quality classes (Order No. 111-НҚ, 2025-06-04) do not apply to seas and lakes "
        "— the order's own scope note names the Caspian, Aral, and Balkhash explicitly. "
        "Lake figures below are MPC ratio and WQI only."
    ),
    "ru": (
        "Классы качества воды (приказ №111-НҚ от 04.06.2025) не распространяются на моря и озёра "
        "— это прямо указано в примечании к приказу (Каспийское, Аральское, Балхаш названы явно). "
        "Для озёр ниже показаны только кратность ПДК и WQI."
    ),
    "kk": (
        "Су сапасының кластары (04.06.2025 жылғы №111-НҚ бұйрығы) теңіздер мен көлдерге "
        "қолданылмайды — бұл бұйрықтың өз ескертпесінде тікелей көрсетілген (Каспий, Арал, Балқаш "
        "нақты аталған). Көлдер үшін төменде тек ШРК еселігі мен WQI көрсетілген."
    ),
}


def chart_labels(lang: str) -> dict[str, str]:
    return CHART_LABELS.get(norm_lang(lang), CHART_LABELS["en"])


def norm_lang(lang: str) -> str:
    return lang if lang in ("en", "ru", "kk") else "en"
