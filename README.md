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

**Master file:** `db/kazakhstan_water_master.csv` (~53,595 rows)

| Source label | Rows (approx.) | Description |
|--------------|----------------|-------------|
| `observed` | 48,798 | Kazhydromet water-level observations (8 river basins) |
| `observed_chemical` | 1,521 | Real chemical pollution measurements extracted from official Kazhydromet monthly environmental bulletins (1,220 for 2025 — 11 of 12 months, all 8 basins; 301 for 2024 — the 6 months with full 8-basin coverage: Jun, Aug–Dec) |
| `reference` | 3,276 | Kaggle water potability (methodological comparison only) |

**Real chemical data:** `db/kazhydromet_real_pollution_2025.csv` and `db/kazhydromet_real_pollution_2024.csv` — extracted by `data/kazhydromet_bulletin_etl.py` from the PDF bulletins Kazhydromet's oblast branches publish monthly ("Информационный бюллетень о состоянии окружающей среды"), each including a hydrochemical table of measured pollutant concentrations for surface water objects. Six pollutants with a defined MPC are extracted: Nitrates, Copper, Sulfates, Zinc, Phenols, Oil Products (see section 7 for which standard each MPC comes from). Every row carries:

- `source_bulletin` — the exact source PDF filename, for traceability (full URL manifests: `ollama/kazhydromet_bulletin_manifest_2025.json`, `..._2024.json`)
- `water_body` / `water_body_type` (`river` or `lake`) — which specific river, lake, reservoir, or sea point the reading is from, when the source table's layout allows it to be determined (98.4% of 2025 rows, 100% of 2024 rows). For "Кесте"/worst_parameter tables, a value's water body is resolved by finding the class-exceedance label ("N – сынып"/"N класс") that starts its block — a value belongs to the last such block whose name starts at or before it, never to a name that merely sits nearby by raw line count (see [Round 3](#round-3--class-label-block-boundaries-suspected_source_error-recovered-burabay-tables) below for why line-distance alone gets this wrong). Names split across lines by column wrapping (e.g. "Глубочанка" / value row / "өзені") are recombined; a curated spelling/abbreviation map (`CANONICAL_NAMES`) unifies variants of the same water body (e.g. "Балкаш көлі" → "Балқаш көлі", "Еміл өз." → "Еміл өзені") so the same river isn't split across two names in any per-water-body statistic. A repeated-classifier-prefix header table (e.g. "Көл Копа Көл Зеренді ...") is recovered by anchoring columns on the classifier tokens' positions and validated per table instance (pH 4–10, mineralization > hardness, copper < 0.05 mg/dm³ in every column) before being trusted — an instance that fails any check is excluded and logged rather than risk a wrong concentration. A cell where several parameter names are stacked around a single value (pdftotext linearizing a visually-stacked block) is also skipped rather than guessed at.
- `table_type` (`full_panel` or `worst_parameter`) — which of the two source layouts the reading came from; see the dedicated section below.
- `below_detection` — `True` when the bulletin reported `0`; kept as a real, meaningful zero rather than dropped as if no reading existed (Ratio/WQI both compute to 0 = Safe, correctly).
- `exceeds_plausible` — `True` when the concentration is above the generous `PLAUSIBLE_MAX` ceiling (data/kazhydromet_bulletin_etl.py); flagged rather than dropped (see section 22 — the one row this has ever caught in the full corpus was manually confirmed as a real reading, not a PDF artifact).
- `suspected_source_error` — `True` for one specific reading (Balkash-Alakol_2025-01.pdf, Темірлік өзені, Copper) that manual cross-checking found almost certainly transposed with its neighboring phosphorus reading *in the source PDF itself* — see [Round 3](#round-3--class-label-block-boundaries-suspected_source_error-recovered-burabay-tables). The value is kept exactly as printed (never corrected) and excluded only from `exceedance_catalog()`, so a probable data-entry error upstream doesn't read as a real contamination spike.
- `station` — present in the schema for a numbered monitoring-post code, but these bulletins organize hydrochemical readings by water-body name/location description rather than a numeric post code (unlike the separate water-level hydrological posts in `STATION_MAP`), so it is empty for this data source.

**River/lake split in analytics (L7):** naturally saline lakes (Alakol, Balkhash, Tengiz/Northern Caspian) show Sulfates ratios of natural mineralization, not pollution, and blending them into a regional pollution ranking misrepresents lake-adjacent regions. `analytics/water_body.py` provides `exclude_lakes`/`only_lakes`; the dashboard's KPIs, regional facts/insights, the chat analyst's grounding context, and the map's per-region stats all default to rivers (`exclude_lakes`) and expose a parallel lake-only view (`kpi_lakes`, `lake_facts`, `region_stats_lakes` in the `/api/dashboard/summary` response) shown as a separate panel in the frontend rather than merged into the main numbers.

**full_panel/worst_parameter split in analytics (L8):** a `worst_parameter` table only ever lists whichever substance(s) exceeded a class boundary that month — it never contributes a "clean" reading — so a median or "share above MPC" computed on it overstates typical pollution. `analytics/table_type.py` provides `restrict_to_full_panel`/`only_worst_parameter`/`only_full_panel`, used the same way as the river/lake split (`kpi_full_panel`, `kpi_worst_parameter`, `full_panel_facts`, `worst_parameter_facts`, `region_stats_worst_parameter`).

Because the river-default `kpi()` is necessarily worst_parameter data, it **omits `over_mpc_share`/`high_risk_share` entirely** rather than show a share computed on a pre-filtered-to-exceedances sample (that share would measure the reporting table's policy, not river pollution prevalence — every row already exceeded something by construction). In their place, `dashboard_service.exceedance_catalog()` reports, per river + pollutant: the maximum MPC ratio recorded and in how many distinct months an exceedance (Ratio > 1) was reported out of how many months observed — "which river, which substance, how bad, how often" is the question this kind of data can actually answer. `kpi_full_panel`/`kpi_lakes` (representative-sampling data) keep the share fields, since a "% above MPC" is meaningful there. Exposed as `exceedance_catalog` in `/api/dashboard/summary`, rendered in `NationalStatusPanel.jsx` in place of the removed high-risk/over-MPC figures.

**Important structural finding, not assumed — checked directly against the data:** `table_type` and `water_body_type` are **not independent** in this dataset. Kazhydromet's oblast branches report lakes/seas via the comprehensive full_panel table almost exclusively, and rivers via worst_parameter almost exclusively:

|  | full_panel | worst_parameter |
|---|---:|---:|
| river | 0 | 450 |
| lake | 1,032 | 20 |

Consequently `kpi()` (the river-default main view) is **not** also restricted to full_panel — doing so would return zero records, since rivers ∩ full_panel is empty. River statistics are necessarily built from worst_parameter data; this is disclosed (L8) rather than hidden. `kpi_full_panel()`/`kpi_worst_parameter()` split on table_type across both rivers and lakes together (not lake-excluded) — that is where the distinction is actually meaningful: full_panel medians run close to the MPC line (representative sampling, mostly lakes), worst_parameter means run into the thousands (exceedance-biased by construction, mostly rivers) — verified on the live data, not a hypothetical.

**Coverage note:** row volume is not uniform across months — Kazhydromet's bulletins report substantially more readings of these 6 pollutants in the ice-free season (May–October) than in winter (November–April). This was verified by reading source bulletins directly, not assumed: winter "class exceedance" tables are dominated by suspended solids/turbidity (ice break-up, effluent) rather than the 6 tracked substances, and the richer multi-parameter "Ингредиенттер атауы" panel tables (which report all 6 together) appear more often in the warmer months.

**Superseded:** `db/Kazakhstan_Water_Pollution_Dataset.csv` — the original 520-row statistically-reconstructed chemical dataset, kept in the repo for provenance/history but no longer loaded by the build pipeline.

**Raw inputs for rebuild:** Kazhydromet basin CSVs and reference files in `ollama/` (see [Rebuilding the Dataset](#16-rebuilding-the-dataset)).

### Key columns

`Date`, `Basin`, `Region`, `Pollutant`, `Concentration`, `MPC`, `WQI_Score`, `Hazard_Class`, `data_source`, `Year`, `Ratio`, `Risk_Level`, `water_body`, `water_body_type`, `table_type`, `below_detection`, `exceeds_plausible`, `suspected_source_error`

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

Documented in `config/settings.py` (L1–L8):

1. **L1:** Small sample for annual ML forecasting — n ≈ 5 years using the multi-decade water-level series; chemical-pollutant forecasting is unavailable below `MIN_ML_FORECAST_YEARS = 4` (currently n = 2: 2024, 2025) — a same-month year-over-year comparison is shown instead (see section 8)
2. **L2:** Chemical pollution records are real measurements extracted from official Kazhydromet monthly bulletins (2025: 11/12 months; 2024: 6 fully-covered months), not statistically reconstructed; readings reported as nitrate-nitrogen were converted to nitrate-ion equivalents (×4.4266, see section 7)
3. **L3:** Kazhydromet water-level observations proxy hydrological state, not chemical concentration
4. **L4:** International reference data (Kaggle) is for methodological comparison only
5. **L5:** Tree-based and boosting models on n < 10 demonstrate overfitting; trust cross-validation metrics
6. **L6:** WQI uses MPC-anchored sub-indices; the 6 MPCs mix two different official standards — see section 7 for the full sourced table (this is disclosure, not a data error)
7. **L7:** Sulfates in naturally saline lakes (Alakol, Balkhash, Tengiz) reflect natural mineralization, not pollution — check `water_body_type` before reading a high Sulfates ratio there as a pollution signal
8. **L8:** `table_type` and `water_body_type` are not independent — Kazhydromet reports lakes/seas via the comprehensive panel and rivers via the worst-exceeding-parameter table almost exclusively (0 river rows are full_panel), so river statistics are necessarily built from the exceedance-biased worst_parameter table; see section 6

### Repeated-prefix table recovery/exclusion (L2)

One source table layout — a repeated classifier prefix per column instead of a suffix per name (e.g. "Көл Копа Көл Зеренді Көл Бурабай ..."), used for the Esil (Akmola) region's lake tables — cannot be column-separated by the normal proximity clustering used elsewhere (adjacent columns sit closer together than a single wrapped 2-word name). It is recovered instead by anchoring each column on the x-position of its own repeated classifier token, then **validated per table instance** before being trusted: every column's pH must fall in 4–10, mineralization must exceed hardness, and copper must be below 0.05 mg/dm³ — the same symptom (a hardness- or BOD-scale value under the pH label) that a real row-shift produced once before (Esil_2024-06.pdf, found during Round 1). An instance that fails is excluded and logged; one that passes is included at full column resolution. This is a change from the previous behavior (blanket-excluding the entire layout), driven by a specific request during Round 3 review not to throw away recoverable data.

Outcome across the full 2024+2025 corpus (`python3 -m data.kazhydromet_bulletin_etl --year <year>` logs a `WARNING` for every excluded instance):

| Bulletin | Table (lake group) | Outcome | Reason if excluded |
|---|---|---|---|
| Esil_2025-06/07/08/10 | both groups (12 lakes) | ✅ included | — |
| Esil_2025-05 | Копа/Зеренді/Бурабай/Щучье/Шабақты/Сұлуколь | ✅ included | — |
| Esil_2025-05 | Карасье/Кіші Шабақты/Майбалық/Қатаркөл/Текекөл/Жүкей | ❌ excluded | page-break column-alignment drift (copper column not resolvable) |
| Esil_2025-09 | Копа/Зеренді/Бурабай/Щучье/Шабақты/Сұлуколь | ✅ included | — |
| Esil_2025-09 | Карасье/Кіші Шабақты/Майбалық/Қатаркөл/Текекөл/Жүкей | ❌ excluded | two adjacent columns too narrow to separate (hardness row ambiguous) |
| Esil_2024-06/08/09/10 | both groups | ❌ excluded | 2024 bulletins label these rows in a Russian-transliterated spelling the pH/mineralization/hardness/copper detectors don't yet match — could not validate, so not trusted |

2024's Esil lake tables remain unrecovered for this reason; documented here rather than silently returning fewer 2024 lake rows than 2025.

---

## 22. Validation

Every real chemical row is traceable to an exact source PDF and page (`source_bulletin` column; page derivable from pdftotext's page-break markers, as done for the two samples below). Two random samples were pulled for manual spot-checking directly against the source bulletins, each with a fixed `random.seed` for reproducibility.

### Round 1 — `validation_sample.csv` (30 rows, `random.seed(20260911)`)

**Result: 30/30 concentrations correct, 27/30 water bodies correct (3 misses).**

All 3 misses were the same root cause: Ertis "Кесте" (worst-exceeding-parameter) tables where a water-body name is split across lines by column wrapping, and the trailing classifier suffix ("өзені", "қоймасы", ...) lands only *after* the value line — sometimes for the *next* object in the table, not the one the reader is currently looking at. The old attribution logic carried the previous object's name forward and wrongly claimed the value.

| Bulletin | Reported value | Wrongly attributed to | Correct water body |
|---|---|---|---|
| Ertis_2025-11, p.15 | Zinc 0.076 | Үлбі өзені | **Глубочанка өзені** |
| Ertis_2025-07 | Copper 0.0011 | Үржар өзені | **Бұқтырма су қоймасы** |
| Ertis_2025-12 | Sulfates 242 | Оба өзені | **Еміл өзені** |

Fixed in `data/kazhydromet_bulletin_etl.py`: `_scan_water_body_lines()` now recognizes a name orphaned from its suffix by up to 3 lines, and attribution always takes the nearest name line by line-count distance regardless of whether it comes before or after the value (previously a "current" name carried forward from earlier in the table took priority even when stale). All 3 cases are regression tests in `tests/test_kazhydromet_bulletin_etl.py`.

### Round 2 — `validation_sample_2.csv` (30 rows, `random.seed(20260912)`, stratified ≥10 Ertis-basin + ≥10 full_panel rows)

**Result: 30/30 concentrations correct, 29/30 water bodies correct (1 miss, 0 wrong attributions).** The one miss was a blank `water_body` (an honest gap — a name split across lines in a shape `_scan_water_body_lines()` doesn't yet cover, e.g. extra trailing status text on the same line as the orphaned name fragment — left unattributed rather than guessed, consistent with the "missing beats wrong" principle applied throughout this ETL).

The round also surfaced a real *extraction* gap while cross-checking source pages: Ertis_2025-06.pdf and Ertis_2025-08.pdf report Copper for Еміл өзені via the Russian spelling "медь" (0.0012 and 0.0011 mg/dm³) instead of Kazakh "мыс" — not in the recognized-term list, so silently absent rather than misattributed. Checking systematically for other unrecognized Russian variants across the full corpus found one more: "Азот нитратный" (reversed word order vs. the already-handled "нитратты азот"). Both added to `TERMS` in `data/kazhydromet_bulletin_etl.py`, with tests.

### PLAUSIBLE_MAX audit

Before this round, a concentration over `PLAUSIBLE_MAX` was silently dropped (assumed to be a PDF column-misalignment artifact). Auditing every row that ceiling had ever dropped found exactly **one** in the full 2024+2025 corpus: Copper 32.9 mg/dm³ at Ertis_2024-09 — **Кіші Қарақожа өзені** again, the same river already on record with 22.7, 9.04, and 2.27 mg/dm³ Copper in other months (see section 6, exceedance catalog). Manual inspection of the source line confirmed it as a genuine reading, not an artifact — dropping it would have discarded real data about a documented, recurring contamination event. `PLAUSIBLE_MAX` now flags via `exceeds_plausible=True` instead of dropping.

### Round 3 — class-label block boundaries, `suspected_source_error`, recovered Burabay tables

Manual verification requests against `validation_sample_2.csv`'s underlying pages (not the sample rows themselves) found that the Round 1/2 attribution rule — the water body is whichever name is *nearest by raw line count*, checked in both directions — is wrong in principle, not just missing a couple of name shapes. Balkash-Alakol_2025-01.pdf p.13, Темірлік өзені block: Copper 0.254 sits several lines below Темірлік's own name line but only one line above the *next* object's name (Лепсі өзені), so nearest-by-line-count attributed it to Лепсі. Rendering the page as an image and tracing the block boundaries by hand across both this bulletin's format and Ertis's showed the actual rule Kazhydromet's layout follows: **every object's block starts at its class-exceedance label** ("N – сынып" / "N класс" / "N– класс" — always the bare nominative form, never the "сыныпқа"/"класқа" dative form used in narrative summary sentences elsewhere in the same PDF), and a value belongs to whichever label most recently started, not to whichever name is textually closest.

`_scan_class_label_blocks()` replaces the nearest-line scan for worst_parameter attribution: it finds every class-label line, then resolves each block's name by checking the label's own line first (covers "Үлбі өзені 6 – сынып ..." and "Темірлік өзені - 3 класс ..." — name and label share a line), then searching forward — never backward — up to the next label for a name (including the orphaned-name-plus-trailing-suffix shape from Round 1). A value's block is whichever label is nearest *at or before* it. This fixed all 3 Round 1 cases and the newly found ones:

| Bulletin | Reported value | Old (nearest-line) attribution | Correct (class-label block) |
|---|---|---|---|
| Balkash-Alakol_2025-01, p.13 | Copper 0.254 | Лепсі өзені | **Темірлік өзені** *(see suspected_source_error below)* |
| Balkash-Alakol_2025-01, p.13 | Copper 0.00205 | (unattributed) | **Іле өзені** |
| Balkash-Alakol_2025-01, p.13 | Copper 0.0014 | (unattributed) | **Баянкөл өзені** |

**Value-on-next-line:** the same page also has "Мыс мг/дм3" ending a line with no number at all (Түрген өзені) — the value ("0,0011") is the last token of the *next* line instead. This row was previously dropped silently, not misattributed (`LINE_RE` didn't match at all). Now, when a tracked term's own line has no number, the next 1–2 lines are checked for one, stopping at the next class label.

**`suspected_source_error`:** Темірлік өзені's phosphorus reading (0.0024 mg/dm³) is ~100x lower than every other river's phosphorus that month, while its Copper reading (0.254 mg/dm³) is ~100x higher than every other river's Copper — and each value is exactly the *typical* magnitude for the *other* substance. This reads as the two values being transposed in the bulletin PDF itself, not an extraction bug. Per instruction, **the value is not corrected** — `suspected_source_error=True` is set on this one row (keyed by exact bulletin+water body+pollutant, not a general heuristic, to avoid false positives elsewhere), and `dashboard_service.exceedance_catalog()` excludes flagged rows so a probable upstream data-entry error doesn't surface as a real contamination spike. Темірлік's other months' Copper readings are unaffected and still appear.

**Recovered Burabay/Esil lake tables:** see [Repeated-prefix table recovery/exclusion](#repeated-prefix-table-recoveryexclusion-l2) above — 8 of 12 checked table instances (4 bulletins × 2 lake groups, plus 2 single-group months) were recovered rather than excluded wholesale, adding 12 lakes' full chemical panels (Sulfates, Nitrates, Copper, Zinc, Phenols, Oil Products) across the months they validate. This is the single largest contributor to the row-count increase this round (2025: 846 → 1,220; 2024: 297 → 301).

**`validation_sample_3.csv`** (30 rows, `random.seed(20260913)`, stratified ≥15 from Balkash-Alakol/Ertis worst_parameter "Кесте" blocks and ≥8 from the newly recovered Esil full_panel Burabay tables) is provided for the next round of manual spot-checking against source pages.

---

## 23. Authors

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
