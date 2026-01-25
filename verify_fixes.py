"""Verify fixes for Doctor List and Patient update issues."""
import urllib.request
import urllib.error
import json
import time

BASE_URL = "http://127.0.0.1:8000/api/v1"

def make_request(method, url, data=None, token=None):
    headers = {
        "Content-Type": "application/json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    if data:
        data = json.dumps(data).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))
    except Exception as e:
        return 0, str(e)

def verify_doctor_list():
    print("\n=== Verifying Doctor List Endpoint ===")
    status, response = make_request("GET", f"{BASE_URL}/doctors?page=1&page_size=5")
    print(f"Status: {status}")
    if status == 200:
        print("✓ Doctor list endpoint is working!")
        items = response.get('items', [])
        if items:
            print(f"  Found {len(items)} doctors.")
            print(f"  First doctor: {items[0].get('full_name')} - {items[0].get('title')}")
        else:
            print("  No doctors found (but endpoint worked).")
    else:
        print("✗ Doctor list endpoint failed!")
        print(response)

def verify_patient_update_as_doctor():
    print("\n=== Verifying Patient Update as Doctor ===")
    
    # 1. Login as doctor (using the one we created/fixed earlier)
    # Reuse token if possible or login again
    login_data = {
        "email": "testdoctor123@example.com", 
        "password": "TestPass123!"
    }
    
    # Try existing doctor credential if above fails
    status, response = make_request("POST", f"{BASE_URL}/auth/login", login_data)
    if status != 200:
        # Try the other doctor created in tests
        login_data["email"] = "newdoc999@example.com"
        status, response = make_request("POST", f"{BASE_URL}/auth/login", login_data)
    
    if status != 200:
        print("Skipping patient test - could not login as doctor.")
        return

    token = response["tokens"]["access_token"]
    print(f"Logged in as doctor. Token obtained.")
    
    # 2. Try to update patient profile
    print("Attempting PUT /api/v1/patients/me...")
    update_data = {
        "blood_group": "A+",
        "allergies": "None"
    }
    
    status, response = make_request("PUT", f"{BASE_URL}/patients/me", update_data, token)
    print(f"Status: {status}")
    
    if status == 200:
        print("✓ Patient profile updated successfully!")
        print(f"  Patient ID: {response.get('id')}")
    else:
        print("✗ Patient profile update failed!")
        print(response)

if __name__ == "__main__":
    verify_doctor_list()
    verify_patient_update_as_doctor()
