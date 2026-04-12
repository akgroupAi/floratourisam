import asyncio
from app.api.v1.pages import router
from app.db.base import Base
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_hero_slider_endpoints():
    print("Testing GET /api/v1/pages/hero-sliders...")
    response = client.get("/api/v1/pages/hero-sliders")
    print("Status:", response.status_code)
    print("Body:", response.json())
    
    print("\nTesting GET /api/v1/pages/home...")
    response = client.get("/api/v1/pages/home")
    print("Status:", response.status_code)
    data = response.json()
    print("Keys in home page:", list(data.keys()))
    if "hero_sliders" in data:
        print("Hero sliders array length:", len(data["hero_sliders"]))

if __name__ == "__main__":
    test_hero_slider_endpoints()
