"""Notification helper — create and optionally push notifications.

Usage:
    from app.utils.notifications import notify

    await notify(
        db=self.db,
        user_id=patient_user.id,
        title="Appointment Confirmed",
        message="Your appointment with Dr. Smith on April 22 is confirmed.",
        notification_type="consultation",
        entity_type="consultation",
        entity_id=consultation.id,
        action_url=f"/consultation/{consultation.id}",
    )
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.system import Notification
from app.services.notification_service import notification_service

logger = get_logger(__name__)


async def notify(
    db: AsyncSession,
    user_id: UUID,
    title: str,
    message: str,
    notification_type: str = "info",
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    action_url: Optional[str] = None,
    action_text: Optional[str] = None,
    metadata: Optional[dict] = None,
    created_by: Optional[UUID] = None,
) -> Notification:
    """Create a notification record and push it via WebSocket.

    This is best-effort: failures are logged but never raised.
    """
    try:
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            entity_type=entity_type,
            entity_id=entity_id,
            action_url=action_url,
            action_text=action_text,
            config_metadata=metadata,
            created_by=created_by,
        )
        db.add(notif)
        await db.flush()

        # Push via WebSocket (real-time)
        try:
            await notification_service.send_notification(
                user_id,
                {
                    "type": "notification",
                    "data": {
                        "id": str(notif.id),
                        "title": title,
                        "message": message,
                        "notification_type": notification_type,
                        "entity_type": entity_type,
                        "entity_id": str(entity_id) if entity_id else None,
                        "action_url": action_url,
                        "created_at": notif.created_at.isoformat() if notif.created_at else None,
                    },
                },
            )
        except Exception as ws_exc:
            logger.warning("websocket_push_failed", user_id=str(user_id), error=str(ws_exc))

        return notif

    except Exception as exc:
        logger.error("notification_create_failed", user_id=str(user_id), error=str(exc))
        raise
