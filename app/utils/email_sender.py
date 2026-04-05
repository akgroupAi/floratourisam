"""Async SMTP email sender.

Sends transactional emails via SMTP and writes an audit record to ``email_logs``.
Uses Python's built-in ``smtplib`` via ``asyncio.to_thread`` so it doesn't block
the async event loop.

Usage::

    await send_email(
        db=db,
        to_email="patient@example.com",
        to_name="Alice",
        subject="Your appointment is confirmed",
        body_html="<h1>Confirmed!</h1>",
        category="consultation",
    )
"""

import asyncio
import smtplib
import uuid as _uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.system import EmailLog

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Low-level sync sender (runs in thread pool)
# ---------------------------------------------------------------------------

def _send_smtp_sync(
    *,
    to_email: str,
    to_name: Optional[str],
    subject: str,
    body_html: str,
    body_text: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """Send an email via SMTP. Returns (success, error_message)."""
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        return False, "SMTP credentials not configured"

    from_addr = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>"
    to_addr = f"{to_name} <{to_email}>" if to_name else to_email

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    if body_text:
        msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        if settings.SMTP_USE_TLS:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.ehlo()
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)

        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAIL_FROM_ADDRESS, [to_email], msg.as_string())
        server.quit()
        return True, None
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------

async def send_email(
    *,
    db: AsyncSession,
    to_email: str,
    to_name: Optional[str] = None,
    subject: str,
    body_html: str,
    body_text: Optional[str] = None,
    category: str = "notification",
    user_id: Optional[_uuid.UUID] = None,
) -> bool:
    """Send an email and log the result in ``email_logs``.

    Returns True if the email was dispatched successfully, False otherwise.
    A log record is always created regardless of outcome.
    """
    success, error = await asyncio.to_thread(
        _send_smtp_sync,
        to_email=to_email,
        to_name=to_name,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
    )

    now = datetime.now(timezone.utc)
    log = EmailLog(
        user_id=user_id,
        to_email=to_email,
        to_name=to_name,
        subject=subject,
        body_html=body_html,
        status="sent" if success else "failed",
        sent_at=now if success else None,
        error_message=error,
        provider="smtp",
        audit_metadata={"category": category},
    )
    db.add(log)
    # Flush so the log is persisted even if the caller rolls back later
    await db.flush()

    if success:
        logger.info("email_sent", to=to_email, subject=subject)
    else:
        logger.error("email_send_failed", to=to_email, subject=subject, error=error)

    return success


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

def render_appointment_confirmation_html(
    *,
    patient_name: str,
    doctor_name: str,
    consultation_type: str,
    scheduled_at: datetime,
    duration_minutes: int,
    reference_number: str,
    meet_link: Optional[str],
    fee: float,
) -> str:
    meet_section = (
        f"""
        <tr>
          <td style="padding:8px 0;color:#555;font-size:14px;"><strong>Meeting Link:</strong></td>
          <td style="padding:8px 0;font-size:14px;">
            <a href="{meet_link}" style="color:#0066cc;">{meet_link}</a>
          </td>
        </tr>"""
        if meet_link
        else ""
    )

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px;">
      <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        <div style="background:#0066cc;padding:24px;text-align:center;">
          <h1 style="color:#fff;margin:0;font-size:22px;">Appointment Confirmed</h1>
        </div>
        <div style="padding:32px;">
          <p style="font-size:16px;color:#333;">Dear <strong>{patient_name}</strong>,</p>
          <p style="font-size:14px;color:#555;">
            Your appointment has been successfully scheduled. Here are the details:
          </p>
          <table style="width:100%;border-collapse:collapse;margin:20px 0;">
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Reference:</strong></td>
                <td style="padding:8px 0;font-size:14px;">{reference_number}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Doctor:</strong></td>
                <td style="padding:8px 0;font-size:14px;">{doctor_name}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Type:</strong></td>
                <td style="padding:8px 0;font-size:14px;">{consultation_type.replace('_',' ').title()}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Date &amp; Time:</strong></td>
                <td style="padding:8px 0;font-size:14px;">{scheduled_at.strftime('%B %d, %Y at %I:%M %p')} UTC</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Duration:</strong></td>
                <td style="padding:8px 0;font-size:14px;">{duration_minutes} minutes</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Fee:</strong></td>
                <td style="padding:8px 0;font-size:14px;">${fee:.2f}</td></tr>
            {meet_section}
          </table>
          <p style="font-size:13px;color:#888;">
            If you need to cancel or reschedule, please do so at least 24 hours in advance.
          </p>
        </div>
        <div style="background:#f9f9f9;padding:16px;text-align:center;">
          <p style="font-size:12px;color:#aaa;margin:0;">Medical Tourism Platform</p>
        </div>
      </div>
    </body>
    </html>
    """


def render_hotel_booking_confirmation_html(
    *,
    guest_name: str,
    hotel_name: str,
    room_name: str,
    room_type: str,
    check_in_date: str,
    check_out_date: str,
    nights: int,
    guest_count: int,
    total_price: float,
    currency: str,
    reference_number: str,
    special_requests: Optional[str],
) -> str:
    requests_section = (
        f"<p><strong>Special Requests:</strong> {special_requests}</p>"
        if special_requests
        else ""
    )
    return f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8"></head>
    <body style="font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px;">
      <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        <div style="background:#1a3c6e;padding:24px;text-align:center;">
          <h1 style="color:#fff;margin:0;font-size:22px;">Hotel Booking Confirmed</h1>
        </div>
        <div style="padding:32px;">
          <p style="font-size:16px;color:#333;">Dear <strong>{guest_name}</strong>,</p>
          <p style="font-size:14px;color:#555;">Your hotel booking has been confirmed. Here are the details:</p>
          <table style="width:100%;border-collapse:collapse;margin:20px 0;">
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Reference:</strong></td><td style="padding:8px 0;font-size:14px;">{reference_number}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Hotel:</strong></td><td style="padding:8px 0;font-size:14px;">{hotel_name}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Room:</strong></td><td style="padding:8px 0;font-size:14px;">{room_name} ({room_type})</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Check-in:</strong></td><td style="padding:8px 0;font-size:14px;">{check_in_date}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Check-out:</strong></td><td style="padding:8px 0;font-size:14px;">{check_out_date}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Nights:</strong></td><td style="padding:8px 0;font-size:14px;">{nights}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Guests:</strong></td><td style="padding:8px 0;font-size:14px;">{guest_count}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Total:</strong></td><td style="padding:8px 0;font-size:14px;">{currency} {total_price:.2f}</td></tr>
          </table>
          {requests_section}
        </div>
        <div style="background:#f9f9f9;padding:16px;text-align:center;">
          <p style="font-size:12px;color:#aaa;margin:0;">Medical Tourism Platform</p>
        </div>
      </div>
    </body></html>"""


def render_apartment_booking_confirmation_html(
    *,
    guest_name: str,
    apartment_name: str,
    bedroom_type: str,
    check_in_date: str,
    check_out_date: str,
    nights: int,
    guest_count: int,
    total_price: float,
    currency: str,
    reference_number: str,
    address: str,
    special_requests: Optional[str],
) -> str:
    requests_section = (
        f"<p><strong>Special Requests:</strong> {special_requests}</p>"
        if special_requests
        else ""
    )
    return f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8"></head>
    <body style="font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px;">
      <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        <div style="background:#2d6a4f;padding:24px;text-align:center;">
          <h1 style="color:#fff;margin:0;font-size:22px;">Apartment Booking Confirmed</h1>
        </div>
        <div style="padding:32px;">
          <p style="font-size:16px;color:#333;">Dear <strong>{guest_name}</strong>,</p>
          <p style="font-size:14px;color:#555;">Your apartment booking has been confirmed:</p>
          <table style="width:100%;border-collapse:collapse;margin:20px 0;">
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Reference:</strong></td><td style="padding:8px 0;font-size:14px;">{reference_number}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Apartment:</strong></td><td style="padding:8px 0;font-size:14px;">{apartment_name} ({bedroom_type})</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Address:</strong></td><td style="padding:8px 0;font-size:14px;">{address}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Check-in:</strong></td><td style="padding:8px 0;font-size:14px;">{check_in_date}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Check-out:</strong></td><td style="padding:8px 0;font-size:14px;">{check_out_date}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Nights:</strong></td><td style="padding:8px 0;font-size:14px;">{nights}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Guests:</strong></td><td style="padding:8px 0;font-size:14px;">{guest_count}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Total:</strong></td><td style="padding:8px 0;font-size:14px;">{currency} {total_price:.2f}</td></tr>
          </table>
          {requests_section}
        </div>
        <div style="background:#f9f9f9;padding:16px;text-align:center;">
          <p style="font-size:12px;color:#aaa;margin:0;">Medical Tourism Platform</p>
        </div>
      </div>
    </body></html>"""


def render_restaurant_booking_confirmation_html(
    *,
    guest_name: str,
    restaurant_name: str,
    booking_date: str,
    booking_time: str,
    meal_type: str,
    guest_count: int,
    reference_number: str,
    dietary_requirements: Optional[str],
    ordered_items_summary: Optional[str],
    estimated_cost: Optional[float],
    currency: str,
) -> str:
    dietary_section = (
        f"<p><strong>Dietary Requirements:</strong> {dietary_requirements}</p>"
        if dietary_requirements
        else ""
    )
    items_section = (
        f"<p><strong>Pre-ordered Items:</strong> {ordered_items_summary}</p>"
        if ordered_items_summary
        else ""
    )
    cost_section = (
        f"<p><strong>Estimated Cost:</strong> {currency} {estimated_cost:.2f}</p>"
        if estimated_cost
        else ""
    )
    return f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8"></head>
    <body style="font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px;">
      <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        <div style="background:#b5451b;padding:24px;text-align:center;">
          <h1 style="color:#fff;margin:0;font-size:22px;">Restaurant Booking Confirmed</h1>
        </div>
        <div style="padding:32px;">
          <p style="font-size:16px;color:#333;">Dear <strong>{guest_name}</strong>,</p>
          <p style="font-size:14px;color:#555;">Your table reservation has been confirmed:</p>
          <table style="width:100%;border-collapse:collapse;margin:20px 0;">
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Reference:</strong></td><td style="padding:8px 0;font-size:14px;">{reference_number}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Restaurant:</strong></td><td style="padding:8px 0;font-size:14px;">{restaurant_name}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Date:</strong></td><td style="padding:8px 0;font-size:14px;">{booking_date}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Time:</strong></td><td style="padding:8px 0;font-size:14px;">{booking_time}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Meal:</strong></td><td style="padding:8px 0;font-size:14px;">{meal_type.title()}</td></tr>
            <tr><td style="padding:8px 0;color:#555;font-size:14px;"><strong>Guests:</strong></td><td style="padding:8px 0;font-size:14px;">{guest_count}</td></tr>
          </table>
          {dietary_section}
          {items_section}
          {cost_section}
        </div>
        <div style="background:#f9f9f9;padding:16px;text-align:center;">
          <p style="font-size:12px;color:#aaa;margin:0;">Medical Tourism Platform</p>
        </div>
      </div>
    </body></html>"""


def render_doctor_appointment_html(
    *,
    doctor_name: str,
    patient_name: str,
    consultation_type: str,
    scheduled_at: datetime,
    duration_minutes: int,
    reference_number: str,
    meet_link: Optional[str],
    reason: Optional[str],
) -> str:
    meet_section = (
        f'<p><strong>Meeting Link:</strong> <a href="{meet_link}">{meet_link}</a></p>'
        if meet_link
        else ""
    )
    reason_section = (
        f"<p><strong>Reason:</strong> {reason}</p>" if reason else ""
    )

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px;">
      <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        <div style="background:#1a7a4c;padding:24px;text-align:center;">
          <h1 style="color:#fff;margin:0;font-size:22px;">New Appointment Scheduled</h1>
        </div>
        <div style="padding:32px;">
          <p style="font-size:16px;color:#333;">Dear <strong>{doctor_name}</strong>,</p>
          <p style="font-size:14px;color:#555;">
            A patient has scheduled an appointment with you:
          </p>
          <p><strong>Reference:</strong> {reference_number}</p>
          <p><strong>Patient:</strong> {patient_name}</p>
          <p><strong>Type:</strong> {consultation_type.replace('_',' ').title()}</p>
          <p><strong>Date &amp; Time:</strong> {scheduled_at.strftime('%B %d, %Y at %I:%M %p')} UTC</p>
          <p><strong>Duration:</strong> {duration_minutes} minutes</p>
          {reason_section}
          {meet_section}
        </div>
        <div style="background:#f9f9f9;padding:16px;text-align:center;">
          <p style="font-size:12px;color:#aaa;margin:0;">Medical Tourism Platform</p>
        </div>
      </div>
    </body>
    </html>
    """
def render_verification_email_html(
    *,
    full_name: str,
    verification_url: str,
) -> str:
    """Render the email verification HTML template."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px;">
      <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        <div style="background:#0066cc;padding:24px;text-align:center;">
          <h1 style="color:#fff;margin:0;font-size:22px;">Verify Your Email</h1>
        </div>
        <div style="padding:32px;">
          <p style="font-size:16px;color:#333;">Welcome <strong>{full_name}</strong>,</p>
          <p style="font-size:14px;color:#555;">
            Thank you for registering. Please click the button below to verify your email address and activate your account:
          </p>
          <div style="text-align:center;margin:30px 0;">
            <a href="{verification_url}" style="background:#0066cc;color:#fff;padding:12px 24px;text-decoration:none;border-radius:4px;font-weight:bold;">Verify Email</a>
          </div>
          <p style="font-size:14px;color:#555;">
            If the button above doesn't work, you can copy and paste the following link into your browser:
          </p>
          <p style="font-size:12px;color:#888;word-break:break-all;">
            <a href="{verification_url}" style="color:#0066cc;">{verification_url}</a>
          </p>
          <p style="font-size:13px;color:#888;margin-top:30px;">
            If you did not create an account, no further action is required.
          </p>
        </div>
        <div style="background:#f9f9f9;padding:16px;text-align:center;">
          <p style="font-size:12px;color:#aaa;margin:0;">Medical Tourism Platform</p>
        </div>
      </div>
    </body>
    </html>
    """
