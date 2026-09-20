# 🌊 IN-GRES AI

**Indian Groundwater Resource Estimation System — AI Virtual Assistant**

An AI-powered multilingual and multimodal virtual assistant for Indian groundwater-resource
information. It combines conversational AI, LangGraph-based agent orchestration,
retrieval-augmented generation, structured groundwater-data querying, GIS visualization,
and real-time voice interaction.

> ⚠️ **Development status:** Phases 1–19 implemented: foundation, auth/RBAC + dashboard, the
> groundwater data model with analytics + GIS + reports, an AI chat assistant with language,
> intent, location (state, district **or village**) and metric extraction, graph-based
> orchestration, retrieval-augmented generation, expert escalation, admin console, multilingual
> UI, simulated phone voice, and statistical groundwater forecasting (linear / moving-average /
> exponential-smoothing projections with confidence bands and risk classification).
> Later phases add a knowledge-base explorer, PWA offline + push, GIS time-lapse, deep-learning
> forecasting with river-basin scopes, CI/CD, an assistant feedback loop, question understanding,
> Groq-native web search, a multi-scope comparison workspace, a data-quality anomaly engine with
> admin review workflow, scheduled PDF report digests, and a Scenario Studio for what-if
> projections.
> Groundwater datasets are clearly labelled: the synthetic demo set is always marked demo, and
> the real CGWB/IMD station data (see below) is served in preference to it wherever it exists.
> No official IN-GRES/CGWB data is fabricated.

### National all-India dataset

The demo seed now builds a **national** synthetic dataset covering **all 36 states/union
territories and ~780 real districts** plus a generated **village layer (~517k villages)**,
each with per-village groundwater assessments for 2017–2022. Everything is clearly labelled
demo/synthetic:

- Real boundaries: every state/UT, its ISO code, region, centroid and ~780 district names.
- Generated villages: regionally-plausible names (e.g. `-palli`, `-pur`, `-gram`), deterministic
  coordinates clustered inside each district, and a population estimate.
- One assessment unit per village, linked to a new `villages` table, with recharge,
  extraction, extractable resource, stage-of-extraction and category per year.

Seeding is controlled by `SEED_DATASET` (`national` | `demo` | `none`) and
`SEED_VILLAGES_PER_DISTRICT` (0 = auto to reach the target; a positive number forces the same
count per district for faster dev). It is idempotent — re-running skips an already-seeded
dataset. A full national seed takes roughly 3 minutes on SQLite and is much faster on Postgres.

Because the village layer is very large, the GIS service maps at **district level** when a query
would otherwise return more than `MAX_MAP_FEATURES` (8000) polygons, and always renders the
All-India choropleth by state.

### Real CGWB/IMD station data

The `states/*.csv` files from the PDF-extraction pipeline hold **station-level 2025** groundwater
and rainfall observations (29 states/UTs, ~765k stations, ~725 districts). They are loaded with:

```bash
cd backend
python -m app.ingres.real_import          # idempotent; loads states/*.csv
```

or automatically at boot by setting `SEED_REAL_DATA=true` in `.env`. Real rows are stored
`is_demo=False` and carry provenance (source file, extraction method, PDF page numbers, URLs).
The API resolves a per-scope dataset mode:

- `auto` (default) — serves **real** data for any state/district/village that has it, otherwise
  falls back to the synthetic demo set. Preference is decided on assessment *records* (not bare
  unit rows), so a scope whose real units carry no assessment data (e.g. a partial import) also
  falls back to demo instead of returning an empty aggregate;
- `real` / `demo` / `all` — force the dataset via the `data_source` query parameter on
  `/api/groundwater/*`, `/api/analytics/*` and `/api/gis/*` endpoints.

Summary responses include `is_demo` and `source` so the UI can label figures correctly. The real
set is single-year (2025), so multi-year trends and forecasts still use the full available
history (labelled as statistical estimates).

### Live government data (CGWB telemetry + IMD rainfall)

On top of the CSV baseline, the app can pull **live** readings straight from government APIs:

- **Groundwater levels** — CGWB Digital Water Level Recorder (DWLR) telemetry, 6-hourly, via the
  National Water Data Portal (`nwdp.nwic.gov.in`). Open API, **no key required**.
- **District rainfall** — IMD `api.imd.gov.in` (needs a free API key + IP whitelisting).

When `LIVE_DATA_ENABLED=true`, the backend syncs once at boot and then every
`LIVE_SYNC_INTERVAL_MINUTES` (default 360). Each telemetry station is matched to its village
(exact name in the same district, else nearest within `LIVE_STATION_MATCH_RADIUS_KM`, default
15 km) and its freshest depth is written into the `CGWB Telemetry & IMD Rainfall (Live)`
dataset as a `groundwater_levels` row; IMD rainfall becomes `groundwater_rainfall`. Re-syncing
replaces the previous live snapshot, so the process is idempotent and the annual CSV baseline is
never touched.

```bash
python -m app.ingres.live                 # manual sync (all states)
python -m app.ingres.live --states telangana
```

or via the admin API `POST /api/admin/datasets/sync-live?states=telangana`. Add your IMD key to
`.env` (`IMD_API_KEY=...`) to enable the rainfall half; without it, rainfall is skipped and the
water-level sync still runs.

### Live weather forecast

The web app's **Live Weather** page (`/weather`) shows current conditions and a multi-day
outlook (up to 7 days) for any state, district or village, plus a map marker. Forecasts come
from **official IMD data** (India Meteorological Department, `api.imd.gov.in`) when an
`IMD_API_KEY` is configured — city 7-day forecast + station observations, nearest station
selected by distance. Without a key, the app falls back to Open-Meteo (free, no key;
GFS/ICON/IFS models) and labels the response as **not** official IMD data. The endpoint is
`GET /api/weather/forecast?state=&district=&village=&days=`. IMD does not publish hourly
forecasts, so the hourly strip is only shown for the Open-Meteo fallback.

---

## Quick start

Prerequisites: Docker with Compose v2.

```bash
cp .env.example .env   # edit values if needed
docker compose up --build
```

Then open:

- Web app: http://localhost:5173
- Backend API docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/api/health

Demo accounts (dev only, created on first boot — configure via `SEED_ADMIN_EMAIL`, `SEED_ADMIN_PASSWORD`, `SEED_USER_EMAIL`, `SEED_USER_PASSWORD` in `.env`):

| Role  | Email           |
|-------|-----------------|
| Admin | admin@ingres.in |
| User  | user@ingres.in  |

> Change the default passwords before exposing publicly. Never commit `.env` with real secrets.

> When dependency lists change (`requirements.txt`, `package.json`) or you want a clean slate,
> run `docker compose down -v` first to recreate the anonymous node_modules volume and volumes.

---

## Local development (no Docker)

```bash
# Backend (SQLite, no PostGIS needed)
cd backend
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example ..\.env                        # then set DATABASE_URL=sqlite:///dev.db, ENABLE_GEOMETRY=false, AUTO_CREATE_SCHEMA=true
python -m app.database.local_init                # create schema + seed demo data
uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend
cd ../frontend
npm install
npm run dev                                       # http://localhost:5173
```

Optional — Google Maps on the GIS page:

```bash
cd frontend
copy .env.example .env                            # set VITE_GOOGLE_MAPS_API_KEY
```

Without a key the GIS page falls back to the built-in SVG choropleth map. Restart `npm run dev`
after changing the key. Note the plotted positions are the synthetic demo unit centroids — not
official IN-GRES/CGWB coordinates.

Backend tests:

```bash
cd backend
.venv\Scripts\python -m pytest                    # 130 tests
```

Frontend checks:

```bash
cd frontend
npm run typecheck                                 # tsc --noEmit
npm test                                          # vitest (5 tests)
npm run build                                     # production bundle
```

To enable LLM answers (optional — the heuristic assistant works without one):

```text
# Local & keyless (Ollama):  LLM_PROVIDER=ollama
# Fastest cloud free tier:   LLM_PROVIDER=groq + LLM_API_KEY=gsk_...
LLM_ENABLED=true
LLM_PROVIDER=ollama          # ollama | groq | openai | gemini | mistral
LLM_API_KEY=                 # only needed for cloud providers
LLM_MODEL=                   # blank = per-provider default (e.g. qwen2.5:3b / openai/gpt-oss-120b)
```

The client speaks the OpenAI-compatible chat protocol and walks a **backend
chain**: if a cloud provider has no key or is unreachable, it transparently
falls back to local Ollama (`http://localhost:11434/v1`). Conversation history
is passed to every call so follow-up questions ("what about Guntur?") are
understood in context. Structured groundwater numbers never come from the LLM.

---

## Architecture

```text
                        USER
                          |
              +-----------+-----------+
              |           |           |
           TEXT        VOICE (web)   PHONE CALL
              |           |           |
              |           STT         |
              |           |      Telephony provider
              +-----------+-----------+
                          |
                   LANGGRAPH ORCHESTRATOR
                          |
        +-----------+-----+-----+-----------+
        |           |           |           |
      Intent     Data       RAG         GIS
      Agent     Agent      Agent       Agent
        |           |           |           |
        |    PostgreSQL    Qdrant/    PostGIS
        |                 pgvector       |
        +-----------+-----+-----+-----------+
                          |
                    RESPONSE AGENT
                          |
                   +------+------+
                   |             |
                 TEXT           TTS
                          Telugu/Hindi/English
                          |
                        USER
```

---

## Technology stack

| Layer        | Technology                                              |
|--------------|---------------------------------------------------------|
| Frontend     | React, TypeScript, Vite, Tailwind CSS, shadcn/ui-style components, React Router, Axios, Lucide |
| Backend      | Python, FastAPI, Pydantic, SQLAlchemy, Alembic, WebSockets |
| Database     | PostgreSQL + PostGIS (Docker), SQLite (local dev)        |
| AI           | Dependency-free graph orchestrator mirroring LangGraph, RAG (BM25 over knowledge docs), configurable LLM via OpenAI-compatible API (e.g. Ollama) |
| Voice        | Telephony/STT/TTS provider abstractions (simulation + Twilio), Web Speech API in the browser |
| Infrastructure| Docker, Docker Compose, Redis                            |

---

## Project structure

```text
ingres-ai/
├── frontend/            # React + Vite SPA (nginx production build)
│   └── src/
│       ├── components/  # ui/, layout, BarChart/LineChart/Choropleth, protected route
│       ├── pages/       # Landing, Login, Register, Dashboard, Assistant, GIS, Reports, History, Voice, Expert, Admin, Groundwater
│       ├── services/    # api + auth/chat/gis/reports/analytics/expert/admin/voice clients
│       ├── contexts/    # AuthContext, LanguageContext (EN/TE/HI)
│       ├── types/ utils/ hooks/
│       └── App.tsx
├── backend/
│   ├── app/
│   │   ├── api/         # FastAPI routers (auth, chat, groundwater, gis, voice, reports, analytics, predictions, expert, admin, rag)
│   │   ├── ai/          # graph orchestrator + assistant (language/intent/location/metric extraction)
│   │   ├── ingres/      # groundwater domain service/queries/terminology + national dataset
│   │   │   │            #   india_data.py (states/districts/village generator),
│   │   │   │            #   national_seed.py (bulk all-India seeding)
│   │   ├── rag/         # BM25 retriever + LLM client
│   │   ├── gis/ voice/  # GIS geojson service, telephony providers
│   │   ├── models/      # SQLAlchemy models
│   │   ├── schemas/     # Pydantic schemas
│   │   ├── database/    # engine, session, seed, local_init
│   │   ├── core/        # security, config, audit
│   │   └── main.py
│   ├── tests/           # pytest suite (130 tests)
│   ├── migrations/      # Alembic migrations
│   ├── requirements.txt
│   └── Dockerfile
├── data/                # raw / processed / geo / demo datasets
├── knowledge/           # RAG documents
├── docker-compose.yml
└── .env.example
```

---

## Development roadmap (phases)

| Phase | Scope                                                            | Status    |
|-------|------------------------------------------------------------------|-----------|
| 1     | Project setup, Docker, Postgres/PostGIS, FastAPI, React, auth foundation | ✅ Done |
| 2     | Authentication & RBAC polish, user dashboard                       | ✅ Done   |
| 3     | Groundwater database, demo dataset, groundwater APIs               | ✅ Done   |
| 4     | AI chat, language/intent/location/metric extraction                | ✅ Done   |
| 5     | Graph-based orchestration (LangGraph-compatible)                   | ✅ Done   |
| 6     | RAG (knowledge documents, BM25 retrieval, optional LLM)            | ✅ Done   |
| 7     | GIS (GeoJSON map API + choropleth UI)                              | ✅ Done   |
| 8     | Charts and reports (CSV/PDF export)                                | ✅ Done   |
| 9     | Multilingual support (EN/TE/HI UI + assistant)                     | ✅ Done   |
| 10    | Web voice (Web Speech API mic + TTS)                               | ✅ Done   |
| 11    | Phone voice (simulation + Twilio providers, IVR-style flows)       | ✅ Done   |
| 12    | Expert assistance (escalation + resolution workflow)               | ✅ Done   |
| 13    | Admin console (users, datasets, audit log)                         | ✅ Done   |
| 14    | Analytics (trends, district ranking, auto insights)                | ✅ Done   |
| 15    | Testing (pytest backend suite, frontend typecheck + build)         | ✅ Done   |
| 16    | Docker deployment hardening (non-root, healthchecks, CSP, limits)  | ✅ Done   |
| 17    | Data import pipeline, semantic RAG, chat memory, alerts & notifications, PWA | ✅ Done |
| 18    | Real telephone integration (Twilio/Exotel/Plivo abstraction, STT/TTS, voice pipeline, media streaming, admin voice dashboard) | ✅ Done |
| 19    | Prediction & ML (statistical time-series forecasting: linear trend, moving average, exponential smoothing; 95% confidence bands, risk classification, forecast page + API) | ✅ Done |
| 22    | Assistant feedback loop & conversation workflow (👍/👎 message ratings, answer regeneration, contextual follow-up suggestions, Markdown conversation export, error retry) | ✅ Done |
| 23    | Question-understanding pipeline, Groq-native web search, admin command centre, registration CAPTCHA, voice auto language detection | ✅ Done |
| 24    | Comparison workspace, data-quality anomaly engine + admin review workflow, scheduled reports & email digests | ✅ Done |
| 25    | Scenario Studio (what-if sliders, baseline vs scenario projections, saved scenarios) | ✅ Done |
| 26    | Village-friendly visualisation pass: big stat cards with icons, water-level gauge with plain status words, trend chips, "What does this mean?" explanations, EN/TE/HI | ✅ Done |

---

## Telephone integration

Real phone calls connect to the **same LangGraph AI brain** as the web app —
only the input/output adapters differ.

```
Phone call -> Telephony webhook (/api/voice/incoming) -> WebSocket media stream
  -> STT -> language detect (en/te/hi) -> LangGraph orchestrator
  -> data/RAG/GIS/expert -> TTS -> back to the caller
```

- **Providers:** `TELEPHONY_PROVIDER` = `twilio | exotel | plivo | mock`.
  The provider abstraction lives in `backend/app/voice/telephony/`; swap vendors
  without touching the AI pipeline (`backend/app/voice/pipeline.py`).
- **Endpoints:** `POST /api/voice/incoming`, `POST /api/voice/status`,
  `WS /api/voice/stream`, `POST /api/voice/test`, `POST /api/voice/escalate`,
  `POST /api/voice/link`, `GET /api/voice/calls`, `GET /api/voice/calls/{id}/transcript`,
  `GET /api/voice/analytics`, `GET /api/voice/config`.
- **Privacy:** caller numbers are stored masked (`+91******1234`) and hashed;
  audio recording is off unless `VOICE_RECORDING_ENABLED=true`.
- **Webhook security:** Twilio/Exotel/Plivo signatures are validated when
  credentials are configured.
- **Admin dashboard:** `/admin/voice` — call log, transcripts, analytics,
  connection test, and an end-to-end Telugu voice test.
- **Local dev:** no credentials needed (`mock` provider); the simulator runs a
  scripted call through the same pipeline.
- **Free voice stack (no API keys):** `STT_PROVIDER=vosk` (local, offline;
  models in `backend/voice_models/` for English/Telugu/Hindi) or `whisper`
  (faster-whisper, downloads from Hugging Face) and `TTS_PROVIDER=edge`
  (Microsoft Edge neural voices). Install: `pip install -r requirements.txt`,
  then grab the small Vosk models from https://alphacephei.com/vosk/models
  and extract them under `backend/voice_models/`.
  The dev `.env` already points at `vosk` + `edge`.

---

## Forecasting (Phase 19)

The **Forecast** page (`/forecast`) and `GET /api/predictions/forecast` project
groundwater metrics for any scope (state, district or village) using pure-Python
statistical time-series models — no external ML dependencies:

- `linear` — ordinary least-squares trend extrapolation with a 95% prediction
  interval and R² goodness-of-fit.
- `moving_average` — trailing-window mean carried forward.
- `exponential` — simple exponential smoothing carried forward.
- `arima` — ARIMA(1,1,0) fit in pure NumPy.
- `holt` — double exponential smoothing with trend.
- `auto` — walks a hold-out window across all methods and picks the best by
  RMSE (reported via `best_method`). `GET /api/predictions/compare` runs every
  model and returns per-method RMSE/MAE/MAPE plus a recommendation.

All projections are clearly labelled as statistical estimates derived from the
current dataset (synthetic demo or user-imported), never official IN-GRES/CGWB
forecasts. For the stage-of-extraction metric the service also classifies the
projected end-of-horizon category (safe / semi-critical / critical /
over-exploited) and, when the trend is rising, estimates the years until the
over-exploited threshold (100%) is crossed.

```text
GET /api/predictions/forecast?state=Telangana&district=Warangal&metric=stage&horizon=5&method=auto
```

---

## Phase 20

### Knowledge base explorer

The **Knowledge** page (`/knowledge`, "RAG") turns the document store into a
browsable, administrable resource:

- `GET /api/rag/documents` — list stored documents with chunk counts.
- `POST /api/rag/documents` — admins upload a `.md`/`.txt` file; it is
  chunked and embedded into the knowledge base.
- `DELETE /api/rag/documents/{id}` — admins remove a document (and its file).
- `GET /api/rag/search` — now returns rich metadata (`document_title`,
  `section`, `source`, `score`, `file_path`) per chunk.

### PWA offline + push notifications

The frontend is now an installable PWA (service worker, app manifest,
offline asset precaching) that also caches `GET /api` reads with
NetworkFirst so the app keeps working offline. Web push alerts are wired to
the existing alert engine:

- `GET /api/push/config` — advertises VAPID public key / availability.
- `POST /api/push/subscribe` / `DELETE /api/push/subscribe` — manage a
  device subscription (`PushSubscription` table).
- `backend/app/services/push.py` — generates and persists VAPID keys
  (`data/vapid-keys.json`) and sends notifications on alert creation.
- Enabled with `WEB_PUSH_ENABLED=true` (and `WEB_PUSH_EMAIL`); requires
  HTTPS. See `.env.example`.

### GIS time-lapse & comparison

The **GIS Map** page gained a year time-lapse and a two-year comparison:

- A year slider with play/pause animates through all assessment years.
- `GET /api/gis/compare` and `GET /api/gis/compare/india` return a
  FeatureCollection whose features carry `metric_value_a`, `metric_value_b`,
  `delta`, `category_a`, `category_b` and `category_changed`, so the map can
  colour the change and show it in popups.

### Assistant multi-script language support

The assistant detects and answers in **nine Indian scripts**, not just English:

- Telugu, Hindi/Marathi (Devanagari), Tamil, Kannada, Malayalam, Bengali/Assamese,
  Gujarati, Punjabi (Gurmukhi) and Odia.
- State names are recognised in their own regional scripts **and** the common
  national ones (Devanagari, Telugu, Tamil, Kannada, Malayalam, Bengali, Gujarati,
  Punjabi, Odia), including case-marked locative forms (e.g. `தமிழ்நாட்டில்`,
  `కర్ణాటకలో`, `ଓଡ଼ିଶାରେ`).
- Every state/UT also resolves by its canonical English name, so scopes like
  Mizoram, Ladakh, Tripura or Goa work without a regional alias. A question that
  mentions a state is always treated as a data query (e.g. "What is the
  groundwater situation in Mizoram?") rather than a terminology lookup.
- Greetings, thanks, help, recommendation, why and metric keywords are covered
  across the scripts, and message tokenisation preserves every script.
- With an LLM configured (`LLM_ENABLED=true`), the final answer is translated into
  the user's language via `app.rag.llm.translate`, keeping all figures, units and
  line structure verbatim. Without an LLM the assistant still classifies and
  answers in English with the detected language recorded.

### Assistant forecast, scenario & data-source answers

The **AI Assistant** now embodies the modelling workflow from the system
proposal:

- **Forecast / trend questions** ("predicted trend in Telangana", "next 5
  years", "by 2030") run the forecast engine with `method=auto` and answer with
  the projected value, a 95% confidence band, direction, R² and the validated
  model (RMSE) — always labelled as a statistical estimate, never an official
  IN-GRES/CGWB projection.
- **What-if scenarios** ("what if pumping increases 10%?", "what if recharge
  decreases 20%?") re-forecast the series with the extraction/recharge scaled by
  the stated percentage and report the projected change versus the baseline.
  Scenario support is in `predict.forecast(..., scenario=...)`.
- **Data-source & reliability questions** are answered from new knowledge-base
  documents (`knowledge/documents/data-sources.md` and
  `modeling-approach.md`) covering CGWB, IMD, CWC/NWDP, NRSC/Bhuvan, NASA
  GRACE/SMAP, soil, socio-economic and policy data — resolution, frequency,
  access and quality caveats.
- Explainability (fit metrics and selected model) is surfaced in every
  forecast/scenario answer.

---

## Phase 21

### River-basin scopes

Forecasting, backtesting and summaries now accept an **Indian river basin**
scope, using the 20 major basins of the Central Water Commission:

- `backend/app/ingres/basins.py` maps each basin (Ganga, Godavari, Krishna,
  Cauvery, Mahanadi, Narmada, Tapi, …) to the states it covers and, where a
  state drains into more than one basin, the specific districts. Aggregation
  only ever uses assessment data that exists in the database.
- `GET /api/predictions/basins` lists every basin with its states, district
  coverage, and latest-year stage summary (`list_basins`).
- `/api/predictions/forecast` and `/api/predictions/compare` accept `basin=<name>`
  (e.g. `Krishna`, `Godavari`); a basin forecast aggregates the
  stage/extraction/recharge series across the basin's districts.
- The **AI Assistant** recognises basin names in free text ("Godavari basin",
  "Krishna river basin") and runs forecast / scenario answers over the basin,
  resolving them before district names (a "Krishna" district never shadows the
  Krishna basin).
- `GET /api/predictions/backtest` walks the held-out years and compares models
  with RMSE/MAE/MAPE plus probabilistic skill (CRPS, direction accuracy).

### Deep-learning forecasting (optional torch)

`backend/app/ingres/ml_forecast.py` adds LSTM and Transformer forecasters plus
**transfer learning** — a basin/state-wide model is pre-trained on the pool
series and fine-tuned on the scope:

- `method` values `lstm`, `transformer` and `ml` (best available) select the
  deep-learning models; `transfer=true` pre-trains on the containing
  state/basin before fine-tuning; `epochs` controls the training budget.
- Deep learning is **optional**: install `backend/requirements-ml.txt`
  (`pip install -r requirements-ml.txt`, pulls PyTorch). Without torch the
  requested ML method transparently falls back to the best validated
  statistical model with a note explaining why.
- The Dockerfile builds the ML stack when `INCLUDE_ML=1`
  (`docker compose build --build-arg INCLUDE_ML=1`); the docker-compose
  `backend` service forwards the `INCLUDE_ML` build arg (default off).
- The Forecast page exposes basin selection, ML methods, a normal vs.
  bootstrap band, transfer learning and a backtest card when the backend has
  torch; otherwise the ML controls degrade gracefully.

### CI/CD

`.github/workflows/ci.yml` runs on every push/PR to `main`:

- **backend** — installs `requirements.txt` on Python 3.12 and runs the full
  pytest suite (SQLite test database; no external services).
- **frontend** — `npm ci`, `tsc --noEmit`, `vitest run`, `vite build`.
- **docker** — builds the backend image both with and without the ML stack
  (`INCLUDE_ML=1`) to catch Dockerfile regressions early.

---

## Phase 22

### Assistant feedback loop & conversation workflow

- **Message ratings** — `POST /api/chat/messages/{id}/feedback` stores a
  👍/👎 rating (and optional note) on assistant answers; thumbs buttons appear
  in the chat action bar and persist with the message.
- **Answer regeneration** — `POST /api/chat/conversations/{id}/regenerate`
  re-answers the latest question through the same orchestrator, replacing the
  previous reply (refresh button on the newest answer).
- **Follow-up suggestions** — every data/forecast/scenario/recommend/terminology
  answer carries up to three deterministic next questions derived from the
  resolved scope (`app/ai/followups.py`), rendered as clickable chips that send
  the question through the normal flow. They are stored on the message so they
  survive reloads.
- **Conversation export** — `GET /api/chat/conversations/{id}/export`
  downloads the full transcript (with sources, follow-ups and data-labelling
  footer) as Markdown; "Export" button in the chat header.
- **Error retry** — failed sends keep an inline Retry button that resends the
  original question once connectivity returns.

---

## Phase 23

### Question understanding & answer-shape matching

The orchestrator now follows an understand-first pipeline
(`backend/app/ai/orchestrator.py`):

- **Ambiguity clarification** — data questions referencing unresolved places
  ("how is the situation *there*?") get one short clarifying question instead
  of a misleading all-India aggregate. Locations carried from earlier turns
  still resolve silently.
- **WHETHER verdicts** — "Is the stage rising in Telangana?" leads with a real
  Yes/No computed from the historical series, then evidence.
- **In-chat comparisons** — "Compare groundwater in A and B" renders a markdown
  indicator table (recharge/extraction/stage/category/units) from dataset
  aggregates plus a better/worse verdict; unresolvable sides fall back to web.
- **Entity-enriched RAG** — retrieval queries are extended with the resolved
  state/district/metric so documents match the actual question.
- The LLM system prompt encodes the full answer-type matrix (WHAT/WHY/WHEN/
  WHERE/HOW/WHETHER/HOW MUCH/comparison/prediction), direct-answer-first
  structure, numbers-with-context, and never-answer-a-different-question rules.

### Groq-native internet search

- Questions the KB can't answer go to **`openai/gpt-oss-120b`** with Groq's
  built-in `browser_search` tool (server-side, Exa-powered), which browses
  the live web itself; visited URLs are extracted from its tool log and shown
  as source chips in the chat. DuckDuckGo (`ddgs`) + `gpt-oss-120b` remain as
  an explicit fallback chain, then local Ollama. Transient 413/429 responses
  are retried with backoff honouring `Retry-After`; permanent 400/401/404
  (e.g. decommissioned model) fail over immediately. (`groq/compound` was
  retired 2026-09-21 and is no longer used.)
- Provider presets in `app/config.py`: `ollama | groq | openai | gemini |
  mistral` — set `LLM_PROVIDER` (+ key) and everything else auto-resolves.
  Override the search pass with `LLM_SEARCH_MODEL` (e.g. `openai/gpt-oss-20b`
  for a faster/cheaper search).

### Registration CAPTCHA

Self-hosted signed arithmetic CAPTCHA (`app/core/captcha.py`): noisy SVG
question + HMAC-signed expiring token, verified statelessly on signup. No
third-party keys. Toggle: `REGISTRATION_CAPTCHA_ENABLED`.

### Voice: automatic language detection

Mic mode defaults to **Auto-detect**: audio is transcribed by local Whisper
(`STT_PROVIDER=whisper`, faster-whisper) which detects Telugu/Hindi/English by
itself; the assistant replies in that language and speaks it back. Fixed
languages use fast live browser dictation instead.

### Admin Groundwater Command Center

`/admin` is now a tabbed operations console: Overview (live stat cards +
interactive India map + critical zones), Data (import + registry),
AI/RAG status & re-indexing, Model validation metrics (cached walk-forward
backtests per state/metric), AI query monitor (intents, feedback, recent
answers), Users, and Audit log. Powered by `GET /api/admin/overview`,
`GET /api/admin/queries` and `GET /api/admin/models/metrics`.

### Other upgrades

- Silent JWT refresh in the web client (401 → refresh → retry) so sessions
  survive access-token expiry; bulk conversation delete with select-all;
  mic-tap stops TTS instantly; markdown tables render inside chat bubbles.

---

## Phase 24

### Comparison workspace

The new **Compare** page (`/compare`) puts any 2–4 scopes side-by-side:

- Each slot resolves a **state, district, village or river basin** (cascading
  pickers; basins come from the CWC list). `GET
  /api/comparison/metrics?scopes=state:Telangana,basin:Krishna,…` returns per-
  scope latest-year summaries (`get_summary`), full annual trend series and an
  overall **better/worse verdict** based on the final-year stage of extraction.
- The workspace renders a metric table (units / recharge / extraction / stage /
  dominant category with badges), multi-series trend charts (stage, recharge,
  extraction — new `MultiLineChart` SVG component), and a latest-stage bar
  comparison. Unresolvable scopes are labelled instead of silently dropped.

### Data-quality anomaly engine

`app/services/data_quality.py` scans observations for problems and stores them
as reviewable `AnomalyFlag` rows (fingerprints make re-scans idempotent):

- **Rules:** impossible stage values (<0% or >200%), negative recharge/
  extraction volumes, category labels inconsistent with the numeric stage,
  extraction ≫ recharge while reporting a sane stage, |z|>4 statistical
  outliers within each district+year cohort, implausible water-level depths and
  monthly rainfall totals.
- **Review workflow:** `GET/POST /api/quality/*`, `PATCH
  /api/quality/flags/{id}` (open → acknowledged → resolved/dismissed, with
  notes + audit log). New high-severity findings notify admins in-app.
- **Dashboard:** Admin → **Data Quality** tab — open/high-severity/resolved
  cards, last scan time, "Scan now" button and a filterable flag table.

### Scheduled reports & email digests

Users can subscribe any scope to a recurring PDF digest (Reports → **Scheduled
reports** tab):

- `ReportSchedule` rows are processed by a background loop in `app.main`
  (mirroring the live-sync loop): due schedules render through the existing
  assessment-report pipeline, are stored under `data/scheduled_reports/`
  (3 newest kept) and emailed via SMTP when configured.
- Endpoints under `/api/reports/schedules`: list (admins see all with
  `?all=true`), create (scope-validated, recipient emails validated),
  update/pause, delete (removes stored files), **run now** for an immediate
  issue, and download-latest.
- Enabled with `SCHEDULED_REPORTS_ENABLED=true`; email delivery additionally
  needs the SMTP settings. Without SMTP the PDFs are still generated and
  downloadable from the UI. `QUALITY_SCAN_ON_BOOT` optionally runs an anomaly
  scan at startup.

---

## Phase 25

### Scenario Studio

The new **Scenario Studio** page (`/studio`) turns the assistant's what-if
answers into a hands-on workspace:

- Pick any state/district/village or river basin, a metric (stage / recharge /
  extraction), horizon, model and confidence band.
- Two sliders set the **extraction (pumping)** and **recharge** change in
  percent; for the stage metric both combine multiplicatively
  (factor = (1+e)/(1+r)). Presets ("-20% pumping", "+10% pumping · drier
  recharge") give quick starting points.
- `GET /api/predictions/scenario-compare` runs the baseline and the modified
  projection through the same validated forecast engine in one call and
  returns both plus a delta block (end values, absolute/percent difference,
  risk category shift). The UI renders side-by-side forecast charts with
  confidence bands and colour-coded difference cards.
- Scenarios can be saved (`SavedScenario` table + `/api/scenarios` CRUD) with
  just their inputs — reloading always recomputes on the latest data.

As everywhere else, projections are statistical estimates from the labelled
dataset, never official IN-GRES/CGWB forecasts.

---

## Environment variables

See [`.env.example`](./.env.example). Never commit `.env`.

## Safety & data trust

- Never hallucinate groundwater numbers or invent official data.
- Always show source / year where applicable.
- Demo/synthetic data is always clearly labelled.
- If information is unavailable, the assistant says so and may escalate to a human expert.
