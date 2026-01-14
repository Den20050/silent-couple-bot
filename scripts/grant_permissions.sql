-- Скрипт для выдачи прав пользователю bot_user на схему public
-- Запустите этот скрипт от имени суперпользователя PostgreSQL (postgres)

-- Выдать права на схему public
GRANT ALL ON SCHEMA public TO bot_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bot_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO bot_user;

-- Выдать права на будущие таблицы
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO bot_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO bot_user;

-- Если схема public не существует или недоступна, создайте её
CREATE SCHEMA IF NOT EXISTS public;
GRANT USAGE ON SCHEMA public TO bot_user;
GRANT CREATE ON SCHEMA public TO bot_user;

