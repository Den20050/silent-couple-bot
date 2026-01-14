# Руководство по перезапуску Worker

## Как перезапустить Worker

### Способ 1: Если Worker запущен через `run.py` (единая точка входа)

Если вы запускали бота командой `python run.py`, то worker запущен как отдельный процесс внутри этого скрипта.

**Перезапуск:**
1. Остановите процесс `run.py` (нажмите `Ctrl+C` в терминале)
2. Запустите заново:
   ```bash
   python run.py
   ```

### Способ 2: Если Worker запущен отдельно

Если worker запущен в отдельном терминале командой `python -m src.worker.main`:

**Перезапуск:**
1. Остановите процесс worker (нажмите `Ctrl+C` в терминале с worker)
2. Запустите заново:
   ```bash
   python -m src.worker.main
   ```

### Способ 3: Если Worker запущен в фоне (Windows PowerShell)

Если worker запущен в фоне и вы не знаете, где он запущен:

**Найти процесс:**
```powershell
# Найти процесс Python, который запускает worker
Get-Process python | Where-Object {$_.Path -like "*python*"}
```

**Остановить процесс:**
```powershell
# Найти процесс по имени модуля (если видно в командной строке)
Get-Process python | Where-Object {$_.CommandLine -like "*worker.main*"} | Stop-Process

# Или остановить все процессы Python (осторожно!)
Get-Process python | Stop-Process
```

**Запустить заново:**
```powershell
python -m src.worker.main
```

### Способ 4: Через Task Manager (Windows)

1. Откройте **Диспетчер задач** (Ctrl+Shift+Esc)
2. Найдите процесс `python.exe` или `pythonw.exe`
3. Посмотрите в колонке "Командная строка" - найдите процесс с `worker.main`
4. Остановите процесс (Правый клик → Завершить задачу)
5. Запустите заново в терминале:
   ```bash
   python -m src.worker.main
   ```

---

## Проверка, что Worker запущен

### Проверка через логи

Worker должен выводить логи о запуске. Ищите сообщения типа:
```
Worker started
Arq worker running
```

### Проверка через Redis

Worker использует Redis для хранения задач. Можно проверить подключение:
```bash
redis-cli
> KEYS arq:*
```

Если видите ключи с префиксом `arq:`, значит worker работает.

---

## Полный перезапуск (Bot + Worker)

Если нужно перезапустить и бота, и worker:

### Вариант 1: Единая точка входа
```bash
# Остановите текущий процесс (Ctrl+C)
# Запустите заново:
python run.py
```

### Вариант 2: Раздельный запуск
```bash
# Терминал 1: Остановите бота (Ctrl+C), затем:
python -m src.bot.main

# Терминал 2: Остановите worker (Ctrl+C), затем:
python -m src.worker.main
```

---

## После очистки БД

После очистки базы данных рекомендуется:

1. **Остановить worker** (если запущен)
2. **Очистить Redis** (опционально):
   ```bash
   redis-cli FLUSHALL
   ```
3. **Перезапустить worker**:
   ```bash
   python -m src.worker.main
   ```

Это очистит кеш и состояние worker, чтобы он начал работать с пустой БД.

---

## Решение проблем

### Worker не запускается

1. **Проверьте Redis:**
   ```bash
   redis-cli ping
   # Должно ответить: PONG
   ```

2. **Проверьте переменные окружения:**
   Убедитесь, что `.env` файл настроен правильно, особенно:
   - `REDIS_URL`
   - `DATABASE_URL`

3. **Проверьте логи:**
   Worker выведет ошибки при запуске, если что-то не так.

### Worker запускается, но не выполняет задачи

1. **Проверьте подключение к Redis:**
   Worker требует Redis для работы cron-задач.

2. **Проверьте подключение к БД:**
   Убедитесь, что SSH туннель создан (если БД на сервере).

3. **Проверьте логи worker:**
   Ищите ошибки в выводе worker.

---

## Автоматический перезапуск (для продакшена)

Для автоматического перезапуска worker можно использовать:

### Windows Task Scheduler
1. Создайте задачу в Планировщике задач
2. Настройте запуск при старте системы
3. Добавьте действие: `python -m src.worker.main`

### systemd (Linux)
Создайте файл `/etc/systemd/system/silent-couple-worker.service`:
```ini
[Unit]
Description=Silent Couple Bot Worker
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/Silent-Couple-Bot
ExecStart=/usr/bin/python3 -m src.worker.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Затем:
```bash
sudo systemctl enable silent-couple-worker
sudo systemctl start silent-couple-worker
```

