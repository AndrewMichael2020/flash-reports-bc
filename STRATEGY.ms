# Crimewatch Intel – Backend Strategy (Police Newsroom Edition, v2)

> **Goal:** Keep the existing Crimewatch Intel UI *identical* while replacing the ad-hoc, client-side Gemini `googleSearch` flow with a **local, source-driven backend** built on **Python ingestion + FastAPI + PostgreSQL**, using **cheap Gemini Flash** only once per article.

This document is aligned with the current frontend described in the README:

- **Frontend:** React 19, Tailwind CSS, TypeScript
- **Visualization:** D3.js force-directed "Neural Link Graph", Leaflet.js dark-mode map
- **AI engine (today):** Google GenAI SDK with `gemini-2.5-flash` called from the client
- **UX:** Region dropdown, **REFRESH FEED** button, reports feed, threat HUD, entity mind map, geospatial map, and Tactical Analysis panel

The goal is to preserve this behaviour pixel-for-pixel while moving aggregation and intelligence work to the backend.

---

## 1. High-level architecture

### 1.1 Components

1. **Frontend (existing React 19 app)**  
   - Stays exactly as now:
     - Same React components, Tailwind styling, and layout.
     - Same D3 mind map and Leaflet map rendering.
     - Same user flow: select region → click **REFRESH FEED** → see updated incidents, graph, and map.
   - Only change: data comes from our API instead of direct Gemini calls.

2. **FastAPI backend (new)**  
   - Single service exposing REST endpoints to the UI.  
   - Owns:
     - Ingestion orchestration for a given region.
     - Calls to Gemini Flash for enrichment.
     - Access to PostgreSQL.

3. **PostgreSQL database (new)**  
   - Stores:
     - Static **source registry** (police newsrooms).
     - **Raw articles** (as scraped from newsroom pages).
     - **Enriched incidents** (LLM output consumed by the UI).
     - Optional cached graph JSON.

4. **Python ingestion & enrichment layer (new)**  
   - Library of “source parsers” (RCMP, municipal PD, generic list, WordPress, etc.).  
   - LLM enrichment worker that converts raw articles into structured incidents.

### 1.2 Trigger model

There is **no background cron** in v2.

- When the user presses **REFRESH FEED** in the React UI:
  1. Frontend calls `POST /api/refresh` with the selected region.
  2. Backend:
     - Pulls the static source list for that region.
     - Scrapes each newsroom for **new** articles only.
     - Runs Gemini Flash on *only those new articles*.
     - Persists results in PostgreSQL.
  3. Frontend then calls `GET /api/incidents?region=Fraser%20Valley%2C%20BC` and re-renders exactly as today.

For demo scale, a synchronous call is acceptable; if needed we can move enrichment to a background task runner later without changing the UI contract.

---

## 2. Data flow (end-to-end)

### 2.1 Refresh Feed

1. **UI action**  
   - User selects e.g. “Fraser Valley, BC” in the header dropdown.  
   - User clicks **REFRESH FEED** (top-right button).

2. **API call**  
   - Frontend sends:
     ```http
     POST /api/refresh
     Content-Type: application/json

     {
       "region": "Fraser Valley, BC"
     }
     ```

3. **Backend orchestration**

   For the supplied region:

   1. Load relevant **sources** from `sources` table (e.g., Langley RCMP, Abbotsford PD, Surrey Police Service).
   2. For each source:
      - Determine `since = max(published_at)` from `articles_raw` for that source.
      - Invoke the appropriate parser:
        ```python
        new_articles = parser.fetch_new(source, since=since)
        ```
      - Upsert new rows into `articles_raw`.
   3. For each *new* `articles_raw` row:
      - Call Gemini Flash with a compact prompt to produce:
        - `severity`
        - `summary_tactical`
        - `tags`
        - `entities`
        - `location_label`, `lat`, `lng`
        - `graph_cluster_key`
      - Insert into `incidents_enriched`.

4. **Return value**

   - The `POST /api/refresh` response gives:
     ```json
     {
       "region": "Fraser Valley, BC",
       "new_articles": 5,
       "total_incidents": 47
     }
     ```

5. **Incident fetch**

   - Frontend then calls:
     ```http
     GET /api/incidents?region=Fraser%20Valley,%20BC
     ```
   - Backend translates the region into the relevant sources / jurisdictions and returns an array of incidents shaped to match the current TypeScript `Incident` type.

6. **Graph and map**

   - Frontend calls:
     - `GET /api/graph?region=Fraser%20Valley,%20BC`
     - `GET /api/map?region=Fraser%20Valley,%20BC`
   - Backend derives graph nodes/edges and map markers directly from `incidents_enriched`.

UI behaviour, chips, severity colours, D3 interactions, and Leaflet markers do **not** change.

---

## 3. Technical stack

### 3.1 Backend & ingestion

- **Language**: Python 3.11
- **Web framework**: FastAPI
- **HTTP client**: `httpx` or `requests`
- **HTML parsing**: `selectolax` or `beautifulsoup4`
- **Validation / models**: `pydantic`
- **Database driver**: `asyncpg` or `psycopg2` (depending on sync/async choice)

### 3.2 Database

- **Engine**: PostgreSQL (local Docker or managed service)  
- Migrations with Alembic.

### 3.3 LLM

- **Provider**: Gemini  
- **Model**: cheapest Flash model (e.g., `gemini-1.5-flash`).  
- **Call pattern**: exactly *one* completion per article, small prompt and JSON output.  
- No `googleSearch` tools; input is the parsed article text plus minimal metadata.

---

## 4. Data model

### 4.1 Sources

Static registry of police newsroom endpoints.

```sql
CREATE TABLE sources (
  id SERIAL PRIMARY KEY,
  agency_name      TEXT NOT NULL,
  jurisdiction     TEXT NOT NULL,  -- e.g. 'BC', 'AB', 'WA'
  region_label     TEXT NOT NULL,  -- e.g. 'Fraser Valley, BC'
  source_type      TEXT NOT NULL,  -- 'RCMP_NEWSROOM', 'MUNICIPAL_PD_NEWS', etc.
  base_url         TEXT NOT NULL,  -- newsroom root URL
  parser_id        TEXT NOT NULL,  -- which parser to use
  active           BOOLEAN NOT NULL DEFAULT TRUE,
  last_checked_at  TIMESTAMPTZ
);
```

Seed data comes from a **YAML/JSON file** under version control; on startup the backend syncs it into this table (upsert by `base_url`).

### 4.2 Raw articles

```sql
CREATE TABLE articles_raw (
  id SERIAL PRIMARY KEY,
  source_id       INT NOT NULL REFERENCES sources(id),
  external_id     TEXT NOT NULL,      -- hash of URL+title for idempotence
  url             TEXT NOT NULL,
  title_raw       TEXT NOT NULL,
  published_at    TIMESTAMPTZ,
  body_raw        TEXT NOT NULL,
  raw_html        TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source_id, external_id)
);
```

### 4.3 Enriched incidents

```sql
CREATE TABLE incidents_enriched (
  id INT PRIMARY KEY REFERENCES articles_raw(id) ON DELETE CASCADE,
  severity         TEXT NOT NULL,        -- 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  summary_tactical TEXT NOT NULL,
  tags             JSONB NOT NULL,       -- array of strings
  entities         JSONB NOT NULL,       -- [{ "type": "Person", "name": "..." }, ...]
  location_label   TEXT,
  lat              DOUBLE PRECISION,
  lng              DOUBLE PRECISION,
  graph_cluster_key TEXT,
  llm_model        TEXT NOT NULL,
  prompt_version   TEXT NOT NULL,
  processed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

This schema is intentionally close to the current `Incident`/entity concepts used by the React app. The backend will map DB rows into the **exact TS types already defined in the repo** (e.g., `Incident`, `GraphNode`, `GraphEdge`, etc.), so the UI code does not need to change shape.

---

## 5. API design (aligned with existing UI)

The React app currently expects:

- An in-memory list of `Incident` objects for the **Reports Feed** and **Tactical Analysis** panel.
- Structures for the D3 **Neural Link Graph**.
- Marker data for the Leaflet **Geospatial Map**.

The API will serve those directly.

### 5.1 Incidents

`GET /api/incidents`

- **Query params**
  - `region` (string, required) – human label like `Fraser Valley, BC`.
  - `severity_min` (optional, default `LOW`).
  - `limit` (optional, default 100).

- **Response**
  ```json
  {
    "region": "Fraser Valley, BC",
    "incidents": [ /* Incident[] in the existing TS shape */ ]
  }
  ```

The backend joins `sources` → `articles_raw` → `incidents_enriched` where `region_label = :region`.

### 5.2 Refresh

`POST /api/refresh`

As described in §2.1. Runs ingestion + enrichment for that region. Returns counts only; the UI then calls `/api/incidents` to rebind state.

### 5.3 Graph

`GET /api/graph`

- **Query params:** `region`, `sinceDays` (optional), `severity_min`.
- Backend derives a graph structure equivalent to what the client now builds:
  - Nodes: incidents, entities, locations.
  - Edges: “incident–entity”, “entity–entity (same gang)”, “incident–location”.

For now, derive on the fly from `incidents_enriched`. If performance becomes an issue, materialize into a `graphs` table as JSON (one row per region / time window).

### 5.4 Map

`GET /api/map`

- Returns a list of `{ incidentId, severity, lat, lng, label }` for markers, consumed by the existing Leaflet layer.

---

## 6. Ingestion design

### 6.1 Parser interface

```python
class SourceParser(Protocol):
    def fetch_new(self, source: Source, since: datetime | None) -> list[RawArticle]:
        ...
```

Implementation modules:

- `rcmp_parser.py` – handles all `*.rcmp-grc.gc.ca` detachment newsrooms.
- `wordpress_parser.py` – for WordPress-based PD sites (e.g., VPD, VicPD).
- `municipal_list_parser.py` – generic UL/LI or card list (Surrey Police, Abbotsford PD).
- Additional special-case parsers as needed (Calgary, EPS, etc.).

### 6.2 New-article detection

Per source:

1. Fetch the first page of the newsroom.
2. Parse each release (title, URL, date, body link).
3. Stop when `published_at <= since` to avoid re-processing older items.
4. For each candidate:
   - Compute `external_id = sha256(url + title)`.
   - If `(source_id, external_id)` already exists in `articles_raw`, skip.
   - Else, fetch the article detail page and extract main text into `body_raw`.

Because sources are mostly static and volume is low, this process will typically touch only a handful of new posts.

---

## 7. LLM enrichment design

### 7.1 Model

- **Gemini 1.5 Flash** (or equivalent lowest-cost Flash model in your GCP project).
- JSON mode if available; otherwise enforce JSON-only responses via prompt.

### 7.2 Prompt sketch

System prompt (conceptual):

> You are a tactical analyst working with police news releases from British Columbia, Alberta, and Washington State.  
> Given a single article, output a compact JSON object with fields: severity, summary_tactical, tags, entities, location_label, lat, lng, graph_cluster_key.  
> Severity must be one of: LOW, MEDIUM, HIGH, CRITICAL.

User content: article title, source agency, region, publication date, and `body_raw` truncated to a safe token budget.

### 7.3 Idempotence and versioning

- Record `llm_model` and `prompt_version` in `incidents_enriched`.
- If you update prompts or models later, write a one-off script that:
  - Selects incidents with old version.
  - Replays enrichment.
  - Updates rows in place.

---

## 8. Frontend integration (React, D3, Leaflet)

The goal is **zero visual change** to Crimewatch Intel:

1. **Data source swap**
   - Replace current Gemini calls in the front-end services layer with REST calls to:
     - `POST /api/refresh`
     - `GET /api/incidents`
     - `GET /api/graph`
     - `GET /api/map`
   - Keep all TS types the same; adjust the backend serializers to fit them.

2. **REFRESH FEED button**
   - On click:
     1. Call `POST /api/refresh`.
     2. Show “Refreshing…” state in the same header area where “Monitoring complete. N events logged.” appears.
     3. On success, call `GET /api/incidents` + `GET /api/graph` + `GET /api/map` in parallel.
     4. Rebind React state; the feed, mind map (D3), and Leaflet map all re-render.

3. **Filters & selections**
   - Filters (severity chips, tags) remain client-side in React, applied on the incident list returned by the backend.
   - Selected incident ID is still held in React state; Tactical Panel continues to display fields from the `Incident` object.
   - The Threat Condition, Active Factions, Critical Events counters in the HUD are recomputed from the new incident list, just as now.

4. **Local-only dev**
   - In dev, run:
     - `npm start` for the React app.
     - `uvicorn app.main:app --reload` for FastAPI.
   - Configure a `.env` value like `VITE_API_BASE_URL=http://localhost:8000` and use it in the front-end fetch client.

---

## 9. Implementation phases

### Phase A – Minimal backend with one region

1. Stand up PostgreSQL locally.  
2. Implement schema and Alembic migrations.  
3. Implement:
   - `rcmp_parser` for 2–3 BC RCMP detachments.
   - A single FastAPI app with `/api/refresh` and `/api/incidents`.
4. Wire the frontend to those endpoints for a single region (e.g., Fraser Valley, BC).

### Phase B – Full BC coverage

1. Add Surrey Police, Abbotsford PD, VPD, etc. to `sources` seed.  
2. Implement any additional parsers required.  
3. Extend backend to support `/api/graph` and `/api/map` for BC.

### Phase C – AB & WA rollout

1. Add Calgary, Edmonton, Lethbridge, Medicine Hat, WSP, Spokane, Yakima, King County Sheriff, etc. to the registry.  
2. Add/extend parsers as needed (Calgary newsroom, EPS layout).  
3. Ensure region labels like `Calgary, AB`, `Seattle Metro, WA` map cleanly into the same `incidents_enriched` schema.

### Phase D – Hardening

- 429 / rate-limit handling.
- Logging with correlation IDs for each refresh.
- Basic auth / API key if you host the backend outside localhost.

---

## 10. Summary

- **UI stays the same** – same React 19 dashboard, same D3 mind map, same Leaflet map and HUD.
- **Data now comes from a local corpus** of police newsroom articles stored in Postgres.
- **Python + FastAPI** handle ingestion, enrichment, and serving.
- **Gemini Flash** is used once per article for cheap, structured intelligence extraction.
- The result is a repeatable, region-aware police intelligence dashboard you can demo and extend without touching the React/D3/Leaflet presentation layer.
