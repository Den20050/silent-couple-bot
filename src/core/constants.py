"""Application constants."""

from datetime import time
from enum import Enum

from src.core.config import settings


class PairMode(str, Enum):
    """Pair communication mode."""

    SILENT = "silent"
    CHAT = "chat"


class PairStatus(str, Enum):
    """Pair subscription status."""

    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"


class SubscriptionStatus(str, Enum):
    """Subscription status."""

    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PicType(str, Enum):
    """Picture type."""

    MORNING = "morning"
    EVENING = "evening"


class DeliveryChat(str, Enum):
    """Delivery chat type for pictures."""

    BOT_DM = "bot_dm"  # Send to bot DM (default)
    PAIR_DM = "pair_dm"  # Send to pair's private chat


# Time windows (UTC) - loaded from config as time objects
MORNING_WINDOW_START: time = settings.morning_start_time
MORNING_WINDOW_END: time = settings.morning_end_time
EVENING_WINDOW_START: time = settings.evening_start_time
EVENING_WINDOW_END: time = settings.evening_end_time

# Trial period (days) - loaded from config
TRIAL_PERIOD_DAYS = settings.trial_period_days

# Subscription period (days)
SUBSCRIPTION_PERIOD_DAYS = 30

# Supported currencies for Robokassa
SUPPORTED_CURRENCIES = {
    "RUB": {"name": "Российский рубль", "symbol": "₽", "decimals": 2},
    "EUR": {"name": "Евро", "symbol": "€", "decimals": 2},
    "USD": {"name": "Доллар США", "symbol": "$", "decimals": 2},
    "KZT": {"name": "Казахстанский тенге", "symbol": "₸", "decimals": 2},
}

# Subscription plans (period in days)
# Prices are loaded from config (subscription_prices) for each currency
# For lifetime plan, days should be None (handled specially)
SUBSCRIPTION_PLANS = {
    "1_month": {"days": 30, "name": "1 месяц"},
    "3_months": {"days": 90, "name": "3 месяца"},
    "6_months": {"days": 180, "name": "6 месяцев"},
    "1_year": {"days": 365, "name": "1 год"},
    "lifetime": {"days": None, "name": "Навсегда", "is_lifetime": True},
}

# Daily state retention (days)
DAILY_STATE_RETENTION_DAYS = 31

# Circuit breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 3
CIRCUIT_BREAKER_TIMEOUT_SECONDS = 60

# Rate limiting
RATE_LIMIT_MESSAGES_PER_SECOND = 50
RATE_LIMIT_MESSAGES_PER_USER_PER_MINUTE = 20
RATE_LIMIT_BAN_DURATION_SECONDS = 3600  # 1 hour

# Telegram API retry
TELEGRAM_RETRY_ATTEMPTS = 3
TELEGRAM_RETRY_DELAYS = [1, 2, 4]  # seconds

# Warm caption pools for Chat Mode (randomly selected on each send)
CHAT_MORNING_CAPTIONS = [
    "Доброе утро, солнце ☀️",
    "Просыпайся — думаю о тебе ❤️",
    "Доброе утро, мой человек 🌤",
    "Твоё утро начинается со мной — и это прекрасно ☀️",
    "С добрым утром! Пусть день будет тёплым 🌞",
    "Доброе утро ☀️ Ты в моих мыслях",
    "Открой глаза — день начинается для нас двоих 🌅",
    "Доброе утро! Скучаю по тебе с самого пробуждения ❤️",
    "Утро с тобой в мыслях — лучшее утро ☀️",
    "Просыпайся, тебя ждёт хороший день 🌤",
    "Доброе утро ☀️… а теперь иди целуй меня",
    "Ты — моё любимое утро ❤️",
    "Это утро — для тебя 🌅",
    "Доброе утро, самый любимый человек ☀️",
    "С добрым утром! Я рядом, даже на расстоянии ❤️",
]

CHAT_EVENING_CAPTIONS = [
    "Спокойной ночи, мой человек 🌙",
    "Засыпай — я рядом, даже если молчу ❤️",
    "Спокойной ночи! Думаю о тебе 🌙",
    "Закрой глаза — всё хорошо ❤️",
    "Спокойной ночи, солнце 🌙",
    "Пусть тебе приснится что-то хорошее 🌙",
    "Спокойной ночи! Ты в моих мыслях этой ночью ❤️",
    "Засыпай спокойно — завтра будет хорошим 🌙",
    "Спокойной ночи… и не думай о ком-то другом ❤️",
    "До завтра! Спи сладко 🌙",
    "Спокойной ночи, мой самый любимый человек ❤️",
    "Закрывай глаза — утро будет хорошим 🌙",
    "Спокойной ночи! Я думаю о тебе ❤️",
    "Засыпай — завтра мы снова рядом 🌙",
    "Спокойной ночи, ты мой любимый человек ❤️",
]

# Kept for backward compatibility with surprise_logic.py (unused in main flow)
MICRO_SURPRISE_MORNING_CAPTIONS = CHAT_MORNING_CAPTIONS
MICRO_SURPRISE_EVENING_CAPTIONS = CHAT_EVENING_CAPTIONS
MICRO_SURPRISE_MIN_HOURS = 72
