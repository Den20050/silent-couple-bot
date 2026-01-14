"""Configuration using pydantic-settings."""

import json
from datetime import time
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Telegram Bot
    tg_bot_token: str

    # Alternative bot token for loading images (deprecated)  # noqa: E501
    # Kept for backward compatibility, but all images are now loaded via main bot  # noqa: E501
    tg_bot_token_loader: Optional[str] = Field(  # noqa: E501
        default=None,
        description=(  # noqa: E501
            "[DEPRECATED] Alternative bot token - not used anymore. "  # noqa: E501
            "All images are loaded via main bot."
        ),
    )

    # Database
    database_url: str

    # SSH Tunnel for Database (optional)
    database_ssh_host: Optional[str] = Field(
        default=None,
        description="SSH host for Database tunnel (IP or hostname)",
    )
    database_ssh_user: Optional[str] = Field(
        default="root",
        description="SSH user for Database tunnel (default: root)",
    )
    database_ssh_port: Optional[int] = Field(
        default=22,
        description="SSH port for Database tunnel (default: 22)",
    )
    database_remote_port: Optional[int] = Field(
        default=None,
        description=(
            "Remote PostgreSQL port on server (default: same as port in DATABASE_URL). "
            "Use this if PostgreSQL on server listens on different port than in DATABASE_URL"
        ),
    )

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_db: int = 0

    # SSH Tunnel for Redis (optional)
    redis_ssh_host: Optional[str] = Field(
        default=None,
        description="SSH host for Redis tunnel (IP or hostname)",
    )
    redis_ssh_user: Optional[str] = Field(
        default="root",
        description="SSH user for Redis tunnel (default: root)",
    )
    redis_ssh_port: Optional[int] = Field(
        default=22,
        description="SSH port for Redis tunnel (default: 22)",
    )

    # YooKassa (DEPRECATED - закомментировано)
    # yookassa_shop_id: str
    # yookassa_secret_key: str

    # Robokassa
    robokassa_merchant_login: str
    robokassa_password_1: str  # Password #1 для генерации подписи оплаты
    robokassa_password_2: str  # Password #2 для проверки подписи ResultURL
    robokassa_is_production: bool = Field(
        default=False,
        description="Использовать продакшн режим (True) или тестовый (False)",
    )
    robokassa_domain: str = Field(
        default="robokassa.ru",
        description="Домен Робокассы: robokassa.ru (Россия), robokassa.kz (Казахстан), robokassa.com (международный)",
    )
    robokassa_include_shp_in_signature: bool = Field(
        default=True,
        description=(
            "Включать ли Shp_ параметры в подпись платежа. "
            "Иногда помогает диагностировать 500 на стороне Robokassa."
        ),
    )
    robokassa_shp_kv_separator: str = Field(
        default="=",
        description=(
            "Разделитель между ключом и значением для Shp_ параметров в подписи. "
            "Обычно используется '=' (Shp_key=value), но некоторые примеры/кастомные настройки "
            "могут ожидать ':' (Shp_key:value). Допустимые значения: '=' или ':'."
        ),
    )

    @field_validator("robokassa_shp_kv_separator")
    @classmethod
    def validate_robokassa_shp_kv_separator(cls, v: str) -> str:
        """Validate Shp_ key/value separator for Robokassa signature."""
        if v not in ("=", ":"):
            raise ValueError("robokassa_shp_kv_separator must be '=' or ':'")
        return v

    # Currency prices for subscriptions (JSON format)
    # Format: {"CURRENCY": {"plan_id": price, ...}, ...}
    # Prices are in main currency units (not kopecks/cents)
    # Supported currencies: RUB, EUR, USD, UAH, BYN, KZT, AED, THB, TRY, CNY  # noqa: E501
    # IMPORTANT: Store only RUB prices. Prices for other currencies are calculated automatically
    # with margin (see currency_margin_percent and currency_exchange_rates)
    # Example: {"RUB": {"1_month": 199, "3_months": 549, ...}}  # noqa: E501
    subscription_prices: str = Field(  # noqa: E501
        default=(
            '{"RUB": {"1_month": 299, "3_months": 799, '
            '"6_months": 1399, "1_year": 2499, "lifetime": 4999}}'
        ),
        description="JSON with subscription prices (only RUB required, others calculated automatically)",
    )
    
    # Currency margin percentage (added to exchange rate for non-RUB currencies)
    # Example: 17 means +17% margin (price = RUB_price * exchange_rate * 1.17)
    currency_margin_percent: float = Field(
        default=17.0,
        ge=0.0,
        le=100.0,
        description="Margin percentage added to exchange rate for non-RUB currencies (default: 17%)",
    )
    
    # Fixed exchange rates from RUB to other currencies (JSON format)
    # Format: {"CURRENCY": rate, ...}
    # Rate means: 1 RUB = rate * CURRENCY
    # Example: {"USD": 0.010, "EUR": 0.009} means 1 RUB = 0.010 USD = 0.009 EUR
    # If currency not specified, approximate rates will be used
    currency_exchange_rates: str = Field(
        default=(
            '{"USD": 0.010, "EUR": 0.009, "UAH": 0.40, "BYN": 0.033, '
            '"KZT": 4.5, "AED": 0.037, "THB": 0.36, "TRY": 0.32, "CNY": 0.072}'
        ),
        description="Fixed exchange rates from RUB to other currencies (JSON format)",
    )
    
    # Currency rates cache TTL in minutes
    # Rates are fetched from ЦБ РФ API and cached in Redis
    currency_rates_cache_ttl_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,  # Max 24 hours
        description="TTL for currency rates cache in minutes (default: 30)",
    )

    # MinIO
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket_pics: str = "pics"

    # Environment
    environment: str = "dev"
    log_level: str = "INFO"
    
    # Logging
    log_file: Optional[str] = Field(
        default="logs/bot.log",
        description="Path to log file (relative to project root). Set to empty string to disable file logging.",
    )
    log_file_max_bytes: int = Field(
        default=10 * 1024 * 1024,  # 10 MB
        description="Maximum size of log file before rotation (in bytes)",
    )
    log_file_backup_count: int = Field(
        default=5,
        description="Number of backup log files to keep",
    )

    # Mini App URL
    mini_app_url: str = "http://localhost:8000"  # noqa: E501

    # Telegram Bot Webhook (optional)
    # If set, bot will use webhook instead of polling
    webhook_url: Optional[str] = Field(
        default=None,
        description=(
            "Full URL for Telegram webhook "
            "(e.g., https://your-domain.com/webhook/telegram)"
        ),
    )
    webhook_path: str = Field(
        default="/webhook/telegram",
        description="Path for Telegram webhook endpoint",  # noqa: E501
    )
    webhook_port: int = Field(
        default=8443,
        description="Port for webhook server (if different from mini_app)",
    )
    webhook_secret_token: Optional[str] = Field(
        default=None,
        description=(
            "Secret token for webhook verification "
            "(optional but recommended)"  # noqa: E501
        ),
    )

    # Admin
    admin_tg_id: Optional[int] = Field(
        default=None,
        description="Admin Telegram ID for dev commands",
    )

    # Sending times (user local time, format HH:MM)
    # These times are interpreted as the desired local time for each user
    # The bot will check each user's timezone (utc_offset)
    # and send messages accordingly
    morning_start: str = "7:00"  # 07:00 user local time  # noqa: E501
    morning_end: str = "8:00"  # 08:00 user local time
    evening_start: str = "21:00"  # 21:00 user local time
    evening_end: str = "22:00"  # 22:00 user local time

    # Trial period (days)
    trial_period_days: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Duration of trial period in days (default: 7)",
    )
    
    # Redis key prefixes
    redis_key_prefix_reminder_sent: str = Field(
        default="reminder_sent",
        description="Redis key prefix for sent reminders",
    )
    redis_key_prefix_warning_cancelled: str = Field(
        default="initiator_warning_cancelled",
        description="Redis key prefix for cancelled warnings",
    )
    redis_key_prefix_warning_last_time: str = Field(
        default="initiator_warning_last_time",
        description="Redis key prefix for last warning timestamp",
    )
    redis_key_prefix_task_lock: str = Field(
        default="task_lock",
        description="Redis key prefix for task locks",
    )
    redis_key_prefix_wish_request: str = Field(
        default="wish_request",
        description="Redis key prefix for wish request tracking",
    )
    
    # Reminder settings
    reminder_hours: str = Field(
        default="3,6,9",
        description="Hours after picture sent to send reminders (comma-separated, e.g., '3,6,9')",
    )
    reminder_ttl_hours: int = Field(
        default=24,
        ge=1,
        description="TTL for reminder keys in hours (default: 24)",
    )
    
    # Warning settings
    warning_min_hours: int = Field(
        default=10,
        ge=1,
        description="Minimum hours after picture sent before sending warnings (default: 10)",
    )
    warning_interval_hours: int = Field(
        default=6,
        ge=1,
        description="Interval between warnings in hours (default: 6)",
    )
    warning_ttl_days: int = Field(
        default=7,
        ge=1,
        description="TTL for warning keys in days (default: 7)",
    )
    
    # Task lock settings
    task_lock_ttl_seconds: int = Field(
        default=60,
        ge=1,
        description="TTL for task locks in seconds (default: 60)",
    )
    
    # Other notification TTL settings
    nudge_ttl_hours: int = Field(
        default=24,
        ge=1,
        description="TTL for nudge keys in hours (default: 24)",
    )
    summary_ttl_days: int = Field(
        default=7,
        ge=1,
        description="TTL for summary keys in days (default: 7)",
    )
    
    # Subscription renewal reminder settings
    subscription_renewal_days_before: int = Field(
        default=3,
        ge=1,
        le=30,
        description="Days before subscription expiry to send renewal reminder (default: 3)",
    )
    subscription_renewal_reminder_interval_hours: int = Field(
        default=6,
        ge=1,
        le=24,
        description="Interval between renewal reminders in hours (default: 6)",
    )
    redis_key_prefix_renewal_reminder: str = Field(
        default="renewal_reminder_sent",
        description="Redis key prefix for renewal reminder tracking",
    )
    redis_key_prefix_feedback_ticket: str = Field(
        default="feedback_ticket",
        description="Redis key prefix for feedback tickets (TTL: 72 hours)",
    )
    feedback_ticket_ttl_hours: int = Field(
        default=72,
        ge=1,
        description="TTL for feedback tickets in hours (default: 72)",
    )
    
    # Resource information (for display in user menu)
    # If a field is not relevant (e.g., EGRIP or OGRN), comment it out in .env
    resource_inn: Optional[str] = Field(
        default=None,
        description="ИНН (обязательно для ИП и организаций)",
    )
    resource_status: Optional[str] = Field(
        default=None,
        description="Статус (форма собственности): ИП, Самозанятый, ООО и т.д.",
    )
    resource_ogrn: Optional[str] = Field(
        default=None,
        description="ОГРН (для организаций, закомментируйте если не актуально)",
    )
    resource_egrip: Optional[str] = Field(
        default=None,
        description="ЕГРИП (для ИП, закомментируйте если не актуально)",
    )
    resource_email: Optional[str] = Field(
        default=None,
        description="Email для связи",
    )
    resource_phone: Optional[str] = Field(
        default=None,
        description="Телефон для связи",
    )
    
    def get_reminder_hours(self) -> list[int]:
        """Parse reminder hours from comma-separated string.
        
        Returns:
            List of hours as integers
        """
        try:
            return [int(h.strip()) for h in self.reminder_hours.split(",") if h.strip()]
        except (ValueError, AttributeError):
            return [3, 6, 9]  # Default fallback

    @field_validator(  # noqa: E501
        "morning_start",
        "morning_end",
        "evening_start",
        "evening_end",
        mode="before",
    )
    @classmethod
    def parse_time(cls, v):
        """Parse time string: support both HH:MM and HH formats."""
        if isinstance(v, int):
            # Backward compatibility: convert int hour to HH:MM format
            return f"{v}:00"
        if isinstance(v, str):
            # Validate format HH:MM or HH
            parts = v.split(":")  # noqa: E501
            if len(parts) == 1:
                # Only hour provided, add :00
                try:
                    hour = int(parts[0])
                    if 0 <= hour <= 23:
                        return f"{hour}:00"
                except ValueError:
                    pass
            elif len(parts) == 2:
                # HH:MM format
                try:
                    hour = int(parts[0])
                    minute = int(parts[1])
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        return f"{hour:02d}:{minute:02d}"
                except ValueError:
                    pass
        # If validation fails, raise error
        raise ValueError(
            f"Invalid time format: {v}. Expected HH:MM or HH (0-23)"
        )

    @field_validator("admin_tg_id", mode="before")
    @classmethod
    def parse_admin_tg_id(cls, v):
        """Parse admin_tg_id: empty string -> None, otherwise int."""
        if v == "" or v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None
    
    @field_validator(
        "resource_inn",
        "resource_status",
        "resource_ogrn",
        "resource_egrip",
        "resource_email",
        "resource_phone",
        mode="before",
    )
    @classmethod
    def parse_resource_field(cls, v):
        """Parse resource fields: empty string -> None."""
        if v == "" or v is None:
            return None
        return str(v).strip() if v else None

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment.lower() == "prod"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment.lower() == "dev"

    def parse_time_to_time(self, time_str: str) -> time:
        """Parse time string (HH:MM) to time object."""
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return time(hour, minute)

    @property
    def morning_start_time(self) -> time:
        """Get morning start time as time object."""
        return self.parse_time_to_time(self.morning_start)

    @property
    def morning_end_time(self) -> time:
        """Get morning end time as time object."""
        return self.parse_time_to_time(self.morning_end)

    @property
    def evening_start_time(self) -> time:
        """Get evening start time as time object."""
        return self.parse_time_to_time(self.evening_start)

    @property
    def evening_end_time(self) -> time:
        """Get evening end time as time object."""
        return self.parse_time_to_time(self.evening_end)

    def get_currency_exchange_rates(self) -> dict:
        """Get currency exchange rates parsed from JSON.
        
        Returns:
            Dictionary with exchange rates: {"USD": 0.010, "EUR": 0.009, ...}
            Rates mean: 1 RUB = rate * CURRENCY
        """
        try:
            return json.loads(self.currency_exchange_rates)
        except (json.JSONDecodeError, TypeError):
            # Fallback to approximate rates
            return {
                "USD": 0.010,
                "EUR": 0.009,
                "UAH": 0.40,
                "BYN": 0.033,
                "KZT": 4.5,
                "AED": 0.037,
                "THB": 0.36,
                "TRY": 0.32,
                "CNY": 0.072,
            }
    
    def get_subscription_prices(self) -> dict:
        """Get subscription prices with automatic calculation for non-RUB currencies.
        
        Prices for non-RUB currencies are calculated from RUB prices using:
        - Fixed exchange rates (currency_exchange_rates)
        - Margin percentage (currency_margin_percent)
        
        Formula: price_in_currency = price_in_rub * exchange_rate * (1 + margin_percent / 100)
        
        Returns:
            Dictionary with prices for all currencies:
            {"RUB": {...}, "USD": {...}, "EUR": {...}, ...}
        """
        # Parse base RUB prices
        try:
            base_prices = json.loads(self.subscription_prices)
        except (json.JSONDecodeError, TypeError):
            # Fallback to default RUB prices
            base_prices = {
                "RUB": {
                    "1_month": 299,
                    "3_months": 799,
                    "6_months": 1399,
                    "1_year": 2499,
                    "lifetime": 4999,
                }
            }
        
        # Ensure RUB prices exist
        if "RUB" not in base_prices:
            raise ValueError("RUB prices must be specified in subscription_prices")
        
        # Extract only RUB prices (ignore any other currencies if specified)
        # Other currencies will be calculated automatically
        rub_prices = base_prices["RUB"]
        
        # Get exchange rates
        exchange_rates = self.get_currency_exchange_rates()
        
        # Calculate margin multiplier (e.g., 25% = 1.25)
        margin_multiplier = 1.0 + (self.currency_margin_percent / 100.0)
        
        # Get supported currencies from constants
        from src.core.constants import SUPPORTED_CURRENCIES
        
        # Build result dictionary starting with RUB prices
        result = {"RUB": rub_prices.copy()}
        
        # Calculate prices for each supported currency (except RUB)
        for currency_code in SUPPORTED_CURRENCIES.keys():
            if currency_code == "RUB":
                continue
            
            # Get exchange rate (default to 1.0 if not found)
            exchange_rate = exchange_rates.get(currency_code, 1.0)
            
            # Calculate prices for this currency
            currency_prices = {}
            for plan_id, rub_price in rub_prices.items():
                # Calculate: price = RUB_price * exchange_rate * margin_multiplier
                calculated_price = rub_price * exchange_rate * margin_multiplier
                
                # Round to appropriate decimals based on currency
                decimals = SUPPORTED_CURRENCIES[currency_code]["decimals"]
                currency_prices[plan_id] = round(calculated_price, decimals)
            
            result[currency_code] = currency_prices
        
        return result


settings = Settings()
