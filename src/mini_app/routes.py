"""Mini App API routes."""

import os

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import DeliveryChat, PairStatus
from src.core.logger import get_logger
from src.db.base import async_session_maker
from src.db.models import Pair, PicsPool, User
from src.mini_app.api import router as api_router
from src.mini_app.security import extract_user_id, verify_init_data
from src.services.telegram import send_photo_with_retry

logger = get_logger(__name__)

router = APIRouter()
router.include_router(api_router)


async def get_db_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session


async def _authorize_send(
    session: AsyncSession,
    *,
    tg_id: int,
    chat_id: int,
    file_id: str,
) -> str | None:
    """Return the trusted picture type when this user may send it to this chat."""
    user_result = await session.execute(select(User).where(User.tg_id == tg_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        return None

    pairs_result = await session.execute(
        select(Pair).where(
            or_(Pair.uid_a == user.id, Pair.uid_b == user.id),
            Pair.status.in_([PairStatus.TRIAL.value, PairStatus.ACTIVE.value]),
        )
    )
    pairs = pairs_result.scalars().all()
    destination_allowed = False
    for pair in pairs:
        if (
            pair.delivery_chat == DeliveryChat.PAIR_DM.value
            and pair.private_chat_id == chat_id
        ):
            destination_allowed = True
            break
        if pair.delivery_chat == DeliveryChat.BOT_DM.value:
            partner_id = pair.uid_b if pair.uid_a == user.id else pair.uid_a
            partner_result = await session.execute(
                select(User.tg_id).where(User.id == partner_id)
            )
            if partner_result.scalar_one_or_none() == chat_id:
                destination_allowed = True
                break
    if not destination_allowed:
        return None

    picture_result = await session.execute(
        select(PicsPool.type).where(PicsPool.file_id == file_id)
    )
    return picture_result.scalar_one_or_none()


@router.get("/tz-sync", response_class=HTMLResponse)
async def tz_sync_page() -> str:
    """Serve timezone sync Mini App page."""
    html_path = os.path.join(os.path.dirname(__file__), "static", "tz-sync.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="tz-sync.html not found")


@router.get("/", response_class=HTMLResponse)
async def index() -> str:
    """Serve Mini App HTML."""
    # Read HTML file
    import os

    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Silent Couple Bot</title></head>
        <body>
            <h1>Mini App</h1>
            <p>HTML file not found. Please create src/mini_app/static/index.html</p>
        </body>
        </html>
        """


@router.post("/send")
async def send_photo(
    request: Request,
    initData: str = Form(...),
    file_id: str = Form(...),
    chat_id: str = Form(...),
    session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    """Send photo to chat."""
    # Verify initData
    if not verify_init_data(initData):
        logger.warning("Invalid initData signature", ip=request.client.host)
        raise HTTPException(status_code=403, detail="Invalid signature")

    tg_id = extract_user_id(initData)
    if tg_id is None:
        raise HTTPException(status_code=403, detail="Invalid user")

    try:
        chat_id_int = int(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id")

    pic_type = await _authorize_send(
        session,
        tg_id=tg_id,
        chat_id=chat_id_int,
        file_id=file_id,
    )
    if pic_type is None:
        logger.warning("Mini App send denied", tg_id=tg_id, chat_id=chat_id_int)
        raise HTTPException(
            status_code=403, detail="Destination or picture not allowed"
        )

    # Send photo via bot
    try:
        await send_photo_with_retry(
            chat_id=chat_id_int,
            photo=file_id,
            caption="Доброе утро ❤️" if pic_type == "morning" else "Спокойной ночи ❤️",
            pic_type=pic_type,
        )
        return JSONResponse({"status": "ok", "message": "Photo sent"})
    except Exception as e:
        logger.error("Failed to send photo", error=str(e), chat_id=chat_id_int)
        raise HTTPException(status_code=500, detail="Failed to send photo")


@router.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "ok"})
