-- Выдача прав на конкретную базу данных silent_couple_bot
-- Выполните эти команды в psql от имени postgres

-- Подключитесь к базе данных silent_couple_bot
\c silent_couple_bot

-- Выдайте права на схему public в этой БД
GRANT ALL ON SCHEMA public TO bot_user;
GRANT CREATE ON SCHEMA public TO bot_user;
GRANT USAGE ON SCHEMA public TO bot_user;

-- Выдайте права на все существующие объекты
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bot_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO bot_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO bot_user;

-- Выдайте права на будущие объекты
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO bot_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO bot_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO bot_user;

-- Также выдайте права на саму базу данных
GRANT CONNECT ON DATABASE silent_couple_bot TO bot_user;
GRANT CREATE ON DATABASE silent_couple_bot TO bot_user;

