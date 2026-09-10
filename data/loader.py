"""Data loading for the dashboard and analytics pipeline."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from config.logging_config import get_logger
from config.settings import DATA_PATH, LEGACY_DATASET_PATH, MASTER_DATASET_PATH

logger = get_logger(__name__)


def load_raw_csv(path: Path | None = None) -> pd.DataFrame:
    """
    Load the master water quality CSV.

    Falls back to legacy dataset if master has not been built yet.
    """
    path = path or DATA_PATH
    if not path.exists():
        logger.warning("Master dataset missing, falling back to legacy: %s", LEGACY_DATASET_PATH)
        path = LEGACY_DATASET_PATH
    if not path.exists():
        raise FileNotFoundError(f"No dataset found at {path}")

    df = pd.read_csv(path)
    logger.info("Loaded %d rows from %s", len(df), path.name)
    return df


def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derive Year, Ratio, and ensure data_source column exists.

    If Ratio/WQI are missing (legacy file), they are recomputed downstream
    by the validator/build step; here we only add derived temporal fields.
    """
    out = df.copy()
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out["Year"] = out["Date"].dt.year

    if "Ratio" not in out.columns and {"Concentration", "MPC"}.issubset(out.columns):
        out["Ratio"] = np.where(out["MPC"] > 0, out["Concentration"] / out["MPC"], np.nan)

    if "data_source" not in out.columns:
        out["data_source"] = "unknown"
        logger.warning("data_source column missing — defaulting to 'unknown'")

    if "Risk_Level" not in out.columns and "Ratio" in out.columns:
        from analytics.hazard import classify_risk_level

        out["Risk_Level"] = out["Ratio"].apply(classify_risk_level)

    return out


def load_enriched(path: Path | None = None) -> pd.DataFrame:
    """Load and enrich dataset for dashboard use."""
    df = load_raw_csv(path)
    enriched = enrich_dataframe(df)
    logger.info("Enriched dataset: %d rows after date filter", len(enriched))
    return enriched


def data_quality_summary(df: pd.DataFrame) -> dict:
    """Return provenance fractions for the data quality panel."""
    total = len(df)
    if total == 0 or "data_source" not in df.columns:
        return {"total": 0, "sources": {}}
    counts = df["data_source"].value_counts(normalize=True).mul(100).round(1)
    return {
        "total": total,
        "sources": counts.to_dict(),
        "observed_pct": float(counts.get("observed", 0)),
        "observed_chemical_pct": float(counts.get("observed_chemical", 0)),
        "reference_pct": float(counts.get("reference", 0)),
    }
