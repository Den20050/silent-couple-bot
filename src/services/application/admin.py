"""Application service for admin operations."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.services.messaging.ui.admin_ui import AdminUIService

logger = get_logger(__name__)


class AdminApplicationService:
    """Application service for admin-related use cases.
    
    Coordinates domain services, repositories, and UI services
    to implement admin operations.
    """
    
    def __init__(
        self,
        session: AsyncSession,
        admin_ui: AdminUIService,
    ) -> None:
        """Initialize admin application service.
        
        Args:
            session: Database session
            admin_ui: UI service for admin-related messages
        """
        self._session = session
        self._admin_ui = admin_ui
    
    async def get_statistics(self) -> tuple[bool, str]:
        """Get admin statistics.
        
        Returns:
            Tuple of (success: bool, message_text: str)
        """
        try:
            from src.bot.handlers.admin.use_cases.stats import get_admin_statistics
            
            stats = await get_admin_statistics(self._session)
            message_text = self._admin_ui.format_statistics_message(stats)
            
            logger.info(
                "Admin statistics retrieved",
                **stats,
            )
            
            return True, message_text
        except Exception as e:
            logger.error("Error getting admin statistics", error=str(e), exc_info=True)
            raise
    
    async def reset_demo_for_user(
        self,
        tg_id: int,
    ) -> tuple[bool, str]:
        """Reset demo mode for user.
        
        Args:
            tg_id: Telegram user ID
            
        Returns:
            Tuple of (success: bool, message_text: str)
        """
        try:
            from src.bot.handlers.admin.use_cases.reset_demo import reset_demo_for_user
            
            success, message_text = await reset_demo_for_user(tg_id, self._session)
            
            return success, message_text
        except Exception as e:
            logger.error(
                "Error resetting demo",
                tg_id=tg_id,
                error=str(e),
                exc_info=True,
            )
            await self._session.rollback()
            raise

