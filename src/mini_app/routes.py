"""Mini App API routes."""

from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse

from src.core.logger import get_logger
from src.mini_app.security import verify_init_data
from src.services.telegram import send_photo_with_retry

logger = get_logger(__name__)

router = APIRouter()


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
) -> JSONResponse:
    """Send photo to chat."""
    # Verify initData
    if not verify_init_data(initData):
        logger.warning("Invalid initData signature", ip=request.client.host)
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    try:
        chat_id_int = int(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id")
    
    # Send photo via bot
    try:
        await send_photo_with_retry(
            chat_id=chat_id_int,
            photo=file_id,
            caption="Доброе утро ❤️",
            pic_type="morning",
        )
        return JSONResponse({"status": "ok", "message": "Photo sent"})
    except Exception as e:
        logger.error("Failed to send photo", error=str(e), chat_id=chat_id_int)
        raise HTTPException(status_code=500, detail="Failed to send photo")


@router.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "ok"})

