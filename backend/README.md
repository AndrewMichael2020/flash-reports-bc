# Crimewatch Intel Backend

FastAPI backend for the Crimewatch Intel police newsroom aggregator.

## Features

- **FastAPI** web framework with automatic OpenAPI docs
- **SQLAlchemy** ORM with **Alembic** migrations
- **Pluggable parsers** for different police newsroom sources
- **PostgreSQL/SQLite** database support
- **CORS** enabled for frontend integration

## Setup

### 1. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure database (optional)

By default, the backend uses SQLite (`crimewatch.db`). To use PostgreSQL:

```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/crimewatch"
```

Or create a `.env` file:

```
DATABASE_URL=postgresql://user:password@localhost:5432/crimewatch
```

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Start the server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Health Check

```
GET /
```

Returns service status and version.

### Refresh Feed

```
POST /api/refresh
Content-Type: application/json

{
  "region": "Fraser Valley, BC"
}
```

Triggers ingestion for the specified region. Fetches new articles from all active sources and creates enriched incidents.

**Response:**

```json
{
  "region": "Fraser Valley, BC",
  "new_articles": 3,
  "total_incidents": 15
}
```

### Get Incidents

```
GET /api/incidents?region=Fraser+Valley,+BC&limit=100
```

Returns incidents for the specified region in a format compatible with the frontend.

**Response:**

```json
{
  "region": "Fraser Valley, BC",
  "incidents": [
    {
      "id": "1",
      "timestamp": "2025-12-06T10:30:00Z",
      "source": "Local Police",
      "location": "Langley, BC",
      "coordinates": { "lat": 49.1042, "lng": -122.6604 },
      "summary": "Article title",
      "fullText": "Full article body...",
      "severity": "Medium",
      "tags": [],
      "entities": [],
      "relatedIncidentIds": []
    }
  ]
}
```

## API Documentation

Interactive API documentation is available at:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Database Schema

### sources

Static registry of police newsroom endpoints.

- `id` (PK)
- `agency_name`
- `jurisdiction` (e.g., "BC")
- `region_label` (e.g., "Fraser Valley, BC")
- `source_type` (e.g., "RCMP_NEWSROOM")
- `base_url`
- `parser_id`
- `active`
- `last_checked_at`

### articles_raw

Raw articles scraped from newsrooms.

- `id` (PK)
- `source_id` (FK → sources)
- `external_id` (unique with source_id)
- `url`
- `title_raw`
- `published_at`
- `body_raw`
- `raw_html`
- `created_at`

### incidents_enriched

Enriched incidents with LLM-extracted intelligence (1:1 with articles_raw).

- `id` (PK, FK → articles_raw)
- `severity` ("LOW" | "MEDIUM" | "HIGH" | "CRITICAL")
- `summary_tactical`
- `tags` (JSONB array)
- `entities` (JSONB array of objects)
- `location_label`
- `lat`, `lng`
- `graph_cluster_key`
- `llm_model`
- `prompt_version`
- `processed_at`

## Parsers

Parsers extract articles from different police newsroom formats.

### RCMP Parser

- **parser_id**: `rcmp`
- **Source type**: RCMP detachment newsrooms
- **Example**: Langley RCMP newsroom

Parsers implement the `SourceParser` interface in `app/ingestion/parser_base.py`.

## Development

### Running tests

```bash
pytest
```

### Creating a new migration

```bash
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

### Adding a new parser

1. Create a new file in `app/ingestion/` (e.g., `municipal_parser.py`)
2. Implement the `SourceParser` interface
3. Register it in `get_parser()` function in `app/main.py`
4. Add sources to the database with the corresponding `parser_id`

## Production Deployment

1. Set `DATABASE_URL` to a PostgreSQL connection string
2. Run migrations: `alembic upgrade head`
3. Use a production ASGI server:
   ```bash
   gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```
4. Set up reverse proxy (nginx) for SSL/TLS
5. Configure environment variables for secrets

## License

See repository LICENSE file.
