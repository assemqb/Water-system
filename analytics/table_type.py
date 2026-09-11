"""
Split chemical-pollutant analytics by table_type (full_panel vs worst_parameter).

Kazhydromet's bulletins report chemical readings via two different table
layouts (see data/kazhydromet_bulletin_etl.py module docstring):

  - "full_panel": every tracked substance reported for a water body, whether
    or not it happens to be elevated that month — a representative snapshot.
  - "worst_parameter": only whichever substance(s) exceeded a class boundary
    that month is listed at all. This is a biased sample by construction —
    it never reports a "normal" reading — so a median or "share above MPC"
    computed over worst_parameter rows overstates typical pollution.

Primary statistics (median WQI, share above MPC) should be computed on
full_panel data only; worst_parameter rows are shown as a separate
"exceedances reported" view, not blended into the headline numbers.

`table_type` is only populated for `data_source == "observed_chemical"`
rows; water-level and reference rows have no value there and are left
untouched by `restrict_to_full_panel` (excluded only by `only_worst_parameter`).
"""

from __future__ import annotations

import pandas as pd


def restrict_to_full_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Default view: everything except rows explicitly typed worst_parameter."""
    if "table_type" not in df.columns:
        return df
    return df[df["table_type"].fillna("") != "worst_parameter"]


def only_worst_parameter(df: pd.DataFrame) -> pd.DataFrame:
    """worst_parameter-only view, shown separately rather than blended in."""
    if "table_type" not in df.columns:
        return df.iloc[0:0]
    return df[df["table_type"].fillna("") == "worst_parameter"]


def only_full_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Strictly full_panel chemical rows only (excludes water-level/reference
    rows too, unlike restrict_to_full_panel which keeps them as untouched)."""
    if "table_type" not in df.columns:
        return df.iloc[0:0]
    return df[df["table_type"].fillna("") == "full_panel"]
