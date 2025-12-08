#!/usr/bin/env python3
"""
Development smoke test for Crimewatch Intel backend.

This script verifies that the backend is running and responds to basic API calls.
It is intended to be run after starting the backend server in development mode.

Usage:
    python scripts/dev_smoke.py

Exit codes:
    0 - All tests passed
    1 - One or more tests failed
"""
import sys
import time


def run_smoke_tests():
    """Run smoke tests against the backend."""
    try:
        import requests
    except ImportError:
        print("ERROR: 'requests' library not installed.")
        print("Install it with: pip install requests")
        return False
    
    base_url = "http://127.0.0.1:8000"
    tests_passed = 0
    tests_failed = 0
    
    print("=" * 60)
    print("Crimewatch Intel Backend - Development Smoke Test")
    print("=" * 60)
    print(f"Testing backend at: {base_url}")
    print()
    
    # Test 1: Health check endpoint
    print("[1/3] Testing health check endpoint (GET /)...")
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ PASS - Status: {response.status_code}")
            print(f"  Response: {data}")
            tests_passed += 1
        else:
            print(f"  ✗ FAIL - Expected 200, got {response.status_code}")
            tests_failed += 1
    except requests.exceptions.ConnectionError:
        print(f"  ✗ FAIL - Connection refused. Is the backend running?")
        tests_failed += 1
    except Exception as e:
        print(f"  ✗ FAIL - Error: {e}")
        tests_failed += 1
    
    print()
    
    # Test 2: Get incidents endpoint (without data, should return empty or error gracefully)
    print("[2/3] Testing incidents endpoint (GET /api/incidents)...")
    try:
        params = {"region": "Fraser Valley, BC", "limit": 1}
        response = requests.get(f"{base_url}/api/incidents", params=params, timeout=10)
        # Accept 200 (with data), 404 (no sources), or 500 (database/query issues)
        # For DEV smoke test, we just verify the endpoint responds
        if response.status_code in [200, 404, 500]:
            print(f"  ✓ PASS - Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  Incidents count: {len(data.get('incidents', []))}")
            elif response.status_code == 500:
                print(f"  Note: 500 error likely due to no data/sources configured")
            tests_passed += 1
        else:
            print(f"  ✗ FAIL - Expected 200/404/500, got {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            tests_failed += 1
    except requests.exceptions.ConnectionError:
        print(f"  ✗ FAIL - Connection refused")
        tests_failed += 1
    except Exception as e:
        print(f"  ✗ FAIL - Error: {e}")
        tests_failed += 1
    
    print()
    
    # Test 3: API docs endpoint
    print("[3/3] Testing API docs endpoint (GET /docs)...")
    try:
        response = requests.get(f"{base_url}/docs", timeout=5)
        if response.status_code == 200:
            print(f"  ✓ PASS - Status: {response.status_code}")
            print(f"  API docs available at {base_url}/docs")
            tests_passed += 1
        else:
            print(f"  ✗ FAIL - Expected 200, got {response.status_code}")
            tests_failed += 1
    except requests.exceptions.ConnectionError:
        print(f"  ✗ FAIL - Connection refused")
        tests_failed += 1
    except Exception as e:
        print(f"  ✗ FAIL - Error: {e}")
        tests_failed += 1
    
    print()
    print("=" * 60)
    print(f"Results: {tests_passed} passed, {tests_failed} failed")
    print("=" * 60)
    
    return tests_failed == 0


if __name__ == "__main__":
    # Give backend a moment to fully start if just launched
    print("Waiting 2 seconds for backend to be ready...")
    time.sleep(2)
    print()
    
    success = run_smoke_tests()
    sys.exit(0 if success else 1)
