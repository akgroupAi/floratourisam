"""Quick test to verify the doctor profile endpoint works"""
import urllib.request
import urllib.error
import json

BASE_URL = "http://127.0.0.1:8000/api/v1"

# Use the token from the original issue
access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NjkzNDExMjQsImlhdCI6MTc2OTMzOTMyNCwic3ViIjoiZjRmMDZmZjgtNjYyYy00YjE2LWI1YTYtMDc0NzA4MDJlNmU4IiwidHlwZSI6ImFjY2VzcyIsInJvbGUiOiJkb2N0b3IiLCJlbWFpbCI6ImFhYUBleGFtcGxlLmNvbSJ9.F-ZoYNNuXCs1xTge0bcowrSQ6BpgjjlTtX0TVd46EcE"

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

print("Testing GET /api/v1/doctors/me...")
req = urllib.request.Request(f"{BASE_URL}/doctors/me", headers=headers, method="GET")

try:
    with urllib.request.urlopen(req) as response:
        status = response.status
        data = json.loads(response.read().decode('utf-8'))
        print(f"Status: {status}")
        print(f"SUCCESS! Doctor profile found:")
        print(json.dumps(data, indent=2))
except urllib.error.HTTPError as e:
    print(f"Status: {e.code}")
    print(f"Error: {e.read().decode('utf-8')}")
