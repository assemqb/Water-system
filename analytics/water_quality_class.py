"""
River water quality classification analytics (Order No. 111-НҚ, 2025-06-04).

`water_quality_class` (see config.settings.classify_water_quality and
data/kazhydromet_bulletin_etl.py:is_wqc_eligible) is populated ONLY for
rivers, canals, and channel reservoirs — blank for seas/lakes, which the
order's own scope note excludes. Filtering on "class is not null" is
therefore sufficient scoping on its own; no separate exclude_lakes() call
is needed here (a channel reservoir carries a class despite
water_body_type=="lake" for the unrelated L7 concern — see
is_wqc_eligible's docstring).
"""

from __future__ import annotations

import pandas as pd

CLASS_NUMBERS = (1, 2, 3, 4, 5, 6)
POOR_CLASSES = (5, 6)  # "жоғары ластанған" / "өте жоғары ластанған" — reported as the exceedance signal


def _eligible(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "water_quality_class" not in df.columns:
        return df.iloc[0:0]
    return df[df["water_quality_class"].notna()]


def class_distribution(df: pd.DataFrame) -> dict:
    """Primary river metric: how many measurements fall in each class
    (1-6), and the worst (highest-numbered) class observed. Empty/None
    fields when there is no classifiable data in the current filter."""
    scoped = _eligible(df)
    if scoped.empty:
        return {"records": 0, "class_counts": {n: 0 for n in CLASS_NUMBERS}, "worst_class": None}
    counts = scoped["water_quality_class"].astype(int).value_counts()
    return {
        "records": int(len(scoped)),
        "class_counts": {n: int(counts.get(n, 0)) for n in CLASS_NUMBERS},
        "worst_class": int(scoped["water_quality_class"].max()),
    }


def class_distribution_by_basin(df: pd.DataFrame) -> list[dict]:
    """Same as class_distribution, broken out per basin — used for the
    corpus-wide summary report, not currently wired into a UI panel."""
    scoped = _eligible(df)
    if scoped.empty or "Basin" not in scoped.columns:
        return []
    rows: list[dict] = []
    for basin, grp in scoped.groupby("Basin"):
        counts = grp["water_quality_class"].astype(int).value_counts()
        rows.append({
            "basin": str(basin),
            "records": int(len(grp)),
            "class_counts": {n: int(counts.get(n, 0)) for n in CLASS_NUMBERS},
            "worst_class": int(grp["water_quality_class"].max()),
        })
    rows.sort(key=lambda r: r["basin"])
    return rows


def class_exceedance_catalog(df: pd.DataFrame) -> list[dict]:
    """Per river/canal/reservoir + pollutant: the worst class ever recorded,
    and in how many distinct bulletins a poor class (5 or 6 — "high" or
    "extremely high" pollution) was reported. Replaces the earlier MPC-
    ratio-based catalog (max_ratio/months_exceeded) now that the class is
    the primary assessment; MPC ratio remains available at the row level
    for anyone who wants it (see dashboard_service._kpi_for's mean_ratio).
    """
    scoped = _eligible(df)
    if scoped.empty or "water_body" not in scoped.columns or "Pollutant" not in scoped.columns:
        return []
    scoped = scoped[scoped["water_body"].fillna("") != ""].copy()
    if "suspected_source_error" in scoped.columns:
        # See dashboard_service.exceedance_catalog's prior docstring — a
        # reading flagged as probably transposed in the source PDF itself
        # is kept in the dataset unmodified but must not read as a real
        # worst-class spike here.
        flagged = scoped["suspected_source_error"].fillna(False).astype(bool)
        scoped = scoped[~flagged]
    if scoped.empty:
        return []

    rows: list[dict] = []
    for (water_body, pollutant), grp in scoped.groupby(["water_body", "Pollutant"]):
        poor = grp[grp["water_quality_class"].isin(POOR_CLASSES)]
        bulletins_5_6 = (
            poor["source_bulletin"].nunique() if "source_bulletin" in poor.columns else int(len(poor))
        )
        rows.append({
            "water_body": str(water_body),
            "pollutant": str(pollutant),
            "basin": str(grp["Basin"].mode().iloc[0]) if "Basin" in grp.columns and len(grp["Basin"].dropna()) else None,
            "worst_class": int(grp["water_quality_class"].max()),
            "bulletins_5_6": int(bulletins_5_6),
            "bulletins_observed": (
                int(grp["source_bulletin"].nunique()) if "source_bulletin" in grp.columns else int(len(grp))
            ),
        })
    rows.sort(key=lambda r: (r["worst_class"], r["bulletins_5_6"]), reverse=True)
    return rows
