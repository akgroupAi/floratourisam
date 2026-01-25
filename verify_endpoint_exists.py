
import urllib.request
import urllib.error

try:
    url = "http://127.0.0.1:8000/api/v1/users/me/avatar"
    req = urllib.request.Request(url, method="POST")
    
    with urllib.request.urlopen(req) as response:
        print(f"Status Code: {response.status}")
        print("Endpoint FOUND (Unexpected success without auth)")
        
except urllib.error.HTTPError as e:
    print(f"Status Code: {e.code}")
    if e.code == 404:
        print("Endpoint NOT FOUND (404)")
    elif e.code == 405:
        print("Endpoint Found but Method Not Allowed (405)")
    elif e.code == 401 or e.code == 403:
        print(f"Endpoint FOUND (Received expected auth error: {e.code})")
    else:
        print(f"Endpoint FOUND (Received error: {e.code})")
        
except Exception as e:
    print(f"Connection Error: {e}")
