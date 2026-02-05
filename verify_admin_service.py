
import asyncio
import sys
import uuid

from app.db.session import async_session_factory
from app.models.site import Treatment
from app.models.user import User
from app.utils.enums import UserRole

async def verify_admin_service_creation():
    print("=== Verifying Admin Service Creation API ===")
    
    async with async_session_factory() as db:
        try:
            # Cleanup
            from sqlalchemy import delete
            await db.execute(delete(Treatment).where(Treatment.slug == "new-service-test"))
            await db.execute(delete(User).where(User.email == "admin_test@example.com"))
            await db.commit()
            
            # 1. Create Admin User
            print("Creating admin user...")
            from app.core.security import get_password_hash
            admin = User(
                email="admin_test@example.com",
                full_name="Admin Test",
                hashed_password=get_password_hash("password"),
                role=UserRole.ADMIN.value,
                is_active=True
            )
            db.add(admin)
            await db.commit()
            await db.refresh(admin)
            
            # 2. Get Token (Simulating login/dependencies)
            # Since we can't easily fake dependencies in integration test without overriding,
            # we will assume the dependency injection works and just test the endpoint logic 
            # by manually creating the request with a mocked user context if we were unit testing.
            # However, for integration testing via TestClient/AsyncClient, we need a token.
            
            from app.core.security import create_access_token
            access_token = create_access_token(str(admin.id))
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # 3. Test Create Service
            from httpx import AsyncClient, ASGITransport
            from app.main import app
            
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                
                print("\nTest 1: Create Service (should succeed with Admin)")
                payload = {
                    "name": "New Service Test",
                    "slug": "new-service-test",
                    "category": "cardiology",
                    "short_description": "A new cardiac service",
                    "price_from": 1000.0
                }
                
                response = await client.post(
                    "/api/v1/admin/site/services", # Assuming routed under admin/site
                    json=payload,
                    headers=headers
                )
                
                # Note: Routing might be different. Let's check api_router.py if it fails.
                if response.status_code == 404:
                   print("Trying alternative route /api/v1/admin/services...")
                   response = await client.post(
                       "/api/v1/admin/services",
                       json=payload,
                       headers=headers
                   )

                if response.status_code != 200:
                    print(f"❌ Failed: {response.status_code} - {response.text}")
                    # If it's 401/403, it's auth. If 404, routing.
                    # admin_site.py is usually included in api_router.py
                    sys.exit(1)
                    
                data = response.json()
                print(f"Created Service ID: {data['id']}")
                assert data['name'] == "New Service Test"
                assert data['slug'] == "new-service-test"
                print("✓ Service creation successful")
                
                # Verify in DB
                result = await db.execute(select(Treatment).where(Treatment.slug == "new-service-test"))
                treatment = result.scalar_one_or_none()
                assert treatment is not None
                assert treatment.category == "cardiology"
                print("✓ Persisted to DB")

            # Cleanup
            print("\nCleaning up...")
            await db.delete(treatment)
            await db.delete(admin)
            await db.commit()
            
            print("\nAll Admin Service Creation tests passed!")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    from sqlalchemy import select
    asyncio.run(verify_admin_service_creation())
