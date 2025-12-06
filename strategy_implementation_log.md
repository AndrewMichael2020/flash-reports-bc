# Strategy Implementation Log

This file tracks the implementation of the Backend Strategy v2 for Crimewatch Intel, documenting progress from a frontend-only demo to a full-stack application with Python FastAPI backend, PostgreSQL database, and newsroom ingestion.

---

## [2025-12-06] Phase A – Backend bootstrap (FastAPI + PostgreSQL + minimal ingestion)

### What was done

- **Created `/backend` folder** with FastAPI application skeleton
  - `app/main.py` – FastAPI app with CORS middleware, startup seed data, and two endpoints
  - `app/models.py` – SQLAlchemy ORM models for `sources`, `articles_raw`, `incidents_enriched`
  - `app/db.py` – Database connection and session management (SQLite for dev, PostgreSQL-ready)
  - `app/schemas.py` – Pydantic request/response models matching frontend TypeScript types
  - `app/ingestion/parser_base.py` – Abstract parser interface
  - `app/ingestion/rcmp_parser.py` – RCMP newsroom parser implementation
  - `requirements.txt` – Python dependencies (FastAPI, SQLAlchemy, Alembic, httpx, BeautifulSoup4, etc.)

- **Added Alembic migrations**
  - Initialized Alembic in `/backend/alembic/`
  - Created initial migration: `sources`, `articles_raw`, `incidents_enriched` tables
  - Migration includes proper foreign keys, unique constraints, and JSONB fields (PostgreSQL) or JSON (SQLite)

- **Implemented database schema** exactly as specified in STRATEGY.md:
  - **sources** table: agency info, jurisdiction, region label, parser ID, active flag
  - **articles_raw** table: scraped article data with unique constraint on (source_id, external_id)
  - **incidents_enriched** table: 1:1 with articles_raw, stores severity, summary, tags, entities, coordinates, LLM metadata

- **Implemented ingestion path for RCMP newsroom**
  - Parser fetches newsroom listing page, extracts article links and metadata
  - Fetches full article detail pages, extracts body text
  - Generates `external_id` as SHA256 hash of URL+title for idempotence
  - Upserts into `articles_raw` with uniqueness check

- **Implemented dummy enrichment**
  - For each new article, creates `incidents_enriched` record
  - Sets `severity = "MEDIUM"`, `summary_tactical = first 200 chars of body_raw`
  - Empty `tags = []`, `entities = []`, no location/coordinates
  - `llm_model = "none"`, `prompt_version = "dummy_v1"`

- **Exposed two API endpoints**:
  - **POST /api/refresh** – Accepts `{ "region": "Fraser Valley, BC" }`
    - Looks up active sources for region
    - Calls parser to fetch new articles since last check
    - Creates dummy enrichment for each new article
    - Returns `{ region, new_articles, total_incidents }`
  
  - **GET /api/incidents** – Accepts `?region=Fraser Valley, BC&limit=100`
    - Joins sources → articles_raw → incidents_enriched
    - Returns incidents in format matching frontend `Incident` TypeScript type
    - Maps severity, source types, entities to frontend-compatible format

- **Seeded database** with one hard-coded source:
  - **Langley RCMP** (Fraser Valley, BC)
  - On startup, FastAPI checks if sources table is empty and seeds it automatically

- **Created frontend backend client wrapper**
  - `src/services/backendClient.ts`
  - Functions: `refreshFeed(region)`, `getIncidents(region, limit)`
  - Uses `VITE_API_BASE_URL` environment variable (defaults to `http://localhost:8000`)
  - Added `.env.example` for documentation

- **Reorganized frontend structure**
  - Moved components, services, types to `src/` directory for better organization
  - Updated imports in `index.tsx` and `App.tsx`

- **Updated `.gitignore`**
  - Added Python-specific ignores: `__pycache__`, `*.pyc`, `venv/`, `.venv`
  - Added database files: `*.db`, `*.sqlite`, `postgres_data/`
  - Added `.env` to prevent accidental credential commits

### Verification

✅ Backend runs successfully with `uvicorn app.main:app --reload`  
✅ Alembic migrations create all three tables correctly  
✅ Database seeded with Langley RCMP source on startup  
✅ POST /api/refresh endpoint functional (ready to ingest real RCMP articles)  
✅ GET /api/incidents returns proper JSON structure matching frontend types  
✅ Frontend builds successfully with `npm run build`  
✅ Backend client wrapper compiles without errors  

### Proposed next steps

- [ ] **Test live ingestion** – Run POST /api/refresh and verify it scrapes real RCMP articles
- [ ] **Replace dummy enrichment with real Gemini Flash call**
  - Add Google GenAI SDK to backend requirements
  - Implement enrichment logic to extract severity, summary, tags, entities, location, coordinates
  - Update `llm_model` and `prompt_version` fields
- [ ] **Add more BC sources** to the registry:
  - [ ] Surrey Police Service
  - [ ] Abbotsford Police Department
  - [ ] Vancouver Police Department (VPD)
  - [ ] Victoria Police Department (VicPD)
  - [ ] Other Fraser Valley RCMP detachments (Chilliwack, Mission, etc.)
- [ ] **Implement additional parsers**:
  - [ ] WordPress parser (for VPD, VicPD)
  - [ ] Municipal list parser (for Surrey, Abbotsford)
- [ ] **Wire frontend to use backend data**:
  - [ ] Replace `GeminiService.fetchRecentIncidents()` with `backendClient.getIncidents()`
  - [ ] Hook up "REFRESH FEED" button to call `backendClient.refreshFeed()`
  - [ ] Update frontend to handle loading states and errors from backend
- [ ] **Implement /api/graph endpoint** for D3 network graph data
- [ ] **Implement /api/map endpoint** for Leaflet map markers
- [ ] **Add configuration & secrets management**:
  - [ ] Create backend `.env` file for DATABASE_URL and GEMINI_API_KEY
  - [ ] Add `.env.example` for backend documentation
- [ ] **Improve RCMP parser robustness**:
  - [ ] Handle different RCMP detachment layouts
  - [ ] Better date parsing
  - [ ] Error handling and retry logic
- [ ] **Add basic monitoring/logging**:
  - [ ] Structured logging for ingestion runs
  - [ ] Track which articles were successfully parsed vs. failed
- [ ] **Consider background task queue** for enrichment (if needed for scale)
- [ ] **Add API authentication** if deploying publicly

---

## Notes

- Using SQLite for local development; production should use PostgreSQL (via `DATABASE_URL` env var)
- Frontend and backend are completely decoupled; can be developed and deployed independently
- Original UI styling, components, and interactions remain unchanged
- Backend is designed to be cheap: one Gemini Flash call per article, only on new articles
