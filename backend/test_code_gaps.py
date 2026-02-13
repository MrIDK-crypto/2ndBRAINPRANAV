#!/usr/bin/env python
"""Test the code gap analysis"""
import os
import requests
import json

TOKEN = os.getenv("TEST_AUTH_TOKEN", "YOUR_TOKEN_HERE")

BASE_URL = "http://localhost:5003/api"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Test documents API first
print("=== TESTING DOCUMENTS API ===")
resp = requests.get(f"{BASE_URL}/documents", headers=headers)
data = resp.json()
docs = data.get('documents', [])
github_docs = [d for d in docs if d.get('source_type') == 'github']
print(f"Total docs: {len(docs)}, GitHub docs: {len(github_docs)}")
for d in github_docs[:3]:
    print(f"  - {d['title'][:60]}")

# Now run code gap analysis
print("\n=== RUNNING CODE GAP ANALYSIS ===")
resp = requests.post(
    f"{BASE_URL}/knowledge/analyze",
    headers=headers,
    json={"mode": "code"}
)
result = resp.json()
print(f"Status: {resp.status_code}")
print(json.dumps(result, indent=2)[:2000])
