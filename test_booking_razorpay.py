#!/usr/bin/env python3
"""
Script to test Razorpay order creation with actual apartment booking data.
"""

import asyncio
import json
import requests
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.booking import Booking
from app.models.base import Base

async def main():
    print("\n" + "="*60)
    print("TESTING RAZORPAY WITH ACTUAL BOOKING DATA")
    print("="*60)
    
    # Create database session
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # Get recent apartment bookings
        result = await db.execute(
            select(Booking)
            .where(Booking.booking_type == "APARTMENT")
            .order_by(Booking.created_at.desc())
            .limit(5)
        )
        bookings = result.scalars().all()
        
        if not bookings:
            print("❌ No apartment bookings found in database")
            return
        
        print(f"\nFound {len(bookings)} recent apartment bookings\n")
        
        for i, booking in enumerate(bookings, 1):
            print(f"\n{'-'*60}")
            print(f"Booking #{i}")
            print(f"{'-'*60}")
            print(f"ID: {booking.id}")
            print(f"Type: {booking.booking_type}")
            print(f"Status: {booking.status}")
            print(f"Is Paid: {booking.is_paid}")
            print(f"Total Price: {booking.total_price}")
            print(f"Currency: {booking.currency}")
            print(f"Created At: {booking.created_at}")
            
            # Validate the data
            print(f"\nValidation Check:")
            
            errors = []
            
            if not booking.total_price or booking.total_price <= 0:
                errors.append(f"❌ Invalid amount: {booking.total_price}")
            else:
                amount = round(booking.total_price, 2)
                amount_paise = int(round(amount * 100))
                print(f"✅ Amount valid: {amount} (→ {amount_paise} paise)")
            
            currency = (booking.currency or settings.RAZORPAY_CURRENCY).upper()
            if not currency or len(currency) != 3:
                errors.append(f"❌ Invalid currency: {currency}")
            else:
                print(f"✅ Currency valid: {currency}")
            
            receipt = f"order_{booking.id}"
            if len(receipt) > 40:
                errors.append(f"❌ Receipt too long: {len(receipt)} chars (max 40)")
            else:
                print(f"✅ Receipt valid: {receipt} ({len(receipt)} chars)")
            
            if booking.is_paid:
                errors.append(f"❌ Booking already paid")
            else:
                print(f"✅ Booking not yet paid")
            
            if errors:
                print(f"\n⚠️  Issues found:")
                for error in errors:
                    print(f"   {error}")
                continue
            
            # Try to create order with this booking
            print(f"\nAttempting to create Razorpay order...")
            
            try:
                payload = {
                    "amount": int(round(booking.total_price * 100)),
                    "currency": currency,
                    "receipt": receipt,
                    "notes": {
                        "booking_id": str(booking.id),
                        "user_id": str(booking.user_id),
                        "booking_type": booking.booking_type,
                    },
                }
                
                response = requests.post(
                    "https://api.razorpay.com/v1/orders",
                    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
                    json=payload,
                    timeout=10
                )
                
                if response.status_code in [200, 201]:
                    order_data = response.json()
                    print(f"✅ ORDER CREATED: {order_data.get('id')}")
                else:
                    print(f"❌ ORDER CREATION FAILED (HTTP {response.status_code})")
                    try:
                        error_response = response.json()
                        print(f"\nError Details:")
                        print(json.dumps(error_response, indent=2))
                    except:
                        print(f"Response: {response.text}")
                        
            except Exception as e:
                print(f"❌ Exception: {str(e)}")
    
    await engine.dispose()
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
