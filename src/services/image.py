"""Image selection service."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import PicType
from src.core.logger import get_logger
from src.db.repositories.daily_state import DailyStateRepository
from src.db.repositories.pics_pool import PicsPoolRepository

logger = get_logger(__name__)


class ImageService:
    """Service for image selection."""

    def __init__(self, session: AsyncSession):
        """Initialize service."""
        self.session = session
        self.pics_pool_repo = PicsPoolRepository(session)
        self.daily_state_repo = DailyStateRepository(session)

    async def get_random_image(
        self,
        pair_id: int,
        pic_type: PicType,
        exclude_last_days: int = 30,
    ) -> Optional[str]:
        """Get random image for pair, excluding used in last N days.
        
        Returns file_id or None if no images available.
        """
        # Get used file IDs
        used_file_ids = await self.daily_state_repo.get_used_file_ids(
            pair_id=pair_id,
            days=exclude_last_days,
        )
        
        # Get random image excluding used ones
        pic = await self.pics_pool_repo.get_random(
            pic_type=pic_type,
            exclude_file_ids=used_file_ids if used_file_ids else None,
        )
        
        if pic:
            logger.debug(
                "Selected image",
                pair_id=pair_id,
                pic_type=pic_type.value,
                file_id=pic.file_id,
            )
            return pic.file_id
        
        # If no images available, check if we should reset
        total_count = await self.pics_pool_repo.count(pic_type=pic_type)
        if total_count > 0 and len(used_file_ids) >= total_count:
            # All images were used, reset by returning None
            # Caller should handle this case (can select any image)
            logger.info(
                "All images used, resetting",
                pair_id=pair_id,
                pic_type=pic_type.value,
                total_count=total_count,
            )
            # Return random image without exclusions
            pic = await self.pics_pool_repo.get_random(pic_type=pic_type, exclude_file_ids=None)
            if pic:
                return pic.file_id
        
        logger.warning(
            "No images available",
            pair_id=pair_id,
            pic_type=pic_type.value,
        )
        return None

