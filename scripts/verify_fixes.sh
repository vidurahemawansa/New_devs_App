#!/bin/bash
set -e

BASE="http://localhost:8000/api/v1"

login() {
  curl -s -X POST "$BASE/auth/login" -H "Content-Type: application/json" \
    -d "{\"email\":\"$1\",\"password\":\"$2\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])"
}

TOKEN_A=$(login "sunset@propertyflow.com" "client_a_2024")
TOKEN_B=$(login "ocean@propertyflow.com" "client_b_2024")

echo "--- Tenant A prop-001 total (expect real DB: 2250.00, count 4) ---"
curl -s "$BASE/dashboard/summary?property_id=prop-001" -H "Authorization: Bearer $TOKEN_A"; echo

echo "--- Tenant B prop-001 total (expect DIFFERENT data - their own Mountain Lodge Beta) ---"
curl -s "$BASE/dashboard/summary?property_id=prop-001" -H "Authorization: Bearer $TOKEN_B"; echo

echo "--- Tenant A prop-001 MARCH 2024 revenue (expect 2250.00 incl. res-tz-1, Paris local time = March) ---"
curl -s "$BASE/dashboard/summary?property_id=prop-001&month=3&year=2024" -H "Authorization: Bearer $TOKEN_A"; echo

echo "--- Tenant A prop-001 FEBRUARY 2024 revenue (expect 0.00 - res-tz-1 belongs to March in Paris time) ---"
curl -s "$BASE/dashboard/summary?property_id=prop-001&month=2&year=2024" -H "Authorization: Bearer $TOKEN_A"; echo

echo "--- Tenant B prop-004 total (Lakeside Cottage, expect real: 1776.50, count 4) ---"
curl -s "$BASE/dashboard/summary?property_id=prop-004" -H "Authorization: Bearer $TOKEN_B"; echo

echo "--- Tenant A requesting Tenant B's prop-004 directly (expect 0, not leaked/cross-tenant) ---"
curl -s "$BASE/dashboard/summary?property_id=prop-004" -H "Authorization: Bearer $TOKEN_A"; echo
