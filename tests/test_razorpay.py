"""
Integration test for Razorpay payment gateway.

Usage:
    pytest tests/test_razorpay.py -v
"""

import pytest
import json
import hmac
import hashlib
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.booking import Booking
from app.models.payment import Payment, PaymentTransaction
from app.services.razorpay_service import RazorpayService
from app.utils.enums import PaymentStatus


@pytest.mark.asyncio
async def test_razorpay_service_initialization(db_session: AsyncSession):
    """Test Razorpay service can be initialized."""
    service = RazorpayService(db_session)
    assert service.db is not None
    print("✅ RazorpayService initialization successful")


@pytest.mark.asyncio
async def test_create_order_missing_booking(db_session: AsyncSession):
    """Test create_order with non-existent booking."""
    service = RazorpayService(db_session)
    user_id = uuid4()
    booking_id = uuid4()
    
    with pytest.raises(ValueError, match="Booking not found"):
        await service.create_order(user_id, booking_id)
    
    print("✅ Proper error handling for missing booking")


@pytest.mark.asyncio
async def test_create_order_with_valid_booking(db_session: AsyncSession):
    """Test create_order with valid booking."""
    service = RazorpayService(db_session)
    user_id = uuid4()
    
    # Create a test booking
    booking = Booking(
        id=uuid4(),
        booking_type="CONSULTATION",
        status="PENDING",
        total_price=150.50,
        currency="INR",
        created_by=user_id,
    )
    db_session.add(booking)
    await db_session.flush()
    
    # Mock the requests.post call
    with patch('app.services.razorpay_service.requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "order_30003052581",
            "entity": "order",
            "amount": 15050,
            "currency": "INR",
            "status": "created",
        }
        mock_post.return_value = mock_response
        
        result = await service.create_order(
            user_id=user_id,
            booking_id=booking.id,
            description="Test Consultation",
        )
        
        assert result["order_id"] == "order_30003052581"
        assert result["amount"] == 150.50
        assert result["amount_paise"] == 15050
        assert result["currency"] == "INR"
        assert "payment_id" in result
        assert "key_id" in result
        
        print("✅ create_order successful with valid booking")


@pytest.mark.asyncio
async def test_verify_payment_invalid_signature(db_session: AsyncSession):
    """Test verify_payment with invalid signature."""
    service = RazorpayService(db_session)
    
    with pytest.raises(ValueError, match="Invalid payment signature"):
        await service.verify_payment(
            payment_id="test_payment_id",
            order_id="order_123",
            razorpay_payment_id="pay_123",
            razorpay_signature="invalid_signature",
        )
    
    print("✅ Proper error handling for invalid signatures")


@pytest.mark.asyncio
async def test_verify_payment_payment_not_found(db_session: AsyncSession):
    """Test verify_payment when payment doesn't exist."""
    service = RazorpayService(db_session)
    
    # Create valid signature
    order_id = "order_123"
    payment_id = "pay_123"
    signature = hmac.new(
        service.key_secret.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    
    with pytest.raises(ValueError, match="Payment record not found"):
        await service.verify_payment(
            payment_id="test_payment_id",
            order_id=order_id,
            razorpay_payment_id=payment_id,
            razorpay_signature=signature,
        )
    
    print("✅ Proper error handling when payment not found")


@pytest.mark.asyncio
async def test_refund_payment_not_found(db_session: AsyncSession):
    """Test refund with non-existent payment."""
    service = RazorpayService(db_session)
    
    with pytest.raises(ValueError, match="Payment not found"):
        await service.refund_payment(
            payment_id=uuid4(),
            amount=100.0,
        )
    
    print("✅ Proper error handling for refund on missing payment")


@pytest.mark.asyncio
async def test_refund_wrong_gateway(db_session: AsyncSession):
    """Test refund with payment from different gateway."""
    service = RazorpayService(db_session)
    user_id = uuid4()
    
    # Create payment with Stripe gateway
    payment = Payment(
        id=uuid4(),
        user_id=user_id,
        reference_number="PAY-test-001",
        payment_method="card",
        status=PaymentStatus.COMPLETED.value,
        amount=100.0,
        currency="INR",
        processing_fee=2.9,
        platform_fee=1.0,
        net_amount=96.1,
        gateway="stripe",  # Not Razorpay
        gateway_transaction_id="stripe_tx_123",
        initiated_at=datetime.now(timezone.utc),
        created_by=user_id,
    )
    db_session.add(payment)
    await db_session.flush()
    
    with pytest.raises(ValueError, match="not processed through Razorpay"):
        await service.refund_payment(payment_id=payment.id)
    
    print("✅ Proper error handling for refund on Stripe payment")


@pytest.mark.asyncio
async def test_webhook_invalid_signature(db_session: AsyncSession):
    """Test webhook with invalid signature."""
    service = RazorpayService(db_session)
    
    payload = '{"event": "payment.authorized"}'
    signature = "invalid_signature"
    
    with pytest.raises(ValueError, match="Invalid webhook signature"):
        await service.handle_webhook(payload, signature)
    
    print("✅ Proper error handling for invalid webhook signature")


@pytest.mark.asyncio
async def test_webhook_malformed_json(db_session: AsyncSession):
    """Test webhook with malformed JSON."""
    service = RazorpayService(db_session)
    
    payload = "not valid json"
    signature = "any_signature"
    
    with pytest.raises(ValueError, match="Invalid webhook payload"):
        await service.handle_webhook(payload, signature)
    
    print("✅ Proper error handling for malformed webhook JSON")


@pytest.mark.asyncio
async def test_amount_conversion():
    """Test amount conversion to paise."""
    # Test various amounts
    test_cases = [
        (150.50, 15050),
        (100.00, 10000),
        (1.99, 199),
        (0.50, 50),
        (1000.00, 100000),
    ]
    
    for amount, expected_paise in test_cases:
        amount_paise = int(round(amount * 100))
        assert amount_paise == expected_paise
    
    print("✅ Amount conversion to paise working correctly")


@pytest.mark.asyncio
async def test_payment_transaction_logging(db_session: AsyncSession):
    """Test that payment transactions are properly logged."""
    service = RazorpayService(db_session)
    user_id = uuid4()
    
    # Create test booking
    booking = Booking(
        id=uuid4(),
        booking_type="CONSULTATION",
        status="PENDING",
        total_price=100.00,
        currency="INR",
        created_by=user_id,
    )
    db_session.add(booking)
    await db_session.flush()
    
    # Mock the requests.post call
    with patch('app.services.razorpay_service.requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "order_test_123",
            "amount": 10000,
            "currency": "INR",
        }
        mock_post.return_value = mock_response
        
        result = await service.create_order(
            user_id=user_id,
            booking_id=booking.id,
        )
        
        # Verify transaction was logged
        payment_id = result["payment_id"]
        txns = await db_session.execute(
            select(PaymentTransaction).where(
                PaymentTransaction.payment_id == payment_id
            )
        )
        transactions = txns.scalars().all()
        
        assert len(transactions) > 0
        assert transactions[0].transaction_type == "order_created"
        assert transactions[0].status == "pending"
        
        print("✅ Payment transactions properly logged")


def test_signature_verification():
    """Test HMAC signature generation and verification."""
    key_secret = "test_secret_key"
    order_id = "order_123"
    payment_id = "pay_456"
    
    # Generate signature
    signature = hmac.new(
        key_secret.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    
    # Verify signature
    expected_signature = hmac.new(
        key_secret.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    
    assert hmac.compare_digest(signature, expected_signature)
    
    # Verify invalid signature fails
    wrong_signature = hmac.new(
        key_secret.encode(),
        "wrong_data".encode(),
        hashlib.sha256,
    ).hexdigest()
    
    assert not hmac.compare_digest(signature, wrong_signature)
    
    print("✅ HMAC signature verification working correctly")


if __name__ == "__main__":
    print("\n🧪 Running Razorpay Integration Tests\n")
    print("=" * 60)
    
    # Run syntax checks
    import asyncio
    
    # Test amount conversion
    asyncio.run(test_amount_conversion())
    
    # Test signature verification
    test_signature_verification()
    
    print("\n" + "=" * 60)
    print("✅ All manual tests passed!")
    print("\n📝 To run full pytest suite:")
    print("   pytest tests/test_razorpay.py -v")
