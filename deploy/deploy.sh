#!/bin/bash
# Минимальный скрипт деплоя для Silent Couple Bot
# Использование: ./deploy/deploy.sh

set -e  # Остановить при ошибке

echo "🚀 Silent Couple Bot - Деплой на сервер"

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Проверка переменных окружения
if [ -z "$DEPLOY_HOST" ]; then
    echo -e "${RED}❌ Переменная DEPLOY_HOST не установлена${NC}"
    echo "Установите: export DEPLOY_HOST=user@your-server-ip"
    exit 1
fi

if [ -z "$DEPLOY_PATH" ]; then
    DEPLOY_PATH="/root/Silent-Couple-Bot"
    echo -e "${YELLOW}⚠️  DEPLOY_PATH не установлен, используем: $DEPLOY_PATH${NC}"
fi

echo -e "${GREEN}📦 Шаг 1: Проверка локальных изменений...${NC}"
if ! git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}⚠️  Есть незакоммиченные изменения. Продолжить? (y/n)${NC}"
    read -r response
    if [ "$response" != "y" ]; then
        echo "Отменено"
        exit 1
    fi
fi

echo -e "${GREEN}📤 Шаг 2: Отправка изменений в git...${NC}"
# Проверка, есть ли что пушить
if git diff --quiet origin/main..HEAD 2>/dev/null || git diff --quiet origin/master..HEAD 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Нет изменений для отправки${NC}"
else
    echo "Отправка в git..."
    git push
fi

echo -e "${GREEN}🔄 Шаг 3: Обновление кода на сервере...${NC}"
ssh "$DEPLOY_HOST" "cd $DEPLOY_PATH && git pull"

echo -e "${GREEN}📦 Шаг 4: Установка зависимостей (если нужно)...${NC}"
ssh "$DEPLOY_HOST" "cd $DEPLOY_PATH && pip3 install -q -r requirements.txt"

echo -e "${GREEN}🗄️  Шаг 5: Применение миграций БД...${NC}"
ssh "$DEPLOY_HOST" "cd $DEPLOY_PATH && alembic upgrade head"

echo -e "${GREEN}🔄 Шаг 6: Перезапуск сервиса...${NC}"
ssh "$DEPLOY_HOST" "sudo systemctl restart silent-couple-bot-webhook"

echo -e "${GREEN}✅ Шаг 7: Проверка статуса...${NC}"
sleep 2
ssh "$DEPLOY_HOST" "sudo systemctl status silent-couple-bot-webhook --no-pager -l"

echo -e "${GREEN}✅ Деплой завершен!${NC}"
echo ""
echo "Проверка логов:"
echo "  ssh $DEPLOY_HOST 'sudo journalctl -u silent-couple-bot-webhook -f'"
