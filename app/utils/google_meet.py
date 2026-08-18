"""Google Calendar / Meet integration utility.

Creates Google Calendar events with Meet conferencing links.
Requires GOOGLE_CALENDAR_ENABLED=True and a service account JSON file
(GOOGLE_SERVICE_ACCOUNT_JSON) with the Calendar API enabled and
domain-wide delegation configured.

If credentials are unavailable, falls back gracefully and returns None.
"""

import asyncio
import uuid as _uuid
from datetime import datetime, timedelta, timezone
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


def _generate_room_name(title: str) -> str:
    """Build a unique, URL-safe room name from a consultation title.

    Lowercased: Jitsi's MUC room JIDs are case-normalized, so a mixed-case
    JWT ``room`` claim silently fails to match on servers with JWT auth
    (mod_auth_token) enabled.
    """
    room_id = str(_uuid.uuid4()).replace("-", "")[:16]
    safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-")).strip().replace(" ", "-")
    safe_title = safe_title.lower()[:40]
    return f"{safe_title}-{room_id}" if safe_title else room_id


def _generate_jitsi_link(title: str) -> dict:
    """Generate a public meet.jit.si link as last-resort fallback.

    Note: meet.jit.si requires an authenticated user to start a new room,
    so anonymous participants see a "waiting for the moderator" screen
    until someone logs in. Prefer JaaS (JAAS_ENABLED=True) to avoid this.
    """
    room_name = _generate_room_name(title)
    return {
        "meet_link": f"https://meet.jit.si/{room_name}",
        "google_event_id": None,
        "platform": "jitsi",
    }


def _generate_jaas_room(title: str) -> dict:
    """Reserve a JaaS (8x8.vc) room name.

    Unlike Google Meet / plain Jitsi, JaaS join URLs carry a per-user,
    short-lived JWT — there's no single shareable link to hand back here.
    The real join URL is minted per participant later, in
    ``generate_jaas_join_link``, at the moment they actually join.
    """
    return {
        "meet_link": None,
        "google_event_id": None,
        "platform": "jaas",
        "room": _generate_room_name(title),
    }


def _load_jaas_private_key() -> Optional[str]:
    if not settings.JAAS_PRIVATE_KEY_PATH:
        return None
    try:
        with open(settings.JAAS_PRIVATE_KEY_PATH, "r") as f:
            return f.read()
    except OSError as exc:
        logger.error("jaas_private_key_read_failed", error=str(exc))
        return None


def generate_jaas_join_link(
    *,
    room: str,
    user_id: str,
    name: str,
    email: str,
) -> Optional[str]:
    """Build a per-user JaaS join URL with a moderator JWT.

    Both the patient and the doctor get ``moderator: True`` so neither one
    waits for a host to arrive — the conference is considered started the
    moment either of them opens the link.

    Returns None if JaaS isn't configured or signing fails.
    """
    if not (settings.JAAS_ENABLED and settings.JAAS_APP_ID and settings.JAAS_API_KEY_ID):
        return None

    private_key = _load_jaas_private_key()
    if not private_key:
        return None

    from jose import jwt as jose_jwt

    now = datetime.now(timezone.utc)
    payload = {
        "aud": "jitsi",
        "iss": "chat",
        "sub": settings.JAAS_APP_ID,
        "room": room,
        "exp": int((now + timedelta(hours=3)).timestamp()),
        "nbf": int((now - timedelta(seconds=10)).timestamp()),
        "context": {
            "user": {
                "id": user_id,
                "name": name,
                "email": email,
                "moderator": True,
            },
            "features": {
                "livestreaming": False,
                "recording": False,
                "transcription": False,
                "outbound-call": False,
            },
        },
    }
    headers = {"kid": settings.JAAS_API_KEY_ID, "typ": "JWT"}

    try:
        token = jose_jwt.encode(payload, private_key, algorithm="RS256", headers=headers)
    except Exception as exc:
        logger.error("jaas_jwt_signing_failed", error=str(exc))
        return None

    return f"https://{settings.JAAS_DOMAIN}/{settings.JAAS_APP_ID}/{room}?jwt={token}"


def _generate_selfhosted_jitsi_room(title: str) -> dict:
    """Reserve a room name on a self-hosted Jitsi Meet server.

    Like JaaS, the join URL carries a per-user JWT — minted per participant
    at join time in ``generate_selfhosted_jitsi_join_link``.
    """
    return {
        "meet_link": None,
        "google_event_id": None,
        "platform": "jitsi_selfhosted",
        "room": _generate_room_name(title),
    }


def generate_selfhosted_jitsi_join_link(
    *,
    room: str,
    user_id: str,
    name: str,
    email: str,
) -> Optional[str]:
    """Build a per-user join URL for a self-hosted Jitsi Meet server.

    Both patient and doctor get ``moderator: True``, same as the JaaS flow,
    but signed with your own shared secret (HS256) instead of an RSA
    keypair, and pointed at your own domain instead of 8x8.vc.

    Returns None if self-hosted Jitsi isn't configured or signing fails.
    """
    if not (
        settings.JITSI_SELFHOSTED_ENABLED
        and settings.JITSI_SELFHOSTED_DOMAIN
        and settings.JITSI_SELFHOSTED_APP_SECRET
    ):
        return None

    from jose import jwt as jose_jwt

    now = datetime.now(timezone.utc)
    payload = {
        "aud": settings.JITSI_SELFHOSTED_APP_ID,
        "iss": settings.JITSI_SELFHOSTED_APP_ID,
        "sub": settings.JITSI_SELFHOSTED_DOMAIN,
        "room": room,
        "exp": int((now + timedelta(hours=3)).timestamp()),
        "nbf": int((now - timedelta(seconds=10)).timestamp()),
        "context": {
            "user": {
                "id": user_id,
                "name": name,
                "email": email,
                "moderator": True,
            },
        },
    }

    try:
        token = jose_jwt.encode(payload, settings.JITSI_SELFHOSTED_APP_SECRET, algorithm="HS256")
    except Exception as exc:
        logger.error("selfhosted_jitsi_jwt_signing_failed", error=str(exc))
        return None

    base_path = (settings.JITSI_SELFHOSTED_BASE_PATH or "").strip("/")
    path_prefix = f"{base_path}/" if base_path else ""
    return f"https://{settings.JITSI_SELFHOSTED_DOMAIN}/{path_prefix}{room}?jwt={token}"


def _generate_fallback(title: str) -> dict:
    """Pick the video fallback used when Google Calendar is unavailable.

    Priority: self-hosted Jitsi (free, your own server) > JaaS (hosted,
    metered) > plain meet.jit.si, which gates anonymous joiners behind a
    "waiting for the moderator" screen.
    """
    if settings.JITSI_SELFHOSTED_ENABLED:
        return _generate_selfhosted_jitsi_room(title)
    if settings.JAAS_ENABLED:
        return _generate_jaas_room(title)
    return _generate_jitsi_link(title)


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
    Falls back to JaaS/Jitsi if Google Calendar is disabled or credentials are missing.
    """
    if not settings.GOOGLE_CALENDAR_ENABLED:
        return _generate_fallback(title)

    service = _build_calendar_service(organizer_email)
    if service is None:
        return _generate_fallback(title)

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
        return _generate_fallback(title)


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
    """Async wrapper — creates a video meeting for a consultation.

    Tries, in order: Daily.co (if enabled) > Google Calendar/Meet (if
    enabled) > JaaS (if enabled) > plain meet.jit.si.
    """
    if settings.DAILY_ENABLED:
        from app.utils.daily_co import create_daily_room

        duration_minutes = max(int((end_dt - start_dt).total_seconds() // 60), 1)
        daily_result = await create_daily_room(title, duration_minutes=duration_minutes)
        if daily_result:
            return daily_result

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
