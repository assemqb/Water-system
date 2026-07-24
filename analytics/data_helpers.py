"""Shared dataframe helpers for analytics text modules."""

from __future__ import annotations

import pandas as pd

NON_CHEMICAL = {"Water_Level_cm", "Mixed_Chemicals"}


def _chem(df: pd.DataFrame) -> pd.DataFrame:
    if "Pollutant" not in df.columns:
        return df
    return df[~df["Pollutant"].isin(NON_CHEMICAL)]


def _pick(lang: str, en: str, ru: str, kk: str) -> str:
    if lang == "ru":
        return ru
    if lang == "kk":
        return kk
    return en
