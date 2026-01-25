"""Test PUT endpoint to see the error"""
import urllib.request
import urllib.error
import json

BASE_URL = "http://127.0.0.1:8000/api/v1"

# Login first to get a fresh token
print("1. Logging in...")
login_data = {
    "email": "ttt@example.com",
    "password": "string"  # Adjust if needed
}

req = urllib.request.Request(
    f"{BASE_URL}/auth/login",
    data=json.dumps(login_data).encode('utf-8'),
    headers={"Content-Type": "application/json"},
    method="POST"
)

try:
    with urllib.request.urlopen(req) as response:
        login_response = json.loads(response.read().decode('utf-8'))
        access_token = login_response["tokens"]["access_token"]
        print(f"   Login successful! Token obtained.")
except Exception as e:
    print(f"   Login failed: {e}")
    print("   Using token from request...")
    access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NjkzNDIwNzEsImlhdCI6MTc2OTM0MDI3MSwic3ViIjoiZWE5YzI5ZDAtYmMyNC00OTdjLThlNDctMmI3ZTM5ZTU0Mzc5IiwidHlwZSI6ImFjY2VzcyIsInJvbGUiOiJkb2N0b3IiLCJlbWFpbCI6InR0dEBleGFtcGxlLmNvbSJ9._AdLhQNiOipd9s1kru6LNCbkToY7EaamMxK-GCfoBXY"

# Test PUT endpoint
print("\n2. Testing PUT /api/v1/doctors/me...")
update_data = {
    "title": "Dr.",
    "bio": "Test bio",
    "years_of_experience": 5,
    "consultation_fee": 500
}

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

req = urllib.request.Request(
    f"{BASE_URL}/doctors/me",
    data=json.dumps(update_data).encode('utf-8'),
    headers=headers,
    method="PUT"
)

try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        print(f"   Status: {response.status}")
        print(f"   SUCCESS! Profile updated:")
        print(json.dumps(data, indent=2))
except urllib.error.HTTPError as e:
    print(f"   Status: {e.code}")
    error_data = json.loads(e.read().decode('utf-8'))
    print(f"   Error response:")
    print(json.dumps(error_data, indent=2))
except Exception as e:
    print(f"   Error: {e}")
