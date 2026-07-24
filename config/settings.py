"""
Central configuration for the Kazakhstan Water Quality Monitoring System.

All MPC values, hazard thresholds, file paths, model hyperparameters, and
random seeds are defined here. No magic numbers should appear elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

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
LEGACY_DATASET_PATH = DATA_DIR / "Kazakhstan_Water_Pollution_Dataset.csv"

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

# ── Pollutants: MPC (mg/L, SanPiN fishery-use) + intrinsic hazard class ───────
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
    "reconstructed": "Statistically reconstructed (chemical pollution)",
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

# ── Dashboard copy ────────────────────────────────────────────────────────────
DATASET_BANNER = (
    "Dataset: Hybrid (observed + statistically reconstructed). "
    "See methodology for full disclosure."
)

LIMITATIONS = [
    "L1: Sample size for annual ML forecasting is limited (n≈5 years for pollution aggregates).",
    "L2: Chemical pollution records include statistically reconstructed values where direct measurements were unavailable.",
    "L3: Water-level observations (Kazhydromet) proxy basin hydrological state, not chemical concentration.",
    "L4: International reference data (Kaggle) is included for methodological comparison only, not for Kazakhstan regulatory decisions.",
    "L5: Tree-based and boosting models on n<10 observations demonstrate overfitting; Linear Regression is the primary interpretable model.",
    "L6: WQI uses MPC-anchored sub-indices (Horton 1965; Brown et al. 1970) adapted to Kazakhstan SanPiN fishery MPC standards.",
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
