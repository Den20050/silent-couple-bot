"""Robokassa webhook handler."""

from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import quote

from src.core.constants import PairStatus
from src.core.messages import get_message
from src.core.constants import SUBSCRIPTION_PERIOD_DAYS
from src.core.logger import get_logger
from src.core.redis_client import create_redis_client
from src.db.models import User
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.subscriptions import SubscriptionsRepository
from src.db.repositories.daily_state import DailyStateRepository
from src.services.payment import PaymentService
from src.services.telegram import send_message_with_retry
from src.db.base import async_session_maker

logger = get_logger(__name__)

# FastAPI router for webhook
webhook_router = APIRouter()


async def get_db_session() -> AsyncSession:
    """Get database session for FastAPI dependency injection."""
    async with async_session_maker() as session:
        yield session


async def _notify_payment_not_confirmed(
    session: AsyncSession,
    *,
    shp_params: dict[str, str],
    inv_id: str | None,
    out_sum: str | None,
    is_production: bool,
) -> None:
    """Notify users about unconfirmed test payment (best-effort)."""
    if is_production:
        return

    pair_id_value = shp_params.get("pair_id")
    if not pair_id_value or not pair_id_value.isdigit():
        return

    pair_id = int(pair_id_value)
    pairs_repo = PairsRepository(session)
    pair = await pairs_repo.get_by_id(pair_id)
    if not pair:
        return

    user_a_result = await session.execute(select(User).where(User.id == pair.uid_a))
    user_a = user_a_result.scalar_one_or_none()
    user_b_result = await session.execute(select(User).where(User.id == pair.uid_b))
    user_b = user_b_result.scalar_one_or_none()

    if not user_a or not user_b:
        return

    message_text = get_message(
        "PAYMENT_NOT_CONFIRMED_TEST",
        inv_id=inv_id or "-",
        out_sum=out_sum or "-",
    )

    await send_message_with_retry(chat_id=user_a.tg_id, text=message_text)
    await send_message_with_retry(chat_id=user_b.tg_id, text=message_text)

    logger.info(
        "Sent payment not confirmed notice (test mode)",
        pair_id=pair_id,
        inv_id=inv_id,
        out_sum=out_sum,
    )


# =============================================================================
# YooKassa webhook (DEPRECATED - закомментировано)
# =============================================================================
# @webhook_router.post("/webhook/yookassa")
# async def yookassa_webhook(request: Request, session: AsyncSession) -> dict:
#     """Handle YooKassa webhook."""
#     body = await request.body()
#     signature = request.headers.get("X-YooMoney-Signature", "")
#     
#     # Create Redis client for payment service
#     redis_client = await create_redis_client()
#     payment_service = PaymentService(redis_client)
#     
#     # Verify signature
#     if not await payment_service.verify_webhook(body.decode(), signature):
#         logger.warning("Invalid webhook signature", ip=request.client.host)
#         raise HTTPException(status_code=403, detail="Invalid signature")
#     
#     # Parse webhook data
#     import json
#     webhook_data = json.loads(body)
#     
#     # Process webhook
#     result = await payment_service.process_webhook(webhook_data)
#     
#     if not result or result["status"] != "succeeded":
#         return {"status": "ok"}
#     
#     # Update subscription and pair
#     pair_id = result["pair_id"]
#     payment_id = result["payment_id"]
#     is_lifetime = result.get("is_lifetime", False)
#     period_days = result.get("period_days")  # Can be None for lifetime
#     
#     pairs_repo = PairsRepository(session)
#     subs_repo = SubscriptionsRepository(session)
#     users_repo = UsersRepository(session)
#     
#     pair = await pairs_repo.get_by_id(pair_id)
#     if not pair:
#         logger.error("Pair not found", pair_id=pair_id)
#         return {"status": "ok"}
#     
#     subscription = await subs_repo.get_by_pair_id(pair_id)
#     if not subscription:
#         logger.error("Subscription not found", pair_id=pair_id)
#         return {"status": "ok"}
#     
#     # Calculate period_end: for lifetime, use far future date (2099-12-31)
#     if is_lifetime:
#         period_end = date(2099, 12, 31)
#     else:
#         # Regular subscription: extend from current period_end or from today if expired
#         current_period_end = subscription.period_end
#         today = date.today()
#         period_days = period_days or SUBSCRIPTION_PERIOD_DAYS
#         
#         if current_period_end >= today:
#             # Extend from current period_end
#             period_end = current_period_end + timedelta(days=period_days)
#         else:
#             # Start from today if subscription expired
#             period_end = today + timedelta(days=period_days)
#     
#     # Update subscription
#     await subs_repo.update_payment(
#         subscription_id=subscription.id,
#         yoo_id=payment_id,
#         period_end=period_end,
#         is_lifetime=is_lifetime,
#     )
#     
#     # Update pair status
#     await pairs_repo.update_status(pair.id, PairStatus.ACTIVE)
#     
#     # Update payer_id
#     payer_tg_id = result.get("payer_tg_id")  # Should be extracted from metadata
#     if payer_tg_id:
#         payer_user = await users_repo.get_by_tg_id(payer_tg_id)
#         if payer_user:
#             await pairs_repo.update_payer_id(pair.id, payer_user.id)
#             await users_repo.update_payer_id(payer_tg_id, payer_user.id)
#     
#     # Notify both users
#     user_a_result = await session.execute(
#         select(User).where(User.id == pair.uid_a)
#     )
#     user_a = user_a_result.scalar_one()
#     user_b_result = await session.execute(
#         select(User).where(User.id == pair.uid_b)
#     )
#     user_b = user_b_result.scalar_one()
#     
#     period_text = (
#         get_message("WEBHOOK_LIFETIME_TEXT")
#         if is_lifetime
#         else period_end.strftime('%d.%m.%Y')
#     )
#     await send_message_with_retry(
#         chat_id=user_a.tg_id,
#         text=get_message("PAY_SUBSCRIPTION_ACTIVE_UNTIL", period_text=period_text),
#     )
#     await send_message_with_retry(
#         chat_id=user_b.tg_id,
#         text=get_message("PAY_SUBSCRIPTION_ACTIVE_UNTIL", period_text=period_text),
#     )
#     
#     await session.commit()
#     
#     logger.info(
#         "Payment processed",
#         pair_id=pair_id,
#         payment_id=payment_id,
#         period_days=period_days,
#         period_end=period_end,
#         is_lifetime=is_lifetime,
#     )
#     
#     return {"status": "ok"}


@webhook_router.api_route("/webhook/robokassa", methods=["POST", "GET"])
async def robokassa_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> str:
    """Handle Robokassa ResultURL webhook."""
    try:
        query_params = dict(request.query_params)
        form_params: dict[str, str] = {}
        if request.method.upper() == "POST":
            try:
                form = await request.form()
                form_params = dict(form)
            except Exception:
                # If parsing fails, fall back to query-only handling.
                form_params = {}

        # Form params should override query params if both present
        params: dict[str, str] = {**query_params, **form_params}

        out_sum = params.get("OutSum")
        inv_id = params.get("InvId")
        signature = params.get("SignatureValue")

        logger.info(
            "Robokassa webhook received",
            method=request.method.upper(),
            params_keys=list(params.keys()),
            out_sum=out_sum,
            inv_id=inv_id,
            signature_preview=f"{signature[:8]}..." if signature else None,
            shp_params_keys=[k for k in params.keys() if k.startswith("Shp_")],
        )

        if not out_sum or not inv_id or not signature:
            logger.warning(
                "Robokassa webhook missing required parameters",
                has_out_sum=bool(out_sum),
                has_inv_id=bool(inv_id),
                has_signature=bool(signature),
                params_keys=list(params.keys()),
            )
            return "ERROR"

        # Extract Shp_ parameters (may arrive via POST or GET)
        shp_params = {
            k.replace("Shp_", ""): v for k, v in params.items() if k.startswith("Shp_")
        }

        # Create Redis client for payment service
        redis_client = await create_redis_client()
        # Get settings for PaymentService
        from src.core.config import settings as settings_module

        payment_service = PaymentService(redis_client, settings_module)

        # Process webhook
        result = await payment_service.process_webhook(
            out_sum=out_sum,
            inv_id=inv_id,
            signature=signature,
            shp_params=shp_params,
        )

        if not result or result["status"] != "succeeded":
            logger.warning(
                "Robokassa webhook processing failed",
                inv_id=inv_id,
                out_sum=out_sum,
            )
            await _notify_payment_not_confirmed(
                session,
                shp_params=shp_params,
                inv_id=inv_id,
                out_sum=out_sum,
                is_production=settings_module.robokassa_is_production,
            )
            return "ERROR"

        # Update subscription and pair
        pair_id = result["pair_id"]
        payment_id = result["payment_id"]  # Это inv_id
        is_lifetime = result.get("is_lifetime", False)
        period_days = result.get("period_days")  # Can be None for lifetime

        pairs_repo = PairsRepository(session)
        subs_repo = SubscriptionsRepository(session)

        pair = await pairs_repo.get_by_id(pair_id)
        if not pair:
            logger.error("Pair not found", pair_id=pair_id)
            return "ERROR"

        subscription = await subs_repo.get_by_pair_id(pair_id)
        if not subscription:
            logger.error("Subscription not found", pair_id=pair_id)
            return "ERROR"

        # Calculate period_end with remaining days added if subscription is still active
        from src.services.payment.subscription_calculator import (
            calculate_subscription_period_end,
        )

        period_days = period_days or SUBSCRIPTION_PERIOD_DAYS
        period_end = calculate_subscription_period_end(
            subscription=subscription,
            new_period_days=period_days,
            is_lifetime=is_lifetime,
            standard_month_days=30,
        )

        # Update subscription (используем payment_id как yoo_id для совместимости)
        updated_subscription = await subs_repo.update_payment(
            subscription_id=subscription.id,
            yoo_id=payment_id,  # Сохраняем inv_id в поле yoo_id для совместимости
            period_end=period_end,
            is_lifetime=is_lifetime,
        )

        # Use updated subscription if available, otherwise use original
        if updated_subscription:
            subscription = updated_subscription

        # Update pair status
        await pairs_repo.update_status(pair.id, PairStatus.ACTIVE)

        # Reset daily_state for today to start fresh after payment
        # This clears any previous states (initiators, responses, etc.)
        daily_state_repo = DailyStateRepository(session)
        today = date.today()
        daily_state = await daily_state_repo.get_by_pair_and_day(pair.id, today)

        if daily_state:
            # Reset all daily state fields to start fresh
            daily_state.morning_initiator = None
            daily_state.morning_file_id = None
            daily_state.morning_sent_at = None
            daily_state.morning_responded_at = None
            daily_state.evening_initiator = None
            daily_state.evening_file_id = None
            daily_state.evening_sent_at = None
            daily_state.evening_responded_at = None
            daily_state.last_surprise_at = None
            logger.info(
                "Daily state reset after payment",
                pair_id=pair.id,
                day=today.isoformat(),
            )

        # Reset last_past_due_notification_date to allow fresh notifications if needed
        subscription.last_past_due_notification_date = None

        # Notify both users
        user_a_result = await session.execute(select(User).where(User.id == pair.uid_a))
        user_a = user_a_result.scalar_one()
        user_b_result = await session.execute(select(User).where(User.id == pair.uid_b))
        user_b = user_b_result.scalar_one()

        period_text = (
            get_message("WEBHOOK_LIFETIME_TEXT")
            if is_lifetime
            else period_end.strftime("%d.%m.%Y")
        )
        await send_message_with_retry(
            chat_id=user_a.tg_id,
            text=get_message("PAY_SUBSCRIPTION_ACTIVE_UNTIL", period_text=period_text),
        )
        await send_message_with_retry(
            chat_id=user_b.tg_id,
            text=get_message("PAY_SUBSCRIPTION_ACTIVE_UNTIL", period_text=period_text),
        )

        await session.commit()

        logger.info(
            "Robokassa payment processed",
            pair_id=pair_id,
            inv_id=payment_id,
            period_days=period_days,
            period_end=period_end,
            is_lifetime=is_lifetime,
        )

        # Robokassa expects "OK<InvId>" on success (no spaces).
        return f"OK{payment_id}"
    except Exception as exc:
        logger.exception(
            "Robokassa webhook unhandled error",
            error=str(exc),
        )
        # Return 200 with error body to avoid Robokassa seeing HTTP 500.
        return "ERROR"


@webhook_router.get("/webhook/robokassa/return", response_class=HTMLResponse)
async def robokassa_return_page(
    bot: str = Query(..., min_length=3, max_length=64),
    start: str | None = Query(default=None, max_length=64),
) -> HTMLResponse:
    """Payment success return page for Telegram in-app browser.

    Telegram in-app browser on mobile cannot be closed programmatically.
    This page attempts to open the bot chat via tg:// deep link and provides
    a visible fallback button to t.me.
    """
    safe_bot = "".join(ch for ch in bot if ch.isalnum() or ch == "_")
    if safe_bot != bot:
        # Avoid open redirect / XSS vectors: only allow valid bot usernames.
        return HTMLResponse("Invalid bot", status_code=400)

    start_q = quote(start) if start else ""
    tme_url = (
        f"https://t.me/{safe_bot}?start={start_q}"
        if start_q
        else f"https://t.me/{safe_bot}"
    )
    tg_url = (
        f"tg://resolve?domain={safe_bot}&start={start_q}"
        if start_q
        else f"tg://resolve?domain={safe_bot}"
    )

    html_lines = [
        "<!doctype html>",
        '<html lang="ru">',
        "  <head>",
        '    <meta charset="utf-8" />',
        '    <meta name="viewport" content="width=device-width, initial-scale=1" />',
        "    <title>Возврат в бота</title>",
        f'    <meta http-equiv="refresh" content="2;url={tme_url}" />',
        "    <style>",
        "      body {",
        "        font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto,",
        "          Arial, sans-serif;",
        "        padding: 24px;",
        "      }",
        "      .btn {",
        "        display: inline-block;",
        "        padding: 14px 16px;",
        "        border-radius: 12px;",
        "        background: #2aabee;",
        "        color: #fff;",
        "        text-decoration: none;",
        "        font-weight: 600;",
        "      }",
        "      .muted { margin-top: 12px; color: #6b7280; }",
        "      code { background: #f3f4f6; padding: 2px 6px; border-radius: 6px; }",
        "    </style>",
        "  </head>",
        "  <body>",
        "    <h2>Оплата прошла успешно</h2>",
        "    <p>Возвращаем вас в Telegram…</p>",
        f'    <p><a class="btn" href="{tme_url}">Вернуться в бот</a></p>',
        '    <p class="muted">',
        "      Если окно оплаты не закрывается, нажмите <code>×</code> (крестик) и",
        "      закройте встроенный браузер Telegram.",
        "    </p>",
        "    <script>",
        f"      window.location.href = {tg_url!r};",
        "      setTimeout(function () {",
        f"        window.location.href = {tme_url!r};",
        "      }, 900);",
        "    </script>",
        "  </body>",
        "</html>",
    ]
    html = "\n".join(html_lines) + "\n"
    return HTMLResponse(content=html, status_code=200)

