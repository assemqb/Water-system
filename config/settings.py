"""
Central configuration for the Kazakhstan Water Quality Monitoring System.

All MPC values, hazard thresholds, file paths, model hyperparameters, and
random seeds are defined here. No magic numbers should appear elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

# ── Project paths ─────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "db"
# Legacy folder name — holds Kazhydromet raw CSVs for dataset build (not the LLM runtime)
OLLAMA_DIR = PROJECT_ROOT / "ollama"
RAW_DATA_DIR = OLLAMA_DIR

# ── Ollama (Environmental Intelligence Analyst) ───────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = ""  # empty = auto-detect from installed models
OLLAMA_PREFERRED_MODELS = ("llama3.2", "llama3", "qwen2.5", "qwen", "mistral", "gemma2", "gemma")
OLLAMA_TIMEOUT = 45.0
GEOJSON_PATH = PROJECT_ROOT / "kz.json"

# Canonical master dataset (built by data/build_dataset.py)
MASTER_DATASET_PATH = DATA_DIR / "kazakhstan_water_master.csv"
# Superseded statistically-reconstructed chemical dataset — kept for provenance,
# no longer loaded by data/build_dataset.py (see REAL_POLLUTION_PATH).
LEGACY_DATASET_PATH = DATA_DIR / "Kazakhstan_Water_Pollution_Dataset.csv"
# Real chemical measurements extracted from official Kazhydromet monthly
# bulletins (data/kazhydromet_bulletin_etl.py --year <year>). One file per
# year; all are loaded and combined. Replaces LEGACY_DATASET_PATH.
REAL_POLLUTION_PATHS = sorted(DATA_DIR.glob("kazhydromet_real_pollution_*.csv"))

# Default path used by the dashboard
DATA_PATH = MASTER_DATASET_PATH

# Kazhydromet basin CSV files (real observed water levels)
BASIN_FILES: Dict[str, Path] = {
    "balhash-alakol": OLLAMA_DIR / "balhash-alakol.csv",
    "ertis": OLLAMA_DIR / "ertis.csv",
    "esil": OLLAMA_DIR / "esil.csv",
    "nura-sarysu": OLLAMA_DIR / "nura-sarysu.csv",
    "shu-talas": OLLAMA_DIR / "shu-talas.csv",
    "syrdarya": OLLAMA_DIR / "syrdarya.csv",
    "tobol-torgai": OLLAMA_DIR / "tobol-torgai.csv",
    "ural": OLLAMA_DIR / "ural.csv",
}

WATER_POTABILITY_PATH = OLLAMA_DIR / "water_potability.csv"
SQLITE_PATH = DATA_DIR / "water_quality.db"

# ── Reproducibility ───────────────────────────────────────────────────────────
RANDOM_SEED = 42

# ── WQI (MPC-anchored, Horton 1965 / Brown et al. 1970 inspired) ─────────────
# Single-parameter sub-index: q_i = (C_i / MPC_i) × WQI_SCALE_FACTOR
# WQI = 50 at MPC boundary; WQI < 50 = below MPC (safer); WQI > 100 = above 2× MPC
WQI_SCALE_FACTOR = 50.0

# ── Hazard thresholds (ratio = Concentration / MPC) ─────────────────────────
HAZARD_THRESHOLDS: Dict[str, float] = {
    "safe_max": 1.0,       # ratio < 1.0  → Safe
    "moderate_max": 2.0,   # 1.0 ≤ ratio < 2.0 → Moderate; ratio ≥ 2.0 → High
}

# ── Pollutants: MPC (mg/L) + intrinsic hazard class ───────────────────────────
# The six MPCs below are drawn from TWO different official standards, not one
# — despite prior code/README comments calling all of them "SanPiN fishery".
# Verified against primary sources (2026-09):
#
#   Pollutant     MPC (mg/L)  Standard actually matched                                    Source
#   Nitrates      45.0        BOTH standards agree (as NO3-, coincidentally the same value) RF fishery: Order of the RF Ministry
#                                                                                            of Agriculture No. 552 (2016); KZ
#                                                                                            drinking/household-cultural use:
#                                                                                            Kazakhstan sanitary rules "Санитарно-
#                                                                                            эпидемиологические требования к
#                                                                                            водоисточникам..." (FAOLEX KAZ112216), Table 1
#   Copper        0.001       RF fishery MPC (KZ drinking-water value is 1.0, not used)      Order No. 552 (2016)
#   Sulfates      500.0       KZ drinking-water MPC (RF fishery value is 100.0, not used)    FAOLEX KAZ112216, Table 1, item 24
#   Zinc          0.01        RF fishery MPC (KZ drinking-water value is 5.0, not used)       Order No. 552 (2016)
#   Phenols       0.001       RF fishery MPC (KZ drinking "phenol index" is 0.25, not used)   Order No. 552 (2016)
#   Oil Products  0.05        RF fishery MPC (KZ drinking-water value is 0.1, not used)       Order No. 552 (2016)
#
# In short: Copper/Zinc/Phenols/Oil Products use the stricter Russian fishery
# (рыбохозяйственное) standard, which protects aquatic life and is the
# conventional basis for a water-quality/pollution index; Sulfates uses the
# Kazakhstan drinking-water (хозяйственно-питьевое) standard instead — a
# mixed methodology, disclosed here and in README section 7 and limitation
# L2/L7, not a data error. See README section 7 for the full writeup.
@dataclass(frozen=True)
class PollutantSpec:
    """MPC reference and intrinsic hazard class for a pollutant."""

    mpc: float
    hazard_class: int
    unit: str = "mg/L"


POLLUTANTS: Dict[str, PollutantSpec] = {
    "Nitrates": PollutantSpec(mpc=45.0, hazard_class=1),
    "Copper": PollutantSpec(mpc=0.001, hazard_class=2),
    "Sulfates": PollutantSpec(mpc=500.0, hazard_class=4),
    "Zinc": PollutantSpec(mpc=0.01, hazard_class=3),
    "Phenols": PollutantSpec(mpc=0.001, hazard_class=2),
    "Oil Products": PollutantSpec(mpc=0.05, hazard_class=3),
}

# ── Water quality classes: Unified Classification System ─────────────────────
# Order of the Minister of Water Resources and Irrigation of the Republic of
# Kazakhstan No. 111-НҚ dated 2025-06-04 ("Об утверждении Единой системы
# классификации качества воды водных объектов"), in effect from 2025-06-10.
# Approved for use in this project by the academic advisor, replacing the
# mixed-MPC-ratio approach above as the PRIMARY water quality assessment for
# rivers (the MPC ratio / WQI above are kept as a secondary, explicitly
# labeled figure — see dashboard_service.py).
#
# IMPORTANT SCOPE LIMIT, stated in the order's own explanatory note: these
# classes apply to RIVERS, CANALS, and CHANNEL (riverbed) RESERVOIRS only —
# NOT to seas or lakes, explicitly naming the Caspian, Aral, and Balkhash.
# See is_wqc_eligible() in data/kazhydromet_bulletin_etl.py for how that
# scope is applied to water body names, and README L9.
#
# Bulletins report "мыс"/"мырыш"/"ұшқыш фенол" (copper/zinc/phenols) without
# specifying dissolved vs. total/general form. Per the advisor's guidance,
# the GENERAL ("общая"/"общий") form's class thresholds and the VOLATILE
# phenols thresholds are used uniformly — a disclosed methodological choice,
# not a data error (mirrors the MPC standard-mixing disclosure above).
#
# Each bound is the class's UPPER limit in mg/L; a concentration is assigned
# to the LOWEST-numbered class whose bound it satisfies (class 1 = cleanest).
# A concentration above every class-5 bound is class 6. `strict=True` means
# the bound must not be reached (<), otherwise the bound value itself still
# counts as that class (<=) — only Sulfates class 1 is marked strict ("<100")
# in the order's own table; every other class boundary, including ones
# printed as a bare number with no "≤"/"<", is inclusive.
#
# Several pollutants repeat the SAME bound across consecutive classes (e.g.
# Copper classes 1 and 2 both cap at 0.002, Nitrates classes 3-5 all cap at
# 45): this is not a bug — the official table's classes are jointly defined
# across many parameters, and a handful of them coincide for any ONE
# parameter viewed alone. The practical effect: classifying by a single
# pollutant can never land on some of the mid-range classes for that
# pollutant (documented in tests/test_water_quality_class.py), matching the
# source table exactly rather than "smoothing" it into evenly-spaced bins.
@dataclass(frozen=True)
class QualityClassBound:
    """Upper bound for one water quality class (mg/L)."""

    upper: float
    strict: bool = False  # True = concentration must be < upper (not <=)


# Classes 1-5 bounds, in order; anything above class 5's bound is class 6.
WATER_QUALITY_CLASSES: Dict[str, Tuple[QualityClassBound, ...]] = {
    "Sulfates": (
        QualityClassBound(100.0, strict=True),
        QualityClassBound(100.0),
        QualityClassBound(500.0),
        QualityClassBound(600.0),
        QualityClassBound(1500.0),
    ),
    "Nitrates": (
        QualityClassBound(40.0),
        QualityClassBound(40.0),
        QualityClassBound(45.0),
        QualityClassBound(45.0),
        QualityClassBound(45.0),
    ),
    "Copper": (
        QualityClassBound(0.002),
        QualityClassBound(0.002),
        QualityClassBound(2.0),
        QualityClassBound(2.0),
        QualityClassBound(2.4),
    ),
    "Zinc": (
        QualityClassBound(0.04),
        QualityClassBound(0.04),
        QualityClassBound(0.04),
        QualityClassBound(0.12),
        QualityClassBound(0.20),
    ),
    "Phenols": (
        QualityClassBound(0.001),
        QualityClassBound(0.001),
        QualityClassBound(0.001),
        QualityClassBound(0.002),
        QualityClassBound(0.005),
    ),
    "Oil Products": (
        QualityClassBound(0.05),
        QualityClassBound(0.05),
        QualityClassBound(0.10),
        QualityClassBound(0.20),
        QualityClassBound(0.30),
    ),
}


def classify_water_quality(pollutant: str, concentration: float) -> Optional[int]:
    """Water quality class (1-6) for one pollutant reading, per
    WATER_QUALITY_CLASSES. Returns None for a pollutant not covered by the
    order's table (eligibility by water body type is a separate check —
    see is_wqc_eligible in data/kazhydromet_bulletin_etl.py)."""
    bounds = WATER_QUALITY_CLASSES.get(pollutant)
    if bounds is None or concentration is None:
        return None
    for class_number, bound in enumerate(bounds, start=1):
        satisfied = concentration < bound.upper if bound.strict else concentration <= bound.upper
        if satisfied:
            return class_number
    return 6

# ── Kazhydromet station → basin / region / coordinates (lon, lat WGS84) ───────
STATION_MAP: Dict[int, Tuple[str, str, str]] = {
    14002: ("Balkash-Alakol", "Almaty", "Lake Balkhash monitoring station"),
    11001: ("Ertis", "VKO", "Irtysh River — East Kazakhstan"),
    11242: ("Esil", "Akmoal", "Ishim River — Akmola region"),
    13046: ("Nura-Sarysu", "Karaganda", "Nura River — Karaganda region"),
    15125: ("Shu-Talas", "Zhambyl", "Shu River — Zhambyl region"),
    16031: ("Aralo-Syrdarya", "Kyzylorda", "Syr Darya River — Kyzylorda"),
    12001: ("Tobyl-Torgay", "Kostanay", "Tobol River — Kostanay region"),
    19009: ("Zhaiyk-Kaspian", "Atyrau", "Ural River — Atyrau region"),
}

# Kazhydromet hydrological post coordinates (WGS84, verified against basin locations)
STATION_COORDS: Dict[int, Tuple[float, float]] = {
    11001: (82.61, 49.97),   # Ust-Kamenogorsk, Irtysh
    16031: (65.52, 44.85),   # Syr Darya, Kyzylorda
    15125: (73.76, 43.60),   # Shu River, Shu town
    12001: (63.62, 53.21),   # Tobol, Kostanay
    14002: (74.98, 46.82),   # Lake Balkhash
    19009: (51.88, 47.12),   # Ural River, Atyrau
    11242: (69.14, 54.87),   # Ishim, Petropavl
    13046: (73.10, 49.80),   # Nura, Karaganda
}

GIS_DIR = PROJECT_ROOT / "data" / "gis"
RIVERS_GEOJSON_PATH = GIS_DIR / "rivers.geojson"
LAKES_GEOJSON_PATH = GIS_DIR / "lakes.geojson"
BASINS_GEOJSON_PATH = GIS_DIR / "basins.geojson"

# Basin display colors (keys match CSV Basin column exactly)
BASIN_COLORS: Dict[str, str] = {
    "Ertis": "#2dd4bf",
    "Aralo-Syrdarya": "#38bdf8",
    "Balkash-Alakol": "#a78bfa",
    "Zhaiyk-Kaspian": "#fbbf24",
    "Tobyl-Torgay": "#94a3b8",
    "Shu-Talas": "#34d399",
    "Esil": "#60a5fa",
    "Nura-Sarysu": "#f472b6",
    "Global_Reference": "#64748b",
}

# Normal water-level ranges (cm) for Kazhydromet ratio proxy
BASIN_WATER_LEVEL_RANGES: Dict[str, Tuple[float, float]] = {
    "Balkash-Alakol": (50, 400),
    "Ertis": (100, 450),
    "Esil": (400, 800),
    "Nura-Sarysu": (1, 2),
    "Shu-Talas": (50, 400),
    "Aralo-Syrdarya": (50, 600),
    "Tobyl-Torgay": (80, 350),
    "Zhaiyk-Kaspian": (50, 600),
}

# ── GeoJSON region name mapping ───────────────────────────────────────────────
REGION_NAME_MAP: Dict[str, str] = {
    "VKO": "East Kazakhstan",
    "Karaganda": "Karaganda",
    "Kostanay": "Kostanay",
    "Akmoal": "Akmola",
    "Almaty": "Almaty",
    "Zhambyl": "Jambyl",
    "Kyzylorda": "Kyzylorda",
    "Atyrau": "Atyrau",
}

# ── Data source labels (provenance) ───────────────────────────────────────────
DATA_SOURCE_LABELS: Dict[str, str] = {
    "observed": "Kazhydromet observed (water level)",
    "observed_chemical": "Kazhydromet observed (chemical pollution, official bulletins)",
    "reference": "International reference (Kaggle potability)",
}

# ── ML hyperparameters ────────────────────────────────────────────────────────
MODEL_HYPERPARAMS: Dict[str, dict] = {
    "Linear Regression": {},
    "Decision Tree": {"max_depth": 3, "random_state": RANDOM_SEED},
    "Random Forest": {"n_estimators": 200, "random_state": RANDOM_SEED},
    "Extra Trees": {"n_estimators": 200, "random_state": RANDOM_SEED},
    "ElasticNet": {"alpha": 0.1, "l1_ratio": 0.5, "random_state": RANDOM_SEED, "max_iter": 5000},
    "XGBoost": {
        "n_estimators": 200,
        "max_depth": 3,
        "learning_rate": 0.1,
        "random_state": RANDOM_SEED,
        "verbosity": 0,
    },
    "LightGBM": {
        "n_estimators": 200,
        "max_depth": 3,
        "learning_rate": 0.1,
        "random_state": RANDOM_SEED,
        "verbose": -1,
    },
    "CatBoost": {
        "iterations": 200,
        "depth": 3,
        "learning_rate": 0.1,
        "random_seed": RANDOM_SEED,
        "verbose": 0,
    },
}

MODEL_COLORS: Dict[str, str] = {
    "Linear Regression": "#F59E0B",
    "Decision Tree": "#8B5CF6",
    "Random Forest": "#10B981",
    "Extra Trees": "#06B6D4",
    "ElasticNet": "#EC4899",
    "XGBoost": "#EF4444",
    "LightGBM": "#84CC16",
    "CatBoost": "#F97316",
}

# Tree/boosting models eligible for SHAP and overfitting warnings
TREE_MODEL_NAMES = {
    "Decision Tree",
    "Random Forest",
    "Extra Trees",
    "XGBoost",
    "LightGBM",
    "CatBoost",
}

OVERFITTING_R2_THRESHOLD = 0.95
MIN_SAMPLES_DEEP_LEARNING = 50
# Below this many yearly points, TimeSeriesSplit CV is not meaningful (needs
# n>=3 to fold at all) and a 2-point "trend" is just a line through two
# dots, not a forecast. dashboard_service.ml_forecast() returns {"ok": False}
# under this threshold instead of a misleading result.
MIN_ML_FORECAST_YEARS = 4
# dashboard_service.chemical_yoy_comparison() drops any water-body/pollutant
# row where either year has fewer than this many individual measurements —
# a "mean" of 1-2 readings is not a reliable enough estimate to compare
# year over year.
MIN_YOY_SAMPLES = 3

# ── Dashboard copy ────────────────────────────────────────────────────────────
DATASET_BANNER = (
    "Dataset: Hybrid (observed water level + observed chemical pollution + international reference). "
    "See methodology for full disclosure."
)

LIMITATIONS = [
    "L1: Sample size for annual ML forecasting is limited (n≈5 years for the water-level series); "
    "chemical-pollutant forecasting is unavailable below MIN_ML_FORECAST_YEARS=4 (currently n=2) — "
    "a same-month year-over-year comparison is shown instead.",
    "L2: Chemical pollution records are real measurements extracted from official Kazhydromet monthly "
    "environmental bulletins (2025, all 8 basins); readings reported as nitrate-nitrogen were converted "
    "to nitrate-ion equivalents (×4.4266, molar mass ratio NO3/N using IUPAC standard atomic weights).",
    "L3: Water-level observations (Kazhydromet) proxy basin hydrological state, not chemical concentration.",
    "L4: International reference data (Kaggle) is included for methodological comparison only, not for Kazakhstan regulatory decisions.",
    "L5: Tree-based and boosting models on n<10 observations demonstrate overfitting; Linear Regression is the primary interpretable model.",
    "L6: WQI uses MPC-anchored sub-indices (Horton 1965; Brown et al. 1970); the 6 pollutant MPCs mix two "
    "standards (see POLLUTANTS comment and README section 7) — Copper/Zinc/Phenols/Oil Products use the "
    "stricter Russian fishery MPC, Sulfates and Nitrates use the Kazakhstan drinking-water MPC.",
    "L7: Sulfates in naturally saline lakes (Alakol, Balkhash, Tengiz) reflect natural mineralization, not "
    "anthropogenic pollution — see water_body_type ('lake' vs 'river') before reading a high Sulfates "
    "ratio there as a pollution signal.",
    "L8: table_type ('full_panel' vs 'worst_parameter') and water_body_type are not independent — "
    "Kazhydromet reports lakes/seas via the comprehensive panel and rivers via the worst-exceeding-"
    "parameter table almost exclusively, so river statistics are necessarily worst_parameter-based "
    "(a biased, exceedance-only sample); see analytics/table_type.py and README section 6.",
    "L9: water_quality_class (Order No. 111-НҚ, 2025-06-04) is populated for rivers, canals, and "
    "channel reservoirs only, per the order's own scope note — it is blank for seas and lakes "
    "(Caspian, Aral, Balkhash included), where MPC ratio/WQI remain the only quality figures shown.",
]

ML_DISCLAIMER = (
    "n=5 annual observations constrains generalizability. "
    "Tree-based R² near 1.0 indicates overfitting on this temporal sample. "
    "Linear Regression remains the most reliable model for trend characterisation."
)

WHY_NOT_DEEP_LEARNING = (
    "Deep learning (LSTM/MLP) requires n≥50 temporal observations. "
    "With n=5 annual means, neural networks would overfit more severely than XGBoost."
)
