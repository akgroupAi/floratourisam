#!/usr/bin/env python3
"""
Diagnostic script to test Razorpay credentials and API connectivity.
Run this to identify why orders are failing with 400 errors.
"""

import requests
import json
from app.core.config import settings

def test_razorpay_config():
    """Test if Razorpay is configured."""
    print("\n" + "="*60)
    print("1. CHECKING RAZORPAY CONFIGURATION")
    print("="*60)
    
    if not settings.RAZORPAY_KEY_ID:
        print("❌ RAZORPAY_KEY_ID is not configured")
        return False
    if not settings.RAZORPAY_KEY_SECRET:
        print("❌ RAZORPAY_KEY_SECRET is not configured")
        return False
    
    print(f"✅ KEY_ID configured: {settings.RAZORPAY_KEY_ID[:10]}***")
    print(f"✅ KEY_SECRET configured: {settings.RAZORPAY_KEY_SECRET[:10]}***")
    print(f"✅ Currency: {settings.RAZORPAY_CURRENCY}")
    return True

def test_razorpay_auth():
    """Test Razorpay API authentication."""
    print("\n" + "="*60)
    print("2. TESTING RAZORPAY API AUTHENTICATION")
    print("="*60)
    
    try:
        response = requests.get(
            "https://api.razorpay.com/v1/customers",
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Authentication successful")
            data = response.json()
            print(f"   Customers in account: {data.get('count', 0)}")
            return True
        elif response.status_code == 401:
            print("❌ Authentication failed (401 Unauthorized)")
            print("   Your Razorpay credentials are invalid or expired")
            return False
        else:
            print(f"⚠️  Unexpected status code: {response.status_code}")
            try:
                print(f"   Response: {response.json()}")
            except:
                print(f"   Response: {response.text}")
            return False
            
    except requests.RequestException as e:
        print(f"❌ Connection error: {str(e)}")
        return False

def test_create_test_order():
    """Test creating a Razorpay order."""
    print("\n" + "="*60)
    print("3. TESTING ORDER CREATION")
    print("="*60)
    
    test_amount = 50000  # 500 INR
    test_currency = settings.RAZORPAY_CURRENCY or "INR"
    
    print(f"Creating test order: {test_amount} {test_currency} ({test_amount/100} {test_currency})")
    
    try:
        payload = {
            "amount": test_amount,
            "currency": test_currency,
            "receipt": "test_order_diagnostic",
            "notes": {
                "test": "diagnostic script"
            }
        }
        
        print(f"\nPayload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            "https://api.razorpay.com/v1/orders",
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
            json=payload,
            timeout=10
        )
        
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code in [200, 201]:
            print("✅ Order created successfully!")
            order_data = response.json()
            print(f"   Order ID: {order_data.get('id')}")
            print(f"   Amount: {order_data.get('amount')} {order_data.get('currency')}")
            return True
        else:
            print(f"❌ Order creation failed")
            try:
                error_data = response.json()
                print(f"\nError Response:")
                print(json.dumps(error_data, indent=2))
                
                # Parse specific error messages
                if 'error' in error_data:
                    error_info = error_data['error']
                    print(f"\nError Code: {error_info.get('code')}")
                    print(f"Error Description: {error_info.get('description')}")
                    
                    # Provide helpful hints
                    if "invalid_base64" in str(error_info.get('code', '')).lower():
                        print("\n💡 Hint: Invalid credentials format. Check RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET")
                    elif "unauthorized" in str(error_info.get('description', '')).lower():
                        print("\n💡 Hint: Credentials are invalid or test account is not active")
                    elif "invalid_field" in str(error_info.get('code', '')).lower():
                        print("\n💡 Hint: One of the request fields is invalid (amount, currency, etc.)")
                    elif test_currency not in ["INR", "USD", "EUR", "GBP", "AED"]:
                        print(f"\n💡 Hint: Currency '{test_currency}' may not be supported. Try 'INR', 'USD', 'EUR', 'GBP', or 'AED'")
                        
            except Exception as e:
                print(f"Response text: {response.text}")
            return False
            
    except requests.RequestException as e:
        print(f"❌ Connection error: {str(e)}")
        return False

def test_webhook_configuration():
    """Test webhook configuration."""
    print("\n" + "="*60)
    print("4. WEBHOOK CONFIGURATION CHECK")
    print("="*60)
    
    webhook_url = settings.RAZORPAY_WEBHOOK_URL if hasattr(settings, 'RAZORPAY_WEBHOOK_URL') else "Not configured"
    print(f"Webhook URL: {webhook_url}")
    
    if webhook_url == "Not configured":
        print("⚠️  No webhook URL configured (optional for local testing)")
    else:
        print("✅ Webhook URL configured")

def main():
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*10 + "RAZORPAY DIAGNOSTIC TEST SUITE" + " "*18 + "║")
    print("╚" + "="*58 + "╝")
    
    results = {
        "Configuration": test_razorpay_config(),
        "Authentication": test_razorpay_auth(),
        "Order Creation": test_create_test_order(),
    }
    
    test_webhook_configuration()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✅ All tests passed! Razorpay is properly configured.")
    else:
        print("\n❌ Some tests failed. Check the errors above.")
        print("\nCommon fixes:")
        print("1. Verify RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env")
        print("2. Ensure your Razorpay test account is active")
        print("3. Check that credentials are for the same merchant account")
        print("4. Verify currency setting matches your account configuration")
    
    print("\n")

if __name__ == "__main__":
    main()
