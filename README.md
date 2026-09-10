# AquaMonitor

**Kazakhstan Water Quality Intelligence Platform**

Analytical platform for exploring, analyzing, and forecasting surface water quality in Kazakhstan using open environmental monitoring data, MPC-anchored Water Quality Index (WQI) scoring, machine learning, GIS visualization, and a local LLM environmental analyst.

---

## 1. Project Overview

**AquaMonitor** is a bachelor diploma project: *Development of a System for Analyzing and Visualizing Water Pollution Levels in Kazakhstan Using Open Environmental Data.*

The system integrates a **React** web frontend, a **FastAPI** REST backend, and a **Python analytics layer** over a hybrid historical monitoring dataset of **52,000+ records** spanning Kazhydromet hydrological observations, reconstructed chemical pollution records, and international reference data.

Users can filter by region, river basin, pollutant, and year; inspect WQI and MPC-based risk metrics; compare periods and regions; run **8 machine learning models** for temporal forecasting; explore an interactive **Kazakhstan map** with GIS layers; and consult an **Ollama-powered Environmental Intelligence Analyst** in **Kazakh, Russian, and English**.

This is an **analytical research platform** built on a **historical monitoring dataset**. It does not provide real-time government telemetry or production regulatory workflows.

---

## 2. Problem Statement

Surface water quality in Kazakhstan varies across river basins, regions, and pollutants. Public environmental data exists in heterogeneous formats — Kazhydromet hydrological posts, legacy chemical monitoring exports, and international reference datasets — but it is difficult to combine, interpret, and communicate without integrated analytics.

AquaMonitor addresses this by:

- Unifying disparate sources into a single master dataset with documented provenance
- Computing comparable WQI and hazard metrics anchored to Kazakhstan SanPiN MPC standards
- Providing regional and basin-level visualization on a Kazakhstan GIS map
- Supporting exploratory comparison and ML-based trend forecasting with disclosed limitations
- Offering filter-aware natural-language explanations via a local LLM assistant

---

## 3. Main Features

| Module | Description |
|--------|-------------|
| **National overview** | KPIs, data-quality split, risk assessment, automated insights |
| **Interactive map** | Kazakhstan choropleth, river/lake/basin GIS layers, station markers |
| **Charts & trends** | Temporal WQI trends, regional ranking, pollutant heatmap, year-over-year delta |
| **ML forecast** | 8 models with TimeSeriesSplit cross-validation (MAE, RMSE, R², MAPE) |
| **Compare** | Side-by-side region and period comparison with delta metrics |
| **Environmental Intelligence Analyst** | Ollama LLM chat grounded in current dashboard filters and analytics context |
| **Multilingual UI** | Kazakh (default), Russian, English |
| **Export** | Filtered CSV download via API |
| **Streamlit prototype** | Legacy thesis dashboard in `archive/streamlit_thesis_dashboard.py` |

---

## 4. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND — React + Vite + Plotly  (frontend/, :5173)       │
└──────────────────────────┬──────────────────────────────────┘
                           │  REST  /api/*
┌──────────────────────────▼──────────────────────────────────┐
│  BACKEND — FastAPI  (backend/main.py, :8001)                  │
│  backend/services/dashboard_service.py                        │
└───────────────┬──────────────────────────────┬────────────────┘
                │                              │
┌───────────────▼──────────────┐   ┌───────────▼────────────────┐
│  DATA + ANALYTICS             │   │  OLLAMA (local LLM)         │
│  data/  analytics/  config/  │   │  localhost:11434            │
│  db/kazakhstan_water_master  │   │  llama3.2 / qwen / mistral  │
└──────────────────────────────┘   └────────────────────────────┘
```

Layer responsibilities:

- **Frontend** — filter controls, map, charts, forecast tables, chat panel, i18n
- **Backend** — REST API, request validation, orchestration of analytics services
- **Analytics** — WQI, hazard classification, ML engine, GIS layers, chat context, Ollama client
- **Data** — dataset loading, validation, rebuild pipeline

Detailed diagrams and API flows: [ARCHITECTURE.md](ARCHITECTURE.md)

---

## 5. Technology Stack

| Layer | Technologies |
|-------|--------------|
| Frontend | React 18, Vite 5, Plotly.js, react-plotly.js |
| Backend | FastAPI, Uvicorn, Pydantic |
| Analytics | pandas, NumPy, scikit-learn, XGBoost, LightGBM, CatBoost, SHAP |
| Visualization | Plotly (Python + JavaScript) |
| GIS | GeoJSON (`kz.json`, `data/gis/`) |
| AI assistant | Ollama HTTP API (local LLM) |
| Testing | pytest |
| Legacy UI | Streamlit (archive prototype) |

---

## 6. Dataset

**Master file:** `db/kazakhstan_water_master.csv` (~52,594 rows)

| Source label | Rows (approx.) | Description |
|--------------|----------------|-------------|
| `observed` | 48,798 | Kazhydromet water-level observations (8 river basins) |
| `reconstructed` | 520 | Chemical pollution records (WQI recalculated) |
| `reference` | 3,276 | Kaggle water potability (methodological comparison only) |

**Legacy file:** `db/Kazakhstan_Water_Pollution_Dataset.csv` — source for reconstructed chemical records.

**Raw inputs for rebuild:** Kazhydromet basin CSVs and reference files in `ollama/` (see [Rebuilding the Dataset](#16-rebuilding-the-dataset)).

### Key columns

`Date`, `Basin`, `Region`, `Pollutant`, `Concentration`, `MPC`, `WQI_Score`, `Hazard_Class`, `data_source`, `Year`, `Ratio`, `Risk_Level`

---

## 7. Water Quality Index and MPC Explanation

### Pollution ratio

```
Ratio = Concentration / MPC
```

### Hazard classification

| Ratio | Class |
|-------|-------|
| < 1.0 | Safe |
| 1.0 – 2.0 | Moderate |
| ≥ 2.0 | High risk |

### WQI (MPC-anchored)

```
WQI = (Concentration / MPC) × 50
```

- WQI = 50 at the MPC boundary
- WQI < 50 → below MPC (safer)
- WQI > 100 → above 2× MPC

The formula follows Horton (1965) / Brown et al. (1970) sub-index methodology, adapted to Kazakhstan SanPiN fishery MPC standards. Implementation: `analytics/wqi.py`, `config/settings.py`.

Pollutants with defined MPC values include Nitrates, Copper, Sulfates, Zinc, Phenols, and Oil Products.

---

## 8. Machine Learning Forecasting

AquaMonitor trains **8 regression models** on annual WQI aggregates:

Linear Regression, Decision Tree, Random Forest, Extra Trees, ElasticNet, XGBoost, LightGBM, CatBoost

**Methodology:**

- Feature: `Year` (annual aggregation)
- Validation: `TimeSeriesSplit` (preserves temporal order)
- Metrics: MAE, RMSE, R², MAPE (cross-validated)
- Reproducibility: `random_state=42` (`config/settings.py`)

**Important:** Annual aggregation yields approximately **n ≈ 5** temporal points for pollution forecasting. Tree and boosting models may show high in-sample R² due to overfitting; **Linear Regression** is the primary interpretable baseline. Deep learning is intentionally excluded (requires n ≥ 50). See `analytics/ml_engine.py` and limitations L1, L5 in `config/settings.py`.

---

## 9. AI Environmental Analyst with Ollama

The Environmental Intelligence Analyst combines dashboard filter context with a **local Ollama LLM** to produce grounded environmental explanations.

```
User question
    ↓
Active filters (region, basin, year, pollutant, source)
    ↓
Analytics context (WQI, trends, hotspots, basin stats, forecast, risk alerts)
    ↓
Ollama LLM  (analytics/ollama_client.py)
    ↓
Environmental explanation  (analytics/chat_assistant.py)
    ↓
POST /api/dashboard/chat  →  React ChatPanel
```

- **Supported models (auto-detected):** `llama3.2`, `llama3`, `qwen2.5`, `qwen`, `mistral`, `gemma2`, `gemma`
- **Languages:** Kazakh, Russian, English (matches UI language)
- **Fallback:** If Ollama is unreachable, responses include *"Ollama model unavailable"* and rule-based summaries from the same analytics context
- **Status endpoint:** `GET /api/dashboard/analyst/status`

---

## 10. GIS and Interactive Map

The map module combines:

- **National boundary:** `kz.json` (SimpleMaps, CC BY 4.0)
- **GIS layers:** `data/gis/rivers.geojson`, `lakes.geojson`, `basins.geojson`
- **Regional choropleth** colored by WQI or risk metrics
- **Kazhydromet station coordinates** from `config/settings.py`

Map logic: `analytics/gis_layers.py`, frontend map components in `frontend/src/components/map/`.

---

## 11. Frontend

React single-page application with:

- Palantir-inspired control-center layout
- Scroll-driven national water experience (`WaterExperience`)
- Filter panel (region, basin, year, pollutant, data source)
- Lazy-loaded Plotly charts
- Dark/light theme toggle
- Chat panel for the Environmental Intelligence Analyst
- Dev proxy to backend on port 8001 (`frontend/vite.config.js`)

**Run:** `cd frontend && npm install && npm run dev` → [http://localhost:5173](http://localhost:5173)

---

## 12. Backend API

FastAPI application entry point: `backend/main.py`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check and dataset status |
| `/api/dashboard/meta` | GET | Dataset metadata and limitations |
| `/api/dashboard/geojson` | GET | Kazakhstan region GeoJSON |
| `/api/dashboard/gis/static` | GET | Static GIS layer metadata |
| `/api/dashboard/gis` | POST | GIS layers for current filters |
| `/api/dashboard/filter-options` | POST | Available filter values |
| `/api/dashboard/summary` | POST | KPIs and insights for filters |
| `/api/dashboard/charts` | POST | Chart payloads |
| `/api/dashboard/ml` | POST | ML forecast results |
| `/api/dashboard/compare` | POST | Region/period comparison |
| `/api/dashboard/analyst/status` | GET | Ollama availability |
| `/api/dashboard/chat` | POST | Environmental analyst chat |
| `/api/dashboard/export/csv` | POST | Filtered CSV export |

Interactive API docs: [http://localhost:8001/docs](http://localhost:8001/docs)

---

## 13. Installation

### Prerequisites

- Python 3.10+
- Node.js 18+
- (Optional) [Ollama](https://ollama.com) for the AI analyst
- (macOS) OpenMP for XGBoost/LightGBM: `brew install libomp`

### Backend

```bash
cd Water-system
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

---

## 14. Running the Project

**Terminal 1 — Backend:**

```bash
source .venv/bin/activate
python3 -m uvicorn backend.main:app --reload --port 8001
```

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

> Skip dataset rebuild if `db/kazakhstan_water_master.csv` already exists.

---

## 15. Running with Ollama

Install Ollama and pull a supported model:

```bash
ollama pull llama3.2
ollama serve
```

Ensure the Ollama daemon is reachable at **http://localhost:11434**.

Optional environment overrides:

```bash
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama3.2
```

Verify analyst status:

```bash
curl http://localhost:8001/api/dashboard/analyst/status
```

If Ollama is not running, the chat panel still works with rule-based fallback responses.

---

## 16. Rebuilding the Dataset

Rebuild the master CSV from raw Kazhydromet basin files and legacy sources:

```bash
python3 -m data.build_dataset
```

**Inputs:**

- `ollama/balhash-alakol.csv`, `ertis.csv`, `esil.csv`, `nura-sarysu.csv`, `shu-talas.csv`, `syrdarya.csv`, `tobol-torgai.csv`, `ural.csv`
- `ollama/water_potability.csv`
- `db/Kazakhstan_Water_Pollution_Dataset.csv`

**Output:** `db/kazakhstan_water_master.csv`

---

## 17. Running Tests

```bash
python3 -m pytest tests/ -q
```

Test coverage includes:

- WQI calculation and hazard classification (`test_wqi.py`)
- ML pipeline (`test_ml.py`)
- Chat assistant and context building (`test_chat.py`)
- Ollama client resolution and availability (`test_ollama_client.py`)
- AI insights and story engine (`test_ai_insights.py`, `test_story_engine.py`)

---

## 18. Project Structure

```
Water-system/
├── backend/                  # FastAPI REST API
│   ├── main.py
│   ├── api/routes/dashboard.py
│   └── services/dashboard_service.py
├── frontend/                 # React + Vite + Plotly
│   └── src/
│       ├── components/       # map, charts, chat, filters, dashboard
│       ├── i18n/             # EN / RU / KK translations
│       └── hooks/
├── analytics/                # WQI, hazard, ML, GIS, chat, Ollama
│   ├── wqi.py
│   ├── ml_engine.py
│   ├── gis_layers.py
│   ├── chat_assistant.py
│   └── ollama_client.py
├── config/                   # MPC, thresholds, paths, limitations
├── data/                     # loader, validator, build_dataset, gis/
├── db/
│   ├── kazakhstan_water_master.csv
│   └── Kazakhstan_Water_Pollution_Dataset.csv
├── visualization/            # Plotly chart builders (Python)
├── tests/                    # pytest suite
├── ollama/                   # Kazhydromet raw CSVs for dataset rebuild
├── archive/                  # Streamlit thesis prototype
├── kz.json                   # Kazakhstan GeoJSON
├── requirements.txt
└── ARCHITECTURE.md
```

---

## 19. Screenshots / Demo

Capture screenshots after starting the backend and frontend:

1. Overview — national KPIs and map
2. Charts — temporal trends and heatmap
3. Forecast — ML model comparison table
4. Compare — regional delta view
5. AI chat — analyst response with filter context

Save PNG files to `diploma_materials/07_screenshots/` (gitignored; for thesis documentation). See `diploma_materials/07_screenshots/README.txt` for naming conventions.

**API docs:** [http://localhost:8001/docs](http://localhost:8001/docs)

---

## 20. Diploma Context

**Supervisor:** Mira Rakhimzhanova, PhD, Assistant Professor  
**Institution:** Astana IT University  
**Project type:** Bachelor Diploma Project

This repository supports the bachelor thesis:

**AquaMonitor — Development of a System for Analyzing and Visualizing Water Pollution Levels in Kazakhstan Using Open Environmental Data**

Contributions:

- Hybrid dataset construction from open Kazhydromet and legacy chemical monitoring sources
- MPC-anchored WQI methodology adapted to Kazakhstan standards
- Full-stack analytical platform (React + FastAPI + Python)
- Comparative ML study with disclosed sample-size limitations
- Local LLM integration for filter-aware environmental explanations
- Multilingual interface for Kazakh, Russian, and English users

A legacy Streamlit thesis prototype is preserved in `archive/streamlit_thesis_dashboard.py`.

---

## 21. Limitations

Documented in `config/settings.py` (L1–L6):

1. **L1:** Small sample for annual ML forecasting (n ≈ 5 years for pollution aggregates)
2. **L2:** Chemical pollution records include statistically reconstructed values where direct measurements were unavailable
3. **L3:** Kazhydromet water-level observations proxy hydrological state, not chemical concentration
4. **L4:** International reference data (Kaggle) is for methodological comparison only
5. **L5:** Tree-based and boosting models on n < 10 demonstrate overfitting; trust cross-validation metrics
6. **L6:** WQI uses SanPiN MPC standards with disclosed hybrid dataset provenance

---

## 22. Authors

**Authors**

Assem Anarkulova  
Aigerim Koszhanova  
Zhaniya Kazbekova

Bachelor of Computer Science  
Astana IT University  
2026

---

## 23. License / Academic Use

- **Kazakhstan map GeoJSON** (`kz.json`): SimpleMaps, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- **Kazhydromet basin data:** raw CSV files in `ollama/` — open environmental monitoring exports
- **Kaggle water potability:** reference dataset for comparison only
- **Project code and analytics:** academic and research use as part of the diploma thesis

This software is provided for educational and research purposes. It is not endorsed by or affiliated with government environmental agencies.

---

## Build (production frontend)

```bash
cd frontend
npm run build
```

Output: `frontend/dist/` (gitignored; regenerate locally)

## Alternative: Streamlit prototype

Standalone — does not require the FastAPI backend:

```bash
python3 -m streamlit run archive/streamlit_thesis_dashboard.py
```

Open [http://localhost:8501](http://localhost:8501)
