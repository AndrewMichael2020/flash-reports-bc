#!/usr/bin/env python3
"""
Simple dev server launcher for the Crimewatch Intel backend.

Usage:
    cd backend
    python dev_server.py

This is a convenience wrapper around uvicorn for development.
For production, use the full uvicorn command with proper settings.
"""
import os
import sys

# Ensure backend directory is on path
backend_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(backend_dir)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

if __name__ == "__main__":
    import uvicorn
    
    # Set development environment
    os.environ.setdefault("ENV", "dev")
    
    # Get configuration from environment or use defaults
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    print(f"Starting Crimewatch Intel Backend in DEV mode")
    print(f"Server will be available at http://{host}:{port}")
    print(f"API docs at http://{host}:{port}/docs")
    print()
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,  # Enable auto-reload for development
        log_level="info"
    )
