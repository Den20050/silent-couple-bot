#!/bin/bash
# Скрипт для проверки и исправления конфигурации webhook сервиса

echo "🔍 Проверка конфигурации webhook сервиса..."
echo ""

# Проверка существования директории
WORKING_DIR="/root/Silent-Couple-Bot"
if [ ! -d "$WORKING_DIR" ]; then
    echo "❌ Директория $WORKING_DIR не существует!"
    echo "Текущая директория: $(pwd)"
    echo ""
    echo "Возможные решения:"
    echo "1. Убедитесь, что проект находится в $WORKING_DIR"
    echo "2. Или измените WorkingDirectory в /etc/systemd/system/silent-couple-bot-webhook.service"
    exit 1
else
    echo "✅ Директория $WORKING_DIR существует"
fi

# Проверка прав доступа
if [ ! -r "$WORKING_DIR" ]; then
    echo "❌ Нет прав на чтение директории $WORKING_DIR"
    exit 1
else
    echo "✅ Есть права на чтение директории"
fi

# Проверка наличия .env файла
if [ ! -f "$WORKING_DIR/.env" ]; then
    echo "⚠️  Файл .env не найден в $WORKING_DIR"
    echo "Создайте его из env.example:"
    echo "  cp $WORKING_DIR/env.example $WORKING_DIR/.env"
else
    echo "✅ Файл .env найден"
fi

# Проверка Python пути
PYTHON_PATH="/usr/bin/python3"
if [ ! -f "$PYTHON_PATH" ]; then
    echo "⚠️  Python3 не найден по пути $PYTHON_PATH"
    echo "Найденные пути Python:"
    which -a python3
else
    echo "✅ Python3 найден: $PYTHON_PATH"
fi

# Проверка модуля entrypoints.webhook
echo ""
echo "🔍 Проверка модуля src.entrypoints.webhook..."
cd "$WORKING_DIR"
if python3 -c "import src.entrypoints.webhook" 2>/dev/null; then
    echo "✅ Модуль src.entrypoints.webhook доступен"
else
    echo "❌ Модуль src.entrypoints.webhook недоступен"
    echo "Проверьте установку зависимостей:"
    echo "  cd $WORKING_DIR && pip3 install -r requirements.txt"
    exit 1
fi

# Проверка systemd service файла
SERVICE_FILE="/etc/systemd/system/silent-couple-bot-webhook.service"
if [ -f "$SERVICE_FILE" ]; then
    echo ""
    echo "📄 Содержимое service файла:"
    cat "$SERVICE_FILE"
    echo ""
    
    # Проверка WorkingDirectory в service файле
    if grep -q "WorkingDirectory=$WORKING_DIR" "$SERVICE_FILE"; then
        echo "✅ WorkingDirectory в service файле правильный"
    else
        echo "⚠️  WorkingDirectory в service файле может быть неправильным"
        echo "Текущий WorkingDirectory:"
        grep "WorkingDirectory=" "$SERVICE_FILE" || echo "Не найден!"
    fi
else
    echo "❌ Service файл не найден: $SERVICE_FILE"
    echo "Создайте его:"
    echo "  sudo cp $WORKING_DIR/deploy/webhook.service $SERVICE_FILE"
    echo "  sudo systemctl daemon-reload"
fi

echo ""
echo "✅ Проверка завершена"
echo ""
echo "Для запуска сервиса:"
echo "  sudo systemctl start silent-couple-bot-webhook"
echo ""
echo "Для просмотра логов:"
echo "  sudo journalctl -u silent-couple-bot-webhook -f"
