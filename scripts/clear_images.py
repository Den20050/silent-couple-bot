"""Script to clear old image file_ids from database.

This is useful when images were uploaded with a different bot token
and need to be re-uploaded with the new token.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.core.config import settings
from src.core.constants import PicType
from src.core.logger import configure_logging, get_logger
from src.db.models import PicsPool

logger = get_logger(__name__)

# Create engine
engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def clear_images(pic_type: PicType | None = None) -> None:
    """Clear image file_ids from database.
    
    Args:
        pic_type: If specified, clear only this type. Otherwise clear all.
    """
    configure_logging(settings.log_level)
    
    async with async_session_maker() as session:
        # Count before deletion
        query = select(func.count(PicsPool.file_id))
        if pic_type:
            query = query.where(PicsPool.type == pic_type.value)
        
        count_result = await session.execute(query)
        count_before = count_result.scalar() or 0
        
        if count_before == 0:
            type_str = pic_type.value if pic_type else "всех"
            print(f"\n✅ В базе данных нет {type_str} картинок для удаления.")
            await engine.dispose()
            return
        
        # Show what will be deleted
        if pic_type:
            print(f"\n⚠️  Будет удалено {count_before} {pic_type.value} картинок из базы данных.")
        else:
            # Count by type
            morning_count = await session.execute(
                select(func.count(PicsPool.file_id)).where(PicsPool.type == PicType.MORNING.value)
            )
            evening_count = await session.execute(
                select(func.count(PicsPool.file_id)).where(PicsPool.type == PicType.EVENING.value)
            )
            morning_count = morning_count.scalar() or 0
            evening_count = evening_count.scalar() or 0
            print(f"\n⚠️  Будет удалено из базы данных:")
            print(f"   Утренних: {morning_count}")
            print(f"   Вечерних: {evening_count}")
            print(f"   Всего: {count_before}")
        
        # Ask for confirmation
        print(f"\n❓ Продолжить удаление? (yes/no): ", end="")
        confirmation = input().strip().lower()
        
        if confirmation not in ("yes", "y", "да", "д"):
            print("❌ Удаление отменено.")
            await engine.dispose()
            return
        
        # Delete
        delete_query = delete(PicsPool)
        if pic_type:
            delete_query = delete_query.where(PicsPool.type == pic_type.value)
        
        await session.execute(delete_query)
        await session.commit()
        
        print(f"\n✅ Успешно удалено {count_before} записей из базы данных.")
        print(f"💡 Теперь можно запустить скрипт загрузки:")
        print(f"   python scripts/load_images.py <your_chat_id>")
    
    await engine.dispose()


async def main() -> None:
    """Main function."""
    if len(sys.argv) > 1:
        pic_type_str = sys.argv[1].lower()
        if pic_type_str == "morning":
            pic_type = PicType.MORNING
        elif pic_type_str == "evening":
            pic_type = PicType.EVENING
        else:
            print(f"❌ Неверный тип: {pic_type_str}. Используйте 'morning' или 'evening'.")
            print(f"   Или не указывайте тип для удаления всех картинок.")
            sys.exit(1)
    else:
        pic_type = None
    
    await clear_images(pic_type)


if __name__ == "__main__":
    asyncio.run(main())
