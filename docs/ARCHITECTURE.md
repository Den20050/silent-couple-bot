# Архитектура Silent Couple Bot 3.0

## Обзор

Проект следует принципам **SOLID** и **SoC (Separation of Concerns)** для обеспечения поддерживаемости, тестируемости и расширяемости кода.

## Запуск приложения

### Единая точка входа (`run.py`)

`run.py` — CLI wrapper для запуска bot + worker одновременно:

```python
# run.py запускает:
# 1. Bootstrap DI контейнера
# 2. Запускает worker в отдельном процессе
# 3. Запускает bot в основном процессе
python run.py
```

### Раздельный запуск (для отладки)

```bash
# Bot только
python -m src.entrypoints.bot

# Worker только
python -m src.entrypoints.worker
```

### Bootstrap (`src/core/bootstrap.py`)

`bootstrap()` инициализирует DI контейнер со всеми зависимостями:

```python
async def bootstrap() -> Container:
    """Bootstrap application and return DI container."""
    settings = Settings()
    container = Container(settings=settings)
    # Все зависимости лениво инициализируются при первом обращении
    return container
```

**Принцип**: Единая функция инициализации для всех entrypoints.

## Архитектурные слои

```
┌─────────────────────────────────────────────────────────────┐
│                    Entry Points                             │
│  (src/entrypoints/bot.py, src/entrypoints/worker.py)      │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                    Bot Layer                                │
│  (src/bot/handlers/, src/bot/middlewares/)                 │
│  - Handlers: тонкие контроллеры, только оркестрация        │
│  - Middlewares: DI, валидация, обработка ошибок            │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Application Services Layer                     │
│  (src/services/application/)                               │
│  - Координируют domain services + repositories + UI        │
│  - Примеры: SubscriptionApplicationService,                │
│             PaymentApplicationService, SettingsApplicationService│
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Domain Services Layer                          │
│  (src/domain/services/)                                     │
│  - Бизнес-логика, не зависящая от инфраструктуры           │
│  - Примеры: SubscriptionStatusService, PairOnboardingService│
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Infrastructure Layer                           │
│  (src/db/repositories/, src/services/telegram/,            │
│   src/services/payment/, src/services/messaging/)          │
│  - Репозитории: доступ к данным                            │
│  - Сервисы: Telegram API, платежи, UI генерация            │
└─────────────────────────────────────────────────────────────┘
```

## Структура проекта

### 1. Entry Points (`src/entrypoints/`)

Точки входа приложения:
- `bot.py` — запуск Telegram бота (использует `bootstrap()` для инициализации DI)
- `worker.py` — запуск фоновых задач (cron jobs через arq)

**Структура**:
```python
# src/entrypoints/bot.py
async def run_bot(container: Optional[Container] = None) -> None:
    """Run bot application."""
    if container is None:
        container = await bootstrap()
    
    bot, dp = await create_bot_app(container)
    await dp.start_polling(bot)

# src/entrypoints/worker.py
async def run_worker(container: Optional[Container] = None) -> None:
    """Run worker application."""
    if container is None:
        container = await bootstrap()
    
    worker = create_worker(container)
    worker.run()
```

**Принцип**: 
- Единая точка входа для каждого компонента
- Используют общий `bootstrap()` для инициализации DI контейнера
- `run.py` — CLI wrapper для запуска bot + worker одновременно

### 2. Bot Layer (`src/bot/`)

#### Handlers (`src/bot/handlers/`)

Каждый handler организован как пакет:

```
handlers/
├── {handler_name}/
│   ├── router.py              # Регистрация роутера
│   ├── handlers/               # Обработчики событий (тонкие контроллеры)
│   │   └── {handler_name}_handlers.py
│   ├── use_cases/              # Use cases (бизнес-операции)
│   │   └── {operation}.py
│   ├── validators.py           # Валидация (локальные валидаторы)
│   └── states.py               # FSM состояния (если нужны)
```

**Пример структуры** (`src/bot/handlers/menu/`):
```
menu/
├── router.py                   # Регистрация роутера
├── handlers/
│   └── menu_items.py          # Обработчики команд меню
├── use_cases/
│   ├── subscription.py       # Получение информации о подписке
│   └── share.py               # Поделиться ботом
└── validators.py              # Валидация для меню
```

**Принципы**:
- Handlers — тонкие контроллеры, только оркестрация
- Use cases — бизнес-операции, вызывают application services
- Validators — проверка входных данных, выбрасывают исключения

#### Middlewares (`src/bot/middlewares/`)

- `container.py` — внедрение DI контейнера
- `database.py` — внедрение сессии БД и application services
- `error_handler.py` — централизованная обработка ошибок
- `rate_limit.py` — ограничение частоты запросов
- `timezone.py` — обработка временных зон

**Принцип**: Middlewares обеспечивают cross-cutting concerns (DI, логирование, безопасность).

#### Validators (`src/bot/validators/`)

Общие валидаторы, используемые несколькими модулями:
- `user.py` — валидация пользователей
- `pair.py` — валидация пар
- `subscription.py` — валидация подписок

**Принцип**: Валидаторы выбрасывают исключения (`BotException`), а не возвращают булевы значения.

### 3. Application Services (`src/services/application/`)

Координируют работу domain services, repositories и UI services:

- `SubscriptionApplicationService` — управление подписками
- `PaymentApplicationService` — управление платежами
- `SettingsApplicationService` — управление настройками
- `PairApplicationService` — управление парами
- `MenuApplicationService` — операции меню (share, subscription info)
- `AdminApplicationService` — административные операции

**Структура**:
```python
class SubscriptionApplicationService:
    def __init__(
        self,
        session: AsyncSession,
        subscription_status_service: SubscriptionStatusService,
        menu_ui: MenuUIService,
    ):
        self._session = session
        self._subscription_status_service = subscription_status_service
        self._menu_ui = menu_ui
    
    async def show_subscription_info(self, tg_id: int):
        # 1. Валидация (выбрасывает исключения)
        user = await validate_user_exists(self._session, tg_id)
        
        # 2. Бизнес-логика через domain service
        status = await self._subscription_status_service.get_status(...)
        
        # 3. Генерация UI через UI service
        text, keyboard = self._menu_ui.build_subscription_message(status)
        
        return True, text, keyboard
```

**Принцип**: 
- Application services оркестрируют бизнес-операции, но не содержат бизнес-логику
- Используют валидаторы для проверки входных данных
- Координируют domain services + repositories + UI services

### 4. Domain Services (`src/domain/services/`)

Чистая бизнес-логика, не зависящая от инфраструктуры:

- `SubscriptionStatusService` — проверка статуса подписки, расчет дат окончания
- `PairOnboardingService` — создание и онбординг пар, логика приглашений

**Структура**:
```python
class SubscriptionStatusService:
    """Domain service for subscription status logic."""
    
    async def get_status(self, pair_id: int, today: date) -> SubscriptionStatus:
        """Calculate subscription status (pure business logic)."""
        # Чистая бизнес-логика без зависимостей от Telegram/UI
        subscription = await self._subs_repo.get_active_by_pair_id(pair_id)
        if not subscription:
            return SubscriptionStatus.EXPIRED
        
        if subscription.period_end < today:
            return SubscriptionStatus.EXPIRED
        
        return SubscriptionStatus.ACTIVE
```

**Принцип**: 
- Domain services не знают о Telegram API, платежах и UI
- Содержат только бизнес-логику и правила домена
- Могут использовать репозитории для доступа к данным

### 5. Infrastructure Layer

#### Repositories (`src/db/repositories/`)

Доступ к данным через репозитории:
- `users.py` — работа с пользователями
- `pairs.py` — работа с парами
- `subscriptions.py` — работа с подписками
- `daily_state.py` — работа с ежедневным состоянием

**Принцип**: Все запросы к БД через репозитории, не напрямую через SQLAlchemy.

#### UI Services (`src/services/messaging/ui/`)

Генерация сообщений и клавиатур:
- `menu_ui.py` — UI для меню
- `payment_ui.py` — UI для платежей
- `settings_ui.py` — UI для настроек

**Принцип**: Вся генерация UI централизована в UI services, использует шаблоны из `templates.py`.

#### Telegram Services (`src/services/telegram/`)

- `messenger.py` — отправка сообщений (реализует `MessengerProtocol`)
- `bot_provider.py` — провайдер бота (реализует `BotProviderProtocol`)

**Принцип**: Используются протоколы для DI и тестирования.

#### Payment Services (`src/services/payment/`)

- `robokassa_service.py` — интеграция с Robokassa (реализует `PaymentServiceProtocol`)

**Принцип**: Используются протоколы для DI и тестирования.

### 6. Worker Layer (`src/worker/`)

Фоновые задачи (cron jobs):

```
worker/
├── jobs.py                    # Обёртки для Arq cron jobs
├── tasks/                     # Реализация задач
│   ├── morning.py            # Утренние пожелания
│   ├── evening.py            # Вечерние пожелания
│   ├── reminders.py          # Напоминания
│   ├── past_due.py           # Просроченные подписки
│   ├── summary.py            # Еженедельные сводки
│   ├── nudges.py             # Напоминания о share
│   ├── cleanup.py            # Очистка старых данных
│   └── utils/                # Утилиты для задач
│       └── state_checks.py   # Проверки состояния
├── services/                  # Сервисы для worker
│   ├── lock_service.py       # Redis блокировки (использует протоколы)
│   ├── time_window_service.py # Проверка временных окон
│   ├── notification_builder.py # Построение уведомлений (использует MessengerProtocol)
│   └── pair_scheduler.py     # Планирование для пар (использует MessengerProtocol)
└── di/
    └── context.py            # WorkerContext для DI
```

**Структура task**:
```python
# src/worker/tasks/morning.py
async def morning_sender(
    ctx: dict[str, Any],
    worker_context: WorkerContext,
) -> None:
    """Send morning pictures within configured time window."""
    lock_service = worker_context.lock_service
    lock_acquired = await lock_service.acquire_task_lock("morning_sender")
    
    async with worker_context.session_factory() as session:
        scheduler = worker_context.create_pair_scheduler(session)
        # Используем сервисы из контекста
```

**Принцип**: 
- Worker tasks используют `WorkerContext` для DI, не глобальные переменные
- Все задачи используют сервисы (`LockService`, `NotificationBuilder`, `PairScheduler`)
- Сервисы используют протоколы (`MessengerProtocol`) для DI

## Dependency Injection (DI)

### Container (`src/core/di/container.py`)

Контейнер управляет всеми зависимостями:
- Использует протоколы (`BotProviderProtocol`, `MessengerProtocol`, `PaymentServiceProtocol`) для типизации
- Ленивая инициализация зависимостей при первом обращении
- Провайдеры в `src/core/di/providers/` создают экземпляры

**Структура**:
```python
@dataclass
class Container:
    settings: Settings
    _bot_provider: Optional[BotProviderProtocol] = field(default=None)
    _telegram_messenger: Optional[MessengerProtocol] = field(default=None)
    
    @property
    def bot_provider(self) -> BotProviderProtocol:
        if self._bot_provider is None:
            self._bot_provider = provide_bot_provider()
        return self._bot_provider
```

### Protocols (`src/core/protocols/`)

Протоколы для DI и тестирования:
- `BotProviderProtocol` — провайдер бота (`get_bot()`, `has_bot()`, `set_bot()`)
- `MessengerProtocol` — отправка сообщений (`send_message()`, `send_photo()`, `edit_message()`, `delete_message()`)
- `PaymentServiceProtocol` — создание платежей (`create_payment()`, `verify_payment()`)

**Использование в реализациях**:
```python
# Реализация использует протокол в конструкторе
class TelegramMessenger:
    def __init__(
        self,
        bot_provider: BotProviderProtocol,  # Протокол, не конкретный класс
        message_store: MessageStore,
    ):
        self._bot_provider = bot_provider
```

**Использование в сервисах**:
```python
# Application services используют протоколы
class WishSenderService:
    def __init__(
        self,
        session: AsyncSession,
        telegram_messenger: MessengerProtocol,  # Протокол
    ):
        self.telegram_messenger = telegram_messenger

# Worker services используют протоколы
class NotificationBuilder:
    def __init__(self, messenger: MessengerProtocol):
        self.messenger = messenger
```

**Тестирование с протоколами**:
```python
# Легко создать мок для тестирования
class MockMessenger:
    async def send_message(self, chat_id: int, text: str, ...) -> Message:
        return MockMessage()
    
    # Реализуем только нужные методы протокола

# Используем мок в тестах
messenger = MockMessenger()
service = WishSenderService(session, messenger)
```

**Принцип**: 
- Зависимости зависят от абстракций (протоколов), а не от конкретных реализаций (DIP)
- Протоколы обеспечивают structural subtyping (duck typing)
- Легко создавать моки для тестирования
- Можно заменить реализацию без изменения зависимостей
- Container использует протоколы для type hints, но хранит конкретные реализации

## Принципы проектирования

### SOLID

1. **Single Responsibility Principle (SRP)**
   - Каждый класс/модуль имеет одну ответственность
   - Handlers — только оркестрация
   - Use cases — одна бизнес-операция
   - Services — одна область ответственности

2. **Open/Closed Principle (OCP)**
   - Код открыт для расширения, закрыт для модификации
   - Новые handlers добавляются через роутеры, не изменяя существующий код

3. **Liskov Substitution Principle (LSP)**
   - Реализации протоколов взаимозаменяемы
   - Можно подменить `TelegramMessenger` на мок для тестов

4. **Interface Segregation Principle (ISP)**
   - Протоколы разделены по функциональности
   - `MessengerProtocol` — только отправка сообщений
   - `PaymentServiceProtocol` — только платежи

5. **Dependency Inversion Principle (DIP)**
   - Зависимости зависят от абстракций (протоколов)
   - Container использует протоколы для типизации
   - Тесты используют моки протоколов

### Separation of Concerns (SoC)

- **Handlers** — обработка событий Telegram
- **Application Services** — оркестрация бизнес-операций
- **Domain Services** — бизнес-логика
- **Repositories** — доступ к данным
- **UI Services** — генерация UI
- **Infrastructure** — внешние сервисы (Telegram, платежи)

## Обработка ошибок

### Иерархия исключений (`src/bot/exceptions.py`)

```python
BotException (базовый класс)
├── ValidationError
│   ├── UserNotFoundError
│   ├── PairNotFoundError
│   ├── PairAccessDeniedError
│   ├── SubscriptionNotFoundError
│   └── SubscriptionExpiredError
├── BusinessLogicError
└── PaymentError
```

**Принцип**: Валидаторы выбрасывают исключения, `ErrorHandlerMiddleware` обрабатывает их централизованно.

## Тестирование

### Unit Tests (`tests/unit/`)

- Тесты для application services с моками протоколов
- Используют `AsyncMock` для async функций
- Патчат валидаторы в месте их использования

**Пример**: `tests/unit/test_application_subscription.py`

### Протоколы для тестирования

Протоколы позволяют легко создавать моки:
- `MockMessenger` реализует `MessengerProtocol`
- `MockPaymentService` реализует `PaymentServiceProtocol`

## Чек-лист архитектурных принципов

При добавлении нового функционала проверьте:

- [ ] Handler — тонкий контроллер, только оркестрация
- [ ] Use case — одна бизнес-операция
- [ ] Application service — координирует domain services + repositories + UI
- [ ] Domain service — чистая бизнес-логика, не зависит от инфраструктуры
- [ ] Repository — только доступ к данным
- [ ] UI service — генерация UI централизована
- [ ] Валидатор — выбрасывает исключения, не возвращает булевы значения
- [ ] Протоколы — используются для DI и тестирования
- [ ] Ошибки — обрабатываются через `ErrorHandlerMiddleware`
- [ ] Тесты — написаны с использованием моков протоколов

