"""Verification script for new flows."""
import asyncio
import json
import uuid
from datetime import datetime, timedelta, date, time
import sys
import os

# Add app to path
sys.path.append(os.getcwd())

from app.db.session import async_session_factory as async_session_maker
from app.services.doctor_service import DoctorService
from app.services.patient_service import PatientService
from app.services.consultation_service import ConsultationService
from app.services.hotel_service import HotelService
from app.services.restaurant_service import RestaurantService
from app.services.booking_service import BookingService
from app.schemas.doctor import DoctorUpdate
from app.schemas.consultation import ConsultationCreate
from app.schemas.booking import HotelBookingCreate, RestaurantBookingCreate
from app.models.user import User
from app.core.security import get_password_hash
from app.utils.enums import ConsultationType

async def verify_doctor_flow(db):
    print("\n=== Verifying Doctor Flow ===")
    
    # Create doctor user
    email = f"doc_{uuid.uuid4()}@example.com"
    user = User(
        email=email,
        hashed_password=get_password_hash("password"),
        full_name="Test Doctor",
        role="doctor",
        is_active=True
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    print("Created Doctor User")

    # Service
    service = DoctorService(db)
    doctor = await service.get_by_user_id(user.id)
    if not doctor:
        from app.schemas.doctor import DoctorCreate
        create_data = DoctorCreate(user_id=user.id, full_name=user.full_name)
        doctor = await service.create(user.id, create_data, user.id)
    print("Created Doctor Profile")

    # Update with new schema (List[dict])
    update_data = DoctorUpdate(
        education=[
            {"degree": "MBBS", "university": "Test Uni", "year": 2010},
            {"degree": "MD", "university": "Test Uni 2", "year": 2015}
        ],
        certifications=[
            {"name": "Board Certified", "year": 2016}
        ],
        consultation_fee=150.0
    )
    
    updated_doc = await service.update(doctor, update_data, user.id)
    print(f"Updated Profile: Education type is {type(updated_doc.education)}")
    print(f"Education data: {updated_doc.education}")
    
    assert isinstance(updated_doc.education, list)
    assert len(updated_doc.education) == 2
    print("✓ Doctor Profile Update Verified")
    return updated_doc

async def verify_patient_consultation(db, doctor_id):
    print("\n=== Verifying Patient Consultation ===")
    
    # Create patient user
    email = f"pat_{uuid.uuid4()}@example.com"
    user = User(
        email=email,
        hashed_password=get_password_hash("password"),
        full_name="Test Patient",
        role="patient",
        is_active=True
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    print("Created Patient User")
    
    # Service
    patient_service = PatientService(db)
    patient = await patient_service.get_or_create(user.id)
    
    # Book Consultation
    consultation_service = ConsultationService(db)
    booking_service = BookingService(db)
    
    print("Booking Consultation...")
    data = ConsultationCreate(
        doctor_id=doctor_id,
        scheduled_at=datetime.now() + timedelta(days=1),
        consultation_type=ConsultationType.VIDEO.value,
        reason="Headache"
    )
    
    consultation = await consultation_service.create(patient.id, data, user.id)
    print(f"Created Consultation ID: {consultation.id}")
    
    # Verify Booking created
    booking = await booking_service.get_by_reference(f"BKG-{consultation.reference_number.split('-')[1]}") 
    # Reference logic might differ, let's find by consultation_id directly using raw query or just list
    
    bookings, _ = await booking_service.get_list(
        pagination=type('obj', (object,), {'offset': 0, 'page_size': 10})(),
        patient_id=patient.id
    )
    
    booking = next((b for b in bookings if b.consultation_id == consultation.id), None)
    
    assert booking is not None
    print(f"✓ Associated Booking found: {booking.reference_number}")
    print(f"✓ Booking Price: {booking.total_price}")
    
    return patient

async def verify_hotel_flow(db, patient):
    print("\n=== Verifying Hotel Flow ===")
    
    # Assume we have a hotel and room (or create one for test)
    # Since we didn't implement hotel creation API, let's create DB entry manually
    from app.models.hotel import Hotel, Room
    
    hotel = Hotel(
        name="Test Hotel",
        slug=f"test-hotel-{uuid.uuid4()}",
        city="Test City",
        country="Test Country",
        address_line1="123 Test St"
    )
    db.add(hotel)
    await db.flush()
    
    room = Room(
        hotel_id=hotel.id,
        name="Deluxe Room",
        price_per_night=200.0,
        total_rooms=5
    )
    db.add(room)
    await db.commit()
    print("Created Mock Hotel and Room")
    
    # Service
    hotel_service = HotelService(db)
    hotels, _ = await hotel_service.get_list(type('obj', (object,), {'offset': 0, 'page_size': 10})())
    assert len(hotels) > 0
    print(f"✓ Listed Hotels: {len(hotels)}")
    
    # Book Hotel
    booking_service = BookingService(db)
    booking_data = HotelBookingCreate(
        room_id=room.id,
        check_in_date=date.today() + timedelta(days=5),
        check_out_date=date.today() + timedelta(days=7),
        guest_count=2
    )
    
    booking = await booking_service.create_hotel_booking(patient.id, booking_data, patient.user_id)
    print(f"✓ Hotel Booking Created: {booking.reference_number}")
    print(f"✓ Total Price: {booking.total_price} (Should be ~ 440.0 with tax)")

async def verify_restaurant_flow(db, patient):
    print("\n=== Verifying Restaurant Flow ===")
    
    # Mock Restaurant
    from app.models.restaurant import Restaurant, MenuItem
    
    restaurant = Restaurant(
        name="Test Restaurant",
        slug=f"test-rest-{uuid.uuid4()}",
        city="Test City",
        country="Test Country",
        address_line1="456 Food St"
    )
    db.add(restaurant)
    await db.flush()
    
    item = MenuItem(
        restaurant_id=restaurant.id,
        name="Test Burger",
        category="Mains",
        price=15.0
    )
    db.add(item)
    await db.commit()
    print("Created Mock Restaurant and Menu")
    
    # Service
    restaurant_service = RestaurantService(db)
    menu = await restaurant_service.get_menu(restaurant.id)
    assert len(menu) > 0
    print(f"✓ Menu Retrieved: {len(menu)} items")
    
    # Book Restaurant
    booking_service = BookingService(db)
    booking_data = RestaurantBookingCreate(
        restaurant_id=restaurant.id,
        booking_date=date.today() + timedelta(days=2),
        booking_time=time(19, 0),
        guest_count=2
    )
    
    booking = await booking_service.create_restaurant_booking(patient.id, booking_data, patient.user_id)
    print(f"✓ Restaurant Booking Created: {booking.reference_number}")


async def main():
    async with async_session_maker() as db:
        try:
            doctor = await verify_doctor_flow(db)
            patient = await verify_patient_consultation(db, doctor.id)
            await verify_hotel_flow(db, patient)
            await verify_restaurant_flow(db, patient)
            print("\nAll verifications passed successfully!")
        except Exception as e:
            print(f"\n❌ Verification Failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
