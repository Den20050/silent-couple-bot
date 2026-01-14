"""Pairs repository."""

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import DeliveryChat, PairMode, PairStatus
from src.db.models import Pair


class PairsRepository:
    """Repository for pairs."""

    def __init__(self, session: AsyncSession):
        """Initialize repository."""
        self.session = session

    async def get_by_id(self, pair_id: int) -> Optional[Pair]:
        """Get pair by ID."""
        result = await self.session.execute(select(Pair).where(Pair.id == pair_id))
        return result.scalar_one_or_none()

    async def get_by_user_tg_id(self, tg_id: int) -> Optional[Pair]:
        """Get pair by user Telegram ID (returns first pair found)."""
        # Need to join with users table to get tg_id
        from src.db.models import User
        from src.core.logger import get_logger
        
        logger = get_logger(__name__)

        # First, get user ID by tg_id
        user_result = await self.session.execute(
            select(User.id).where(User.tg_id == tg_id)
        )
        user_id = user_result.scalar_one_or_none()
        
        logger.info(
            "get_by_user_tg_id: user lookup",
            tg_id=tg_id,
            user_id=user_id,
        )
        
        if not user_id:
            logger.warning(
                "get_by_user_tg_id: user not found",
                tg_id=tg_id,
            )
            return None
        
        # Then find pair where user is either uid_a or uid_b
        # Use explicit OR condition to find pairs where user is in either position
        result = await self.session.execute(
            select(Pair).where(
                (Pair.uid_a == user_id) | (Pair.uid_b == user_id)
            )
        )
        pair = result.scalar_one_or_none()
        
        logger.info(
            "get_by_user_tg_id: pair lookup result",
            tg_id=tg_id,
            user_id=user_id,
            pair_id=pair.id if pair else None,
            pair_uid_a=pair.uid_a if pair else None,
            pair_uid_b=pair.uid_b if pair else None,
        )
        
        return pair

    async def get_all_by_user_tg_id(self, tg_id: int) -> list[Pair]:
        """Get all pairs by user Telegram ID."""
        from src.db.models import User
        from src.core.logger import get_logger
        
        logger = get_logger(__name__)

        # First, get user ID by tg_id
        user_result = await self.session.execute(
            select(User.id).where(User.tg_id == tg_id)
        )
        user_id = user_result.scalar_one_or_none()
        
        if not user_id:
            logger.warning(
                "get_all_by_user_tg_id: user not found",
                tg_id=tg_id,
            )
            return []
        
        # Find all pairs where user is either uid_a or uid_b
        result = await self.session.execute(
            select(Pair).where(
                (Pair.uid_a == user_id) | (Pair.uid_b == user_id)
            )
        )
        pairs = list(result.scalars().all())
        
        logger.info(
            "get_all_by_user_tg_id: pairs lookup result",
            tg_id=tg_id,
            user_id=user_id,
            pairs_count=len(pairs),
        )
        
        return pairs

    async def get_by_user_ids(self, uid_a: int, uid_b: int) -> Optional[Pair]:
        """Get pair by user IDs (order-independent)."""
        # Ensure uid_a < uid_b for consistent lookup
        if uid_a > uid_b:
            uid_a, uid_b = uid_b, uid_a
        
        result = await self.session.execute(
            select(Pair).where(Pair.uid_a == uid_a, Pair.uid_b == uid_b)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        uid_a: int,
        uid_b: int,
        mode: PairMode | str = PairMode.SILENT,
        delivery_chat: str | DeliveryChat = DeliveryChat.BOT_DM,
    ) -> Pair:
        """Create new pair."""
        # Ensure uid_a < uid_b
        if uid_a > uid_b:
            uid_a, uid_b = uid_b, uid_a

        # Convert string to enum if needed
        if isinstance(mode, str):
            mode_enum = PairMode(mode)
            mode_value = mode_enum.value
        else:
            mode_value = mode.value
        
        # Convert delivery_chat to string if needed
        if isinstance(delivery_chat, DeliveryChat):
            delivery_chat_value = delivery_chat.value
        else:
            delivery_chat_value = delivery_chat

        pair = Pair(
            uid_a=uid_a,
            uid_b=uid_b,
            mode=mode_value,
            status=PairStatus.TRIAL.value,
            delivery_chat=delivery_chat_value,
        )
        self.session.add(pair)
        await self.session.flush()
        return pair

    async def update_status(self, pair_id: int, status: PairStatus) -> Optional[Pair]:
        """Update pair status."""
        stmt = update(Pair).where(Pair.id == pair_id).values(status=status.value).returning(Pair)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def update_payer_id(self, pair_id: int, payer_id: int) -> Optional[Pair]:
        """Update payer ID for this pair."""
        stmt = update(Pair).where(Pair.id == pair_id).values(payer_id=payer_id).returning(Pair)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def update_mode(self, pair_id: int, mode: PairMode | str) -> Optional[Pair]:
        """Update pair mode."""
        if isinstance(mode, str):
            mode_enum = PairMode(mode)
            mode_value = mode_enum.value
        else:
            mode_value = mode.value
        
        stmt = update(Pair).where(Pair.id == pair_id).values(mode=mode_value).returning(Pair)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def update_delivery_chat(
        self, pair_id: int, delivery_chat: str | DeliveryChat, private_chat_id: int | None = None
    ) -> Optional[Pair]:
        """Update pair delivery chat."""
        if isinstance(delivery_chat, DeliveryChat):
            delivery_chat_value = delivery_chat.value
        else:
            delivery_chat_value = delivery_chat
        
        values = {"delivery_chat": delivery_chat_value}
        if private_chat_id is not None:
            values["private_chat_id"] = private_chat_id
        
        stmt = update(Pair).where(Pair.id == pair_id).values(**values).returning(Pair)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def get_active_pairs(self) -> list[Pair]:
        """Get active pairs (trial or active status)."""
        result = await self.session.execute(
            select(Pair).where(Pair.status.in_([PairStatus.TRIAL.value, PairStatus.ACTIVE.value]))
        )
        return list(result.scalars().all())

    async def get_past_due_pairs(self) -> list[Pair]:
        """Get pairs with past due status."""
        result = await self.session.execute(
            select(Pair).where(Pair.status == PairStatus.PAST_DUE.value)
        )
        return list(result.scalars().all())

    async def update_nickname(
        self, pair_id: int, user_id: int, nickname: Optional[str]
    ) -> Optional[Pair]:
        """Update nickname for a user in pair.
        
        Args:
            pair_id: Pair ID
            user_id: User ID (determines which nickname to update: nickname_a if uid_a, nickname_b if uid_b)
            nickname: Nickname to set (None to clear)
            
        Returns:
            Updated Pair object or None if not found
        """
        from src.core.logger import get_logger
        logger = get_logger(__name__)
        
        pair = await self.get_by_id(pair_id)
        if not pair:
            logger.warning(
                "update_nickname: pair not found",
                pair_id=pair_id,
                user_id=user_id,
            )
            return None
        
        # Determine which nickname field to update
        # nickname_a: name that user A gave to partner B
        # nickname_b: name that user B gave to partner A
        if pair.uid_a == user_id:
            field = "nickname_a"
            old_value = pair.nickname_a
        elif pair.uid_b == user_id:
            field = "nickname_b"
            old_value = pair.nickname_b
        else:
            # User is not part of this pair
            logger.warning(
                "update_nickname: user is not part of pair",
                pair_id=pair_id,
                user_id=user_id,
                pair_uid_a=pair.uid_a,
                pair_uid_b=pair.uid_b,
            )
            return None
        
        logger.info(
            "update_nickname: updating nickname",
            pair_id=pair_id,
            user_id=user_id,
            field=field,
            old_value=old_value,
            new_value=nickname,
        )
        
        stmt = update(Pair).where(Pair.id == pair_id).values(**{field: nickname}).returning(Pair)
        result = await self.session.execute(stmt)
        await self.session.flush()
        
        updated_pair = result.scalar_one_or_none()
        if updated_pair:
            logger.info(
                "update_nickname: nickname updated successfully",
                pair_id=pair_id,
                user_id=user_id,
                field=field,
                new_value=nickname,
                verified_value=getattr(updated_pair, field),
            )
        
        return updated_pair
    
    async def set_nickname(
        self, pair_id: int, user_id: int, nickname: str
    ) -> Optional[Pair]:
        """Set nickname for a user in pair.
        
        Args:
            pair_id: Pair ID
            user_id: User ID (determines which nickname to update: nickname_a if uid_a, nickname_b if uid_b)
            nickname: Nickname to set
            
        Returns:
            Updated Pair object or None if not found
        """
        return await self.update_nickname(pair_id, user_id, nickname)
    
    async def clear_nickname(
        self, pair_id: int, user_id: int
    ) -> Optional[Pair]:
        """Clear nickname for a user in pair.
        
        Args:
            pair_id: Pair ID
            user_id: User ID (determines which nickname to clear: nickname_a if uid_a, nickname_b if uid_b)
            
        Returns:
            Updated Pair object or None if not found
        """
        return await self.update_nickname(pair_id, user_id, None)
    
    def get_partner_nickname(self, pair: Pair, user_id: int) -> Optional[str]:
        """Get partner's nickname for a user in pair.
        
        This returns the nickname that the PARTNER gave to the user.
        For example, if user A calls partner B "сестра", and partner B calls user A "брат",
        then for user A this returns "брат" (what partner B calls user A).
        
        Args:
            pair: Pair object
            user_id: User ID
            
        Returns:
            Partner's nickname for the user (what partner calls the user) or None if not set
        """
        if pair.uid_a == user_id:
            return pair.nickname_b
        elif pair.uid_b == user_id:
            return pair.nickname_a
        return None
    
    def get_my_nickname_for_partner(self, pair: Pair, user_id: int) -> Optional[str]:
        """Get the nickname that the user gave to their partner.
        
        This returns the nickname that the USER gave to their PARTNER.
        For example, if user A calls partner B "сестра", and partner B calls user A "брат",
        then for user A this returns "сестра" (what user A calls partner B).
        
        Args:
            pair: Pair object
            user_id: User ID
            
        Returns:
            User's nickname for the partner (what user calls the partner) or None if not set
        """
        if pair.uid_a == user_id:
            return pair.nickname_a
        elif pair.uid_b == user_id:
            return pair.nickname_b
        return None

