"""Daily.co integration utility.

Creates private Daily.co video rooms and per-user meeting tokens via REST
API. Requires DAILY_ENABLED=True, DAILY_API_KEY and DAILY_DOMAIN.

Rooms are private (token-gated, so a guessed URL alone can't get in) with
knocking disabled, and every participant's token carries ``is_owner: True``
— so whoever opens their link first just starts the call. Neither patient
nor doctor waits on the other, and no admin/host account is ever involved.
"""

import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _room_name(title: str) -> str:
    """Build a unique room name from a consultation title.

    Daily room names allow letters, numbers, hyphens and underscores;
    lowercased to sidestep any case-sensitivity edge cases.
    """
    room_id = str(_uuid.uuid4()).replace("-", "")[:16]
    safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-")).strip().replace(" ", "-")
    safe_title = safe_title.lower()[:40]
    return f"{safe_title}-{room_id}" if safe_title else room_id


async def create_daily_room(title: str, duration_minutes: int = 60) -> Optional[dict]:
    """Create a private Daily.co room for a consultation.

    Returns ``{"meet_link": None, "google_event_id": None, "platform":
    "daily", "room": <name>}`` on success, or None if Daily isn't
    configured or the API call fails (caller should fall back).
    """
    if not (settings.DAILY_ENABLED and settings.DAILY_API_KEY and settings.DAILY_DOMAIN):
        return None

    room_name = _room_name(title)
    # Keep the room alive a bit past the scheduled end in case the call runs long.
    exp = int((datetime.now(timezone.utc) + timedelta(minutes=duration_minutes + 60)).timestamp())

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.DAILY_API_BASE_URL}/rooms",
                headers={"Authorization": f"Bearer {settings.DAILY_API_KEY}"},
                json={
                    "name": room_name,
                    "privacy": "private",
                    "properties": {
                        "exp": exp,
                        "enable_knocking": False,
                        "eject_at_room_exp": True,
                    },
                },
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("daily_room_creation_failed", error=str(exc))
        return None

    return {
        "meet_link": None,
        "google_event_id": None,
        "platform": "daily",
        "room": room_name,
    }


async def generate_daily_join_link(
    *,
    room: str,
    name: str,
    exp_minutes: int = 180,
) -> Optional[str]:
    """Mint a per-user, owner-level Daily.co join link.

    ``is_owner: True`` for every participant means neither patient nor
    doctor has to wait for the other, or for any admin, to arrive first.
    Returns None if Daily isn't configured or the API call fails.
    """
    if not (settings.DAILY_ENABLED and settings.DAILY_API_KEY and settings.DAILY_DOMAIN):
        return None

    exp = int((datetime.now(timezone.utc) + timedelta(minutes=exp_minutes)).timestamp())

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.DAILY_API_BASE_URL}/meeting-tokens",
                headers={"Authorization": f"Bearer {settings.DAILY_API_KEY}"},
                json={
                    "properties": {
                        "room_name": room,
                        "user_name": name,
                        "is_owner": True,
                        "exp": exp,
                    }
                },
            )
            response.raise_for_status()
            token = response.json().get("token")
    except httpx.HTTPError as exc:
        logger.error("daily_token_creation_failed", error=str(exc))
        return None

    if not token:
        return None

    return f"https://{settings.DAILY_DOMAIN}.daily.co/{room}?t={token}"
