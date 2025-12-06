#!/bin/bash
# Convenience script to run the FastAPI backend server

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Check if database is initialized
if [ ! -f "crimewatch.db" ]; then
    echo "Database not found. Running migrations..."
    alembic upgrade head
fi

echo "Starting Crimewatch Intel Backend..."
echo "API will be available at: http://localhost:8000"
echo "API docs at: http://localhost:8000/docs"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
