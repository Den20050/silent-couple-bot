"""Script to check Redis connection."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.core.logger import configure_logging, get_logger
from src.core.redis_client import create_redis_client, test_redis_connection

logger = get_logger(__name__)
configure_logging()


async def check_redis() -> None:
    """Check Redis connection."""
    print("🔍 Проверка подключения к Redis...")
    print(f"   URL: {settings.redis_url}")
    print(f"   DB: {settings.redis_db}")
    print()
    
    try:
        redis = await create_redis_client()
        
        if redis:
            print("✅ Подключение к Redis установлено")
            
            # Test ping
            if await test_redis_connection(redis):
                print("✅ Redis ping успешен")
                
                # Test set/get
                try:
                    await redis.set("test_key", "test_value", ex=10)
                    value = await redis.get("test_key")
                    if value == "test_value":
                        print("✅ Тест записи/чтения успешен")
                        await redis.delete("test_key")
                    else:
                        print("⚠️  Тест записи/чтения: значение не совпадает")
                except Exception as e:
                    print(f"⚠️  Ошибка при тесте записи/чтения: {e}")
                
                # Get Redis info
                try:
                    info = await redis.info("server")
                    redis_version = info.get("redis_version", "unknown")
                    print(f"✅ Версия Redis: {redis_version}")
                except Exception as e:
                    print(f"⚠️  Не удалось получить информацию о Redis: {e}")
                
            else:
                print("❌ Redis ping не прошел")
            
            await redis.aclose()
            print("\n✅ Redis работает корректно!")
            
        else:
            print("❌ Не удалось подключиться к Redis")
            print("\nВозможные причины:")
            print("   1. Redis не запущен")
            print("   2. Неверный URL в REDIS_URL")
            print("   3. Проблемы с сетью")
            print("\nРешение:")
            print("   - Запустите Redis: docker-compose up -d redis")
            print("   - Или проверьте настройки в .env файле")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Ошибка при проверке Redis: {e}")
        logger.error("Redis check failed", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(check_redis())

