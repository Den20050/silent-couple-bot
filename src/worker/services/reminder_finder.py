"""Service for finding reminders that need to be sent."""

from datetime import date, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import PairStatus
from src.core.logger import get_logger
from src.db.models import DailyState, Pair, User
from src.db.repositories.daily_state import DailyStateRepository
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository

logger = get_logger(__name__)


class ReminderCandidate:
    """Represents a reminder candidate with all necessary data."""
    
    def __init__(
        self,
        pair: Pair,
        daily_state: DailyState,
        initiator: User,
        recipient: User,
        target_day: date,
        pic_type: str,
    ):
        """Initialize reminder candidate.
        
        Args:
            pair: Pair object
            daily_state: DailyState object
            initiator: Initiator user object
            recipient: Recipient user object
            target_day: Target day for reminder
            pic_type: Picture type ("morning" or "evening")
        """
        self.pair = pair
        self.daily_state = daily_state
        self.initiator = initiator
        self.recipient = recipient
        self.target_day = target_day
        self.pic_type = pic_type


class ReminderFinder:
    """Service for finding reminders that need to be sent."""
    
    def __init__(
        self,
        session: AsyncSession,
        daily_state_repo: DailyStateRepository,
        pairs_repo: PairsRepository,
        users_repo: UsersRepository,
    ):
        """Initialize reminder finder.
        
        Args:
            session: Database session
            daily_state_repo: DailyStateRepository instance
            pairs_repo: PairsRepository instance
            users_repo: UsersRepository instance
        """
        self._session = session
        self._daily_state_repo = daily_state_repo
        self._pairs_repo = pairs_repo
        self._users_repo = users_repo
    
    async def find_unanswered_pictures(
        self,
        hours: int,
        pic_type: str,
    ) -> list[DailyState]:
        """Find unanswered pictures for given hours and type.
        
        Args:
            hours: Hours since picture was sent
            pic_type: Picture type ("morning" or "evening")
            
        Returns:
            List of DailyState objects for unanswered pictures
        """
        return await self._daily_state_repo.get_unanswered_pictures(hours, pic_type)
    
    async def build_reminder_candidate(
        self,
        state: DailyState,
        pic_type: str,
    ) -> Optional[ReminderCandidate]:
        """Build reminder candidate from daily state.
        
        Args:
            state: DailyState object
            pic_type: Picture type ("morning" or "evening")
            
        Returns:
            ReminderCandidate if valid, None otherwise
        """
        # Get pair
        pair = await self._pairs_repo.get_by_id(state.pair_id)
        if not pair:
            return None
        
        # Skip reminders for past_due pairs
        if pair.status == PairStatus.PAST_DUE.value:
            return None
        
        # Get current state to check conditions
        target_day = state.day
        current_state = await self._daily_state_repo.get_by_pair_and_day(
            state.pair_id,
            target_day,
        )
        
        if not current_state:
            return None
        
        # Get initiator ID
        if pic_type == "morning":
            initiator_id = state.morning_initiator
        else:
            initiator_id = state.evening_initiator
        
        if not initiator_id:
            return None
        
        # Get users
        user_a = await self._users_repo.get_by_id(pair.uid_a)
        user_b = await self._users_repo.get_by_id(pair.uid_b)
        if not user_a or not user_b:
            return None
        
        initiator = user_a if initiator_id == user_a.id else user_b
        recipient = user_b if initiator_id == user_a.id else user_a
        
        return ReminderCandidate(
            pair=pair,
            daily_state=current_state,
            initiator=initiator,
            recipient=recipient,
            target_day=target_day,
            pic_type=pic_type,
        )


class WarningFinder:
    """Service for finding warnings that need to be sent."""
    
    def __init__(
        self,
        session: AsyncSession,
        daily_state_repo: DailyStateRepository,
        pairs_repo: PairsRepository,
        users_repo: UsersRepository,
    ):
        """Initialize warning finder.
        
        Args:
            session: Database session
            daily_state_repo: DailyStateRepository instance
            pairs_repo: PairsRepository instance
            users_repo: UsersRepository instance
        """
        self._session = session
        self._daily_state_repo = daily_state_repo
        self._pairs_repo = pairs_repo
        self._users_repo = users_repo
    
    async def find_unanswered_pictures(
        self,
        hours: int,
        pic_type: str,
    ) -> list[DailyState]:
        """Find unanswered pictures for given hours and type.
        
        Args:
            hours: Hours since picture was sent
            pic_type: Picture type ("morning" or "evening")
            
        Returns:
            List of DailyState objects for unanswered pictures
        """
        return await self._daily_state_repo.get_unanswered_pictures(hours, pic_type)
    
    async def build_warning_candidate(
        self,
        state: DailyState,
        pic_type: str,
    ) -> Optional[ReminderCandidate]:
        """Build warning candidate from daily state.
        
        Args:
            state: DailyState object
            pic_type: Picture type ("morning" or "evening")
            
        Returns:
            ReminderCandidate if valid, None otherwise
        """
        # Get pair
        pair = await self._pairs_repo.get_by_id(state.pair_id)
        if not pair:
            return None
        
        # Skip warnings for past_due pairs
        if pair.status == PairStatus.PAST_DUE.value:
            return None
        
        # Get current state to check conditions
        target_day = state.day
        current_state = await self._daily_state_repo.get_by_pair_and_day(
            state.pair_id,
            target_day,
        )
        
        if not current_state:
            return None
        
        # Get initiator ID
        if pic_type == "morning":
            initiator_id = state.morning_initiator
        else:
            initiator_id = state.evening_initiator
        
        if not initiator_id:
            return None
        
        # Get users
        user_a = await self._users_repo.get_by_id(pair.uid_a)
        user_b = await self._users_repo.get_by_id(pair.uid_b)
        if not user_a or not user_b:
            return None
        
        initiator = user_a if initiator_id == user_a.id else user_b
        recipient = user_b if initiator_id == user_a.id else user_a
        
        return ReminderCandidate(
            pair=pair,
            daily_state=current_state,
            initiator=initiator,
            recipient=recipient,
            target_day=target_day,
            pic_type=pic_type,
        )

