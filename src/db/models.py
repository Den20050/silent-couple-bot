"""SQLAlchemy models."""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import ARRAY, BigInteger, Boolean, CheckConstraint, Date, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.constants import DeliveryChat, PairMode, PairStatus, PicType, SubscriptionStatus
from src.db.base import Base


class User(Base):
    """User model."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    utc_offset: Mapped[int] = mapped_column(default=3)  # Default UTC+3
    # Preferred 1-hour notification windows (user local time)
    # Defaults match MORNING_START=07:00-08:00 and EVENING_START=21:00-22:00
    morning_window_start_hour: Mapped[int] = mapped_column(default=7, nullable=False)
    evening_window_start_hour: Mapped[int] = mapped_column(default=21, nullable=False)
    notification_windows_prompted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    preferred_mode: Mapped[Optional[str]] = mapped_column(
        Text,
        CheckConstraint("preferred_mode IN ('silent', 'chat')", name="preferred_mode_check"),
        nullable=True,
    )  # Mode selected during onboarding
    consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_dt: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    consent_ip: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payer_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Who paid for any pair
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("tg_id > 0", name="tg_id_positive"),
    )


class Pair(Base):
    """Pair relationship model."""

    __tablename__ = "pairs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    uid_a: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    uid_b: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    mode: Mapped[str] = mapped_column(
        Text,
        CheckConstraint("mode IN ('silent', 'chat')", name="mode_check"),
        default=PairMode.SILENT.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Text,
        CheckConstraint("status IN ('trial', 'active', 'past_due', 'cancelled')", name="status_check"),
        default=PairStatus.TRIAL.value,
        nullable=False,
    )
    payer_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Who paid for this pair
    delivery_chat: Mapped[str] = mapped_column(
        Text,
        CheckConstraint("delivery_chat IN ('bot_dm', 'pair_dm')", name="delivery_chat_check"),
        default=DeliveryChat.BOT_DM.value,
        nullable=False,
    )
    private_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Private chat ID for pair_dm mode
    nickname_a: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Nickname for user A (how user B calls user A)
    nickname_b: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Nickname for user B (how user A calls user B)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("uid_a < uid_b", name="uid_order_check"),  # Prevent duplicates (A,B) and (B,A)
        Index("idx_pairs_status_mode", "status", "mode"),
    )


class DailyState(Base):
    """Daily state for pair interactions."""

    __tablename__ = "daily_state"

    pair_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pairs.id", ondelete="CASCADE"), primary_key=True, nullable=False
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True, nullable=False)
    morning_initiator: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    morning_file_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    morning_sent_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)  # When picture was sent to partner
    morning_responded_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)  # When partner responded
    evening_initiator: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    evening_file_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evening_sent_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)  # When picture was sent to partner
    evening_responded_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)  # When partner responded
    last_surprise_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)  # Last time Micro-Surprise was used (Chat Mode)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_daily_state_day", "day"),
        Index("idx_daily_state_created_at", "created_at"),
        Index("idx_daily_state_morning_sent", "morning_sent_at"),
        Index("idx_daily_state_evening_sent", "evening_sent_at"),
    )


class Subscription(Base):
    """Subscription model."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pair_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pairs.id", ondelete="CASCADE"), nullable=False)
    payer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    yoo_id: Mapped[Optional[str]] = mapped_column(Text, unique=True, nullable=True)  # Payment ID (для совместимости хранит inv_id от Robokassa, ранее использовался для YooKassa)
    status: Mapped[str] = mapped_column(
        Text,
        CheckConstraint(
            "status IN ('trial', 'active', 'past_due', 'cancelled', 'refunded')", name="subscription_status_check"
        ),
        default=SubscriptionStatus.TRIAL.value,
        nullable=False,
    )
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    is_lifetime: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Lifetime subscription flag
    last_past_due_notification_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True
    )  # Last date when past_due notification was sent (fallback when Redis unavailable)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_subscriptions_period", "period_end", "status"),
    )


class BotMessage(Base):
    """Bot messages for cleanup tracking."""

    __tablename__ = "bot_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False, index=True)

    __table_args__ = (
        Index("idx_bot_messages_sent_at", "sent_at"),
        Index("idx_bot_messages_chat_message", "chat_id", "message_id"),
    )


class PairDemo(Base):
    """Pair demo blocklist - tracks which pairs have used demo."""

    __tablename__ = "pair_demo"

    uid_a: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False)  # User ID A
    uid_b: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False)  # User ID B
    
    __table_args__ = (
        CheckConstraint("uid_a < uid_b", name="pair_demo_uid_order_check"),  # Prevent duplicates
    )


class LifetimePairHistory(Base):
    """History of broken pairs with lifetime subscriptions."""

    __tablename__ = "lifetime_pair_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    uid_a: Mapped[int] = mapped_column(BigInteger, nullable=False)  # User ID A (not FK to avoid CASCADE issues)
    uid_b: Mapped[int] = mapped_column(BigInteger, nullable=False)  # User ID B (not FK to avoid CASCADE issues)
    broken_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    
    __table_args__ = (
        CheckConstraint("uid_a < uid_b", name="lifetime_uid_order_check"),  # Prevent duplicates
        Index("idx_lifetime_pair_history_users", "uid_a", "uid_b"),  # For fast lookup
    )


class PicsPool(Base):
    """Pictures pool (Telegram file_ids)."""

    __tablename__ = "pics_pool"

    file_id: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    type: Mapped[str] = mapped_column(
        Text,
        CheckConstraint("type IN ('morning', 'evening')", name="pic_type_check"),
        nullable=False,
    )
    tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), default=list, nullable=True)

    __table_args__ = (
        Index("idx_pics_pool_type", "type"),
    )

