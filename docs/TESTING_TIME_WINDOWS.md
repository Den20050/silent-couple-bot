# Алгоритм тестирования отправки картинок с изменением времени

## Проблема

После изменения времени в `.env` и перезапуска бота, картинки могут не отправляться. Это происходит потому что:
1. Константы `MORNING_WINDOW_START` и `MORNING_WINDOW_END` загружаются **один раз** при импорте модуля `src/core/constants.py`
2. Если изменить `.env` **после** запуска бота, новые значения не загрузятся
3. Нужно **полностью перезапустить процесс** бота (`python run.py`)

## Подробный алгоритм тестирования

### Шаг 1: Подготовка

1. **Узнайте текущее время (локальное для пользователей):**
   ```powershell
   # В PowerShell можно узнать текущее время
   Get-Date
   ```

2. **Определите время для тестирования:**
   - Выберите время, которое наступит через **2-3 минуты** от текущего
   - Например, если сейчас `21:07`, установите `21:10` или `21:15`
   - **Важно:** Учитывайте часовой пояс пользователей (`utc_offset`)

### Шаг 2: Изменение времени в .env

1. **Откройте файл `.env`** (не `env.example`!)

2. **Измените время отправки:**
   ```env
   # Пример: установить утреннее окно на текущее время + 2 минуты
   MORNING_START=21:10    # Начало окна (локальное время пользователя)
   MORNING_END=21:15      # Конец окна (локальное время пользователя)
   
   # Для вечерних сообщений
   EVENING_START=21:20
   EVENING_END=21:25
   ```

3. **Сохраните файл `.env`**

### Шаг 3: Остановка бота

1. **Найдите процесс бота:**
   ```powershell
   # В PowerShell найдите процесс Python
   Get-Process python | Where-Object {$_.Path -like "*Silent-Couple-Bot*"}
   ```

2. **Остановите процесс:**
   - Нажмите `Ctrl+C` в терминале, где запущен бот
   - ИЛИ используйте Task Manager для завершения процесса
   - **Важно:** Убедитесь, что процесс полностью остановлен

### Шаг 4: Проверка остановки

1. **Проверьте, что процесс остановлен:**
   ```powershell
   Get-Process python -ErrorAction SilentlyContinue
   ```
   Если процесс не найден - хорошо, бот остановлен.

2. **Проверьте, что порты свободны** (если используете webhook):
   ```powershell
   netstat -ano | findstr :8443
   ```

### Шаг 5: Запуск бота

1. **Перейдите в директорию проекта:**
   ```powershell
   cd C:\Silent-Couple-Bot
   ```

2. **Запустите бота:**
   ```powershell
   python run.py
   ```

3. **Проверьте логи при запуске:**
   - Должны появиться сообщения о подключении к Redis и БД
   - Должно быть сообщение "Bot connected"
   - Должно быть сообщение "Starting worker for ... functions"

### Шаг 6: Проверка загрузки настроек

1. **Проверьте логи в течение первой минуты после запуска:**
   - Найдите строку с `"Morning time check"` или `"Evening time check"`
   - Проверьте значения:
     - `config_morning_start` - должно быть новое значение из `.env`
     - `window_start` - должно соответствовать новому времени
     - `window_start_hour` и `window_start_minute` - должны быть правильными

2. **Пример правильного лога:**
   ```json
   {
     "config_morning_start": "21:10",
     "config_morning_start_time": "21:10:00",
     "window_start": "21:10:00",
     "window_start_hour": 21,
     "window_start_minute": 10,
     "user_a_local_time": "21:09:00",
     "user_a_in_window": false
   }
   ```

### Шаг 7: Ожидание времени окна

1. **Дождитесь наступления времени окна:**
   - Если установили `MORNING_START=21:10`, дождитесь 21:10
   - Бот проверяет время **каждую минуту** в начале минуты (секунды :00)

2. **Проверьте логи в момент наступления времени:**
   - Найдите строку с `"Morning time check"` в момент времени 21:10:00
   - Проверьте:
     - `user_a_local_time` должно быть `21:10:00` или позже
     - `user_a_in_window` должно быть `true`
     - Должно появиться сообщение `"Users in morning window, proceeding"`

### Шаг 8: Проверка отправки

1. **После наступления времени окна проверьте:**
   - Должно появиться сообщение `"Sending morning messages"`
   - Должно появиться сообщение `"Morning message sent"`
   - Пользователи должны получить сообщения в Telegram

2. **Если сообщения не отправлены:**
   - Проверьте логи на наличие ошибок
   - Проверьте, что `daily_state.morning_initiator` не установлен (если уже отправляли сегодня)
   - Проверьте, что пара активна (`pair.status == "trial"` или `"active"`)

## Быстрое тестирование (рекомендуемый подход)

### Вариант 1: Использовать скрипт для проверки настроек

1. **Запустите скрипт проверки:**
   ```powershell
   python scripts/check_time_settings.py
   ```
   
   Скрипт покажет:
   - Текущее время
   - Настройки из .env
   - Загруженные константы
   - Рекомендуемое время для теста

2. **Следуйте рекомендациям скрипта**

### Вариант 2: Установить время на текущее + 1-2 минуты вручную

1. **Узнайте текущее время:**
   ```powershell
   $now = Get-Date
   $hour = $now.Hour
   $minute = $now.Minute
   Write-Host "Текущее время: $hour:$minute"
   ```

2. **Вычислите время для теста:**
   - Если сейчас `21:07`, установите `MORNING_START=21:09` (через 2 минуты)
   - Установите `MORNING_END=21:12` (окно 3 минуты)

3. **Остановите и перезапустите бота**

4. **Подождите 2 минуты и проверьте логи**

### Вариант 2: Использовать скрипт для автоматического тестирования

Создайте скрипт `scripts/test_time_windows.py`:

```python
"""Скрипт для тестирования временных окон отправки картинок."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sys

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


def print_time_info():
    """Вывести информацию о текущих настройках времени."""
    now_utc = datetime.utcnow()
    now_local = datetime.now()
    
    print("=" * 60)
    print("ТЕКУЩИЕ НАСТРОЙКИ ВРЕМЕНИ")
    print("=" * 60)
    print(f"Текущее UTC время: {now_utc.strftime('%H:%M:%S')}")
    print(f"Текущее локальное время: {now_local.strftime('%H:%M:%S')}")
    print()
    print("Из .env файла:")
    print(f"  MORNING_START={settings.morning_start}")
    print(f"  MORNING_END={settings.morning_end}")
    print(f"  EVENING_START={settings.evening_start}")
    print(f"  EVENING_END={settings.evening_end}")
    print()
    print("Загруженные константы:")
    print(f"  MORNING_WINDOW_START={MORNING_WINDOW_START}")
    print(f"  MORNING_WINDOW_END={MORNING_WINDOW_END}")
    print(f"  EVENING_WINDOW_START={EVENING_WINDOW_START}")
    print(f"  EVENING_WINDOW_END={EVENING_WINDOW_END}")
    print()
    print("Рекомендации для тестирования:")
    
    # Вычислить время для теста (текущее + 2 минуты)
    test_time = now_local + timedelta(minutes=2)
    test_hour = test_time.hour
    test_minute = test_time.minute
    
    print(f"  Установите MORNING_START={test_hour}:{test_minute:02d}")
    print(f"  Установите MORNING_END={test_hour}:{test_minute+3:02d}")
    print(f"  Перезапустите бота и подождите до {test_hour}:{test_minute:02d}")
    print("=" * 60)


if __name__ == "__main__":
    print_time_info()
```

## Частые ошибки

### Ошибка 1: Бот не перезапущен
**Симптомы:** В логах видно старое значение `config_morning_start`
**Решение:** Полностью остановите процесс (`Ctrl+C` или Task Manager) и запустите заново

### Ошибка 2: Неправильный формат времени
**Симптомы:** Ошибка при запуске бота или неправильное время в логах
**Решение:** Используйте формат `HH:MM` (например, `21:10`) или `HH` (например, `21`)

### Ошибка 3: Время уже прошло
**Симптомы:** В логах `user_a_in_window: false`, хотя время окна наступило
**Решение:** Установите время на будущее (текущее время + 2-3 минуты)

### Ошибка 4: Картинка уже отправлена сегодня
**Симптомы:** В логах `"Morning message already sent today, skipping"` или `morning_initiator` не `None`
**Решение:** 
- **Используйте скрипт для сброса (рекомендуется):**
  ```powershell
  python scripts/reset_daily_state.py <pair_id> both
  ```
  Например: `python scripts/reset_daily_state.py 4 both`
- **ИЛИ очистите вручную через SQL:**
  ```sql
  UPDATE daily_state 
  SET morning_initiator = NULL, morning_sent_at = NULL, morning_file_id = NULL
  WHERE pair_id = <pair_id> AND day = CURRENT_DATE;
  ```
- **ИЛИ дождитесь следующего дня**

## Проверка в логах

После перезапуска бота проверьте логи на наличие:

1. **Правильные значения времени:**
   ```json
   {
     "config_morning_start": "21:10",
     "window_start": "21:10:00",
     "window_start_hour": 21,
     "window_start_minute": 10
   }
   ```

2. **Попадание в окно:**
   ```json
   {
     "user_a_local_time": "21:10:00",
     "user_a_in_window": true,
     "event": "Users in morning window, proceeding"
   }
   ```

3. **Отправка сообщений:**
   ```json
   {
     "event": "Sending morning messages",
     "event": "Morning message sent"
   }
   ```

## Пример тестирования

1. **Текущее время:** 21:07
2. **Проверить, не отправлялись ли картинки сегодня:**
   - Запустите `python scripts/check_time_settings.py`
   - ИЛИ проверьте логи на наличие `"Morning message already sent today"`
3. **Если картинки уже отправлялись сегодня:**
   - Запустите скрипт сброса: `python scripts/reset_daily_state.py <pair_id> both`
   - ИЛИ очистите `daily_state` в БД (см. Ошибка 4 выше)
   - ИЛИ дождитесь следующего дня
4. **Установить в .env:**
   ```env
   MORNING_START=21:10
   MORNING_END=21:13
   ```
5. **Остановить бота:** `Ctrl+C`
6. **Запустить бота:** `python run.py`
7. **Проверить логи в 21:10:00** - должно быть:
   - `user_a_in_window: true`
   - `"Users in morning window, proceeding"`
   - НЕ должно быть `"Morning message already sent today"`
8. **Проверить Telegram** - должны прийти сообщения

## Важные замечания

### Почему картинки могут не отправляться даже при правильном времени?

1. **Картинка уже отправлена сегодня:**
   - Бот отправляет картинку **только один раз в день**
   - Проверьте логи на наличие `"Morning message already sent today"`
   - Решение: очистите `daily_state` или дождитесь следующего дня

2. **Случайная задержка внутри окна:**
   - Бот выбирает случайную минуту внутри окна для естественности
   - Если окно `21:20-21:30`, сообщение может быть отправлено в любую минуту от 21:20 до 21:29
   - Это нормальное поведение!

3. **Проверка происходит в начале каждой минуты:**
   - Бот проверяет время в секунды :00 каждой минуты
   - Если установили окно `21:20-21:30`, проверка будет в 21:20:00, 21:21:00, и т.д.
