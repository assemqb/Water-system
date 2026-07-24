"""Short localized interpretations for dashboard charts."""

from __future__ import annotations

import pandas as pd

from analytics.ai_insights import _chem, _pick, norm_lang


def chart_narratives(df: pd.DataFrame, lang: str = "en") -> dict[str, str]:
    lang = norm_lang(lang)
    if df.empty:
        return {}

    chem = _chem(df)
    base = chem if not chem.empty else df
    out: dict[str, str] = {}

    if "Region" in base.columns and "WQI_Score" in base.columns:
        reg = base.groupby("Region")["WQI_Score"].mean().sort_values(ascending=False)
        if len(reg) >= 1:
            worst, wv = reg.index[0], reg.iloc[0]
            best, bv = reg.index[-1], reg.iloc[-1]
            out["map"] = _pick(
                lang,
                f"{worst} has the highest mean WQI ({wv:.1f}) — focus monitoring there. {best} is lowest ({bv:.1f}).",
                f"{worst} — максимальный WQI ({wv:.1f}). {best} — минимальный ({bv:.1f}).",
                f"{worst} — ең жоғары WQI ({wv:.1f}). {best} — ең төмен ({bv:.1f}).",
            )

    if "Year" in base.columns and "WQI_Score" in base.columns:
        yearly = base.groupby("Year")["WQI_Score"].mean().dropna().sort_index()
        if len(yearly) >= 2:
            d = yearly.iloc[-1] - yearly.iloc[0]
            word = _pick(lang, "worsened" if d > 0 else "improved", "ухудшилось" if d > 0 else "улучшилось", "нашарлады" if d > 0 else "жақсарды")
            out["trend"] = _pick(
                lang,
                f"Mean WQI {word} by {abs(d):.1f} points from {int(yearly.index[0])} to {int(yearly.index[-1])}.",
                f"Средний WQI {word} на {abs(d):.1f} с {int(yearly.index[0])} по {int(yearly.index[-1])}.",
                f"Орташа WQI {int(yearly.index[0])}–{int(yearly.index[-1])} аралығында {abs(d):.1f}-ге {word}.",
            )

    if "Pollutant" in base.columns and "Ratio" in base.columns:
        p = base.groupby("Pollutant")["Ratio"].mean().sort_values(ascending=False)
        if not p.empty:
            out["heatmap"] = _pick(
                lang,
                f"{p.index[0]} exceeds other pollutants on average ({p.iloc[0]:.2f}× MPC).",
                f"{p.index[0]} опережает другие загрязнители (ср. {p.iloc[0]:.2f}× ПДК).",
                f"{p.index[0]} орташа {p.iloc[0]:.2f}× ШРК — басқа ластаушылардан жоғары.",
            )

    if "Region" in base.columns and "Year" in base.columns and "WQI_Score" in base.columns:
        deltas = []
        for region, grp in base.groupby("Region"):
            yearly = grp.groupby("Year")["WQI_Score"].mean().dropna().sort_index()
            if len(yearly) >= 2:
                deltas.append(abs(float(yearly.iloc[-1] - yearly.iloc[0])))
        if deltas:
            mx = max(deltas)
            out["yoy"] = _pick(
                lang,
                f"Regional WQI shifts reach up to {mx:.1f} points between first and last year in filter.",
                f"По регионам WQI меняется до {mx:.1f} пунктов между первым и последним годом фильтра.",
                f"Аудандар бойынша WQI сүзгідегі бірінші мен соңғы жыл арасында {mx:.1f}-ге дейін өзгереді.",
            )

    return out
