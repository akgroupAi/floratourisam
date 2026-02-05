
import asyncio
import sys
import uuid
from datetime import datetime, time

from app.db.session import async_session_factory
from app.models.site import Treatment
from app.models.doctor import Doctor, DoctorSpecialization
from app.models.user import User

async def verify_service_endpoints():
    print("=== Verifying Service Page Endpoints ===")
    
    async with async_session_factory() as db:
        try:
            # Cleanup
            from sqlalchemy import delete
            await db.execute(delete(Treatment).where(Treatment.slug == "knee-replacement-test"))
            await db.execute(delete(User).where(User.email == "dr_ortho_test@example.com"))
            await db.commit()
            
            # 1. Create Test Treatment
            print("Creating test treatment...")
            treatment = Treatment(
                name="Knee Replacement",
                slug="knee-replacement-test",
                category="Orthopedics",
                description="Total knee replacement surgery.",
                price_from=5000.0,
                price_to=8000.0
            )
            db.add(treatment)
            await db.flush()
            
            # 2. Create Test Doctor
            print("Creating test doctor...")
            user = User(
                email="dr_ortho_test@example.com",
                full_name="Dr. Ortho Test",
                hashed_password="hashed_password",
                is_active=True
            )
            db.add(user)
            await db.flush()
            
            doctor = Doctor(
                user_id=user.id,
                title="Chief Surgeon",
                years_of_experience=15,
                rating=4.9,
                is_verified=True,
                consultation_fee=100.0
            )
            db.add(doctor)
            await db.flush()
            
            # 3. Add Specialization
            print("Adding specialization 'Orthopedics'...")
            spec = DoctorSpecialization(
                doctor_id=doctor.id,
                specialization="Orthopedics", # Matches treatment category
                is_primary=True
            )
            db.add(spec)
            await db.commit()
            
            # 4. Test Service Doctors Endpoint
            from httpx import AsyncClient, ASGITransport
            from app.main import app
            
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                
                print("\nTest 1: Get Doctors for Service (by Category Match)")
                response = await client.get("/api/v1/pages/services/knee-replacement-test/doctors")
                
                if response.status_code != 200:
                    print(f"❌ Failed: {response.text}")
                    sys.exit(1)
                    
                data = response.json()
                print(f"Found {data['total']} doctors")
                assert data['total'] >= 1
                assert any(d['name'] == "Dr. Ortho Test" for d in data['items'])
                print("✓ Found doctor matching category")
                
                # Verify response structure (TeamMemberResponse) fields
                doc_item = next(d for d in data['items'] if d['name'] == "Dr. Ortho Test")
                assert doc_item['role'] == "Chief Surgeon"
                assert doc_item['department'] == "Orthopedics"
                print("✓ Response structure verified")

            # Cleanup
            print("\nCleaning up...")
            await db.delete(spec)
            await db.delete(doctor)
            await db.delete(user)
            await db.delete(treatment)
            await db.commit()
            
            print("\nAll Service Endpoint tests passed!")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(verify_service_endpoints())
