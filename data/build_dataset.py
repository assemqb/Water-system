"""
Build the unified Kazakhstan water quality master dataset.

Sources:
  1. Kazhydromet basin CSVs (observed water levels)
  2. Kazhydromet monthly environmental bulletins (real observed chemical
     records, extracted by data/kazhydromet_bulletin_etl.py)
  3. Kaggle Water Potability (international reference)

Run: python -m data.build_dataset
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from analytics.hazard import classify_risk_code, classify_risk_level, pollutant_hazard_class
from analytics.wqi import (
    compute_pollution_ratio,
    compute_pollution_wqi,
    compute_potability_ratio,
    compute_potability_wqi,
    compute_water_level_ratio,
    compute_water_level_wqi,
)
from config.logging_config import get_logger
from config.settings import (
    BASIN_FILES,
    MASTER_DATASET_PATH,
    POLLUTANTS,
    REAL_POLLUTION_PATHS,
    SQLITE_PATH,
    STATION_MAP,
    WATER_POTABILITY_PATH,
)

logger = get_logger(__name__)

MASTER_COLUMNS = [
    "ID",
    "Date",
    "Basin",
    "Region",
    "Pollutant",
    "Concentration",
    "MPC",
    "WQI_Score",
    "Hazard_Class",
    "Ratio",
    "Risk_Level",
    "data_source",
    "country",
    "station_code",
    "description",
    "water_body",
    "water_body_type",
    "table_type",
    "below_detection",
    "exceeds_plausible",
    "suspected_source_error",
]


def _load_kazhydromet_basins() -> pd.DataFrame:
    """Load real Kazhydromet water-level observations."""
    frames: list[pd.DataFrame] = []
    for key, path in BASIN_FILES.items():
        if not path.exists():
            logger.warning("Basin file not found: %s — skipping", path)
            continue
        raw = pd.read_csv(path)
        raw["Значение"] = pd.to_numeric(raw["Значение"], errors="coerce")
        raw["Дата"] = pd.to_datetime(raw["Дата"], errors="coerce")
        rows: list[dict] = []
        for _, row in raw.iterrows():
            station = int(row["Код поста"])
            basin, region, desc = STATION_MAP.get(station, ("Unknown", "Unknown", ""))
            value = row["Значение"]
            ratio = compute_water_level_ratio(value, basin)
            wqi = compute_water_level_wqi(value, basin)
            rows.append(
                {
                    "Date": row["Дата"],
                    "Basin": basin,
                    "Region": region,
                    "Pollutant": "Water_Level_cm",
                    "Concentration": value,
                    "MPC": np.nan,
                    "WQI_Score": wqi,
                    "Hazard_Class": classify_risk_code(ratio),
                    "Ratio": ratio,
                    "Risk_Level": classify_risk_level(ratio),
                    "data_source": "observed",
                    "country": "Kazakhstan",
                    "station_code": station,
                    "description": desc,
                }
            )
        df_basin = pd.DataFrame(rows)
        frames.append(df_basin)
        logger.info("Loaded %s: %d rows", key, len(df_basin))
    if not frames:
        return pd.DataFrame(columns=MASTER_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def _load_real_pollution() -> pd.DataFrame:
    """Load real Kazhydromet chemical measurements (official monthly bulletins, all years)."""
    if not REAL_POLLUTION_PATHS:
        logger.warning(
            "No real pollution dataset found in db/ — run "
            "`python3 -m data.kazhydromet_bulletin_etl --year <year>` to build one"
        )
        return pd.DataFrame(columns=MASTER_COLUMNS)

    raw = pd.concat([pd.read_csv(p) for p in REAL_POLLUTION_PATHS], ignore_index=True)
    raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce")
    rows: list[dict] = []
    for _, row in raw.iterrows():
        pollutant = str(row["Pollutant"])
        conc = float(row["Concentration"])
        mpc = float(row["MPC"])
        spec = POLLUTANTS.get(pollutant)
        if spec and spec.mpc != mpc:
            logger.warning("MPC mismatch for %s: file=%s config=%s", pollutant, mpc, spec.mpc)
        ratio = compute_pollution_ratio(conc, mpc)
        wqi = compute_pollution_wqi(conc, mpc)
        hazard = pollutant_hazard_class(pollutant) or int(row.get("Hazard_Class", 0))
        rows.append(
            {
                "Date": row["Date"],
                "Basin": row["Basin"],
                "Region": row["Region"],
                "Pollutant": pollutant,
                "Concentration": conc,
                "MPC": mpc,
                "WQI_Score": wqi,
                "Hazard_Class": hazard,
                "Ratio": ratio,
                "Risk_Level": classify_risk_level(ratio),
                "data_source": "observed_chemical",
                "country": "Kazakhstan",
                "station_code": row.get("station") or np.nan,
                "description": f"Kazhydromet official bulletin — {row['source_bulletin']}",
                "water_body": row.get("water_body") or "",
                "water_body_type": row.get("water_body_type") or "",
                "table_type": row.get("table_type") or "",
                "below_detection": bool(row.get("below_detection", False)),
                "exceeds_plausible": bool(row.get("exceeds_plausible", False)),
                "suspected_source_error": bool(row.get("suspected_source_error", False)),
            }
        )
    df = pd.DataFrame(rows)
    logger.info("Loaded real Kazhydromet pollution: %d rows", len(df))
    return df


def _load_potability_reference() -> pd.DataFrame:
    """Load Kaggle Water Potability as international reference."""
    if not WATER_POTABILITY_PATH.exists():
        logger.warning("Potability dataset not found: %s", WATER_POTABILITY_PATH)
        return pd.DataFrame(columns=MASTER_COLUMNS)

    raw = pd.read_csv(WATER_POTABILITY_PATH)
    ph = pd.to_numeric(raw["ph"], errors="coerce")
    turb = pd.to_numeric(raw["Turbidity"], errors="coerce")
    rows: list[dict] = []
    for i in range(len(raw)):
        p = ph.iloc[i]
        t = turb.iloc[i]
        ratio = compute_potability_ratio(p, t)
        wqi = compute_potability_wqi(p, t)
        rows.append(
            {
                "Date": pd.NaT,
                "Basin": "Global_Reference",
                "Region": "International",
                "Pollutant": "Mixed_Chemicals",
                "Concentration": t if not pd.isna(t) else np.nan,
                "MPC": 4.0,
                "WQI_Score": wqi,
                "Hazard_Class": classify_risk_code(ratio),
                "Ratio": ratio,
                "Risk_Level": classify_risk_level(ratio),
                "data_source": "reference",
                "country": "International",
                "station_code": np.nan,
                "description": "Drinking water quality — global reference (Kaggle)",
            }
        )
    df = pd.DataFrame(rows)
    logger.info("Loaded potability reference: %d rows", len(df))
    return df


def build_master_dataset() -> pd.DataFrame:
    """Combine all sources into a single standardized master DataFrame."""
    parts = [
        _load_kazhydromet_basins(),
        _load_real_pollution(),
        _load_potability_reference(),
    ]
    combined = pd.concat([p for p in parts if len(p) > 0], ignore_index=True)
    combined = combined.drop_duplicates(
        subset=["data_source", "Date", "Basin", "water_body", "station_code", "Pollutant", "Concentration"],
        keep="first",
    )
    combined = combined[combined["WQI_Score"].notna() | combined["Concentration"].notna()]
    combined.insert(0, "ID", range(1, len(combined) + 1))
    combined["Year"] = pd.to_datetime(combined["Date"], errors="coerce").dt.year
    logger.info(
        "Master dataset: %d rows | sources: %s",
        len(combined),
        combined["data_source"].value_counts().to_dict(),
    )
    return combined


def save_master_dataset(df: pd.DataFrame) -> Path:
    """Persist master dataset to CSV and SQLite."""
    MASTER_DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_cols = [c for c in MASTER_COLUMNS if c in df.columns]
    df[out_cols + (["Year"] if "Year" in df.columns else [])].to_csv(
        MASTER_DATASET_PATH, index=False
    )
    logger.info("Saved CSV: %s (%d rows)", MASTER_DATASET_PATH, len(df))

    conn = sqlite3.connect(SQLITE_PATH)
    df.to_sql("water_quality_data", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_year ON water_quality_data(Year)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_basin ON water_quality_data(Basin)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_region ON water_quality_data(Region)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON water_quality_data(data_source)")
    conn.commit()
    conn.close()
    logger.info("Saved SQLite: %s", SQLITE_PATH)
    return MASTER_DATASET_PATH


def main() -> None:
    """CLI entry point."""
    df = build_master_dataset()
    path = save_master_dataset(df)
    print(f"✅ Master dataset built: {path} ({len(df):,} rows)")
    print(df["data_source"].value_counts())


if __name__ == "__main__":
    main()
