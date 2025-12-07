#!/usr/bin/env python3
"""
Launcher wrapper — run the canonical DB inspect tool under backend/tools.
Usage:
  cd backend && python db_inspect.py list-sources
"""
import os
import sys

TOOLS_SCRIPT = os.path.join(os.path.dirname(__file__), "tools", "db_inspect.py")
if not os.path.exists(TOOLS_SCRIPT):
    print("Missing tools script: backend/tools/db_inspect.py. Use 'python tools/db_inspect.py' instead.")
    sys.exit(1)

os.execv(sys.executable, [sys.executable, TOOLS_SCRIPT] + sys.argv[1:])
