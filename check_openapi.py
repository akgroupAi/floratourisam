
import sys
import os
import json

# Add current directory to path
sys.path.append(os.getcwd())

try:
    from app.main import app
    
    print("Generating OpenAPI schema...")
    schema = app.openapi()
    
    found = False
    paths = []
    
    for path, methods in schema["paths"].items():
        if "/users/me/avatar" in path:
            found = True
            print(f"FOUND ENDPOINT: {path}")
            print(f"Methods: {list(methods.keys())}")
        paths.append(path)
            
    if not found:
        print("ENDPOINT NOT FOUND in OpenAPI schema.")
        print("Available User endpoints:")
        for p in paths:
             if "users" in p:
                 print(f" - {p}")
                 
except Exception as e:
    print(f"Error generating schema: {e}")
    import traceback
    traceback.print_exc()
