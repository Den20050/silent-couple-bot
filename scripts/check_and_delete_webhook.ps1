# Скрипт для проверки и удаления webhook
# Использование: .\scripts\check_and_delete_webhook.ps1

Write-Host "=== Проверка и удаление webhook ===" -ForegroundColor Cyan
Write-Host ""

# Загрузить переменные из .env файла
$envFile = ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "❌ Файл .env не найден!" -ForegroundColor Red
    exit 1
}

# Прочитать TG_BOT_TOKEN из .env
$tgBotToken = $null
Get-Content $envFile | ForEach-Object {
    if ($_ -match "^TG_BOT_TOKEN=(.+)$") {
        $tgBotToken = $matches[1].Trim()
    }
}

if (-not $tgBotToken) {
    Write-Host "❌ TG_BOT_TOKEN не найден в .env файле!" -ForegroundColor Red
    exit 1
}

Write-Host "Токен найден (первые 10 символов): $($tgBotToken.Substring(0, [Math]::Min(10, $tgBotToken.Length)))..." -ForegroundColor Gray
Write-Host ""

# Проверить статус webhook
Write-Host "1. Проверка статуса webhook..." -ForegroundColor Yellow
try {
    $webhookInfo = Invoke-RestMethod -Uri "https://api.telegram.org/bot$tgBotToken/getWebhookInfo" -Method Get
    if ($webhookInfo.ok) {
        if ($webhookInfo.result.url) {
            Write-Host "   ⚠️  Webhook установлен: $($webhookInfo.result.url)" -ForegroundColor Yellow
            Write-Host "   Это может вызывать конфликт с polling!" -ForegroundColor Yellow
            Write-Host ""
            
            $confirm = Read-Host "Удалить webhook? (y/n)"
            if ($confirm -eq "y" -or $confirm -eq "Y") {
                Write-Host "   Удаляю webhook..." -ForegroundColor Yellow
                try {
                    $deleteResult = Invoke-RestMethod -Uri "https://api.telegram.org/bot$tgBotToken/deleteWebhook" -Method Post
                    if ($deleteResult.ok) {
                        Write-Host "   ✅ Webhook успешно удален!" -ForegroundColor Green
                    } else {
                        Write-Host "   ❌ Ошибка при удалении webhook" -ForegroundColor Red
                    }
                } catch {
                    Write-Host "   ❌ Ошибка: $_" -ForegroundColor Red
                }
            } else {
                Write-Host "   Отменено" -ForegroundColor Yellow
            }
        } else {
            Write-Host "   ✅ Webhook не установлен (можно использовать polling)" -ForegroundColor Green
        }
    }
} catch {
    Write-Host "   ❌ Ошибка при проверке webhook: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Готово ===" -ForegroundColor Cyan
Write-Host "Теперь можно запустить бот: python run.py" -ForegroundColor Green
