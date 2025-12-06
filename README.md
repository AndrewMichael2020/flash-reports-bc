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

### Backend Setup

1. **Navigate to backend directory**:
   ```bash
   cd backend
   ```

2. **Create virtual environment and install dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
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

   The app will be available at `http://localhost:5173`

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

See [backend/README.md](backend/README.md) for instructions on:
- Creating new parsers for different newsroom formats
- Adding sources to the database
- Configuring enrichment prompts

### Database Schema

Three core tables:
- **sources**: Police newsroom registry (agency, URL, region, parser)
- **articles_raw**: Scraped articles (title, body, URL, timestamp)
- **incidents_enriched**: AI-enriched intelligence (severity, entities, location, tags)

See [STRATEGY.md](STRATEGY.ms) for complete schema documentation.

## 📝 Implementation Status

✅ **Phase A - Backend Bootstrap** (Complete)
- FastAPI backend with SQLite/PostgreSQL
- Database schema and Alembic migrations
- RCMP newsroom parser
- POST /api/refresh and GET /api/incidents endpoints
- Frontend backend client wrapper

🚧 **Phase B - Full Integration** (Next)
- Wire frontend to use backend data exclusively
- Replace dummy enrichment with real Gemini Flash calls
- Add more BC sources (Surrey PD, VPD, Abbotsford PD)
- Implement /api/graph and /api/map endpoints

📋 **Phase C - Multi-Region Expansion** (Planned)
- Alberta sources (Calgary, Edmonton)
- Washington State sources (WSP, King County)
- Enhanced correlation algorithms

See [strategy_implementation_log.md](strategy_implementation_log.md) for detailed progress tracking.

## ⚠️ Data Disclaimer

This tool aggregates real police newsroom feeds but uses AI to analyze and structure the data. Intelligence assessments are generated by large language models and should be verified against official sources. This is a demonstration platform for visualization and correlation logic - not a replacement for official law enforcement systems or emergency response tools.

## 📄 License

See LICENSE file for details.
