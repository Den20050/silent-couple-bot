# Скрипт для проверки статуса бота
# Использование: .\scripts\check_bot_status.ps1

Write-Host "=== Проверка статуса бота ===" -ForegroundColor Cyan
Write-Host ""

# 1. Проверка локальных процессов Python
Write-Host "1. Локальные процессы Python:" -ForegroundColor Yellow
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    Write-Host "   Найдено процессов: $($pythonProcesses.Count)" -ForegroundColor Red
    $pythonProcesses | Format-Table Id,ProcessName,StartTime,@{Label="CommandLine";Expression={(Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine}} -AutoSize
} else {
    Write-Host "   ✅ Нет запущенных процессов Python" -ForegroundColor Green
}

Write-Host ""

# 2. Проверка webhook статуса (если есть токен)
Write-Host "2. Статус webhook в Telegram:" -ForegroundColor Yellow
if ($env:TG_BOT_TOKEN) {
    try {
        $webhookInfo = Invoke-RestMethod -Uri "https://api.telegram.org/bot$env:TG_BOT_TOKEN/getWebhookInfo" -Method Get
        if ($webhookInfo.ok) {
            if ($webhookInfo.result.url) {
                Write-Host "   ⚠️  Webhook установлен: $($webhookInfo.result.url)" -ForegroundColor Yellow
                Write-Host "   Для локальной разработки нужно удалить webhook!" -ForegroundColor Yellow
            } else {
                Write-Host "   ✅ Webhook не установлен (можно использовать polling)" -ForegroundColor Green
            }
        }
    } catch {
        Write-Host "   ⚠️  Не удалось проверить webhook: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "   ⚠️  TG_BOT_TOKEN не установлен в переменных окружения" -ForegroundColor Yellow
}

Write-Host ""

# 3. Проверка портов
Write-Host "3. Проверка портов:" -ForegroundColor Yellow
$ports = @(6379, 5432, 8443)
foreach ($port in $ports) {
    $connection = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($connection) {
        Write-Host "   ⚠️  Порт $port занят (может быть SSH туннель)" -ForegroundColor Yellow
    } else {
        Write-Host "   ✅ Порт $port свободен" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "=== Рекомендации ===" -ForegroundColor Cyan
if ($pythonProcesses) {
    Write-Host "1. Остановите все процессы Python:" -ForegroundColor Yellow
    Write-Host "   taskkill /f /im python.exe" -ForegroundColor White
    Write-Host ""
}
if ($webhookInfo.result.url) {
    Write-Host "2. Удалите webhook:" -ForegroundColor Yellow
    Write-Host "   curl -X POST `"https://api.telegram.org/bot`$env:TG_BOT_TOKEN/deleteWebhook`"" -ForegroundColor White
    Write-Host ""
}
Write-Host "3. Запустите бот:" -ForegroundColor Yellow
Write-Host "   python run.py" -ForegroundColor White
