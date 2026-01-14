# Contributing to Silent Couple Bot 3.0

## Быстрый старт

### 1. Настройка окружения

```bash
# Клонируйте репозиторий
git clone <repository-url>
cd Silent-Couple-Bot

# Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установите зависимости
pip install -r requirements.txt

# Настройте .env (скопируйте из env.example)
cp env.example .env
# Отредактируйте .env и заполните необходимые переменные
```

### 2. Запуск инфраструктуры

```bash
# Запустите PostgreSQL, Redis и MinIO локально
docker-compose up -d

# Примените миграции
alembic upgrade head
```

### 3. Запуск приложения

```bash
# Запуск бота и worker
python run.py
```

## Архитектура проекта

См. [ARCHITECTURE.md](ARCHITECTURE.md) для подробного описания архитектуры.

### Архитектурные слои

1. **Entry Points** (`src/entrypoints/`) — точки входа (`bot.py`, `worker.py`)
2. **Bot Layer** (`src/bot/`) — handlers, middlewares, validators
3. **Application Services** (`src/services/application/`) — оркестрация бизнес-операций
4. **Domain Services** (`src/domain/services/`) — чистая бизнес-логика
5. **Infrastructure** (`src/db/repositories/`, `src/services/`) — доступ к данным и внешним сервисам

### Ключевые принципы

- **SOLID** — Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion
- **SoC** — Separation of Concerns (разделение ответственности)
- **DIP** — Dependency Inversion Principle (зависимости от абстракций через протоколы)
- **DRY** — Don't Repeat Yourself (избегание дублирования)
- **Explicit DI** — Явное внедрение зависимостей через middleware, не глобальные переменные

## Как добавить новый handler

### Шаг 1: Создайте структуру пакета

```bash
mkdir -p src/bot/handlers/{handler_name}/{handlers,use_cases}
touch src/bot/handlers/{handler_name}/__init__.py
touch src/bot/handlers/{handler_name}/router.py
touch src/bot/handlers/{handler_name}/handlers/__init__.py
touch src/bot/handlers/{handler_name}/handlers/{handler_name}_handlers.py
touch src/bot/handlers/{handler_name}/use_cases/__init__.py
touch src/bot/handlers/{handler_name}/validators.py
```

**Пример**: Для handler `notifications`:

```
notifications/
├── __init__.py
├── router.py
├── handlers/
│   ├── __init__.py
│   └── notifications_handlers.py
├── use_cases/
│   ├── __init__.py
│   └── send_notification.py
└── validators.py
```

### Шаг 2: Создайте router

**`src/bot/handlers/{handler_name}/router.py`**:

```python
"""Notifications router registration."""

from aiogram import Router

from src.bot.handlers.notifications.handlers import notifications_handlers

router = Router(name="notifications")

# Register sub-routers
router.include_router(notifications_handlers.router)
```

### Шаг 3: Создайте handlers

**`src/bot/handlers/{handler_name}/handlers/{handler_name}_handlers.py`**:

```python
"""Notification handlers."""

from aiogram import Router, F
from aiogram.types import Message

from src.services.application.notifications import NotificationApplicationService

router = Router(name="notifications_handlers")


@router.message(F.text == "Уведомления")
async def handle_notifications(
    message: Message,
    notification_application_service: NotificationApplicationService,
) -> None:
    """Handle notifications command."""
    success, text, keyboard = await notification_application_service.show_notifications(
        tg_id=message.from_user.id,
    )
    
    if success:
        await message.answer(text, reply_markup=keyboard)
```

**Принципы**:
- Handler — тонкий контроллер, только оркестрация
- Использует application service для бизнес-логики
- Получает зависимости через DI (middleware)

### Шаг 4: Создайте use cases (если нужны)

**`src/bot/handlers/{handler_name}/use_cases/send_notification.py`**:

```python
"""Send notification use case."""

from src.services.application.notifications import NotificationApplicationService


async def send_notification_use_case(
    tg_id: int,
    notification_application_service: NotificationApplicationService,
) -> tuple[bool, str]:
    """Send notification use case."""
    return await notification_application_service.send_notification(tg_id=tg_id)
```

**Принципы**:
- Use case — одна бизнес-операция
- Вызывает application service
- Может быть вызван из handler или другого use case

### Шаг 5: Создайте validators (если нужны)

**`src/bot/handlers/{handler_name}/validators.py`**:

```python
"""Validators for notifications."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.validators.user import validate_user_exists
from src.bot.exceptions import ValidationError


async def validate_notification_access(
    session: AsyncSession,
    tg_id: int,
) -> None:
    """Validate user has access to notifications.
    
    Raises:
        UserNotFoundError: If user is not found
        ValidationError: If user doesn't have access
    """
    user = await validate_user_exists(session, tg_id)
    
    # Дополнительная валидация
    if not user.has_notifications_enabled:
        raise ValidationError(
            message_key="NOTIFICATIONS_DISABLED",
            message="Уведомления отключены",
        )
```

**Принципы**:
- Валидатор выбрасывает исключения, не возвращает булевы значения
- Использует общие валидаторы из `src/bot/validators/`
- Может быть использован в handler или use case

### Шаг 6: Зарегистрируйте router

**`src/bot/bootstrap/router_registry.py`**:

```python
from src.bot.handlers import (
    # ... existing imports ...
    notifications,  # Добавьте импорт
)

def register_routers(dp: Dispatcher) -> None:
    """Register all routers in dispatcher."""
    # ... existing registrations ...
    
    # Добавьте регистрацию нового router
    dp.include_router(notifications.router)
    
    logger.info("Routers registered", router_count=10)  # Обновите счетчик
```

**Важно**: Порядок регистрации роутеров имеет значение:
1. Commands — регистрируются первыми
2. FSM state handlers — регистрируются перед общими обработчиками
3. General message handlers — регистрируются последними

### Шаг 7: Создайте application service (если нужен)

**`src/services/application/notifications.py`**:

```python
"""Notification application service."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.services.notification import NotificationDomainService
from src.services.messaging.ui.notifications_ui import NotificationsUIService


class NotificationApplicationService:
    """Application service for notifications."""
    
    def __init__(
        self,
        session: AsyncSession,
        notification_domain_service: NotificationDomainService,
        notifications_ui: NotificationsUIService,
    ) -> None:
        """Initialize service."""
        self._session = session
        self._notification_domain_service = notification_domain_service
        self._notifications_ui = notifications_ui
    
    async def show_notifications(
        self,
        tg_id: int,
    ) -> tuple[bool, str, dict | None]:
        """Show notifications."""
        # Валидация (выбрасывает исключения)
        from src.bot.validators.user import validate_user_exists
        user = await validate_user_exists(self._session, tg_id)
        
        # Бизнес-логика через domain service
        notifications = await self._notification_domain_service.get_notifications(user)
        
        # Генерация UI через UI service
        text = self._notifications_ui.build_notifications_message(notifications)
        keyboard = self._notifications_ui.build_notifications_keyboard()
        
        return True, text, keyboard
```

**Принципы**:
- Application service координирует domain services + repositories + UI services
- Не содержит бизнес-логику (она в domain services)
- Использует валидаторы для проверки входных данных
- Получает зависимости через DI (внедряются через middleware)

### Шаг 8: Зарегистрируйте application service в DI

**`src/core/di/providers/application.py`**:

```python
def provide_notification_application_service(
    session: AsyncSession,
    notification_domain_service: NotificationDomainService,
    notifications_ui: NotificationsUIService,
) -> NotificationApplicationService:
    """Provide NotificationApplicationService."""
    return NotificationApplicationService(
        session=session,
        notification_domain_service=notification_domain_service,
        notifications_ui=notifications_ui,
    )
```

**`src/bot/middlewares/database.py`**:

```python
# Добавьте в DatabaseMiddleware.__call__
from src.core.di.providers.application import (
    # ... existing imports ...
    provide_notification_application_service,
)

# В методе __call__ добавьте:
data["notification_application_service"] = provide_notification_application_service(
    session=session,
    notification_domain_service=notification_domain_service,
    notifications_ui=notifications_ui,
)
```

### Чек-лист добавления handler

- [ ] Создана структура пакета `handlers/{handler_name}/`
- [ ] Создан `router.py` с регистрацией под-роутеров
- [ ] Созданы handlers в `handlers/{handler_name}_handlers.py`
- [ ] Handlers — тонкие контроллеры, используют application services
- [ ] Handlers получают зависимости через DI (middleware), не импортируют напрямую
- [ ] Созданы use cases (если нужны) в `use_cases/`
- [ ] Созданы validators (если нужны) в `validators.py`
- [ ] Валидаторы выбрасывают исключения (`BotException`), не возвращают булевы значения
- [ ] Router зарегистрирован в `router_registry.py` в правильном порядке
- [ ] Создан application service (если нужен) в `services/application/`
- [ ] Application service использует протоколы для зависимостей (`MessengerProtocol`, `BotProviderProtocol`)
- [ ] Application service зарегистрирован в DI (`database.py`)
- [ ] UI логика вынесена в UI service (`services/messaging/ui/`)
- [ ] Написаны тесты для application service с моками протоколов

## Где хранить UI компоненты

### UI Services (`src/services/messaging/ui/`)

Все генерация сообщений и клавиатур должна быть в UI services:

**`src/services/messaging/ui/{feature}_ui.py`**:

```python
"""UI service for notifications."""

from src.services.messaging.templates import ButtonTemplates, KeyboardTemplates, MessageTemplates


class NotificationsUIService:
    """UI service for notifications."""
    
    def build_notifications_message(self, notifications: list) -> str:
        """Build notifications message."""
        if not notifications:
            return MessageTemplates.NO_NOTIFICATIONS
        
        text = MessageTemplates.NOTIFICATIONS_HEADER + "\n\n"
        for notification in notifications:
            text += f"• {notification.text}\n"
        
        return text
    
    def build_notifications_keyboard(self) -> dict:
        """Build notifications keyboard."""
        return KeyboardTemplates.back_only()
```

**Принципы**:
- UI service использует шаблоны из `templates.py`
- Не содержит бизнес-логику
- Возвращает готовые строки и словари для Telegram API

### Templates (`src/services/messaging/templates.py`)

Все тексты и структуры клавиатур хранятся в `templates.py`:

```python
class MessageTemplates:
    """Message templates."""
    NO_NOTIFICATIONS = "У вас нет уведомлений"
    NOTIFICATIONS_HEADER = "📬 Уведомления"

class ButtonTemplates:
    """Button templates."""
    @staticmethod
    def notification_button(text: str, callback_data: str) -> dict:
        """Create notification button."""
        return {"text": text, "callback_data": callback_data}

class KeyboardTemplates:
    """Keyboard templates."""
    @staticmethod
    def back_only() -> dict:
        """Create back-only keyboard."""
        return {
            "inline_keyboard": [
                [ButtonTemplates.back_button()]
            ]
        }
```

**Принципы**:
- Все тексты централизованы в `templates.py`
- Используются статические методы для создания кнопок и клавиатур
- Не используются hardcoded строки в handlers или use cases

## Как добавить новый worker task

### Шаг 1: Создайте task

**`src/worker/tasks/{task_name}.py`**:

```python
"""Task for {task_name}."""

from src.worker.di.context import WorkerContext


async def {task_name}_task(worker_context: WorkerContext) -> None:
    """{Task description}."""
    async with worker_context.session_factory() as session:
        # Используйте worker_context для доступа к сервисам
        # worker_context.lock_service
        # worker_context.notification_builder
        # worker_context.messenger
        # worker_context.time_window_service
        
        # Ваша логика здесь
        pass
```

### Шаг 2: Создайте wrapper в jobs.py

**`src/worker/jobs.py`**:

```python
from src.worker.tasks.{task_name} import {task_name}_task
from src.worker.di.context import get_worker_context

async def {task_name}_job(ctx: dict) -> None:
    """Wrapper for {task_name} task."""
    container = ctx.get("container")
    if not container:
        raise RuntimeError("Container not found in context")
    
    worker_context = await get_worker_context(container)
    await {task_name}_task(worker_context)
```

### Шаг 3: Зарегистрируйте cron job

**`src/worker/app.py`**:

```python
from arq import cron

functions = [
    # ... existing functions ...
    {task_name}_job,
]

cron_jobs = [
    # ... existing cron jobs ...
    cron(
        {task_name}_job,
        hour={hour},
        minute={minute},
    ),
]
```

### Чек-лист добавления worker task

- [ ] Создан task в `worker/tasks/{task_name}.py`
- [ ] Task использует `WorkerContext` для DI (не глобальные переменные)
- [ ] Task использует сервисы из `worker_context` (`lock_service`, `notification_builder`, `messenger`, `time_window_service`)
- [ ] Сервисы используют протоколы (`MessengerProtocol`) для зависимостей
- [ ] Создан wrapper в `jobs.py` с правильной сигнатурой
- [ ] Cron job зарегистрирован в `WorkerSettings.cron_jobs` в `jobs.py`
- [ ] Task использует `LockService` для блокировок, не прямые вызовы Redis
- [ ] Task использует `NotificationBuilder` для построения сообщений

## Тестирование

### Unit Tests

**`tests/unit/test_application_{service}.py`**:

```python
"""Unit tests for {Service}ApplicationService."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.application.{service} import {Service}ApplicationService


@pytest.fixture
def mock_session():
    """Create mock database session."""
    return AsyncMock()


@pytest.fixture
def {service}_service(mock_session, ...):
    """Create {Service}ApplicationService with mocked dependencies."""
    return {Service}ApplicationService(
        session=mock_session,
        # ... other dependencies ...
    )


@pytest.mark.asyncio
async def test_{operation}_success({service}_service, ...):
    """Test successful {operation}."""
    # Setup mocks
    # Execute
    # Assert
    pass
```

**Принципы**:
- Используйте моки протоколов для зависимостей
- Патчите валидаторы в месте их использования
- Используйте `AsyncMock` для async функций

### Запуск тестов

```bash
# Все тесты
pytest

# Конкретный файл
pytest tests/unit/test_application_subscription.py

# С покрытием
pytest --cov=src --cov-report=html
```

## Code Review Checklist

Перед отправкой PR проверьте:

### Архитектура

- [ ] Handler — тонкий контроллер, только оркестрация
- [ ] Use case — одна бизнес-операция
- [ ] Application service — координирует domain services + repositories + UI
- [ ] Domain service — чистая бизнес-логика, не зависит от инфраструктуры
- [ ] Repository — только доступ к данным
- [ ] UI service — генерация UI централизована
- [ ] Валидатор — выбрасывает исключения, не возвращает булевы значения

### DI и протоколы

- [ ] Используются протоколы для зависимостей (`MessengerProtocol`, `PaymentServiceProtocol`)
- [ ] Зависимости внедряются через middleware, не глобальные переменные
- [ ] Container использует протоколы для типизации

### Обработка ошибок

- [ ] Валидаторы выбрасывают `BotException` подклассы
- [ ] Ошибки обрабатываются через `ErrorHandlerMiddleware`
- [ ] Нет bare `except:` блоков

### UI и шаблоны

- [ ] Все тексты в `templates.py`, не hardcoded
- [ ] Клавиатуры генерируются через UI services
- [ ] Используются `ButtonTemplates` и `KeyboardTemplates`

### Тестирование

- [ ] Написаны unit тесты для application services
- [ ] Используются моки протоколов
- [ ] Тесты изолированы, не зависят от внешних сервисов

### Код

- [ ] Код отформатирован (`black`, `isort`)
- [ ] Нет неиспользуемых импортов
- [ ] Типы указаны для функций и методов
- [ ] Docstrings для публичных функций

## Форматирование кода

```bash
# Форматирование с black
black src/ tests/

# Сортировка импортов
isort src/ tests/

# Проверка типов
mypy src/
```

## Правила коммитов

Используйте [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — новая функциональность
- `fix:` — исправление бага
- `refactor:` — рефакторинг (без изменения функциональности)
- `docs:` — документация
- `test:` — добавление/изменение тестов
- `chore:` — обновление зависимостей, конфигурации

**Примеры**:
```
feat: add notifications handler
fix: handle subscription expiration correctly
refactor: extract UI generation to services
docs: update architecture documentation
test: add unit tests for payment service
```

## Дополнительные ресурсы

- [ARCHITECTURE.md](ARCHITECTURE.md) — подробное описание архитектуры
- [README.md](README.md) — общая информация о проекте
- [BOT_ALGORITHM.md](BOT_ALGORITHM.md) — описание алгоритма работы бота
