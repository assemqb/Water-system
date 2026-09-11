# AquaMonitor

**Kazakhstan Water Quality Intelligence Platform**

Analytical platform for exploring, analyzing, and forecasting surface water quality in Kazakhstan using open environmental monitoring data, MPC-anchored Water Quality Index (WQI) scoring, machine learning, GIS visualization, and a local LLM environmental analyst.

---

## 1. Project Overview

**AquaMonitor** is a bachelor diploma project: *Development of a System for Analyzing and Visualizing Water Pollution Levels in Kazakhstan Using Open Environmental Data.*

The system integrates a **React** web frontend, a **FastAPI** REST backend, and a **Python analytics layer** over a hybrid historical monitoring dataset of **53,000+ records** spanning Kazhydromet hydrological observations, real chemical pollution measurements extracted from official Kazhydromet monthly bulletins, and international reference data.

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

**Master file:** `db/kazakhstan_water_master.csv` (~53,076 rows)

| Source label | Rows (approx.) | Description |
|--------------|----------------|-------------|
| `observed` | 48,798 | Kazhydromet water-level observations (8 river basins) |
| `observed_chemical` | 1,002 | Real chemical pollution measurements extracted from official Kazhydromet monthly environmental bulletins (766 for 2025 — 11 of 12 months, all 8 basins; 236 for 2024 — the 6 months with full 8-basin coverage: Jun, Aug–Dec) |
| `reference` | 3,276 | Kaggle water potability (methodological comparison only) |

**Real chemical data:** `db/kazhydromet_real_pollution_2025.csv` and `db/kazhydromet_real_pollution_2024.csv` — extracted by `data/kazhydromet_bulletin_etl.py` from the PDF bulletins Kazhydromet's oblast branches publish monthly ("Информационный бюллетень о состоянии окружающей среды"), each including a hydrochemical table of measured pollutant concentrations for surface water objects. Six pollutants with a defined MPC are extracted: Nitrates, Copper, Sulfates, Zinc, Phenols, Oil Products (see section 7 for which standard each MPC comes from). Every row carries:

- `source_bulletin` — the exact source PDF filename, for traceability (full URL manifests: `ollama/kazhydromet_bulletin_manifest_2025.json`, `..._2024.json`)
- `water_body` / `water_body_type` (`river` or `lake`) — which specific river, lake, reservoir, or sea point the reading is from, when the source table's layout allows it to be determined (~99% of rows for 2025, 100% for the 2024 months added); population by exact table layout is described in the module docstring. One table layout (a repeated-classifier-prefix header, e.g. "Көл Копа Көл Зеренді ...") was found, on inspection, to also have a genuine row-level shift in the source PDF (hardness/mineralization swapped) — rows from that layout are excluded entirely rather than risk a wrong concentration, not just a wrong water body.
- `station` — present in the schema for a numbered monitoring-post code, but these bulletins organize hydrochemical readings by water-body name/location description rather than a numeric post code (unlike the separate water-level hydrological posts in `STATION_MAP`), so it is empty for this data source.

**River/lake split in analytics (L7):** naturally saline lakes (Alakol, Balkhash, Tengiz/Northern Caspian) show Sulfates ratios of natural mineralization, not pollution, and blending them into a regional pollution ranking misrepresents lake-adjacent regions. `analytics/water_body.py` provides `exclude_lakes`/`only_lakes`; the dashboard's KPIs, regional facts/insights, the chat analyst's grounding context, and the map's per-region stats all default to rivers (`exclude_lakes`) and expose a parallel lake-only view (`kpi_lakes`, `lake_facts`, `region_stats_lakes` in the `/api/dashboard/summary` response) shown as a separate panel in the frontend rather than merged into the main numbers.

**Coverage note:** row volume is not uniform across months — Kazhydromet's bulletins report substantially more readings of these 6 pollutants in the ice-free season (May–October: roughly 70–100 rows/month) than in winter (November–April: roughly 35–42 rows/month). This was verified by reading source bulletins directly, not assumed: winter "class exceedance" tables are dominated by suspended solids/turbidity (ice break-up, effluent) rather than the 6 tracked substances, and the richer multi-parameter "Ингредиенттер атауы" panel tables (which report all 6 together) appear more often in the warmer months. Phenols (40 rows in 2025) is the rarest because it is usually only reported in those fuller panels, close to its detection floor (0.001 mg/dm³).

**Superseded:** `db/Kazakhstan_Water_Pollution_Dataset.csv` — the original 520-row statistically-reconstructed chemical dataset, kept in the repo for provenance/history but no longer loaded by the build pipeline.

**Raw inputs for rebuild:** Kazhydromet basin CSVs and reference files in `ollama/` (see [Rebuilding the Dataset](#16-rebuilding-the-dataset)).

### Key columns

`Date`, `Basin`, `Region`, `Pollutant`, `Concentration`, `MPC`, `WQI_Score`, `Hazard_Class`, `data_source`, `Year`, `Ratio`, `Risk_Level`, `water_body`, `water_body_type`

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

The formula follows Horton (1965) / Brown et al. (1970) sub-index methodology, single-parameter sub-indices anchored to a per-pollutant MPC. Implementation: `analytics/wqi.py`, `config/settings.py`.

### MPC standards used, per pollutant

Verified against primary sources (2026-09) — the six MPCs are **not** all from one standard, despite earlier code comments calling them uniformly "SanPiN fishery":

| Pollutant | MPC (mg/dm³) | Standard actually used | Primary source |
|---|---|---|---|
| Nitrates (as NO3⁻) | 45.0 | Both standards agree (coincidentally the same value) | RF fishery: Order of the RF Ministry of Agriculture No. 552 (2016); KZ drinking/household-cultural: Kazakhstan sanitary rules "Санитарно-эпидемиологические требования к водоисточникам..." (FAOLEX KAZ112216, Table 1) |
| Copper | 0.001 | RF fishery MPC (KZ drinking-water value is 1.0 — not used) | Order No. 552 (2016) |
| Sulfates | 500.0 | **KZ drinking-water MPC** (RF fishery value is 100.0 — not used) | FAOLEX KAZ112216, Table 1, item 24 |
| Zinc | 0.01 | RF fishery MPC (KZ drinking-water value is 5.0 — not used) | Order No. 552 (2016) |
| Phenols | 0.001 | RF fishery MPC (KZ drinking "phenol index" is 0.25 — not used) | Order No. 552 (2016) |
| Oil Products | 0.05 | RF fishery MPC (KZ drinking-water value is 0.1 — not used) | Order No. 552 (2016) |

In short: four of the six pollutants (Copper, Zinc, Phenols, Oil Products) use the stricter Russian **fishery** (рыбохозяйственное) standard, the conventional basis for a pollution/aquatic-life index. **Sulfates uses the Kazakhstan drinking-water standard instead** (500 vs. the fishery standard's 100 mg/dm³) — a 5× difference. This is a disclosed mixed methodology (see limitations L6/L7), not a data error: it was already present in the codebase before the 2025/2024 real-data replacement and has not been changed, since correcting it would retroactively reclassify every historical Sulfates ratio/hazard/WQI value — a methodology decision left to the thesis author.

### Nitrate unit conversion

A number of bulletins report "нитратты азот" (nitrate-**nitrogen**, NO3-N) instead of "нитрат-ионы"/"нитраттар" (nitrate-**ion**, NO3⁻) — chemically different quantities. Every such reading is converted to a NO3⁻ equivalent before comparison to the NO3⁻-based MPC above:

```
NO3⁻ = NO3-N × 4.4266
```

(molar mass of NO3⁻ ÷ molar mass of N, using IUPAC standard atomic weights: (14.007 + 3×15.999) / 14.007 = 4.4266). Implementation and the term-detection list: `data/kazhydromet_bulletin_etl.py` (`NITRATE_N_TO_ION`, `TERMS`).

---

## 8. Machine Learning Forecasting

AquaMonitor trains **8 regression models** on annual WQI aggregates:

Linear Regression, Decision Tree, Random Forest, Extra Trees, ElasticNet, XGBoost, LightGBM, CatBoost

**Methodology:**

- Feature: `Year` (annual aggregation)
- Validation: `TimeSeriesSplit` (preserves temporal order)
- Metrics: MAE, RMSE, R², MAPE (cross-validated)
- Reproducibility: `random_state=42` (`config/settings.py`)

**Important:** Annual aggregation yields approximately **n ≈ 5** temporal points when using the multi-decade water-level series (`Water_Level_cm`, 1995–2022). Tree and boosting models may show high in-sample R² due to overfitting; **Linear Regression** is the primary interpretable baseline. Deep learning is intentionally excluded (requires n ≥ 50). See `analytics/ml_engine.py` and limitations L1, L5 in `config/settings.py`.

**Chemical-pollutant forecasting is not available with the current data.** `dashboard_service.ml_forecast()` requires at least `MIN_ML_FORECAST_YEARS = 4` yearly points (`config/settings.py`) and returns `{"ok": false}` otherwise — a 2-point "trend" is a line through two dots, not a forecast, and `TimeSeriesSplit` cross-validation is undefined below n=3 folds regardless. The real Kazhydromet chemical data currently has only n=2 years (2024, 2025; see section 6), so it fails this gate by design. (This threshold was raised from 2 to 4 after review — at n=2 every one of the 8 regression models degenerated to predicting a flat line at the single available trend, with `NaN` cross-validated metrics; that is not something to present as ML output.)

**In place of a forecast**, filtering to a chemical pollutant (or the `observed_chemical` source) shows a **same-month year-over-year comparison** instead: `dashboard_service.chemical_yoy_comparison()` matches only the calendar months present in *both* of the two most recent years with chemical data (currently Jun, Aug–Dec — the months 2024 and 2025 share), and compares the mean MPC ratio per water body and pollutant between them. This avoids the trap of comparing a winter reading to a summer one, and reports on the exact same real measurements without pretending 2 points can predict a trend. Implementation: `backend/services/dashboard_service.py`, rendered in `frontend/src/components/forecast/ForecastLab.jsx` as the Forecast tab's fallback content.

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
- `db/kazhydromet_real_pollution_2025.csv`, `db/kazhydromet_real_pollution_2024.csv` (every `kazhydromet_real_pollution_*.csv` in `db/` is loaded and combined)

**Output:** `db/kazakhstan_water_master.csv`

To refresh a real chemical dataset (re-download the Kazhydromet bulletins for
a year and re-extract), run this before `build_dataset`:

```bash
python3 -m data.kazhydromet_bulletin_etl --year 2025
python3 -m data.kazhydromet_bulletin_etl --year 2024   # or any other year with a manifest
```

This needs the `pdftotext` binary (poppler-utils: `brew install poppler` /
`apt-get install poppler-utils`). It downloads the monthly PDFs listed in
`ollama/kazhydromet_bulletin_manifest_<year>.json`, extracts hydrochemical
readings (with river/lake attribution where the source table allows it) for
the six MPC-tracked pollutants, and writes
`db/kazhydromet_real_pollution_<year>.csv`.

**Building a manifest for a new year:** `ollama/kazhydromet_bulletin_manifest_<year>.json`
maps `"{Basin}_{YYYY-MM}"` to a source PDF URL. Kazhydromet's monthly-bulletin
listing page (`/ecology/ezhemesyachnyy-informacionnyy-byulleten-o-sostoyanii-okruzhayuschey-sredy/<year>`)
has a year selector back to 2017, but full 8-basin coverage varies sharply by
year — verified 2026-09: 2020 has none; 2021 (32%) and 2022 (39%) are too
sparse for a basin-comparable month; 2023 (54%) and 2024 (57%) each have a
handful of fully-covered months (2023: Mar/May/Jun/Aug; 2024: Jun, Aug–Dec —
already added above); 2025 (98%) is the only near-complete year. Extending
further into 2023 (and cherry-picking the partially-covered months of other
years for single-basin case studies rather than basin comparisons) is
possible with this same pipeline.

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
├── data/                     # loader, validator, build_dataset, bulletin ETL, gis/
├── db/
│   ├── kazakhstan_water_master.csv
│   ├── kazhydromet_real_pollution_2025.csv
│   └── Kazakhstan_Water_Pollution_Dataset.csv   # superseded, kept for provenance
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

Documented in `config/settings.py` (L1–L7):

1. **L1:** Small sample for annual ML forecasting — n ≈ 5 years using the multi-decade water-level series; chemical-pollutant forecasting is unavailable below `MIN_ML_FORECAST_YEARS = 4` (currently n = 2: 2024, 2025) — a same-month year-over-year comparison is shown instead (see section 8)
2. **L2:** Chemical pollution records are real measurements extracted from official Kazhydromet monthly bulletins (2025: 11/12 months; 2024: 6 fully-covered months), not statistically reconstructed; readings reported as nitrate-nitrogen were converted to nitrate-ion equivalents (×4.4266, see section 7)
3. **L3:** Kazhydromet water-level observations proxy hydrological state, not chemical concentration
4. **L4:** International reference data (Kaggle) is for methodological comparison only
5. **L5:** Tree-based and boosting models on n < 10 demonstrate overfitting; trust cross-validation metrics
6. **L6:** WQI uses MPC-anchored sub-indices; the 6 MPCs mix two different official standards — see section 7 for the full sourced table (this is disclosure, not a data error)
7. **L7:** Sulfates in naturally saline lakes (Alakol, Balkhash, Tengiz) reflect natural mineralization, not pollution — check `water_body_type` before reading a high Sulfates ratio there as a pollution signal

### Rows excluded for the repeated-prefix table-corruption fix (L2)

One source table layout — a repeated classifier prefix per column instead of a suffix per name (e.g. "Көл Копа Көл Зеренді Көл Бурабай ...") — was found, on inspection of Esil_2024-06.pdf, to also have a genuine row-level shift in the source PDF (a blank pH row pushed hardness and mineralization to swap places; the row labeled "Мыс"/Copper showed BOD5-scale magnitudes). `data/kazhydromet_bulletin_etl.py` now skips that layout's values entirely rather than keep a wrong concentration. It affects only the Esil (Akmola) region's bulletins — every other basin is unchanged:

| Basin | Year | Before | After | Excluded |
|---|---|---:|---:|---:|
| Aralo-Syrdarya | 2024 | 17 | 17 | 0 |
| Aralo-Syrdarya | 2025 | 35 | 35 | 0 |
| Balkash-Alakol | 2024 | 55 | 55 | 0 |
| Balkash-Alakol | 2025 | 187 | 187 | 0 |
| Ertis | 2024 | 26 | 26 | 0 |
| Ertis | 2025 | 163 | 163 | 0 |
| **Esil** | **2024** | **139** | **0** | **139** |
| **Esil** | **2025** | **247** | **30** | **217** |
| Nura-Sarysu | 2024 | 93 | 93 | 0 |
| Nura-Sarysu | 2025 | 176 | 176 | 0 |
| Shu-Talas | 2024 | 19 | 19 | 0 |
| Shu-Talas | 2025 | 58 | 58 | 0 |
| Tobyl-Torgay | 2025 | 35 | 35 | 0 |
| Zhaiyk-Kaspian | 2024 | 26 | 26 | 0 |
| Zhaiyk-Kaspian | 2025 | 82 | 82 | 0 |
| **Total** | | **1,358** | **1,002** | **356** |

(Tobyl-Torgay/2024 and Esil/2024 rows below the 2024 full-coverage-month set, or with zero matches for the 6 tracked pollutants that month, are omitted from the table rather than shown as 0/0.) Esil retains 30 rows in 2025 from tables that were NOT the repeated-prefix layout (individual river readings); the 2024 Esil bulletins for the covered months happened to report lakes exclusively via that layout, so its 2024 chemical count is zero.

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
