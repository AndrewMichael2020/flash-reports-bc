# Crimewatch Intel Dashboard

**AI-Powered Police Intelligence Aggregator & Correlation Engine**

Crimewatch Intel is a tactical dashboard designed for analyzing, classifying, and visualizing law enforcement incidents. It aggregates police newsroom feeds from BC, Alberta, and Washington State, using Google's **Gemini Flash** model to extract structured intelligence and build correlation graphs identifying organized crime activity, gang conflicts, and systemic threats.

## 🏗️ Architecture

**Version 2.0 - Full-Stack Architecture**

- **Frontend**: React 19 + Tailwind CSS + D3.js + Leaflet.js
- **Backend**: Python FastAPI + PostgreSQL/SQLite
- **AI Engine**: Google Gemini Flash (single enrichment per article)
- **Data Sources**: RCMP newsrooms, municipal police departments, specialized units

The system operates in two layers:

1. **Backend ingestion & enrichment**: Scrapes police newsroom websites, stores raw articles, and enriches them once with structured AI analysis
2. **Frontend visualization**: Renders incidents, relationship graphs, and geospatial maps from backend API

See [STRATEGY.md](STRATEGY.ms) for detailed architecture documentation.

## 🚀 Features

*   **Multi-Source Aggregation**: Ingests real police newsroom feeds from RCMP detachments, municipal police, and specialized units
*   **AI Intelligence Analysis**:
    *   **Severity Scoring**: Auto-classifies incidents (Low to Critical)
    *   **Entity Extraction**: Identifies specific gangs, known associates, and hot-zones
    *   **Summarization**: Converts bureaucratic reports into tactical summaries
    *   **Geocoding**: Extracts and validates incident locations
*   **Visual Intelligence**:
    *   **Neural Link Graph**: A D3.js "Mind Map" showing relationships between incidents, suspects, and locations
    *   **Geospatial Map**: Leaflet.js dark-mode map for physical tracking of events
*   **Tactical HUD**: Real-time metrics on Threat Condition, Active Factions, and Volatility
*   **Region-based filtering**: Fraser Valley, Calgary, Seattle Metro, etc.

<img width="1568" height="928" alt="community-watch" src="https://github.com/user-attachments/assets/bd57848c-2c00-4245-b4f4-0b8a8e6d95f2" />

## 🛠️ Tech Stack

### Frontend
*   **Framework**: React 19
*   **Styling**: Tailwind CSS
*   **Visualization**: D3.js (Force Graph), Leaflet (Maps)
*   **Language**: TypeScript
*   **Build Tool**: Vite

### Backend
*   **Framework**: FastAPI
*   **Database**: PostgreSQL (production) / SQLite (development)
*   **ORM**: SQLAlchemy + Alembic migrations
*   **Scraping**: httpx + BeautifulSoup4 + selectolax
*   **AI Engine**: Google GenAI SDK (`gemini-1.5-flash`)
*   **Language**: Python 3.11+

## ⚡ Quick Start

### GitHub Codespaces Setup

If you're running this in GitHub Codespaces, see [DEV_SETUP.md](DEV_SETUP.md) for detailed instructions.

**Quick Start:**

1. **Create environment files**:
   ```bash
   # Backend
   cd backend
   cp .env.example .env
   # Edit backend/.env and add your GEMINI_API_KEY
   
   # Frontend
   cd ..
   cp .env.example .env
   # Leave VITE_API_BASE_URL unset (default is "/" for proxy mode)
   ```

2. **Start Backend** (in one terminal):
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   alembic upgrade head
   ENV=dev uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

3. **Start Frontend** (in another terminal):
   ```bash
   npm install
   npm run dev -- --host 0.0.0.0 --port 3000
   ```

4. **Access the Application**:
   - Frontend: Open the URL shown by Vite (Codespaces will forward port 3000)
   - Backend API docs: Your Codespace URL on port 8000 + `/docs`

**Important:** Do NOT set `VITE_API_BASE_URL` to your Codespaces backend URL. The frontend uses Vite's proxy in development to avoid CORS issues. See [DEV_SETUP.md](DEV_SETUP.md) for details.

### Local Development Setup

### Backend Setup

1. **Navigate to backend directory**:
   ```bash
   cd backend
   ```

2. **Create virtual environment and install dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt -q
   ```

3. **Run database migrations**:
   ```bash
   alembic upgrade head
   ```

4. **Start the backend server**:
   ```bash
   ./run.sh
   # Or manually:
   uvicorn app.main:app --reload
   ```

   The API will be available at `http://localhost:8000`
   - API docs: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`

### Frontend Setup

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Create `.env` file** (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```

3. **Run the development server**:
   ```bash
   npm run dev
   ```

   The app will be available at `http://localhost:3000` (configured in vite.config.ts)

## 🧠 Usage Guide

### Initial Data Loading

1. **Start both backend and frontend servers** (see Quick Start above)

2. **Trigger ingestion**:
   - In the browser, select a region (e.g., "Fraser Valley, BC")
   - Click **REFRESH FEED** button in the top-right
   - The backend will scrape RCMP newsrooms and enrich articles with AI analysis

3. **View intelligence**:
   - Browse incidents in the left panel
   - Explore entity relationships in the Neural Link Graph
   - See geographic distribution on the map
   - Click any incident for detailed tactical analysis

### Filtering & Analysis

- **Severity chips**: Filter by Low/Medium/High/Critical
- **Category filters**: Focus on specific crime types (Trafficking, Gang Activity, etc.)
- **Graph interactions**: Click nodes to see connections, drag to rearrange
- **Map markers**: Click to view incident details and location context

## 📊 Data Flow

```
User clicks "REFRESH FEED" 
  ↓
Frontend calls POST /api/refresh
  ↓
Backend scrapes newsroom URLs (RCMP, etc.)
  ↓
New articles stored in articles_raw table
  ↓
Gemini Flash enriches each new article
  ↓
Enriched data stored in incidents_enriched table
  ↓
Frontend calls GET /api/incidents
  ↓
UI renders incidents, graph, and map
```

## 🔧 Development

### Project Structure

```
flash-reports-bc/
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── main.py      # API endpoints
│   │   ├── models.py    # Database models
│   │   ├── schemas.py   # Pydantic schemas
│   │   ├── db.py        # Database connection
│   │   └── ingestion/   # Source parsers
│   ├── alembic/         # Database migrations
│   └── requirements.txt
├── src/                 # React frontend
│   ├── components/      # React components
│   ├── services/        # API clients
│   └── types.ts         # TypeScript types
├── strategy_implementation_log.md
└── README.md
```

### Adding New Data Sources

1. **Edit the configuration file**: `backend/config/sources.yaml`
   - Add a new source entry with agency info, URL, and parser type
   - See [backend/config/README.md](backend/config/README.md) for details

2. **Choose or create a parser**:
   - **rcmp**: For RCMP detachment newsrooms
   - **wordpress**: For WordPress-based sites
   - **municipal_list**: For card/list-based municipal sites
   - Custom parsers go in `backend/app/ingestion/`

3. **Restart backend**: Sources automatically sync from YAML to database on startup

### Database Schema

Three core tables:
- **sources**: Police newsroom registry (agency, URL, region, parser)
- **articles_raw**: Scraped articles (title, body, URL, timestamp)
- **incidents_enriched**: AI-enriched intelligence (severity, entities, location, tags)

See [STRATEGY.md](STRATEGY.md) for complete schema documentation.

## 📝 Implementation Status

✅ **Phase A - Backend Bootstrap** (Complete)
- FastAPI backend with SQLite/PostgreSQL
- Database schema and Alembic migrations
- RCMP, WordPress, and Municipal parsers
- Configuration-driven source management
- Structured logging and error handling

✅ **Phase B - Full Integration** (Complete)
- Frontend wired to backend API (no more direct Gemini calls)
- POST /api/refresh, GET /api/incidents, GET /api/graph, GET /api/map endpoints
- Retry logic with exponential backoff
- Comprehensive test suite (27 tests passing)
- Improved date parsing and content extraction
- Real Gemini Flash enrichment integrated
- 19 active BC sources configured

📋 **Phase C - Multi-Region Expansion** (Planned)
- Alberta sources (Calgary, Edmonton) - needs parser customization
- Washington State sources (WSP, King County) - needs parser customization
- Enhanced correlation algorithms

See [strategy_implementation_log.md](strategy_implementation_log.md) for detailed progress tracking.

## ⚠️ Data Disclaimer

This tool aggregates real police newsroom feeds but uses AI to analyze and structure the data. Intelligence assessments are generated by large language models and should be verified against official sources. This is a demonstration platform for visualization and correlation logic - not a replacement for official law enforcement systems or emergency response tools.

## 📄 License

See LICENSE file for details.
