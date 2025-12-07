#!/usr/bin/env python3
"""
Launcher wrapper — run the canonical loader under backend/tools.
This wrapper avoids package import issues and preserves the historical CLI:
  cd backend && python load_rcmp_json.py --base-url ... --create-source --confirm

It simply execs the 'tools/load_rcmp_json.py' script using the current Python interpreter.
"""
import os
import sys

# Resolve canonical tools script path relative to this file
TOOLS_SCRIPT = os.path.join(os.path.dirname(__file__), "tools", "load_rcmp_json.py")
if not os.path.exists(TOOLS_SCRIPT):
    print("Missing tools script: backend/tools/load_rcmp_json.py. Use 'python tools/load_rcmp_json.py' instead.")
    sys.exit(1)

# Exec the tools script with the same Python interpreter, passing through args
os.execv(sys.executable, [sys.executable, TOOLS_SCRIPT] + sys.argv[1:])
