"""Test script to verify doctor profile endpoints using urllib"""
import urllib.request
import urllib.error
import json

BASE_URL = "http://127.0.0.1:8000/api/v1"

def make_request(method, url, data=None, headers=None):
    """Make HTTP request using urllib"""
    if headers is None:
        headers = {}
    
    if data is not None:
        data = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))

def test_existing_doctor():
    """Test with the existing doctor from the original issue"""
    
    print("=" * 60)
    print("Testing Doctor Profile Endpoints with Existing User")
    print("=" * 60)
    
    # Use the token from the original issue
    access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NjkzNDExMjQsImlhdCI6MTc2OTMzOTMyNCwic3ViIjoiZjRmMDZmZjgtNjYyYy00YjE2LWI1YTYtMDc0NzA4MDJlNmU4IiwidHlwZSI6ImFjY2VzcyIsInJvbGUiOiJkb2N0b3IiLCJlbWFpbCI6ImFhYUBleGFtcGxlLmNvbSJ9.F-ZoYNNuXCs1xTge0bcowrSQ6BpgjjlTtX0TVd46EcE"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Test: Get doctor profile
    print("\nGetting doctor profile (GET /doctors/me)...")
    status, response = make_request("GET", f"{BASE_URL}/doctors/me", headers=headers)
    print(f"   Status Code: {status}")
    print(f"   Response: {json.dumps(response, indent=2)}")
    
    if status == 404:
        print("\n   ✗ Doctor profile still not found!")
        print("   This means the existing user needs a doctor profile created.")
        print("   The fix will work for NEW registrations, but existing users need migration.")
    elif status == 200:
        print("\n   ✓ Doctor profile found!")
    else:
        print(f"\n   ? Unexpected status: {status}")

def test_new_registration():
    """Test new doctor registration"""
    print("\n" + "=" * 60)
    print("Testing New Doctor Registration")
    print("=" * 60)
    
    # Register a new doctor
    print("\nRegistering a new doctor...")
    register_data = {
        "email": "newdoc999@example.com",
        "password": "TestPass123!",
        "full_name": "Dr. New Test",
        "role": "doctor"
    }
    
    status, response = make_request("POST", f"{BASE_URL}/auth/register", data=register_data)
    print(f"   Status Code: {status}")
    print(f"   Response: {json.dumps(response, indent=2)}")
    
    if status not in [200, 201]:
        print("   Note: Registration may have failed (possibly duplicate email)")
        return
    
    print("\n   ✓ Registration successful!")
    
    # Login
    print("\nLogging in...")
    login_data = {
        "email": "newdoc999@example.com",
        "password": "TestPass123!"
    }
    
    status, response = make_request("POST", f"{BASE_URL}/auth/login", data=login_data)
    print(f"   Status Code: {status}")
    
    if status != 200:
        print("   ✗ Login failed!")
        return
    
    access_token = response["tokens"]["access_token"]
    print("   ✓ Login successful!")
    
    # Get profile
    print("\nGetting doctor profile...")
    headers = {"Authorization": f"Bearer {access_token}"}
    status, response = make_request("GET", f"{BASE_URL}/doctors/me", headers=headers)
    print(f"   Status Code: {status}")
    print(f"   Response: {json.dumps(response, indent=2)}")
    
    if status == 200:
        print("\n   ✓ Doctor profile auto-created successfully!")
    else:
        print("\n   ✗ Doctor profile not found!")

if __name__ == "__main__":
    test_existing_doctor()
    test_new_registration()
