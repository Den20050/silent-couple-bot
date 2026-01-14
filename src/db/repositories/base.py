"""Base repository."""

from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """Base repository with common methods."""

    def __init__(self, session: AsyncSession, model: type[ModelType]):
        """Initialize repository."""
        self.session = session
        self.model = model

