"""Google Calendar / Meet integration utility.

Creates Google Calendar events with Meet conferencing links.
Requires GOOGLE_CALENDAR_ENABLED=True and a service account JSON file
(GOOGLE_SERVICE_ACCOUNT_JSON) with the Calendar API enabled and
domain-wide delegation configured.

If credentials are unavailable, falls back gracefully and returns None.
"""

import asyncio
import uuid as _uuid
from datetime import datetime, timedelta
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _build_calendar_service(calendar_owner_email: str):
    """Build a Google Calendar service client impersonating `calendar_owner_email`."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credentials = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_JSON,
            scopes=SCOPES,
            subject=calendar_owner_email,
        )
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)
    except Exception as exc:
        logger.warning("google_calendar_service_build_failed", error=str(exc))
        return None


def _generate_jitsi_link(title: str) -> dict:
    """Generate a Jitsi Meet link as fallback when Google Calendar is disabled."""
    room_id = str(_uuid.uuid4()).replace("-", "")[:16]
    safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-")).strip().replace(" ", "-")[:40]
    room_name = f"{safe_title}-{room_id}" if safe_title else room_id
    return {
        "meet_link": f"https://meet.jit.si/{room_name}",
        "google_event_id": None,
        "platform": "jitsi",
    }


def _create_meet_event_sync(
    *,
    title: str,
    description: str,
    start_dt: datetime,
    end_dt: datetime,
    organizer_email: str,
    attendee_emails: list[str],
    timezone: str,
) -> dict:
    """Synchronous Google Calendar event creation (runs in a thread pool).

    Returns a dict with keys: ``meet_link``, ``google_event_id``.
    Falls back to Jitsi Meet if Google Calendar is disabled or credentials are missing.
    """
    if not settings.GOOGLE_CALENDAR_ENABLED:
        return _generate_jitsi_link(title)

    service = _build_calendar_service(organizer_email)
    if service is None:
        return _generate_jitsi_link(title)

    request_id = str(_uuid.uuid4())
    event_body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone},
        "attendees": [{"email": email} for email in attendee_emails],
        "conferenceData": {
            "createRequest": {
                "requestId": request_id,
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 60},
                {"method": "popup", "minutes": 15},
            ],
        },
    }

    try:
        created = (
            service.events()
            .insert(
                calendarId="primary",
                body=event_body,
                conferenceDataVersion=1,
                sendUpdates="all",
            )
            .execute()
        )
        return {
            "meet_link": created.get("hangoutLink"),
            "google_event_id": created.get("id"),
        }
    except Exception as exc:
        logger.error("google_calendar_event_creation_failed", error=str(exc))
        return _generate_jitsi_link(title)


async def create_meet_event(
    *,
    title: str,
    description: str,
    start_dt: datetime,
    end_dt: datetime,
    organizer_email: str,
    attendee_emails: list[str],
    timezone: str = "UTC",
) -> dict:
    """Async wrapper — creates a Google Calendar event with a Meet link.

    Returns a dict with ``meet_link`` and ``google_event_id`` on success,
    or an empty dict if Google Calendar integration is disabled/unavailable.
    """
    return await asyncio.to_thread(
        _create_meet_event_sync,
        title=title,
        description=description,
        start_dt=start_dt,
        end_dt=end_dt,
        organizer_email=organizer_email,
        attendee_emails=attendee_emails,
        timezone=timezone,
    )


def _add_to_user_calendar_sync(
    *,
    calendar_owner_email: str,
    title: str,
    description: str,
    start_dt: datetime,
    end_dt: datetime,
    meet_link: Optional[str],
    timezone: str,
    google_event_id: Optional[str],
) -> Optional[str]:
    """Add (or link) an event to a specific user's calendar. Returns the event ID."""
    if not settings.GOOGLE_CALENDAR_ENABLED:
        return None

    service = _build_calendar_service(calendar_owner_email)
    if service is None:
        return None

    # If we already have the event from the organizer's calendar, just accept it.
    # Otherwise create a standalone event on this user's calendar.
    if google_event_id:
        return google_event_id

    location = meet_link or ""
    event_body = {
        "summary": title,
        "description": description,
        "location": location,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone},
    }
    try:
        created = (
            service.events()
            .insert(calendarId="primary", body=event_body)
            .execute()
        )
        return created.get("id")
    except Exception as exc:
        logger.error("google_calendar_user_event_failed", error=str(exc))
        return None


async def add_to_user_calendar(
    *,
    calendar_owner_email: str,
    title: str,
    description: str,
    start_dt: datetime,
    end_dt: datetime,
    meet_link: Optional[str] = None,
    timezone: str = "UTC",
    google_event_id: Optional[str] = None,
) -> Optional[str]:
    """Async wrapper — ensures an event appears on a specific user's Google Calendar."""
    return await asyncio.to_thread(
        _add_to_user_calendar_sync,
        calendar_owner_email=calendar_owner_email,
        title=title,
        description=description,
        start_dt=start_dt,
        end_dt=end_dt,
        meet_link=meet_link,
        timezone=timezone,
        google_event_id=google_event_id,
    )
