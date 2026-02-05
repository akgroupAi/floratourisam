
import asyncio
import sys
import uuid
from typing import List

from app.db.session import async_session_factory
from app.models.site import TeamMember
from app.models.user import User
from app.utils.enums import UserRole
from app.api.v1.admin_site import create_team_member # Just to verify import

async def verify_team_endpoints():
    print("=== Verifying Team Page Endpoints ===")
    
    async with async_session_factory() as db:
        try:
            # Cleanup
            from sqlalchemy import delete
            await db.execute(delete(TeamMember).where(TeamMember.name.like("Test Team Member%")))
            await db.execute(delete(User).where(User.email == "admin_team_test@example.com"))
            await db.commit()
            
            # 1. Create Admin User
            print("Creating admin user...")
            from app.core.security import get_password_hash
            admin = User(
                email="admin_team_test@example.com",
                full_name="Admin Team Test",
                hashed_password=get_password_hash("password"),
                role=UserRole.ADMIN.value,
                is_active=True
            )
            db.add(admin)
            await db.commit()
            await db.refresh(admin)
            
            # 2. Setup Client
            from httpx import AsyncClient, ASGITransport
            from app.main import app
            from app.core.security import create_access_token
            access_token = create_access_token(str(admin.id))
            headers = {"Authorization": f"Bearer {access_token}"}
            
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                
                # --- Admin Create Tests ---
                print("\nTest 1: Admin Create Team Members")
                
                # Member 1: Leadership
                payload1 = {
                    "name": "Test Team Member 1",
                    "role": "CEO",
                    "bio": "Visionary leader.",
                    "is_leadership": True,
                    "linkedin_url": "https://linkedin.com/in/test1"
                }
                resp1 = await client.post("/api/v1/admin/site/team", json=payload1, headers=headers)
                assert resp1.status_code == 200
                data1 = resp1.json()
                assert data1['is_leadership'] == True
                print("✓ Created Leadership Member")
                
                # Member 2: General
                payload2 = {
                    "name": "Test Team Member 2",
                    "role": "Developer",
                    "is_leadership": False
                }
                resp2 = await client.post("/api/v1/admin/site/team", json=payload2, headers=headers)
                assert resp2.status_code == 200
                data2 = resp2.json()
                assert data2['is_leadership'] == False
                print("✓ Created General Team Member")
                
                # --- Public Get Test ---
                print("\nTest 2: Public Get Team Page")
                resp_public = await client.get("/api/v1/pages/team")
                
                # Fallback if I got the path wrong in my memory (pages.py mounted at /api/v1/pages usually)
                if resp_public.status_code == 404: 
                    print("Trying alternate path...")
                    resp_public = await client.get("/api/v1/team") # Try direct mounting if applicable
                
                assert resp_public.status_code == 200
                public_data = resp_public.json()
                
                # Verify Structure
                assert "leadership" in public_data
                assert "team" in public_data
                
                # Verify Content
                leadership_names = [m['name'] for m in public_data['leadership']]
                team_names = [m['name'] for m in public_data['team']]
                
                assert "Test Team Member 1" in leadership_names
                assert "Test Team Member 2" in team_names
                assert "Test Team Member 1" not in team_names
                print("✓ Public Endpoint returned correct categorized data")
                
                # --- Admin Update Test ---
                print("\nTest 3: Admin Update Member")
                update_payload = {"role": "Founder & CEO"}
                resp_upd = await client.put(f"/api/v1/admin/site/team/{data1['id']}", json=update_payload, headers=headers)
                assert resp_upd.status_code == 200
                assert resp_upd.json()['role'] == "Founder & CEO"
                print("✓ Admin Update successful")
                
                # --- Admin Delete Test ---
                print("\nTest 4: Admin Delete")
                resp_del = await client.delete(f"/api/v1/admin/site/team/{data2['id']}", headers=headers)
                assert resp_del.status_code == 200
                
                # Verify deletion
                resp_check = await client.get("/api/v1/pages/team")
                team_names_after = [m['name'] for m in resp_check.json()['team']]
                assert "Test Team Member 2" not in team_names_after
                print("✓ Admin Delete successful")

            # Cleanup
            print("\nCleaning up...")
            from sqlalchemy import select
            # Get member 1 to delete manually since we deleted member 2 via API
            # Actually just delete all test members
            await db.execute(delete(TeamMember).where(TeamMember.name.like("Test Team Member%")))
            await db.delete(admin)
            await db.commit()
            
            print("\nAll Team Endpoint tests passed!")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(verify_team_endpoints())
