# Development Setup Guide

This guide provides step-by-step instructions for setting up the Crimewatch Intel development environment, with special focus on GitHub Codespaces.

## Table of Contents
- [GitHub Codespaces Setup](#github-codespaces-setup)
- [Local Development Setup](#local-development-setup)
- [Troubleshooting](#troubleshooting)
- [Development Workflow](#development-workflow)

---

## GitHub Codespaces Setup

GitHub Codespaces provides a cloud-based development environment. Follow these steps for a smooth setup:

### 1. Create Environment Files

#### Backend Environment (`.env`)
```bash
cd backend
cp .env.example .env
```

Edit `backend/.env` and add your Gemini API key:
```bash
GEMINI_API_KEY=your_actual_api_key_here
```

**Important:** Keep all other settings at their defaults. The `ENV=dev` and CORS settings are pre-configured for Codespaces.

#### Frontend Environment (`.env`)
```bash
cd ..  # Back to repository root
cp .env.example .env
```

**CRITICAL - Do NOT set `VITE_API_BASE_URL` for development!**

The `.env` file should either:
- Not contain `VITE_API_BASE_URL` at all (recommended), OR
- Set it to `/` explicitly: `VITE_API_BASE_URL=/`

**Why?** In development mode, the frontend uses Vite's built-in proxy to forward `/api/*` requests to the backend. Setting `VITE_API_BASE_URL` to a Codespaces tunnel URL (like `https://your-codespace-8000.app.github.dev`) will bypass the proxy and cause CORS issues.

### 2. Start the Backend

Open a new terminal in Codespaces and run:

```bash
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt -q

# Run database migrations
alembic upgrade head

# Start the backend server
ENV=dev uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Alternative (using the dev launcher):**
```bash
cd backend
source venv/bin/activate
python dev_server.py
```

The backend will be available at:
- Local: `http://127.0.0.1:8000`
- Codespaces: `https://your-codespace-8000.app.github.dev`
- API Docs: Add `/docs` to the URL

### 3. Start the Frontend

Open a **second terminal** and run:

```bash
# Install dependencies (first time only)
npm install

# Start the Vite dev server
npm run dev -- --host 0.0.0.0 --port 3000
```

The frontend will be available at:
- Codespaces: `https://your-codespace-3000.app.github.dev` (Codespaces will show you the URL)

### 4. Verify the Setup

Open the Vite URL in your browser and check the browser console:
- ✅ **Success:** No `ERR_CONNECTION_REFUSED` errors
- ✅ **Success:** Network tab shows requests to `/api/refresh`, `/api/incidents` (relative paths)
- ❌ **Problem:** You see `https://api/refresh` or `http://localhost:8000/api/...` in the network tab
  - **Fix:** Check that your `.env` file does NOT have `VITE_API_BASE_URL` set, or has it set to `/`

### 5. Run the Smoke Test (Optional)

To verify the backend is working correctly:

```bash
# Install requests library if not already installed
pip install requests

# Run the smoke test
python scripts/dev_smoke.py
```

Expected output:
```
[1/3] Testing health check endpoint (GET /)...
  ✓ PASS - Status: 200
[2/3] Testing incidents endpoint (GET /api/incidents)...
  ✓ PASS - Status: 200
[3/3] Testing API docs endpoint (GET /docs)...
  ✓ PASS - Status: 200
Results: 3 passed, 0 failed
```

---

## Local Development Setup

If you're developing on your local machine (not Codespaces):

### 1. Prerequisites
- Python 3.11+
- Node.js 18+
- Git

### 2. Clone the Repository
```bash
git clone https://github.com/AndrewMichael2020/flash-reports-bc.git
cd flash-reports-bc
```

### 3. Backend Setup
```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Run migrations
alembic upgrade head

# Start backend
ENV=dev uvicorn app.main:app --host 0.0.0.0 --port 8000
# Or use: python dev_server.py
```

### 4. Frontend Setup
```bash
# In a new terminal, from repository root
npm install

# Create .env file (leave VITE_API_BASE_URL unset or set to "/")
cp .env.example .env

# Start frontend
npm run dev
```

The frontend will be at `http://localhost:3000` and will proxy API requests to `http://localhost:8000`.

---

## Troubleshooting

### Issue: `ERR_CONNECTION_REFUSED` when calling `/api/refresh`

**Symptoms:**
- Browser console shows: `POST https://api/refresh net::ERR_CONNECTION_REFUSED`
- Network tab shows malformed URLs

**Causes & Fixes:**
1. **Backend not running:** Start the backend server (see step 2 above)
2. **Wrong `VITE_API_BASE_URL`:** Remove it from `.env` or set to `/`
3. **Vite proxy not working:** Check `vite.config.ts` has the proxy configuration

### Issue: CORS errors in Codespaces

**Symptoms:**
- Browser shows: `Access-Control-Allow-Origin` errors
- Requests show preflight (OPTIONS) failures

**Fix:**
- Make sure you're **NOT** setting `VITE_API_BASE_URL` to the Codespaces backend URL
- The frontend should make same-origin requests (relative paths like `/api/...`)
- Vite proxy will handle forwarding to the backend

### Issue: Backend import errors

**Symptoms:**
```
ModuleNotFoundError: No module named 'app'
```

**Fix:**
Make sure you're running uvicorn from the repository root or backend directory:
```bash
cd backend
ENV=dev uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Issue: Smoke test fails with connection refused

**Fix:**
1. Verify backend is running: `curl http://127.0.0.1:8000/`
2. Wait a few seconds for backend to fully start
3. Check that you're using `127.0.0.1` not `localhost` (some systems resolve differently)

---

## Development Workflow

### Typical Development Session

1. **Start Backend:**
   ```bash
   cd backend
   source venv/bin/activate  # If not already activated
   python dev_server.py
   ```

2. **Start Frontend (in new terminal):**
   ```bash
   npm run dev -- --host 0.0.0.0 --port 3000
   ```

3. **Open Browser:**
   - Navigate to the Vite URL (shown in terminal)
   - Open browser DevTools to monitor network requests

4. **Test Your Changes:**
   - Make code changes
   - Vite will hot-reload the frontend
   - Backend will auto-reload (when using `dev_server.py` or `--reload` flag)

### Running Tests

```bash
# Backend tests
cd backend
source venv/bin/activate
pytest

# Smoke test
python scripts/dev_smoke.py
```

### Making API Changes

1. Edit backend code in `backend/app/`
2. The server will auto-reload
3. Visit `http://127.0.0.1:8000/docs` to see updated API docs
4. Test endpoints using the interactive docs or frontend

### Port Forwarding in Codespaces

Codespaces automatically forwards ports 3000 and 8000. You can:
- See forwarded ports in the "Ports" tab
- Change visibility (Public/Private)
- Copy the URL to share with others

**Important:** Keep the backend (port 8000) visibility as "Private" in most cases for security.

---

## Architecture Notes for Developers

### How the Proxy Works

In development mode:
1. Frontend runs on port 3000 (Vite dev server)
2. Backend runs on port 8000 (uvicorn)
3. Browser makes requests to the frontend URL: `https://your-codespace-3000.app.github.dev/api/refresh`
4. Vite proxy intercepts `/api/*` requests and forwards them to `http://127.0.0.1:8000/api/*`
5. Backend responds, Vite forwards response back to browser
6. **Result:** No CORS issues because browser thinks it's same-origin

### Production vs Development

| Environment | VITE_API_BASE_URL | Behavior |
|-------------|-------------------|----------|
| **Development** | `/` or unset | Same-origin requests via Vite proxy |
| **Production** | `https://api.yourdomain.com` | Direct requests to backend |

### File Structure
```
flash-reports-bc/
├── backend/
│   ├── app/              # FastAPI application
│   ├── dev_server.py     # Development launcher
│   └── .env              # Backend config (not in git)
├── src/                  # React frontend
├── scripts/
│   └── dev_smoke.py      # Smoke test
├── vite.config.ts        # Vite config with proxy
├── .env                  # Frontend config (not in git)
└── DEV_SETUP.md          # This file
```

---

## Quick Reference

### Essential Commands

| Task | Command |
|------|---------|
| Start backend | `cd backend && python dev_server.py` |
| Start frontend | `npm run dev -- --host 0.0.0.0 --port 3000` |
| Smoke test | `python scripts/dev_smoke.py` |
| API docs | `http://127.0.0.1:8000/docs` |
| Database migration | `cd backend && alembic upgrade head` |

### Environment Variables

**Backend (`backend/.env`):**
- `GEMINI_API_KEY` - Your Google Gemini API key (required)
- `ENV=dev` - Development mode (default)
- `DATABASE_URL` - Database connection (default: SQLite)

**Frontend (`.env` in root):**
- `VITE_API_BASE_URL` - **Leave unset for development!**

---

## Getting Help

If you encounter issues not covered in this guide:

1. Check the [main README.md](README.md) for general setup info
2. Review the [troubleshooting section](#troubleshooting) above
3. Run the smoke test to identify specific failures: `python scripts/dev_smoke.py`
4. Check browser console and network tab for error details
5. Open an issue on GitHub with:
   - Error messages
   - Smoke test output
   - Browser console logs
   - Your environment (Codespaces vs local, OS, etc.)
