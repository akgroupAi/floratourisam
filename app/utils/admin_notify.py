"""Email the admin when a patient books or a doctor sends a proposal.

Admins previously found out about bookings, consultations, and treatment proposals only
by looking at the dashboard. These helpers push an email at the moment each happens.

Every function is best-effort: a mail failure must never roll back the booking that
triggered it. Failures are logged and swallowed, exactly like the contact and quote
alerts already in place.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.logging import get_logger
from app.models.apartment import Apartment
from app.models.booking import Booking
from app.models.hotel import Room
from app.models.restaurant import Restaurant
from app.utils.email_sender import render_admin_alert_email_html, send_email
from app.utils.enums import BookingType

logger = get_logger(__name__)


def _admin_email() -> Optional[str]:
    return getattr(settings, "FIRST_SUPERUSER_EMAIL", None)


def _money(amount: Optional[float], currency: Optional[str]) -> str:
    if amount is None:
        return ""
    return f"{currency or ''} {amount:,.2f}".strip()


async def _patient_contact(db: AsyncSession, patient_id: Optional[UUID]) -> tuple:
    """(name, email, phone) for a patient, with blanks rather than exceptions."""
    if not patient_id:
        return None, None, None
    from app.models.patient import Patient

    patient = (
        await db.execute(
            select(Patient).options(joinedload(Patient.user)).where(Patient.id == patient_id)
        )
    ).scalar_one_or_none()
    user = patient.user if patient else None
    if not user:
        return None, None, None
    return user.full_name, user.email, getattr(user, "phone", None)


async def _send(db: AsyncSession, subject: str, html: str, category: str) -> None:
    to_email = _admin_email()
    if not to_email:
        logger.warning("admin_alert_skipped_no_recipient", subject=subject)
        return
    try:
        await send_email(
            db=db,
            to_email=to_email,
            to_name="Admin",
            subject=subject,
            body_html=html,
            category=category,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("admin_alert_email_failed", subject=subject, error=str(exc))


async def _send_to(
    db: AsyncSession, to_email: str, to_name, subject: str, html: str, category: str
) -> None:
    """Send to a named recipient. Same best-effort contract as _send."""
    try:
        await send_email(
            db=db, to_email=to_email, to_name=to_name or "Guest",
            subject=subject, body_html=html, category=category,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("customer_email_failed", subject=subject, error=str(exc))


async def notify_customer_refund_processed(db: AsyncSession, booking: Booking) -> None:
    """Tell the patient their refund has been issued.

    Deliberately does not say "refunded" as though the money has arrived - Razorpay
    takes working days to settle, and a customer told otherwise checks their account
    the same evening and raises a ticket.
    """
    try:
        name, email, _ = await _patient_contact(db, booking.patient_id)
        if not email:
            logger.warning(
                "customer_refund_email_skipped_no_email", booking_id=str(booking.id)
            )
            return

        amount = _money(booking.refund_amount, booking.currency)
        rows = [
            ("Booking", booking.reference_number),
            ("Refund amount", amount),
            (
                "Cancellation charge",
                _money(booking.cancellation_charge, booking.currency)
                if booking.cancellation_charge
                else None,
            ),
            ("Original total", _money(booking.total_price, booking.currency)),
            ("Reference", booking.refund_reference),
            (
                "Issued on",
                booking.refund_processed_at.strftime("%B %d, %Y")
                if booking.refund_processed_at
                else None,
            ),
        ]

        html = render_admin_alert_email_html(
            heading="Your Refund Has Been Issued",
            subheading=f"Booking {booking.reference_number}",
            rows=rows,
            message_title="What happens next",
            message_body=(
                f"We have issued a refund of {amount} to your original payment method. "
                "It usually takes 5-7 working days to appear in your account, depending "
                "on your bank. You do not need to do anything."
            ),
            footer_note="If it has not arrived after 7 working days, reply to this email.",
        )
        await _send_to(
            db, email, name, f"Refund issued for {booking.reference_number}", html,
            "customer_refund_processed",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "customer_refund_email_failed", booking_id=str(getattr(booking, "id", "")),
            error=str(exc),
        )


async def notify_customer_refund_rejected(db: AsyncSession, booking: Booking) -> None:
    """Tell the patient their refund was not approved, and why."""
    try:
        name, email, _ = await _patient_contact(db, booking.patient_id)
        if not email:
            return

        rows = [
            ("Booking", booking.reference_number),
            ("Original total", _money(booking.total_price, booking.currency)),
            (
                "Cancelled on",
                booking.cancelled_at.strftime("%B %d, %Y") if booking.cancelled_at else None,
            ),
        ]

        html = render_admin_alert_email_html(
            heading="Update On Your Refund Request",
            subheading=f"Booking {booking.reference_number}",
            rows=rows,
            message_title="Reason",
            message_body=(
                booking.refund_note
                or "Your refund request was reviewed and not approved under our "
                "cancellation policy."
            ),
            footer_note="If you believe this is wrong, reply to this email and we will review it.",
        )
        await _send_to(
            db, email, name, f"Update on your refund - {booking.reference_number}", html,
            "customer_refund_rejected",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "customer_refund_rejection_email_failed",
            booking_id=str(getattr(booking, "id", "")), error=str(exc),
        )


async def notify_admin_new_booking(db: AsyncSession, booking: Booking) -> None:
    """Tell the admin a patient has booked a hotel, apartment, or restaurant."""
    try:
        guest_name, guest_email, guest_phone = await _patient_contact(db, booking.patient_id)

        property_name = None
        property_detail = None

        if booking.booking_type == BookingType.HOTEL.value and booking.hotel_room_id:
            room = (
                await db.execute(
                    select(Room)
                    .options(joinedload(Room.hotel))
                    .where(Room.id == booking.hotel_room_id)
                )
            ).scalar_one_or_none()
            if room:
                property_name = room.hotel.name if room.hotel else "Hotel"
                property_detail = f"{room.room_type} — {room.name}" if room.name else room.room_type
            heading, label = "New Hotel Booking", "Hotel"
        elif booking.booking_type == BookingType.APARTMENT.value and booking.apartment_id:
            apartment = (
                await db.execute(
                    select(Apartment).where(Apartment.id == booking.apartment_id)
                )
            ).scalar_one_or_none()
            if apartment:
                property_name = apartment.name
                property_detail = f"{apartment.bedroom_type} in {apartment.city}"
            heading, label = "New Apartment Booking", "Apartment"
        elif booking.booking_type == BookingType.RESTAURANT.value and booking.restaurant_id:
            restaurant = (
                await db.execute(
                    select(Restaurant).where(Restaurant.id == booking.restaurant_id)
                )
            ).scalar_one_or_none()
            property_name = restaurant.name if restaurant else None
            heading, label = "New Restaurant Booking", "Restaurant"
        else:
            # Consultation bookings are covered by notify_admin_new_consultation.
            return

        nights = None
        if booking.check_in_date and booking.check_out_date:
            nights = max((booking.check_out_date - booking.check_in_date).days, 1)

        rows = [
            ("Reference", booking.reference_number),
            (label, property_name),
            ("Details", property_detail),
            ("Guest", guest_name),
            ("Email", guest_email),
            ("Phone", guest_phone),
            ("Check-in", booking.check_in_date.strftime("%B %d, %Y") if booking.check_in_date else None),
            ("Check-out", booking.check_out_date.strftime("%B %d, %Y") if booking.check_out_date else None),
            ("Nights", str(nights) if nights else None),
            ("Guests", str(booking.guest_count) if booking.guest_count else None),
            ("Platform fee", _money(booking.platform_fee, booking.currency) if booking.platform_fee else None),
            ("Total", _money(booking.total_price, booking.currency)),
            ("Payment", "Paid" if booking.is_paid else "Awaiting payment"),
            ("Status", (booking.status or "").replace("_", " ").title()),
        ]

        html = render_admin_alert_email_html(
            heading=heading,
            subheading=f"Booking {booking.reference_number}",
            rows=rows,
            message_title="Special requests" if booking.special_requests else None,
            message_body=booking.special_requests,
            footer_note=(
                None
                if booking.is_paid
                else "This booking has not been paid yet — it is held as pending."
            ),
        )
        await _send(db, f"{heading}: {booking.reference_number}", html, "booking_admin_alert")
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "admin_booking_alert_failed", booking_id=str(booking.id), error=str(exc)
        )


async def notify_admin_cancellation(db: AsyncSession, booking: Booking) -> None:
    """Tell the admin a booking was cancelled, and whether money is owed.

    A cancellation with a refund needs someone to release it. Without this the only
    signal is the queue, which nobody sees unless they go and look.
    """
    try:
        guest_name, guest_email, guest_phone = await _patient_contact(db, booking.patient_id)

        property_name = None
        if booking.hotel_room_id:
            room = (
                await db.execute(
                    select(Room)
                    .options(joinedload(Room.hotel))
                    .where(Room.id == booking.hotel_room_id)
                )
            ).scalar_one_or_none()
            if room and room.hotel:
                property_name = room.hotel.name
        elif booking.apartment_id:
            property_name = (
                await db.execute(
                    select(Apartment.name).where(Apartment.id == booking.apartment_id)
                )
            ).scalar_one_or_none()
        elif booking.restaurant_id:
            property_name = (
                await db.execute(
                    select(Restaurant.name).where(Restaurant.id == booking.restaurant_id)
                )
            ).scalar_one_or_none()

        refund_amount = float(booking.refund_amount or 0)
        refund_status = booking.refund_status or "none"
        needs_action = refund_status == "pending"

        rows = [
            ("Reference", booking.reference_number),
            ("Type", (booking.booking_type or "").title()),
            ("Property", property_name),
            ("Guest", guest_name),
            ("Email", guest_email),
            ("Phone", guest_phone),
            (
                "Was booked for",
                f"{booking.check_in_date} to {booking.check_out_date}"
                if booking.check_in_date and booking.check_out_date
                else None,
            ),
            ("Booking total", _money(booking.total_price, booking.currency)),
            ("Was paid", "Yes" if booking.is_paid else "No"),
            (
                "Cancellation charge",
                _money(booking.cancellation_charge, booking.currency)
                if booking.cancellation_charge
                else None,
            ),
            (
                "Refund due",
                _money(refund_amount, booking.currency) if refund_amount else "None",
            ),
            ("Refund status", refund_status.replace("_", " ").title()),
        ]

        if needs_action:
            footer = (
                "This refund is waiting for approval. Release it from "
                "Admin -> Refunds, or it will not be paid."
            )
        elif booking.is_paid and refund_amount == 0:
            footer = (
                "No refund is due under the cancellation policy"
                + (f": {booking.refund_note}" if booking.refund_note else ".")
            )
        else:
            footer = None

        heading = (
            "Booking Cancelled - Refund Awaiting Approval"
            if needs_action
            else "Booking Cancelled"
        )

        html = render_admin_alert_email_html(
            heading=heading,
            subheading=f"Booking {booking.reference_number}",
            rows=rows,
            message_title="Reason given" if booking.cancellation_reason else None,
            message_body=booking.cancellation_reason,
            footer_note=footer,
        )
        await _send(
            db,
            f"{heading}: {booking.reference_number}",
            html,
            "cancellation_admin_alert",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "admin_cancellation_alert_failed",
            booking_id=str(getattr(booking, "id", "")),
            error=str(exc),
        )


async def notify_admin_new_consultation(db: AsyncSession, consultation) -> None:
    """Tell the admin a patient has booked a consultation with a doctor."""
    try:
        from app.models.doctor import Doctor

        guest_name, guest_email, guest_phone = await _patient_contact(
            db, consultation.patient_id
        )

        doctor_name = None
        doctor_specialty = None
        hospital_name = None
        doctor = (
            await db.execute(
                select(Doctor)
                .options(joinedload(Doctor.user), joinedload(Doctor.hospital))
                .where(Doctor.id == consultation.doctor_id)
            )
        ).scalar_one_or_none()
        if doctor:
            doctor_name = (
                f"{doctor.title or 'Dr.'} {doctor.user.full_name}".strip()
                if doctor.user
                else None
            )
            doctor_specialty = doctor.primary_specialty
            hospital_name = doctor.hospital.name if doctor.hospital else None

        rows = [
            ("Reference", consultation.reference_number),
            ("Patient", guest_name),
            ("Email", guest_email),
            ("Phone", guest_phone),
            ("Doctor", doctor_name),
            ("Specialty", doctor_specialty),
            ("Hospital", hospital_name),
            ("Type", (consultation.consultation_type or "").replace("_", " ").title()),
            (
                "Scheduled",
                consultation.scheduled_at.strftime("%B %d, %Y at %I:%M %p")
                if consultation.scheduled_at
                else None,
            ),
            ("Duration", f"{consultation.duration_minutes} minutes" if consultation.duration_minutes else None),
            ("Fee", _money(consultation.fee, "")),
            ("Payment", "Paid" if consultation.is_paid else "Awaiting payment"),
            ("Status", (consultation.status or "").replace("_", " ").title()),
        ]

        html = render_admin_alert_email_html(
            heading="New Consultation Booked",
            subheading=f"Consultation {consultation.reference_number}",
            rows=rows,
            message_title="Reason / symptoms" if (consultation.reason or consultation.symptoms) else None,
            message_body=consultation.reason or consultation.symptoms,
            footer_note=(
                None
                if consultation.is_paid
                else "This consultation has not been paid yet."
            ),
        )
        await _send(
            db,
            f"New Consultation: {consultation.reference_number}",
            html,
            "consultation_admin_alert",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "admin_consultation_alert_failed",
            consultation_id=str(getattr(consultation, "id", "")),
            error=str(exc),
        )


async def notify_admin_proposal_response(db: AsyncSession, proposal, action: str) -> None:
    """Tell the admin how a patient answered a treatment proposal.

    An acceptance is the conversion point — treatment is agreed and payment follows — so
    it is the one an admin most needs to see. Rejections and revision requests are sent
    too: one is lost business, the other is waiting on the doctor.
    """
    try:
        outcome = {
            "approve": ("Treatment Proposal Accepted", "The patient accepted this proposal"),
            "reject": ("Treatment Proposal Rejected", "The patient declined this proposal"),
            "request_revision": (
                "Treatment Proposal — Revision Requested",
                "The patient asked the doctor to revise this proposal",
            ),
        }.get(action)
        if not outcome:
            return
        heading, subheading = outcome

        doctor_name = None
        if getattr(proposal, "doctor", None) and getattr(proposal.doctor, "user", None):
            doctor_name = f"{proposal.doctor.title or 'Dr.'} {proposal.doctor.user.full_name}".strip()

        patient_name = None
        patient_email = None
        if getattr(proposal, "patient", None) and getattr(proposal.patient, "user", None):
            patient_name = proposal.patient.user.full_name
            patient_email = proposal.patient.user.email

        rows = [
            ("Reference", proposal.reference_number),
            ("Outcome", (proposal.status or "").replace("_", " ").title()),
            ("Treatment", proposal.treatment_name),
            ("Patient", patient_name),
            ("Patient email", patient_email),
            ("Doctor", doctor_name),
            ("Hospital", proposal.hospital.name if getattr(proposal, "hospital", None) else None),
            (
                "Proposed visit",
                proposal.proposed_visit_date.strftime("%B %d, %Y")
                if proposal.proposed_visit_date
                else None,
            ),
            ("Total", _money(proposal.total_amount, proposal.currency)),
            (
                "Responded",
                proposal.responded_at.strftime("%B %d, %Y at %I:%M %p")
                if proposal.responded_at
                else None,
            ),
        ]

        footer = {
            "approve": "Treatment is agreed — arrange scheduling and payment.",
            "reject": None,
            "request_revision": "The doctor needs to revise and resend this proposal.",
        }.get(action)

        html = render_admin_alert_email_html(
            heading=heading,
            subheading=subheading,
            rows=rows,
            message_title="Patient's notes" if proposal.patient_response_notes else None,
            message_body=proposal.patient_response_notes,
            footer_note=footer,
        )
        await _send(
            db,
            f"{heading}: {proposal.reference_number}",
            html,
            "proposal_response_admin_alert",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "admin_proposal_response_alert_failed",
            proposal_id=str(getattr(proposal, "id", "")),
            error=str(exc),
        )


async def notify_admin_new_proposal(db: AsyncSession, proposal) -> None:
    """Tell the admin a doctor has sent a treatment proposal to a patient."""
    try:
        doctor_name = None
        if getattr(proposal, "doctor", None) and getattr(proposal.doctor, "user", None):
            doctor_name = f"{proposal.doctor.title or 'Dr.'} {proposal.doctor.user.full_name}".strip()

        patient_name = None
        patient_email = None
        if getattr(proposal, "patient", None) and getattr(proposal.patient, "user", None):
            patient_name = proposal.patient.user.full_name
            patient_email = proposal.patient.user.email

        hospital_name = proposal.hospital.name if getattr(proposal, "hospital", None) else None
        currency = proposal.currency

        rows = [
            ("Reference", proposal.reference_number),
            ("Treatment", proposal.treatment_name),
            ("Doctor", doctor_name),
            ("Patient", patient_name),
            ("Patient email", patient_email),
            ("Hospital", hospital_name),
            ("Duration", proposal.estimated_duration),
            (
                "Proposed visit",
                proposal.proposed_visit_date.strftime("%B %d, %Y")
                if proposal.proposed_visit_date
                else None,
            ),
            ("Consultation fee", _money(proposal.consultation_fee, currency) if proposal.consultation_fee else None),
            ("Surgery fee", _money(proposal.surgery_fee, currency) if proposal.surgery_fee else None),
            ("Hospital stay", _money(proposal.hospital_stay_fee, currency) if proposal.hospital_stay_fee else None),
            ("Medications", _money(proposal.medications_fee, currency) if proposal.medications_fee else None),
            ("Other fees", _money(proposal.other_fees, currency) if proposal.other_fees else None),
            ("Total", _money(proposal.total_amount, currency)),
            ("Status", (proposal.status or "").replace("_", " ").title()),
        ]

        html = render_admin_alert_email_html(
            heading="New Treatment Proposal Sent",
            subheading=f"Proposal {proposal.reference_number}",
            rows=rows,
            message_title="Doctor's notes" if proposal.doctor_notes else None,
            message_body=proposal.doctor_notes or proposal.description,
            footer_note="Awaiting the patient's response.",
        )
        await _send(
            db,
            f"New Treatment Proposal: {proposal.reference_number}",
            html,
            "proposal_admin_alert",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "admin_proposal_alert_failed",
            proposal_id=str(getattr(proposal, "id", "")),
            error=str(exc),
        )
