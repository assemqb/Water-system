"""
Split chemical-pollutant analytics by water_body_type (river vs lake).

Naturally saline lakes (Alakol, Balkhash, Tengiz, ...) show very high
Sulfates ratios that reflect geology, not anthropogenic pollution — see
README section 6/7 and limitation L7. Blending them into a single
region/basin ranking or KPI would misrepresent lake-adjacent regions as more
polluted than they are. Default analytics therefore exclude lake rows;
callers that want the lake-specific picture use `only_lakes`.

`water_body_type` is only populated for `data_source == "observed_chemical"`
rows (data/kazhydromet_bulletin_etl.py); water-level and reference rows have
no value there and are left untouched by both functions below.
"""

from __future__ import annotations

import pandas as pd


def exclude_lakes(df: pd.DataFrame) -> pd.DataFrame:
    """Default view: everything except rows explicitly typed as a lake."""
    if "water_body_type" not in df.columns:
        return df
    return df[df["water_body_type"].fillna("") != "lake"]


def only_lakes(df: pd.DataFrame) -> pd.DataFrame:
    """Lake-specific view, shown separately rather than blended in."""
    if "water_body_type" not in df.columns:
        return df.iloc[0:0]
    return df[df["water_body_type"].fillna("") == "lake"]
