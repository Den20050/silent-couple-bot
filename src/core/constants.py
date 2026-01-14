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
    "UAH": {"name": "Украинская гривна", "symbol": "₴", "decimals": 2},
    "BYN": {"name": "Белорусский рубль", "symbol": "Br", "decimals": 2},
    "KZT": {"name": "Казахстанский тенге", "symbol": "₸", "decimals": 2},
    "AED": {"name": "Дирхам ОАЭ", "symbol": "د.إ", "decimals": 2},
    "THB": {"name": "Тайский бат", "symbol": "฿", "decimals": 2},
    "TRY": {"name": "Турецкая лира", "symbol": "₺", "decimals": 2},
    "CNY": {"name": "Китайский юань", "symbol": "¥", "decimals": 2},
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

# Micro-Surprise captions for Chat Mode (random replacement every 3-4 days)
MICRO_SURPRISE_MORNING_CAPTIONS = [
    "Доброе утро ☀️… а теперь иди целуй меня",
    "Твоё утро начинается со мня — и это прекрасно",
    "Доброе утро, солнце ☀️",
]

MICRO_SURPRISE_EVENING_CAPTIONS = [
    "Засыпай — я рядом, даже если молчу",
    "Спокойной ночи… и не думай о ком-то другом ❤️",
    "Спокойной ночи, мой человек 🌙",
]

# Micro-Surprise: minimum hours between surprises (72 hours = 3 days)
MICRO_SURPRISE_MIN_HOURS = 72