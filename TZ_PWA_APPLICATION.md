# Техническое задание: PWA приложение "Тихие объятия"

## 1. Общее описание проекта

### 1.1 Цель проекта
Создание Progressive Web Application (PWA), дублирующего функционал Telegram-бота "Тихие объятия" для обеспечения доступности сервиса в условиях возможных блокировок Telegram в РФ.

### 1.2 Концепция
- **Единая база данных** с Telegram-ботом
- **Кросс-платформенная работа пар**: один пользователь может быть в Telegram, другой в PWA
- **Идентичный функционал** утренних/вечерних пожеланий
- **Общая система подписок** и платежей

### 1.3 Целевая аудитория
- Существующие пользователи Telegram-бота с проблемами доступа
- Новые пользователи, предпочитающие веб-интерфейс
- Пары, где один пользователь использует Telegram, другой — PWA

---

## 2. Функциональные требования

### 2.1 Регистрация и авторизация

#### 2.1.1 Способы регистрации
1. **По номеру телефона**
   - Ввод номера в международном формате (+7...)
   - Отправка SMS с 6-значным OTP кодом
   - Верификация кода
   - Создание аккаунта

2. **OAuth авторизация**
   - Google (OAuth 2.0)
   - Yandex (OAuth 2.0)
   - Apple ID (Sign in with Apple)
   - Mail.ru (OAuth 2.0)

#### 2.1.2 Требования к авторизации
- JWT токены для сессий (access + refresh)
- Access token: срок жизни 1 час
- Refresh token: срок жизни 30 дней
- Автоматическое обновление токенов
- Возможность выхода со всех устройств

#### 2.1.3 Профиль пользователя
При первой авторизации запросить:
- Имя пользователя (отображаемое)
- Согласие на обработку персональных данных (GDPR)
- Разрешение на push-уведомления

### 2.2 Онбординг (идентично Telegram-боту)

#### 2.2.1 Выбор роли
После регистрации пользователь выбирает:
- **"Я инициатор"** — создать новую пару
- **"Я получатель приглашения"** — присоединиться по коду

#### 2.2.2 Создание пары (инициатор)

**Шаг 1: Выбор режима**
- **Режим "Тихий"** (Silent mode):
  - Описание: "Без общего чата. Только картинки-пожелания"
  - Пример: "Со мной всё в порядке ❤️"
  
- **Режим "Общение"** (Chat mode):
  - Описание: "С общим чатом для переписки"
  - Пример: "Доброе утро, солнце ☀️"

**Шаг 2: Настройка временных окон**
- Утреннее окно: выбор часа начала (по умолчанию 9:00)
- Вечернее окно: выбор часа начала (по умолчанию 21:00)
- Timezone: автоматическое определение или ручной выбор

**Шаг 3: Никнейм партнера**
- Ввод никнейма (как обращаться к партнеру)
- Пример: "мама", "любимая", "братик"

**Шаг 4: Выбор подписки**
- **Демо-режим**: 7 дней бесплатно
- **Ежемесячная подписка**: 199 ₽/мес
- **Годовая подписка**: 1490 ₽/год (экономия 40%)
- **Навсегда**: 2990 ₽ (единоразово)

**Шаг 5: Генерация invite-кода**
- 8-значный уникальный код
- Кнопка "Скопировать код"
- Кнопка "Поделиться" (Web Share API)
- Инструкция: "Отправьте этот код вашему близкому человеку"

#### 2.2.3 Присоединение к паре (получатель)

**Шаг 1: Ввод invite-кода**
- Поле для 8-значного кода
- Валидация кода на сервере

**Шаг 2: Подтверждение пары**
- Показать режим, выбранный инициатором
- Показать временные окна
- Кнопка "Принять приглашение"

**Шаг 3: Никнейм партнера**
- Ввод никнейма (как обращаться к инициатору)

**Шаг 4: Старт**
- Пара создана, можно начинать отправлять пожелания

### 2.3 Главный экран (Dashboard)

#### 2.3.1 Статус пары
- Никнейм партнера
- Режим (Тихий/Общение)
- Статус подписки (активна до...)
- Количество дней вместе

#### 2.3.2 Отправка пожеланий

**Кнопки (видны в соответствующее время):**
- **"Отправить доброе утро ☀️"** (видна в утреннее окно)
- **"Отправить спокойной ночи 🌙"** (видна в вечернее окно)

**Процесс отправки:**
1. Нажатие кнопки
2. Случайный выбор картинки из соответствующей категории
3. Preview картинки (опционально: выбрать другую)
4. Кнопка "Отправить"
5. Анимация отправки
6. Уведомление: "Картинка отправлена ❤️"
7. Кнопка неактивна до следующего окна

#### 2.3.3 Полученные пожелания

**Список полученных картинок:**
- Отображение последних 10 картинок от партнера
- Формат: дата/время + preview картинки
- Клик → открытие картинки на весь экран
- Infinite scroll для истории (загрузка по 10)

**Уведомления о новых:**
- Web Push при получении новой картинки
- Badge на иконке приложения (количество непрочитанных)
- Звук уведомления (опционально, настройка)

#### 2.3.4 Общий чат (только для режима "Общение")

**Функционал:**
- Отправка текстовых сообщений
- Отправка эмодзи
- История сообщений
- Real-time обновление (WebSocket или long polling)
- Уведомления о новых сообщениях

**Ограничения:**
- Без отправки файлов/фото/видео (только текст)
- Максимум 1000 символов в сообщении

### 2.4 Меню и навигация

#### 2.4.1 Главное меню (боковое или нижнее)
1. **Главная** 🏠
   - Dashboard с кнопками отправки

2. **История** 📜
   - Все отправленные/полученные картинки
   - Календарь активности

3. **Настройки** ⚙️
   - Профиль
   - Пара
   - Уведомления
   - Подписка

4. **Помощь** ❓
   - FAQ
   - Связь с поддержкой
   - О приложении

#### 2.4.2 Настройки → Профиль
- Имя пользователя
- Телефон / Email (в зависимости от способа регистрации)
- Подключенные OAuth аккаунты
- Сменить пароль (если регистрация по телефону)
- Удалить аккаунт

#### 2.4.3 Настройки → Пара
- Никнейм партнера (редактирование)
- Режим пары (смена возможна 1 раз в месяц)
- Временные окна (утро/вечер)
- Timezone
- **Разорвать пару** (с подтверждением)

#### 2.4.4 Настройки → Уведомления
- Push-уведомления (вкл/выкл)
- Звук уведомлений
- Напоминания о неотправленных пожеланиях
- Email-уведомления (резервные)

#### 2.4.5 Настройки → Подписка
- Текущий тариф
- Срок действия
- **Продлить подписку** (кнопка → оплата)
- **Изменить тариф** (upgrade/downgrade)
- История платежей

### 2.5 Подписки и оплата

#### 2.5.1 Тарифные планы
1. **Демо (Trial)**
   - 7 дней бесплатно
   - Все функции доступны
   - Автоматически активируется при создании пары

2. **Ежемесячная**
   - 199 ₽/месяц
   - Автопродление

3. **Годовая**
   - 1490 ₽/год (экономия 898 ₽)
   - Автопродление

4. **Навсегда (Lifetime)**
   - 2990 ₽ единоразово
   - Без автопродления
   - Бессрочная

#### 2.5.2 Процесс оплаты (Robokassa)

**Шаг 1: Выбор тарифа**
- Карточки с тарифами
- Выделение "Лучшее предложение" (годовая)
- Кнопка "Оплатить"

**Шаг 2: Перенаправление на Robokassa**
- Генерация ссылки на оплату
- Редирект в новой вкладке (или iframe)
- Параметры:
  - `OutSum`: сумма оплаты
  - `InvId`: ID транзакции
  - `Desc`: описание платежа
  - `SignatureValue`: подпись

**Шаг 3: Оплата**
- Пользователь выбирает способ оплаты на стороне Robokassa
- Вводит данные карты / СБП / другое

**Шаг 4: Возврат и активация**
- Success URL: `/payment/success?InvId=XXX`
- Fail URL: `/payment/fail?InvId=XXX`
- Result URL (webhook): обработка на сервере
- Активация подписки после подтверждения платежа

#### 2.5.3 Напоминания о продлении
- За 3 дня до окончания подписки: push + email
- В день окончания: push + email
- Блокировка функций после окончания (см. раздел 2.6)

### 2.6 Окончание подписки (Past Due)

#### 2.6.1 Уведомления о задолженности
**При окончании trial (7 дней):**
- Push: "Ваш пробный период закончился. Оформите подписку, чтобы продолжить."
- Каждые 24 часа повторять уведомление
- Максимум 3 уведомления

**При окончании платной подписки:**
- Push: "Ваша подписка закончилась. Продлите, чтобы продолжить отправлять пожелания."
- Каждые 24 часа
- Максимум 7 уведомлений

#### 2.6.2 Ограничения функций
- ❌ Отправка новых картинок заблокирована
- ✅ Просмотр истории доступен
- ✅ Получение картинок от партнера (если у него активна подписка)
- ✅ Общий чат (только чтение, отправка заблокирована)

#### 2.6.3 Баннер оплаты
- Красный баннер вверху экрана: "Подписка не активна. Оплатить →"
- Постоянно видим на всех экранах
- Клик → экран выбора тарифа

### 2.7 Push-уведомления

#### 2.7.1 Типы уведомлений
1. **Новая картинка от партнера**
   - Заголовок: "Новое пожелание от {nickname} ❤️"
   - Текст: "Доброе утро!" / "Спокойной ночи!"
   - Иконка: preview картинки (если возможно)
   - Action: открыть приложение → показать картинку

2. **Напоминание отправить пожелание**
   - Через 1 час после начала окна (если не отправлено)
   - Заголовок: "Не забудьте отправить пожелание {nickname}"
   - Текст: "Ваш близкий человек ждет ❤️"
   - Action: открыть приложение → кнопка отправки

3. **Напоминание о подписке**
   - За 3 дня / в день окончания / через 1/2/3 дня после
   - Заголовок: "Продлите подписку"
   - Текст: "Ваша подписка заканчивается через {days} дней"
   - Action: открыть приложение → экран оплаты

4. **Новое сообщение в чате** (режим "Общение")
   - Заголовок: "Новое сообщение от {nickname}"
   - Текст: preview сообщения (первые 50 символов)
   - Action: открыть приложение → чат

#### 2.7.2 Настройки уведомлений
- Запрос разрешения при первом входе
- Возможность отключить в настройках
- Управление типами уведомлений (галочки)

#### 2.7.3 Технические требования
- Web Push API (Service Worker)
- VAPID ключи для аутентификации
- Fallback на Email для устройств без поддержки
- Badge на иконке PWA (количество непрочитанных)

### 2.8 Дополнительные функции

#### 2.8.1 Статистика (для админа)
Аналогично Telegram-боту:
- Всего пользователей (с согласием)
- Всего пар
- Пользователей без пар
- Пар с demo-режимом
- Пар с активной подпиской
- Платформа пользователей (Telegram / PWA)

#### 2.8.2 Информация о приложении
- Ссылка на страницу с документами: https://24policybot.ru/legal
- Политика конфиденциальности
- Публичная оферта
- Согласие на обработку ПДн
- Контактная информация

---

## 3. Технические требования

### 3.1 Архитектура системы

#### 3.1.1 Общая архитектура
```
┌─────────────────────────────────────────────────────┐
│                  Клиенты                            │
│  ┌──────────────┐          ┌──────────────┐         │
│  │ Telegram Bot │          │  PWA App     │         │
│  │  (Aiogram)   │          │  (React)     │         │
│  └──────┬───────┘          └──────┬───────┘         │
│         │                         │                 │
└─────────┼─────────────────────────┼─────────────────┘
          │                         │
          ▼                         ▼
┌─────────────────────────────────────────────────────┐
│              Backend (FastAPI)                      │
│  ┌──────────────┐          ┌──────────────┐         │
│  │ Webhook      │          │  REST API    │         │
│  │ Server       │          │  (/api/*)    │         │
│  │ (Telegram)   │          │              │         │
│  └──────┬───────┘          └──────┬───────┘         │
│         │                         │                 │
│         └────────┬────────────────┘                 │
│                  ▼                                  │
│         ┌────────────────┐                          │
│         │ Business Logic │                          │
│         │   (Services)   │                          │
│         └────────┬───────┘                          │
│                  │                                  │
│         ┌────────┴────────┐                         │
│         │  Repositories   │                         │
│         └────────┬────────┘                         │
└──────────────────┼──────────────────────────────────┘
                   │
          ┌────────┴────────┐
          ▼                 ▼
    ┌──────────┐      ┌──────────┐
    │PostgreSQL│      │  Redis   │
    └──────────┘      └──────────┘
          │
    ┌─────┴──────┐
    │   Worker   │
    │   (ARQ)    │
    └────────────┘
```

#### 3.1.2 Backend структура
```
src/
├── api/                         # REST API для PWA
│   ├── __init__.py
│   ├── app.py                   # FastAPI app для API
│   ├── dependencies.py          # Зависимости (auth, db)
│   ├── middleware/
│   │   ├── auth.py              # JWT authentication
│   │   └── cors.py              # CORS настройки
│   └── routes/
│       ├── __init__.py
│       ├── auth.py              # POST /auth/send-otp, /auth/verify-otp
│       ├── user.py              # GET/PUT /user/profile
│       ├── pair.py              # CRUD операции с парами
│       ├── messages.py          # GET /messages, POST /send
│       ├── subscription.py      # Управление подписками
│       └── push.py              # Web Push subscriptions
├── bot/                         # Существующий Telegram bot
├── services/                    # Общая бизнес-логика
│   ├── auth/
│   │   ├── otp_service.py       # Генерация и проверка OTP
│   │   ├── jwt_service.py       # JWT токены
│   │   └── oauth_service.py     # OAuth провайдеры
│   ├── sms/
│   │   └── sms_provider.py      # Отправка SMS (Twilio/SMS.ru)
│   └── push/
│       └── web_push_service.py  # Web Push уведомления
├── db/
│   └── models.py                # Добавить platform, email, etc.
└── worker/                      # Существующий worker
    └── services/
        └── notification_dispatcher.py  # Роутинг: Telegram vs PWA
```

### 3.2 База данных

#### 3.2.1 Изменения в модели User
```sql
ALTER TABLE users 
ADD COLUMN platform VARCHAR(20) DEFAULT 'telegram' CHECK (platform IN ('telegram', 'pwa')),
ADD COLUMN email VARCHAR(255),
ADD COLUMN phone VARCHAR(50),
ADD COLUMN oauth_provider VARCHAR(50),
ADD COLUMN oauth_id VARCHAR(255),
ALTER COLUMN tg_id DROP NOT NULL;

CREATE INDEX idx_users_platform ON users(platform);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_phone ON users(phone);
```

#### 3.2.2 Новая таблица: push_subscriptions
```sql
CREATE TABLE push_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_push_user_id ON push_subscriptions(user_id);
```

#### 3.2.3 Новая таблица: otp_codes
```sql
CREATE TABLE otp_codes (
    id SERIAL PRIMARY KEY,
    phone_or_email VARCHAR(255) NOT NULL,
    code VARCHAR(6) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    attempts INTEGER DEFAULT 0,
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_otp_phone_email ON otp_codes(phone_or_email, verified);
CREATE INDEX idx_otp_expires ON otp_codes(expires_at);
```

#### 3.2.4 Новая таблица: oauth_accounts
```sql
CREATE TABLE oauth_accounts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL CHECK (provider IN ('google', 'yandex', 'apple', 'mailru')),
    provider_user_id VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(provider, provider_user_id)
);

CREATE INDEX idx_oauth_user_id ON oauth_accounts(user_id);
CREATE INDEX idx_oauth_provider ON oauth_accounts(provider, provider_user_id);
```

### 3.3 REST API Endpoints

#### 3.3.1 Авторизация (Auth)

**POST /api/auth/send-otp**
- Request:
  ```json
  {
    "phone": "+79991234567"
  }
  ```
- Response:
  ```json
  {
    "success": true,
    "message": "Код отправлен на +79991234567",
    "expires_in": 300
  }
  ```
- Логика:
  - Генерировать 6-значный код
  - Сохранить в `otp_codes` с временем истечения (5 минут)
  - Отправить SMS
  - Rate limit: максимум 3 запроса в час на номер

**POST /api/auth/verify-otp**
- Request:
  ```json
  {
    "phone": "+79991234567",
    "code": "123456"
  }
  ```
- Response (успех):
  ```json
  {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbG...",
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbG...",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": {
      "id": 123,
      "phone": "+79991234567",
      "platform": "pwa",
      "has_pair": false,
      "consent": false
    }
  }
  ```
- Логика:
  - Проверить код в БД
  - Если пользователь не существует → создать
  - Если существует → обновить last_login
  - Сгенерировать JWT токены
  - Удалить использованный OTP

**POST /api/auth/oauth/google**
- Request:
  ```json
  {
    "id_token": "google_id_token_here"
  }
  ```
- Response: аналогично verify-otp
- Логика:
  - Верифицировать Google ID token
  - Получить email и user_id
  - Найти или создать пользователя
  - Сгенерировать JWT

*Аналогично для Yandex, Apple, Mail.ru*

**POST /api/auth/refresh**
- Request:
  ```json
  {
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbG..."
  }
  ```
- Response:
  ```json
  {
    "access_token": "new_access_token",
    "expires_in": 3600
  }
  ```

**POST /api/auth/logout**
- Headers: `Authorization: Bearer <access_token>`
- Response: `{ "success": true }`
- Логика: инвалидировать refresh token

#### 3.3.2 Пользователь (User)

**GET /api/user/profile**
- Headers: `Authorization: Bearer <access_token>`
- Response:
  ```json
  {
    "id": 123,
    "phone": "+79991234567",
    "email": null,
    "username": "Иван",
    "platform": "pwa",
    "consent": true,
    "created_at": "2026-01-15T10:30:00Z"
  }
  ```

**PUT /api/user/profile**
- Request:
  ```json
  {
    "username": "Иван Петров"
  }
  ```
- Response: обновленный профиль

**POST /api/user/consent**
- Request:
  ```json
  {
    "consent": true
  }
  ```
- Response: `{ "success": true }`

**DELETE /api/user/account**
- Headers: `Authorization: Bearer <access_token>`
- Response: `{ "success": true, "message": "Аккаунт удален" }`
- Логика: soft delete (consent = false, удалить personal data)

#### 3.3.3 Пары (Pair)

**GET /api/pair/status**
- Headers: `Authorization: Bearer <access_token>`
- Response (если пара существует):
  ```json
  {
    "has_pair": true,
    "pair": {
      "id": 456,
      "mode": "silent",
      "status": "active",
      "partner": {
        "nickname": "Маша",
        "platform": "telegram"
      },
      "morning_window_start_hour": 9,
      "evening_window_start_hour": 21,
      "created_at": "2026-01-10T08:00:00Z",
      "days_together": 35
    },
    "subscription": {
      "status": "active",
      "plan": "monthly",
      "period_end": "2026-03-10T23:59:59Z",
      "is_lifetime": false
    }
  }
  ```
- Response (если пары нет):
  ```json
  {
    "has_pair": false
  }
  ```

**POST /api/pair/create**
- Request:
  ```json
  {
    "mode": "silent",
    "morning_window_start_hour": 9,
    "evening_window_start_hour": 21,
    "partner_nickname": "Маша",
    "subscription_plan": "trial"
  }
  ```
- Response:
  ```json
  {
    "success": true,
    "invite_code": "ABC12345",
    "pair_id": 456
  }
  ```
- Логика: аналогично боту

**POST /api/pair/join**
- Request:
  ```json
  {
    "invite_code": "ABC12345",
    "partner_nickname": "Ваня"
  }
  ```
- Response:
  ```json
  {
    "success": true,
    "pair_id": 456,
    "partner": {
      "nickname": "Ваня",
      "platform": "pwa"
    }
  }
  ```

**PUT /api/pair/settings**
- Request:
  ```json
  {
    "partner_nickname": "Машенька",
    "morning_window_start_hour": 10
  }
  ```
- Response: обновленные настройки пары

**DELETE /api/pair**
- Headers: `Authorization: Bearer <access_token>`
- Response: `{ "success": true, "message": "Пара разорвана" }`

#### 3.3.4 Сообщения (Messages)

**GET /api/messages**
- Headers: `Authorization: Bearer <access_token>`
- Query params:
  - `type`: "morning" | "evening" | "all"
  - `limit`: number (default: 10)
  - `offset`: number (default: 0)
- Response:
  ```json
  {
    "messages": [
      {
        "id": 789,
        "type": "morning",
        "image_url": "https://24policybot.ru/static/images/morning/123.jpg",
        "sent_by_me": false,
        "created_at": "2026-03-12T09:15:00Z"
      },
      ...
    ],
    "total": 150,
    "has_more": true
  }
  ```

**POST /api/messages/send**
- Request:
  ```json
  {
    "type": "morning"
  }
  ```
- Response:
  ```json
  {
    "success": true,
    "message": {
      "id": 790,
      "type": "morning",
      "image_url": "https://24policybot.ru/static/images/morning/456.jpg",
      "created_at": "2026-03-12T09:30:00Z"
    }
  }
  ```
- Логика:
  - Проверить временное окно
  - Проверить, что не отправлено уже
  - Выбрать случайную картинку
  - Сохранить в БД (daily_states)
  - Отправить уведомление партнеру
  - Вернуть URL картинки

**GET /api/messages/can-send**
- Response:
  ```json
  {
    "can_send_morning": true,
    "can_send_evening": false,
    "morning_already_sent": false,
    "evening_already_sent": true,
    "current_window": "morning"
  }
  ```

#### 3.3.5 Подписки (Subscription)

**GET /api/subscription/plans**
- Response:
  ```json
  {
    "plans": [
      {
        "id": "trial",
        "name": "Демо",
        "price": 0,
        "duration_days": 7,
        "description": "7 дней бесплатно"
      },
      {
        "id": "monthly",
        "name": "Ежемесячная",
        "price": 199,
        "currency": "RUB",
        "duration_days": 30,
        "description": "199 ₽/месяц"
      },
      ...
    ]
  }
  ```

**POST /api/subscription/create-payment**
- Request:
  ```json
  {
    "plan": "monthly"
  }
  ```
- Response:
  ```json
  {
    "payment_url": "https://auth.robokassa.ru/...",
    "invoice_id": 12345
  }
  ```
- Логика:
  - Создать запись в БД (invoice)
  - Сгенерировать signature для Robokassa
  - Вернуть URL для оплаты

**POST /api/subscription/verify-payment**
- Request (от Robokassa webhook):
  ```json
  {
    "InvId": 12345,
    "OutSum": "199.00",
    "SignatureValue": "hash_from_robokassa"
  }
  ```
- Response: `OK12345` (формат Robokassa)
- Логика:
  - Проверить signature
  - Активировать подписку
  - Отправить push-уведомление пользователю

#### 3.3.6 Push-уведомления (Push)

**POST /api/push/subscribe**
- Request:
  ```json
  {
    "endpoint": "https://fcm.googleapis.com/...",
    "keys": {
      "p256dh": "key_here",
      "auth": "auth_key_here"
    }
  }
  ```
- Response: `{ "success": true }`
- Логика: сохранить subscription в БД

**DELETE /api/push/unsubscribe**
- Request:
  ```json
  {
    "endpoint": "https://fcm.googleapis.com/..."
  }
  ```
- Response: `{ "success": true }`

### 3.4 Frontend (PWA)

#### 3.4.1 Технологический стек
- **Framework**: React 18+ с TypeScript
- **Build tool**: Vite 5+
- **PWA Plugin**: vite-plugin-pwa (Workbox)
- **Routing**: React Router v6
- **State Management**: Zustand или React Context
- **HTTP Client**: Axios с interceptors для JWT
- **UI Library**: 
  - Option 1: Tailwind CSS + HeadlessUI
  - Option 2: Material UI (MUI)
  - Option 3: Ant Design Mobile
- **Icons**: Lucide React или React Icons
- **Image optimization**: next/image аналог или react-lazy-load-image
- **Push notifications**: Web Push API (native)

#### 3.4.2 Структура проекта
```
pwa/
├── public/
│   ├── manifest.json
│   ├── icons/
│   │   ├── icon-72x72.png
│   │   ├── icon-96x96.png
│   │   ├── icon-128x128.png
│   │   ├── icon-144x144.png
│   │   ├── icon-152x152.png
│   │   ├── icon-192x192.png
│   │   ├── icon-384x384.png
│   │   └── icon-512x512.png
│   └── robots.txt
├── src/
│   ├── api/
│   │   ├── client.ts                # Axios instance с interceptors
│   │   ├── auth.ts                  # Auth endpoints
│   │   ├── user.ts                  # User endpoints
│   │   ├── pair.ts                  # Pair endpoints
│   │   ├── messages.ts              # Messages endpoints
│   │   └── subscription.ts          # Subscription endpoints
│   ├── assets/
│   │   ├── images/
│   │   └── sounds/
│   │       └── notification.mp3
│   ├── components/
│   │   ├── auth/
│   │   │   ├── PhoneInput.tsx
│   │   │   ├── OtpInput.tsx
│   │   │   └── OAuthButtons.tsx
│   │   ├── dashboard/
│   │   │   ├── SendButton.tsx
│   │   │   ├── MessagesList.tsx
│   │   │   └── PairStatus.tsx
│   │   ├── shared/
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Modal.tsx
│   │   │   └── Loader.tsx
│   │   └── Layout.tsx
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── usePair.ts
│   │   ├── usePushNotifications.ts
│   │   └── useWebSocket.ts          # Для чата (опционально)
│   ├── pages/
│   │   ├── Auth/
│   │   │   ├── Login.tsx
│   │   │   └── OAuthCallback.tsx
│   │   ├── Onboarding/
│   │   │   ├── SelectRole.tsx
│   │   │   ├── SelectMode.tsx
│   │   │   ├── TimeWindows.tsx
│   │   │   ├── Nickname.tsx
│   │   │   ├── SelectPlan.tsx
│   │   │   └── InviteCode.tsx
│   │   ├── Dashboard.tsx
│   │   ├── History.tsx
│   │   ├── Settings/
│   │   │   ├── Profile.tsx
│   │   │   ├── Pair.tsx
│   │   │   ├── Notifications.tsx
│   │   │   └── Subscription.tsx
│   │   ├── Payment/
│   │   │   ├── SelectPlan.tsx
│   │   │   ├── Success.tsx
│   │   │   └── Fail.tsx
│   │   └── Help.tsx
│   ├── store/
│   │   ├── authStore.ts
│   │   ├── pairStore.ts
│   │   └── notificationsStore.ts
│   ├── utils/
│   │   ├── jwt.ts
│   │   ├── validators.ts
│   │   └── formatters.ts
│   ├── sw.ts                        # Service Worker
│   ├── App.tsx
│   ├── main.tsx
│   └── vite-env.d.ts
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

#### 3.4.3 PWA Manifest (manifest.json)
```json
{
  "name": "Тихие объятия",
  "short_name": "Тихие объятия",
  "description": "Забота без лишних слов",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#FF6B9D",
  "orientation": "portrait",
  "icons": [
    {
      "src": "/icons/icon-72x72.png",
      "sizes": "72x72",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-512x512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ],
  "categories": ["lifestyle", "social"],
  "lang": "ru"
}
```

#### 3.4.4 Service Worker функционал
1. **Кэширование:**
   - Static assets (JS, CSS, fonts)
   - App shell (HTML, layout)
   - API responses (short-term cache)
   - **Важно**: НЕ кэшировать картинки (2000+ файлов), только по запросу

2. **Push notifications:**
   - Слушать события `push`
   - Показывать уведомления
   - Обработка кликов (открытие приложения)

3. **Background sync:**
   - Отложенная отправка сообщений при отсутствии сети

4. **Offline fallback:**
   - Показывать кэшированные данные
   - "Офлайн" баннер

### 3.5 Статические файлы (картинки)

#### 3.5.1 Организация на сервере
```
/var/www/static/
└── images/
    ├── morning/
    │   ├── 1.jpg
    │   ├── 2.jpg
    │   ├── ...
    │   └── 1023.jpg
    └── evening/
        ├── 1.jpg
        ├── 2.jpg
        ├── ...
        └── 1034.jpg
```

**Или в проекте:**
```
/home/telegram-bot/static/
└── images/
    ├── morning/
    └── evening/
```

#### 3.5.2 Nginx конфигурация
```nginx
server {
    listen 443 ssl http2;
    server_name 24policybot.ru;

    # SSL сертификаты (уже настроены)
    ssl_certificate /etc/letsencrypt/live/24policybot.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/24policybot.ru/privkey.pem;

    # Раздача статики
    location /static/ {
        alias /home/telegram-bot/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        add_header Access-Control-Allow-Origin "*";
    }

    # PWA приложение
    location / {
        root /home/telegram-bot/pwa/dist;
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache";
    }

    # REST API
    location /api/ {
        proxy_pass http://127.0.0.1:8445;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Telegram webhook (существующий)
    location /webhook/telegram {
        proxy_pass http://127.0.0.1:8444;
        ...
    }

    # Robokassa webhook (существующий)
    location /webhook/robokassa {
        proxy_pass http://127.0.0.1:8443;
        ...
    }
}
```

#### 3.5.3 Формат URL картинок
```
https://24policybot.ru/static/images/morning/1.jpg
https://24policybot.ru/static/images/evening/1.jpg
```

#### 3.5.4 API возвращает
```json
{
  "image_url": "https://24policybot.ru/static/images/morning/123.jpg"
}
```

Frontend отображает:
```tsx
<img 
  src={message.image_url} 
  alt="Доброе утро"
  loading="lazy"
/>
```

### 3.6 Интеграции

#### 3.6.1 SMS-провайдер (для OTP)
**Рекомендуемые сервисы:**
1. **SMS.ru** (российский, надежный)
   - API: https://sms.ru/api
   - Цена: ~2.5₽ за SMS по РФ
   - Регистрация: https://sms.ru/

2. **Twilio** (международный)
   - API: https://www.twilio.com/docs/sms
   - Цена: ~$0.05 за SMS
   - Альтернатива при проблемах с SMS.ru

**Интеграция:**
```python
# src/services/sms/sms_provider.py
import aiohttp
from src.core.config import settings

class SMSProvider:
    async def send_otp(self, phone: str, code: str):
        async with aiohttp.ClientSession() as session:
            url = f"https://sms.ru/sms/send"
            params = {
                "api_id": settings.sms_api_key,
                "to": phone,
                "msg": f"Ваш код: {code}. Тихие объятия",
                "json": 1
            }
            async with session.post(url, params=params) as resp:
                result = await resp.json()
                if result["status"] == "OK":
                    return True
                raise Exception(f"SMS send failed: {result}")
```

#### 3.6.2 OAuth провайдеры

**Google OAuth 2.0**
- Console: https://console.cloud.google.com/
- Создать OAuth 2.0 Client ID
- Redirect URI: `https://24policybot.ru/auth/google/callback`
- Scopes: `openid`, `email`, `profile`

**Yandex OAuth**
- Console: https://oauth.yandex.ru/
- Создать приложение
- Redirect URI: `https://24policybot.ru/auth/yandex/callback`
- Права: `login:email`, `login:info`

**Apple Sign In**
- Developer: https://developer.apple.com/
- App ID configuration
- Redirect URI: `https://24policybot.ru/auth/apple/callback`
- Требуется Apple Developer аккаунт ($99/год)

**Mail.ru OAuth**
- Console: https://o2.mail.ru/app/
- Создать приложение
- Redirect URI: `https://24policybot.ru/auth/mailru/callback`

**Библиотека для Python:**
```python
# requirements.txt
authlib>=1.2.0
```

**Пример интеграции:**
```python
# src/services/auth/oauth_service.py
from authlib.integrations.starlette_client import OAuth

oauth = OAuth()

oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    client_kwargs={'scope': 'openid email profile'}
)

# Аналогично для других провайдеров
```

#### 3.6.3 Robokassa (уже интегрирована)
- Использовать существующий код из `src/services/application/payment.py`
- Добавить генерацию ссылок для PWA
- Webhook уже настроен

#### 3.6.4 Web Push (VAPID)
**Генерация ключей:**
```bash
npx web-push generate-vapid-keys
```

**Получить:**
- Public Key (для frontend)
- Private Key (для backend)

**Хранение в .env:**
```env
VAPID_PUBLIC_KEY=BMxY...
VAPID_PRIVATE_KEY=abc123...
VAPID_SUBJECT=mailto:tihieobatia@gmail.com
```

**Backend отправка:**
```python
# requirements.txt
py-vapid>=1.9.0
pywebpush>=1.14.0

# src/services/push/web_push_service.py
from pywebpush import webpush, WebPushException

async def send_push(subscription: dict, payload: str):
    try:
        webpush(
            subscription_info=subscription,
            data=payload,
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={
                "sub": settings.vapid_subject
            }
        )
    except WebPushException as e:
        logger.error(f"Push failed: {e}")
```

### 3.7 Безопасность

#### 3.7.1 JWT Токены
- **Access token**: срок жизни 1 час, payload минимален
- **Refresh token**: срок жизни 30 дней, храним в httpOnly cookie
- Алгоритм: RS256 (RSA) или HS256 (HMAC)
- Секрет: длинная случайная строка в `.env`

#### 3.7.2 Rate Limiting
- **OTP запросы**: 3 в час на номер
- **Login попытки**: 5 в 15 минут на IP
- **API запросы**: 100 в минуту на пользователя
- Реализация: Redis + middleware

#### 3.7.3 CORS
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://24policybot.ru"],  # В проде только основной домен
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

#### 3.7.4 HTTPS
- Обязательно для PWA (Service Worker требует HTTPS)
- Уже настроено Let's Encrypt

#### 3.7.5 Валидация данных
- Pydantic models для всех запросов
- Санитизация пользовательского ввода
- SQL injection protection (SQLAlchemy ORM)
- XSS protection (React автоматически экранирует)

#### 3.7.6 GDPR / Персональные данные
- Согласие на обработку ПДн (обязательно)
- Возможность удалить аккаунт
- Экспорт данных (опционально)
- Политика конфиденциальности

### 3.8 Мониторинг и логирование

#### 3.8.1 Логи
- Формат: JSON (как в боте)
- Уровни: DEBUG, INFO, WARNING, ERROR
- Ротация: 10MB, 5 файлов
- Путь: `/home/telegram-bot/logs/api.log`

#### 3.8.2 Метрики
- Количество регистраций (по способам)
- Активные пары (telegram / pwa / mixed)
- Отправленные сообщения (платформа)
- Успешные платежи
- Push delivery rate

#### 3.8.3 Ошибки
- Sentry (опционально) для отслеживания багов
- Email уведомления при критических ошибках

---

## 4. UI/UX требования

### 4.1 Дизайн

#### 4.1.1 Стиль
- **Минимализм**: никаких лишних элементов
- **Mobile-first**: 90% пользователей будут на мобильных
- **Светлая тема**: как основная
- Темная тема: опционально (можно в будущем)

#### 4.1.2 Цветовая схема
Основываясь на https://24policybot.ru/legal:
- **Primary**: #FF6B9D (розовый, для акцентов)
- **Secondary**: #FFB6C1 (светло-розовый)
- **Background**: #FFFFFF (белый)
- **Text**: #333333 (темно-серый)
- **Success**: #4CAF50 (зеленый)
- **Error**: #F44336 (красный)
- **Warning**: #FF9800 (оранжевый)

#### 4.1.3 Типографика
- **Font**: Inter или SF Pro (системный на iOS)
- **Sizes**:
  - H1: 28px, bold
  - H2: 24px, semibold
  - Body: 16px, regular
  - Small: 14px, regular

#### 4.1.4 Компоненты
- **Кнопки**: rounded (border-radius: 12px), крупные (min-height: 48px)
- **Inputs**: border, focus state с primary цветом
- **Cards**: shadow, rounded corners
- **Spacing**: 8px grid (8, 16, 24, 32px)

### 4.2 Экраны и flow

#### 4.2.1 Splash Screen
- Лого "Тихие объятия"
- Загрузка (1-2 секунды)
- Проверка авторизации

#### 4.2.2 Онбординг (для новых пользователей)
- 3 слайда с иллюстрациями:
  1. "Утренние и вечерние пожелания"
  2. "Два режима: тихий и общение"
  3. "Работает на всех платформах"
- Кнопка "Начать" → Login

#### 4.2.3 Login Screen
- **Заголовок**: "Войти в приложение"
- **Варианты входа:**
  1. По номеру телефона (большая кнопка)
  2. OAuth кнопки (4 в ряд):
     - Google (логотип)
     - Yandex (логотип)
     - Apple (логотип)
     - Mail.ru (логотип)

**После ввода номера:**
- OTP экран
- 6 полей для цифр (автофокус)
- "Отправить код повторно" (через 60 сек)

#### 4.2.4 Dashboard (главный экран)
**Структура:**
- **Header**:
  - Логотип
  - Иконка настроек (справа)
  
- **Pair Status Card**:
  - Аватар партнера (инициалы)
  - Никнейм партнера
  - "Режим: Тихий"
  - "Вместе уже 35 дней ❤️"
  - Статус подписки (мини-бейдж)

- **Send Buttons** (в центре):
  - Кнопка "Отправить доброе утро ☀️" (если утреннее окно)
    - Disabled если уже отправлено
    - Показать время отправки
  - Кнопка "Отправить спокойной ночи 🌙" (если вечернее окно)

- **Recent Messages** (внизу):
  - Заголовок "Полученные пожелания"
  - Grid 2x2 с preview картинок
  - "Показать все →"

- **Bottom Navigation**:
  - Главная 🏠
  - История 📜
  - Настройки ⚙️

#### 4.2.5 History Screen
- Tabs:
  - Полученные
  - Отправленные
  - Все
- Список картинок с датой
- Infinite scroll
- Клик → полноэкранный просмотр

#### 4.2.6 Settings Screen
- Список опций (Material Design style):
  - Профиль →
  - Пара →
  - Уведомления →
  - Подписка →
  - Помощь →
  - О приложении →
  - Выйти

### 4.3 Адаптивность

#### 4.3.1 Брейкпоинты
- **Mobile**: < 640px (основной)
- **Tablet**: 640px - 1024px
- **Desktop**: > 1024px (ограничить max-width: 480px по центру)

#### 4.3.2 Поддержка браузеров
- **iOS Safari**: 16.4+
- **Chrome Android**: последние 2 версии
- **Samsung Internet**: последняя версия
- **Firefox Mobile**: последняя версия

---

## 5. Тестирование

### 5.1 Unit тесты
- Backend: pytest для services, repositories
- Frontend: Vitest для компонентов, hooks
- Покрытие: минимум 60%

### 5.2 E2E тесты
- Playwright или Cypress
- Критические flow:
  1. Регистрация → создание пары → отправка пожелания
  2. Оплата подписки
  3. Push-уведомления

### 5.3 Ручное тестирование
- Реальные устройства:
  - iPhone (Safari)
  - Android (Chrome)
  - iPad
- Проверка:
  - Установка PWA на home screen
  - Push-уведомления
  - Offline работа

---

## 6. Развертывание (Deployment)

### 6.1 Структура на сервере

```
/home/telegram-bot/
├── silent-couple-bot/          # Существующий проект
│   ├── src/
│   │   ├── api/                # Новый REST API
│   │   ├── bot/                # Существующий Telegram bot
│   │   └── ...
│   └── ...
├── pwa/                        # PWA приложение (build)
│   └── dist/
│       ├── index.html
│       ├── assets/
│       ├── manifest.json
│       └── sw.js
└── static/                     # Статические файлы
    └── images/
        ├── morning/            # 1023 картинки
        └── evening/            # 1034 картинки
```

### 6.2 Systemd сервисы

**REST API сервис:**
```ini
# /etc/systemd/system/silent-couple-bot-api.service
[Unit]
Description=Silent Couple Bot REST API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=telegram-bot
Group=telegram-bot
WorkingDirectory=/home/telegram-bot/silent-couple-bot
Environment="PATH=/home/telegram-bot/venv/bin"
ExecStart=/home/telegram-bot/venv/bin/uvicorn src.api.app:app --host 127.0.0.1 --port 8445
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Команды:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable silent-couple-bot-api
sudo systemctl start silent-couple-bot-api
sudo systemctl status silent-couple-bot-api
```

### 6.3 Nginx конфигурация
См. раздел 3.5.2

### 6.4 CI/CD (опционально)

**GitHub Actions:**
```yaml
# .github/workflows/deploy-pwa.yml
name: Deploy PWA

on:
  push:
    branches: [main]
    paths:
      - 'pwa/**'

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      - name: Build PWA
        run: |
          cd pwa
          npm ci
          npm run build
      - name: Deploy to server
        uses: appleboy/scp-action@v0.1.4
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: telegram-bot
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          source: "pwa/dist/*"
          target: "/home/telegram-bot/pwa/"
```

---

## 7. Миграция существующих пользователей

### 7.1 Связывание аккаунтов

**Сценарий**: Пользователь хочет перейти с Telegram на PWA

**Flow:**
1. Пользователь в PWA регистрируется по телефону
2. API проверяет: есть ли user с таким телефоном в БД
3. Если есть (из Telegram):
   - Показать: "Найден аккаунт в Telegram. Связать?"
   - После подтверждения: обновить `platform` на `pwa`
   - Пара сохраняется, подписка сохраняется

**Альтернатива**: Спец. код в Telegram боте
- Команда `/link` в боте → получить код
- Ввести код в PWA → связать аккаунты

### 7.2 Кросс-платформенные пары

- User A: Telegram
- User B: PWA
- **Работает полностью**:
  - A отправляет из Telegram → B получает push в PWA
  - B отправляет из PWA → A получает в Telegram
  - Подписка общая
  - Настройки пары общие

---

## 8. Документация

### 8.1 Техническая документация
- API Reference (OpenAPI/Swagger)
  - FastAPI генерирует автоматически: `/api/docs`
- Архитектура системы (этот документ)
- Database schema

### 8.2 Пользовательская документация
- FAQ на сайте
- Онбординг в приложении
- Инструкции по настройке push

### 8.3 Комментарии в коде
- Docstrings для всех функций (Python)
- JSDoc для функций (TypeScript)
- README в каждом модуле

---

## 9. Оценка сроков и ресурсов

### 9.1 Разбивка по этапам

#### Этап 1: Backend API (2-3 недели)
- Миграции БД (1 день)
- Auth endpoints (3 дня)
- User/Pair endpoints (3 дня)
- Messages endpoints (2 дня)
- Subscription endpoints (2 дня)
- Push endpoints (2 дня)
- OAuth интеграции (3 дня)
- Тесты (2 дня)

#### Этап 2: Frontend PWA (3-4 недели)
- Setup проекта (1 день)
- UI компоненты (3 дня)
- Auth flow (3 дня)
- Onboarding flow (4 дня)
- Dashboard (3 дня)
- History (2 дня)
- Settings (3 дня)
- Payment flow (2 дня)
- PWA setup (Service Worker, manifest) (2 дня)
- Push notifications (2 дня)
- Тесты (3 дня)

#### Этап 3: Интеграция (1 неделя)
- Интеграция Backend + Frontend (2 дня)
- Worker изменения (Telegram vs PWA) (2 дня)
- Тестирование E2E (2 дня)
- Баг фиксы (1 день)

#### Этап 4: Деплой и запуск (1 неделя)
- Настройка сервера (1 день)
- Загрузка картинок (1 день)
- Настройка nginx (1 день)
- Настройка systemd (1 день)
- OAuth провайдеры настройка (1 день)
- Финальное тестирование (1 день)
- Запуск (1 день)

**Итого: 7-9 недель (1.5-2 месяца)**

### 9.2 Команда

**Минимальный состав:**
1. **Backend разработчик** (Python/FastAPI) - 1 чел
2. **Frontend разработчик** (React/TypeScript) - 1 чел
3. **DevOps** (part-time для деплоя) - 0.5 чел

**Опционально:**
4. **UI/UX дизайнер** (для макетов) - 0.5 чел
5. **QA инженер** (тестирование) - 0.5 чел

**Если 1 человек (fullstack):** 3-4 месяца

### 9.3 Бюджет (ориентировочный)

**Разработка:**
- Backend dev: 2-3 недели × 80 часов × ставка
- Frontend dev: 3-4 недели × 100 часов × ставка
- DevOps: 1 неделя × 20 часов × ставка

**Сервисы (ежемесячно):**
- **SMS.ru**: ~500₽/мес (100 SMS)
- **OAuth**: бесплатно (кроме Apple: $99/год)
- **Сервер**: текущий (достаточно)
- **Домен/SSL**: текущий (есть)

**Итого: 0₽/мес дополнительно** (если не Apple Sign In)

### 9.4 Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Push-уведомления не работают на некоторых устройствах | Средняя | Высокое | Email fallback |
| OAuth провайдеры блокируют в РФ | Низкая | Среднее | Телефон как основной способ |
| Сложность с Apple Sign In | Высокая | Низкое | Отложить на v2 |
| Загрузка 2000 картинок медленная | Средняя | Низкое | CDN (будущее), lazy loading |
| Недостаточно ресурсов сервера | Низкая | Среднее | Мониторинг, апгрейд при необходимости |

---

## 10. Roadmap после MVP

### Версия 1.0 (MVP)
- ✅ Все функции из ТЗ выше

### Версия 1.1 (через 1-2 месяца)
- Темная тема
- Выбор конкретной картинки (не только рандом)
- Календарь активности
- Статистика пары (сколько пожеланий отправлено)

### Версия 1.2 (через 3-4 месяца)
- Нативное приложение (React Native)
- Apple Sign In
- Расширенный чат (голосовые сообщения, стикеры)

### Версия 2.0 (через 6+ месяцев)
- AI-генерация пожеланий
- Кастомные картинки (загрузка своих)
- Больше режимов (семейный, дружеский)

---

## Приложения

### Приложение А: Переменные окружения (.env)

**Новые переменные для API:**
```env
# === API Settings ===
API_HOST=127.0.0.1
API_PORT=8445
API_SECRET_KEY=<random_64_char_string>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# === SMS Provider ===
SMS_PROVIDER=sms_ru  # sms_ru | twilio
SMS_API_KEY=<sms.ru_api_key>
# Или для Twilio:
# TWILIO_ACCOUNT_SID=<account_sid>
# TWILIO_AUTH_TOKEN=<auth_token>
# TWILIO_PHONE_NUMBER=<phone>

# === OAuth ===
GOOGLE_CLIENT_ID=<client_id>
GOOGLE_CLIENT_SECRET=<client_secret>

YANDEX_CLIENT_ID=<client_id>
YANDEX_CLIENT_SECRET=<client_secret>

APPLE_CLIENT_ID=<service_id>  # Опционально
APPLE_TEAM_ID=<team_id>
APPLE_KEY_ID=<key_id>
APPLE_PRIVATE_KEY_PATH=/path/to/key.p8

MAILRU_CLIENT_ID=<client_id>
MAILRU_CLIENT_SECRET=<client_secret>

# === Web Push (VAPID) ===
VAPID_PUBLIC_KEY=<public_key>
VAPID_PRIVATE_KEY=<private_key>
VAPID_SUBJECT=mailto:tihieobatia@gmail.com

# === CORS ===
CORS_ORIGINS=https://24policybot.ru,http://localhost:5173  # dev + prod

# === Rate Limiting ===
RATE_LIMIT_OTP_PER_HOUR=3
RATE_LIMIT_LOGIN_PER_15MIN=5
RATE_LIMIT_API_PER_MINUTE=100
```

### Приложение Б: Database Migrations

**Alembic миграция:**
```python
# alembic/versions/XXX_add_pwa_support.py

def upgrade():
    # 1. Add platform column
    op.add_column('users', 
        sa.Column('platform', sa.String(20), server_default='telegram', nullable=False)
    )
    op.create_check_constraint(
        'users_platform_check',
        'users',
        "platform IN ('telegram', 'pwa')"
    )
    
    # 2. Add email and phone
    op.add_column('users', sa.Column('email', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('phone', sa.String(50), nullable=True))
    
    # 3. Add OAuth fields
    op.add_column('users', sa.Column('oauth_provider', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('oauth_id', sa.String(255), nullable=True))
    
    # 4. Make tg_id nullable
    op.alter_column('users', 'tg_id', nullable=True)
    
    # 5. Indexes
    op.create_index('idx_users_platform', 'users', ['platform'])
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_phone', 'users', ['phone'])
    
    # 6. Create push_subscriptions table
    op.create_table(
        'push_subscriptions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('endpoint', sa.Text, nullable=False, unique=True),
        sa.Column('p256dh', sa.Text, nullable=False),
        sa.Column('auth', sa.Text, nullable=False),
        sa.Column('user_agent', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP, server_default=sa.text('NOW()'))
    )
    op.create_index('idx_push_user_id', 'push_subscriptions', ['user_id'])
    
    # 7. Create otp_codes table
    op.create_table(
        'otp_codes',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('phone_or_email', sa.String(255), nullable=False),
        sa.Column('code', sa.String(6), nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP, nullable=False),
        sa.Column('attempts', sa.Integer, server_default='0'),
        sa.Column('verified', sa.Boolean, server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('NOW()'))
    )
    op.create_index('idx_otp_phone_email', 'otp_codes', ['phone_or_email', 'verified'])
    op.create_index('idx_otp_expires', 'otp_codes', ['expires_at'])
    
    # 8. Create oauth_accounts table
    op.create_table(
        'oauth_accounts',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('provider_user_id', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('NOW()'))
    )
    op.create_index('idx_oauth_user_id', 'oauth_accounts', ['user_id'])
    op.create_index('idx_oauth_provider', 'oauth_accounts', ['provider', 'provider_user_id'], unique=True)

def downgrade():
    # Reverse all operations
    op.drop_table('oauth_accounts')
    op.drop_table('otp_codes')
    op.drop_table('push_subscriptions')
    op.drop_index('idx_users_phone')
    op.drop_index('idx_users_email')
    op.drop_index('idx_users_platform')
    op.alter_column('users', 'tg_id', nullable=False)
    op.drop_column('users', 'oauth_id')
    op.drop_column('users', 'oauth_provider')
    op.drop_column('users', 'phone')
    op.drop_column('users', 'email')
    op.drop_constraint('users_platform_check', 'users')
    op.drop_column('users', 'platform')
```

---

## Контакты и поддержка

**Разработчик:** Целищев Денис Владиславович
- Email: tihieobatia@gmail.com
- Telegram: @eonubis

**Проект:** Silent Couple Bot (Тихие объятия)
- Сайт: https://24policybot.ru
- Telegram бот: @tish_ob_bot
- GitHub: https://github.com/Den20050/silent-couple-bot

---

**Версия ТЗ:** 1.0
**Дата создания:** 12 марта 2026
**Статус:** Готово к разработке
