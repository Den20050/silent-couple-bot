"""Проверить текущие настройки времени из .env и загруженные константы.

Этот скрипт помогает убедиться, что настройки времени загружены правильно
после изменения .env файла.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import settings
from src.core.constants import (
    MORNING_WINDOW_START,
    MORNING_WINDOW_END,
    EVENING_WINDOW_START,
    EVENING_WINDOW_END,
)


def main():
    """Проверить настройки времени."""
    now_utc = datetime.utcnow()
    now_local = datetime.now()
    
    print("=" * 70)
    print("ПРОВЕРКА НАСТРОЕК ВРЕМЕНИ ОТПРАВКИ КАРТИНОК")
    print("=" * 70)
    print()
    print(f"Текущее UTC время:     {now_utc.strftime('%H:%M:%S')}")
    print(f"Текущее локальное время: {now_local.strftime('%H:%M:%S')}")
    print()
    print("─" * 70)
    print("НАСТРОЙКИ ИЗ .ENV ФАЙЛА:")
    print("─" * 70)
    print(f"  MORNING_START  = {settings.morning_start}")
    print(f"  MORNING_END    = {settings.morning_end}")
    print(f"  EVENING_START  = {settings.evening_start}")
    print(f"  EVENING_END    = {settings.evening_end}")
    print()
    print("─" * 70)
    print("ЗАГРУЖЕННЫЕ КОНСТАНТЫ (из src/core/constants.py):")
    print("─" * 70)
    print(f"  MORNING_WINDOW_START = {MORNING_WINDOW_START}")
    print(f"  MORNING_WINDOW_END   = {MORNING_WINDOW_END}")
    print(f"  EVENING_WINDOW_START = {EVENING_WINDOW_START}")
    print(f"  EVENING_WINDOW_END   = {EVENING_WINDOW_END}")
    print()
    
    # Проверка соответствия
    morning_start_match = (
        settings.morning_start_time.hour == MORNING_WINDOW_START.hour
        and settings.morning_start_time.minute == MORNING_WINDOW_START.minute
    )
    morning_end_match = (
        settings.morning_end_time.hour == MORNING_WINDOW_END.hour
        and settings.morning_end_time.minute == MORNING_WINDOW_END.minute
    )
    evening_start_match = (
        settings.evening_start_time.hour == EVENING_WINDOW_START.hour
        and settings.evening_start_time.minute == EVENING_WINDOW_START.minute
    )
    evening_end_match = (
        settings.evening_end_time.hour == EVENING_WINDOW_END.hour
        and settings.evening_end_time.minute == EVENING_WINDOW_END.minute
    )
    
    print("─" * 70)
    print("ПРОВЕРКА СООТВЕТСТВИЯ:")
    print("─" * 70)
    print(f"  Утреннее окно (начало): {'✅ Совпадает' if morning_start_match else '❌ НЕ СОВПАДАЕТ'}")
    print(f"  Утреннее окно (конец):  {'✅ Совпадает' if morning_end_match else '❌ НЕ СОВПАДАЕТ'}")
    print(f"  Вечернее окно (начало): {'✅ Совпадает' if evening_start_match else '❌ НЕ СОВПАДАЕТ'}")
    print(f"  Вечернее окно (конец):  {'✅ Совпадает' if evening_end_match else '❌ НЕ СОВПАДАЕТ'}")
    print()
    
    if not all([morning_start_match, morning_end_match, evening_start_match, evening_end_match]):
        print("⚠️  ВНИМАНИЕ: Настройки не совпадают!")
        print("   Это означает, что бот был запущен ДО изменения .env файла.")
        print("   Нужно перезапустить бота командой: python run.py")
        print()
    
    # Рекомендации для тестирования
    print("─" * 70)
    print("РЕКОМЕНДАЦИИ ДЛЯ ТЕСТИРОВАНИЯ:")
    print("─" * 70)
    
    # Вычислить время для теста (текущее + 2 минуты)
    from datetime import timedelta
    test_time = now_local.replace(second=0, microsecond=0) + timedelta(minutes=2)
    test_hour = test_time.hour
    test_minute = test_time.minute
    
    print(f"1. Установите в .env:")
    print(f"   MORNING_START={test_hour}:{test_minute:02d}")
    print(f"   MORNING_END={test_hour}:{test_minute+3:02d}")
    print()
    print(f"2. Остановите бота (Ctrl+C в терминале)")
    print()
    print(f"3. Запустите бота: python run.py")
    print()
    print(f"4. Подождите до {test_hour}:{test_minute:02d} (локальное время)")
    print()
    print(f"5. Проверьте логи - должно быть:")
    print(f"   - user_a_in_window: true")
    print(f"   - event: 'Users in morning window, proceeding'")
    print(f"   - event: 'Sending morning messages'")
    print()
    print("─" * 70)
    print("ВАЖНО:")
    print("─" * 70)
    print("• Время в .env указывается в ЛОКАЛЬНОМ времени пользователей")
    print("• Бот автоматически учитывает часовой пояс каждого пользователя (utc_offset)")
    print("• Если пользователи в разных часовых поясах, сообщение отправляется,")
    print("  когда хотя бы один из них находится в указанном временном окне")
    print("• Бот выбирает случайную минуту в окне для отправки (для естественности)")
    print("• Сообщение отправляется только один раз в день")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
