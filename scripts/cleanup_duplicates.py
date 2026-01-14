"""Script to cleanup duplicate evening images from database."""

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


async def cleanup_duplicates() -> None:
    """Cleanup duplicate evening images from database."""
    configure_logging(settings.log_level)
    
    async with async_session_maker() as session:
        # Count current records
        total_evening = await session.execute(
            select(func.count(PicsPool.file_id)).where(PicsPool.type == PicType.EVENING.value)
        )
        evening_count = total_evening.scalar() or 0
        
        print(f"\n📊 Текущее состояние:")
        print(f"   Вечерних записей в БД: {evening_count}")
        print(f"   Ожидаемое количество: 645")
        print(f"   Лишних записей: {evening_count - 645}")
        
        if evening_count <= 645:
            print(f"\n✅ Дубликатов не обнаружено. Очистка не требуется.")
            await engine.dispose()
            return
        
        # Ask for confirmation
        print(f"\n⚠️  ВНИМАНИЕ: Будут удалены ВСЕ вечерние записи из БД!")
        print(f"   После этого нужно будет загрузить их заново командой:")
        print(f"   python scripts/load_images.py <your_chat_id>")
        print(f"\n   Продолжить? (yes/no): ", end="")
        
        confirmation = input().strip().lower()
        if confirmation != "yes":
            print("❌ Очистка отменена.")
            await engine.dispose()
            return
        
        # Delete all evening records
        print(f"\n🗑️  Удаление всех вечерних записей...")
        stmt = delete(PicsPool).where(PicsPool.type == PicType.EVENING.value)
        result = await session.execute(stmt)
        deleted_count = result.rowcount or 0
        await session.commit()
        
        print(f"✅ Удалено {deleted_count} вечерних записей")
        
        # Verify
        total_evening_after = await session.execute(
            select(func.count(PicsPool.file_id)).where(PicsPool.type == PicType.EVENING.value)
        )
        evening_count_after = total_evening_after.scalar() or 0
        
        print(f"\n📊 Результат:")
        print(f"   Вечерних записей в БД: {evening_count_after}")
        
        if evening_count_after == 0:
            print(f"\n✅ Все вечерние записи удалены.")
            print(f"\n💡 Следующий шаг:")
            print(f"   Запустите скрипт загрузки для повторной загрузки вечерних картинок:")
            print(f"   python scripts/load_images.py <your_chat_id>")
            print(f"\n   Скрипт автоматически пропустит уже загруженные утренние картинки")
            print(f"   и загрузит только вечерние (645 файлов).")
        else:
            print(f"⚠️  Осталось {evening_count_after} записей. Возможно, произошла ошибка.")
    
    await engine.dispose()


if __name__ == "__main__":
    import asyncio
    asyncio.run(cleanup_duplicates())

