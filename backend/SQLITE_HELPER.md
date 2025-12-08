# SQLite Helper – Crimewatch Intel

CLI snippets for inspecting and debugging the dev database (`crimewatch.db` by default).

---

## 0. Where is the DB?

```bash
# from repo root
cd backend

# default URL is sqlite:///./crimewatch.db (see app/db.py)
echo "$DATABASE_URL"
ls -l crimewatch.db
```

---

## 1. Open SQLite Shell

```bash
cd backend
sqlite3 crimewatch.db
```

Inside `sqlite3`:

```sql
.headers on;
.mode column;
-- list tables
.tables;
```

Exit with:

```sql
.quit
```

---

## 2. Inspect Schema

```sql
-- show core tables
.schema sources;
.schema articles_raw;
.schema incidents_enriched;

-- list columns (portable across SQLite/Postgres)
PRAGMA table_info('sources');
PRAGMA table_info('articles_raw');
PRAGMA table_info('incidents_enriched');
```

---

## 3. Inspect Sources

```sql
-- all sources, minimal view
SELECT id,
       agency_name,
       jurisdiction,
       region_label,
       source_type,
       base_url,
       parser_id,
       active,
       last_checked_at
FROM sources
ORDER BY region_label, agency_name;

-- active sources only
SELECT id,
       agency_name,
       region_label,
       base_url,
       parser_id
FROM sources
WHERE active = 1
ORDER BY region_label, agency_name;

-- RCMP sources only
SELECT id,
       agency_name,
       base_url,
       parser_id
FROM sources
WHERE parser_id = 'rcmp'
ORDER BY agency_name;
```

Toggle a source:

```sql
UPDATE sources SET active = 1 WHERE id = 1;
UPDATE sources SET active = 0 WHERE id = 1;
```

---

## 4. Raw Articles (`articles_raw`)

```sql
-- newest 10 articles
SELECT ar.id,
       ar.source_id,
       s.agency_name,
       ar.published_at,
       substr(ar.title_raw, 1, 80) AS title
FROM articles_raw AS ar
JOIN sources AS s ON s.id = ar.source_id
ORDER BY ar.published_at DESC
LIMIT 10;

-- by region
SELECT ar.id,
       s.region_label,
       s.agency_name,
       ar.published_at,
       substr(ar.title_raw, 1, 80) AS title
FROM articles_raw AS ar
JOIN sources AS s ON s.id = ar.source_id
WHERE s.region_label = 'Fraser Valley, BC'
ORDER BY ar.published_at DESC
LIMIT 20;
```

Duplicate detector (same `source_id` + `external_id`):

```sql
SELECT source_id, external_id, COUNT(*) AS cnt
FROM articles_raw
GROUP BY source_id, external_id
HAVING cnt > 1
ORDER BY cnt DESC;
```

---

## 5. Enriched Incidents (`incidents_enriched`)

```sql
-- recent incidents with severity + summary
SELECT ie.id,
       s.agency_name,
       s.region_label,
       ie.severity,
       substr(ie.summary_tactical, 1, 80) AS summary,
       ie.location_label,
       ie.lat,
       ie.lng
FROM incidents_enriched AS ie
JOIN articles_raw AS ar ON ar.id = ie.id
JOIN sources AS s ON s.id = ar.source_id
ORDER BY ie.processed_at DESC
LIMIT 20;

-- incident counts by region
SELECT s.region_label,
       COUNT(*) AS incident_count
FROM incidents_enriched AS ie
JOIN articles_raw AS ar ON ar.id = ie.id
JOIN sources AS s ON s.id = ar.source_id
GROUP BY s.region_label
ORDER BY incident_count DESC;
```

Sanity check: 1:1 `articles_raw` ↔ `incidents_enriched`:

```sql
SELECT (SELECT COUNT(*) FROM articles_raw)          AS raw_cnt,
       (SELECT COUNT(*) FROM incidents_enriched)    AS enriched_cnt;
```

---

## 6. After a Refresh/Loader Run

Trigger ingest (two main paths):

```bash
# HTTP refresh (uses config/sources.yaml + parsers + enrichment)
curl -X POST http://127.0.0.1:8000/api/refresh \
  -H 'Content-Type: application/json' \
  -d '{"region":"Fraser Valley, BC"}'

# or: RCMP loader CLI (bypasses HTTP)
cd backend
source venv/bin/activate
python tools/load_rcmp_json.py --source-id 1 --confirm
```

Then in `sqlite3`:

```sql
-- newest articles for that source (1 == example)
SELECT ar.id,
       ar.published_at,
       substr(ar.title_raw, 1, 80) AS title
FROM articles_raw AS ar
WHERE ar.source_id = 1
ORDER BY ar.published_at DESC
LIMIT 5;

-- incidents for that region
SELECT COUNT(*) AS incidents_fraser
FROM incidents_enriched AS ie
JOIN articles_raw AS ar ON ar.id = ie.id
JOIN sources AS s ON s.id = ar.source_id
WHERE s.region_label = 'Fraser Valley, BC';
```

---

## 7. Quick Web UI in Codespaces (Optional)

Simple DB browser (runs inside the dev container):

```bash
cd backend
source venv/bin/activate
pip install sqlite-web

# serve on 8080 inside container
sqlite_web crimewatch.db  # prints URL
```

Open in host browser:

```bash
$BROWSER http://127.0.0.1:8080
```
