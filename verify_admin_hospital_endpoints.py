"""Verification script for admin hospital and department endpoints."""

import asyncio
import httpx
from typing import Optional

BASE_URL = "http://localhost:8000/api/v1"

# You'll need to replace this with a valid admin token
ADMIN_TOKEN = "your_admin_token_here"

headers = {
    "Authorization": f"Bearer {ADMIN_TOKEN}",
    "Content-Type": "application/json"
}


async def test_hospital_endpoints():
    """Test hospital management endpoints."""
    print("\n" + "="*60)
    print("Testing Hospital Management Endpoints")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        # Test Hospital KPIs
        print("\n1. Testing Hospital KPIs...")
        response = await client.get(f"{BASE_URL}/admin/hospitals/kpis", headers=headers)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Total Hospitals: {data.get('total_hospitals')}")
            print(f"   Active Hospitals: {data.get('active_hospitals')}")
            print(f"   Total Departments: {data.get('total_departments')}")
            print(f"   Total Doctors: {data.get('total_doctors')}")
        else:
            print(f"   Error: {response.text}")
        
        # Test List Hospitals
        print("\n2. Testing List Hospitals...")
        response = await client.get(f"{BASE_URL}/admin/hospitals?page=1&page_size=10", headers=headers)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Total: {data.get('total')}")
            print(f"   Items: {len(data.get('items', []))}")
        else:
            print(f"   Error: {response.text}")
        
        # Test Create Hospital
        print("\n3. Testing Create Hospital...")
        hospital_data = {
            "name": "Test Medical Center",
            "slug": "test-medical-center",
            "description": "A test hospital for verification",
            "email": "info@testmedical.com",
            "phone": "+1234567890",
            "website": "https://testmedical.com",
            "address_line1": "123 Test Street",
            "city": "Test City",
            "country": "Test Country",
            "postal_code": "12345",
            "is_active": True
        }
        response = await client.post(f"{BASE_URL}/admin/hospitals", headers=headers, json=hospital_data)
        print(f"   Status: {response.status_code}")
        
        hospital_id = None
        if response.status_code == 200:
            data = response.json()
            hospital_id = data.get('id')
            print(f"   Created Hospital ID: {hospital_id}")
            print(f"   Name: {data.get('name')}")
        else:
            print(f"   Error: {response.text}")
        
        # Test Get Hospital
        if hospital_id:
            print("\n4. Testing Get Hospital...")
            response = await client.get(f"{BASE_URL}/admin/hospitals/{hospital_id}", headers=headers)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Hospital: {data.get('name')}")
            else:
                print(f"   Error: {response.text}")
            
            # Test Update Hospital
            print("\n5. Testing Update Hospital...")
            update_data = {
                "description": "Updated description for test hospital"
            }
            response = await client.put(f"{BASE_URL}/admin/hospitals/{hospital_id}", headers=headers, json=update_data)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print(f"   Hospital updated successfully")
            else:
                print(f"   Error: {response.text}")
            
            # Test Delete Hospital
            print("\n6. Testing Delete Hospital...")
            response = await client.delete(f"{BASE_URL}/admin/hospitals/{hospital_id}", headers=headers)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print(f"   Hospital deleted successfully")
            else:
                print(f"   Error: {response.text}")


async def test_department_endpoints():
    """Test department management endpoints."""
    print("\n" + "="*60)
    print("Testing Department Management Endpoints")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        # Test Department KPIs
        print("\n1. Testing Department KPIs...")
        response = await client.get(f"{BASE_URL}/admin/departments/kpis", headers=headers)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Total Departments: {data.get('total_departments')}")
            print(f"   Active Departments: {data.get('active_departments')}")
            print(f"   Total Hospitals: {data.get('total_hospitals')}")
            print(f"   Total Doctors: {data.get('total_doctors')}")
        else:
            print(f"   Error: {response.text}")
        
        # Test List Departments
        print("\n2. Testing List Departments...")
        response = await client.get(f"{BASE_URL}/admin/departments?page=1&page_size=10", headers=headers)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Total: {data.get('total')}")
            print(f"   Items: {len(data.get('items', []))}")
        else:
            print(f"   Error: {response.text}")
        
        # For Create/Update/Delete, we need a valid hospital_id
        # This would need to be obtained from the database or created first
        print("\n3. Note: Create/Update/Delete tests require a valid hospital_id")
        print("   Please test these manually with a valid hospital_id")


async def main():
    """Run all verification tests."""
    print("\n" + "="*60)
    print("Admin Hospital & Department Endpoints Verification")
    print("="*60)
    print("\nNOTE: Make sure to:")
    print("1. Update ADMIN_TOKEN with a valid admin token")
    print("2. Ensure the API server is running on http://localhost:8000")
    print("3. Have admin authentication set up")
    
    try:
        await test_hospital_endpoints()
        await test_department_endpoints()
        
        print("\n" + "="*60)
        print("Verification Complete!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error during verification: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
