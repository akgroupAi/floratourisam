
import asyncio
import sys
import uuid
from datetime import time

from app.db.session import async_session_factory
from app.models.doctor import Doctor, DoctorSpecialization
from app.models.hospital import Hospital
from app.models.user import User
from app.utils.enums import UserRole

async def verify_doctors_endpoints():
    print("=== Verifying Doctors Page Endpoints ===")
    
    async with async_session_factory() as db:
        try:
            # Cleanup
            from sqlalchemy import delete, select
            await db.execute(delete(DoctorSpecialization).where(
                DoctorSpecialization.doctor_id.in_(
                    select(Doctor.id).where(Doctor.user_id.in_(
                        select(User.id).where(User.email.like("test_doctor%@example.com"))
                    ))
                )
            ))
            await db.execute(delete(Doctor).where(
                Doctor.user_id.in_(
                    select(User.id).where(User.email.like("test_doctor%@example.com"))
                )
            ))
            await db.execute(delete(User).where(User.email.like("test_doctor%@example.com")))
            await db.execute(delete(Hospital).where(Hospital.name == "Test Hospital"))
            await db.commit()
            
            # 1. Create Test Hospital
            print("Creating test hospital...")
            hospital = Hospital(
                name="Test Hospital",
                slug="test-hospital",
                address_line1="123 Test Street",
                city="Delhi",
                country="India",
                is_verified=True
            )
            db.add(hospital)
            await db.flush()
            
            # 2. Create Test Doctors
            print("Creating test doctors...")
            from app.core.security import get_password_hash
            
            # Doctor 1: Cardiologist
            user1 = User(
                email="test_doctor1@example.com",
                full_name="Dr. Test Cardiologist",
                hashed_password=get_password_hash("password"),
                role=UserRole.DOCTOR.value,
                is_active=True
            )
            db.add(user1)
            await db.flush()
            
            doctor1 = Doctor(
                user_id=user1.id,
                hospital_id=hospital.id,
                title="Senior Cardiologist",
                bio="Expert in heart diseases.",
                years_of_experience=15,
                rating=4.8,
                consultation_fee=200.0,
                is_verified=True,
                languages_spoken=["English", "Hindi"],
                qualifications=["MBBS", "MD Cardiology"]
            )
            db.add(doctor1)
            await db.flush()
            
            # Add specialization
            spec1 = DoctorSpecialization(
                doctor_id=doctor1.id,
                specialization="Cardiology",
                is_primary=True
            )
            db.add(spec1)
            
            # Doctor 2: Orthopedic
            user2 = User(
                email="test_doctor2@example.com",
                full_name="Dr. Test Orthopedic",
                hashed_password=get_password_hash("password"),
                role=UserRole.DOCTOR.value,
                is_active=True
            )
            db.add(user2)
            await db.flush()
            
            doctor2 = Doctor(
                user_id=user2.id,
                hospital_id=hospital.id,
                title="Orthopedic Surgeon",
                bio="Specialist in bone and joint surgeries.",
                years_of_experience=10,
                rating=4.5,
                consultation_fee=150.0,
                is_verified=True
            )
            db.add(doctor2)
            await db.flush()
            
            spec2 = DoctorSpecialization(
                doctor_id=doctor2.id,
                specialization="Orthopedics",
                is_primary=True
            )
            db.add(spec2)
            
            await db.commit()
            
            # 3. Test Endpoints
            from httpx import AsyncClient, ASGITransport
            from app.main import app
            
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                
                print("\nTest 1: List All Doctors")
                response = await client.get("/api/v1/pages/doctors")
                assert response.status_code == 200
                data = response.json()
                assert data['total'] >= 2
                print(f"✓ Found {data['total']} doctors")
                
                print("\nTest 2: Search Doctors by Name")
                response = await client.get("/api/v1/pages/doctors?search=Cardiologist")
                assert response.status_code == 200
                data = response.json()
                assert any("Cardiologist" in d['name'] or "Cardiologist" in (d['title'] or "") for d in data['items'])
                print("✓ Search by name works")
                
                print("\nTest 3: Filter by Specialization")
                response = await client.get("/api/v1/pages/doctors?specialization=Cardiology")
                assert response.status_code == 200
                data = response.json()
                assert any("Cardiology" in d['specializations'] for d in data['items'])
                print("✓ Filter by specialization works")
                
                print("\nTest 4: Filter by Location")
                response = await client.get("/api/v1/pages/doctors?location=Delhi")
                assert response.status_code == 200
                data = response.json()
                assert data['total'] >= 1
                print("✓ Filter by location works")
                
                print("\nTest 5: Get Doctor Detail")
                response = await client.get(f"/api/v1/pages/doctors/{doctor1.id}")
                assert response.status_code == 200
                detail = response.json()
                assert detail['name'] == "Dr. Test Cardiologist"
                assert detail['bio'] == "Expert in heart diseases."
                assert "Cardiology" in detail['specializations']
                assert detail['consultation_fee'] == 200.0
                assert "English" in detail['languages_spoken']
                assert "MBBS" in detail['qualifications']
                print("✓ Doctor detail endpoint works")
                
                print("\nTest 6: Pagination")
                response = await client.get("/api/v1/pages/doctors?page=1&page_size=1")
                assert response.status_code == 200
                data = response.json()
                assert len(data['items']) == 1
                assert data['page'] == 1
                print("✓ Pagination works")

            # Cleanup
            print("\nCleaning up...")
            await db.delete(spec1)
            await db.delete(spec2)
            await db.delete(doctor1)
            await db.delete(doctor2)
            await db.delete(user1)
            await db.delete(user2)
            await db.delete(hospital)
            await db.commit()
            
            print("\nAll Doctors Endpoint tests passed!")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(verify_doctors_endpoints())
