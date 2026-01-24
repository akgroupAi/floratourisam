"""Chat endpoints with WebSocket support."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from app.api.deps import CurrentUser, DatabaseSession
from app.schemas.chat import ChatMessageCreate, ChatMessageResponse, ChatRoomCreate, ChatRoomResponse
from app.schemas.common import PaginatedResponse
from app.services.notification_service import notification_service

router = APIRouter()


@router.get("/rooms")
async def list_chat_rooms(current_user: CurrentUser, db: DatabaseSession):
    """List user's chat rooms."""
    return {"rooms": [], "total_unread": 0}


@router.post("/rooms", response_model=ChatRoomResponse)
async def create_chat_room(data: ChatRoomCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a chat room."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/rooms/{room_id}/messages")
async def get_room_messages(room_id: UUID, db: DatabaseSession, page: int = Query(1), page_size: int = Query(50)):
    """Get messages in a chat room."""
    return PaginatedResponse.create([], 0, page, page_size)


@router.post("/rooms/{room_id}/messages", response_model=ChatMessageResponse)
async def send_message(room_id: UUID, data: ChatMessageCreate, current_user: CurrentUser, db: DatabaseSession):
    """Send a message to a chat room."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.websocket("/ws/{room_id}")
async def websocket_chat(websocket: WebSocket, room_id: str):
    """WebSocket endpoint for real-time chat."""
    await notification_service.manager.connect(websocket, room_id)
    try:
        while True:
            data = await websocket.receive_json()
            await notification_service.manager.broadcast(room_id, data)
    except WebSocketDisconnect:
        notification_service.manager.disconnect(websocket, room_id)
