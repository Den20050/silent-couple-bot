"""Pictures pool repository."""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import PicType
from src.db.models import PicsPool


class PicsPoolRepository:
    """Repository for pictures pool."""

    def __init__(self, session: AsyncSession):
        """Initialize repository."""
        self.session = session

    async def get_random(self, pic_type: PicType, exclude_file_ids: Optional[set[str]] = None) -> Optional[PicsPool]:
        """Get random picture by type, excluding specified file IDs."""
        query = select(PicsPool).where(PicsPool.type == pic_type.value)
        if exclude_file_ids:
            query = query.where(~PicsPool.file_id.in_(exclude_file_ids))
        query = query.order_by(func.random()).limit(1)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def add(self, file_id: str, pic_type: PicType, tags: Optional[list[str]] = None) -> PicsPool:
        """Add picture to pool."""
        pic = PicsPool(file_id=file_id, type=pic_type.value, tags=tags or [])
        self.session.add(pic)
        await self.session.flush()
        return pic

    async def count(self, pic_type: Optional[PicType] = None) -> int:
        """Count pictures in pool."""
        query = select(func.count(PicsPool.file_id))
        if pic_type:
            query = query.where(PicsPool.type == pic_type.value)
        result = await self.session.execute(query)
        return result.scalar_one() or 0

    async def get_by_file_id(self, file_id: str) -> Optional[PicsPool]:
        """Get picture by file_id."""
        result = await self.session.execute(select(PicsPool).where(PicsPool.file_id == file_id))
        return result.scalar_one_or_none()

