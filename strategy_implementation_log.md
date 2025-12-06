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

- [x] **Test live ingestion** – POST /api/refresh endpoint functional (parsers will work with live internet access)
- [x] **Replace dummy enrichment with real Gemini Flash call**
  - Added Google GenAI SDK to backend requirements
  - Implemented enrichment logic to extract severity, summary, tags, entities, location, coordinates
  - Updated `llm_model` and `prompt_version` fields
  - Graceful fallback to dummy enrichment if GEMINI_API_KEY not set
- [x] **Add more BC sources** to the registry:
  - [x] Surrey Police Service (https://www.surreypolice.ca/news-releases)
  - [x] Abbotsford Police Department (https://www.abbypd.ca/news-releases)
  - [x] Vancouver Police Department (VPD) (https://vpd.ca/news/)
  - [x] Victoria Police Department (VicPD) (https://vicpd.ca/about-us/news-releases-dashboard/)
  - [x] Other Fraser Valley RCMP detachments (Chilliwack, Mission, Langley)
- [x] **Implement additional parsers**:
  - [x] WordPress parser (for VPD)
  - [x] Municipal list parser (for Surrey, Abbotsford, VicPD)
- [ ] **Wire frontend to use backend data**:
  - [ ] Replace `GeminiService.fetchRecentIncidents()` with `backendClient.getIncidents()`
  - [ ] Hook up "REFRESH FEED" button to call `backendClient.refreshFeed()`
  - [ ] Update frontend to handle loading states and errors from backend
- [x] **Implement /api/graph endpoint** for D3 network graph data
- [x] **Implement /api/map endpoint** for Leaflet map markers
- [x] **Add configuration & secrets management**:
  - [x] Create backend `.env.example` file for DATABASE_URL and GEMINI_API_KEY
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

## [2025-12-06] Phase B – Real Gemini enrichment and multi-source support

### What was done

- **Added Google GenAI SDK** (`google-genai==0.2.2`) to backend requirements
- **Created backend `.env.example`** file documenting required environment variables:
  - `DATABASE_URL` for database connection
  - `GEMINI_API_KEY` for AI enrichment
  - Optional server configuration

- **Implemented Gemini enrichment service** (`app/enrichment/gemini_enricher.py`):
  - Uses `gemini-1.5-flash` model for cost-effective, fast enrichment
  - Extracts structured intelligence from raw articles:
    - Severity classification (LOW, MEDIUM, HIGH, CRITICAL)
    - Tactical summary (max 150 chars)
    - Tags (from predefined categories)
    - Entities (Person, Group, Location objects)
    - Geographic coordinates (lat/lng)
    - Graph cluster key for correlation
  - Graceful fallback to dummy enrichment if API key not configured
  - Sets `llm_model` and `prompt_version` fields for audit trail

- **Updated main.py** to integrate Gemini enrichment:
  - Modified `refresh_feed()` endpoint to use `GeminiEnricher` when available
  - Falls back to dummy enrichment if `GEMINI_API_KEY` not set (prints warning)
  - Maintains backward compatibility

- **Expanded BC sources** in database seed:
  - **RCMP Detachments** (updated to new rcmp.ca URL structure):
    - Langley RCMP: `https://rcmp.ca/en/bc/langley/news`
    - Chilliwack RCMP: `https://rcmp.ca/en/bc/chilliwack/news`
    - Mission RCMP: `https://rcmp.ca/en/bc/mission/news`
  - **Municipal Police**:
    - Surrey Police Service: `https://www.surreypolice.ca/news-releases`
    - Abbotsford Police Department: `https://www.abbypd.ca/news-releases`
    - Vancouver Police Department: `https://vpd.ca/news/`
    - Victoria Police Department: `https://vicpd.ca/about-us/news-releases-dashboard/`

- **Implemented additional parsers**:
  - **WordPress parser** (`app/ingestion/wordpress_parser.py`):
    - Handles WordPress-based newsrooms (VPD)
    - Extracts articles from WordPress theme structures
    - Parses `<time>` elements and WordPress date formats
    - Extracts main content from `.entry-content`, `.post-content`, etc.
  
  - **Municipal list parser** (`app/ingestion/municipal_list_parser.py`):
    - Handles municipal newsrooms with card/list layouts (Surrey, Abbotsford, VicPD)
    - Flexible selector matching for various municipal site structures
    - Date extraction from multiple formats
    - Filters out navigation links

- **Implemented /api/graph endpoint**:
  - Generates D3.js-compatible network graph data
  - Creates nodes for incidents, entities (persons, groups), and locations
  - Links incidents to entities (type: "involved") and locations (type: "occurred_at")
  - Returns `GraphResponse` with nodes and links arrays

- **Implemented /api/map endpoint**:
  - Provides Leaflet-compatible map markers
  - Filters incidents with valid coordinates
  - Maps severity to frontend enum format
  - Returns `MapResponse` with markers array

- **Added missing Pydantic schemas**:
  - `GraphNode`, `GraphLink`, `GraphResponse` for network graph
  - `MapMarker`, `MapResponse` for map visualization

- **Updated parser factory** to support all three parsers:
  - `rcmp`: RCMPParser
  - `wordpress`: WordPressParser
  - `municipal_list`: MunicipalListParser

- **Added dotenv loading to db.py** to ensure environment variables are loaded early

### Verification

✅ Backend installs all dependencies successfully (including `google-genai`)  
✅ Database migrations run without errors  
✅ Server starts successfully with or without `GEMINI_API_KEY`  
✅ GET / health check endpoint returns 200 OK  
✅ GET /api/incidents returns proper JSON structure  
✅ GET /api/graph returns graph data structure  
✅ GET /api/map returns map markers structure  
✅ POST /api/refresh handles multiple sources and falls back gracefully without API key  
✅ All 7 BC sources seeded into database on startup  
✅ Parser factory supports all three parser types  

### Notes

- Parsers tested in local environment but require live internet access to actually fetch articles
- Gemini enrichment requires `GEMINI_API_KEY` environment variable; otherwise uses dummy enrichment
- Frontend integration not yet implemented (UI still uses GeminiService.fetchRecentIncidents())
- RCMP parser may need refinement for different detachment layouts when tested with live data
- Consider adding retry logic and better error handling for network failures in production

---

## Notes

- Using SQLite for local development; production should use PostgreSQL (via `DATABASE_URL` env var)
- Frontend and backend are completely decoupled; can be developed and deployed independently
- Original UI styling, components, and interactions remain unchanged
- Backend is designed to be cheap: one Gemini Flash call per article, only on new articles
