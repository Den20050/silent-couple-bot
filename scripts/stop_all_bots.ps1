# Скрипт для остановки всех экземпляров бота
# Использование: .\scripts\stop_all_bots.ps1

Write-Host "=== Остановка всех экземпляров бота ===" -ForegroundColor Cyan
Write-Host ""

# Найти все процессы Python
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue

if (-not $pythonProcesses) {
    Write-Host "✅ Нет запущенных процессов Python" -ForegroundColor Green
    exit 0
}

Write-Host "Найдено процессов Python: $($pythonProcesses.Count)" -ForegroundColor Yellow
$pythonProcesses | Format-Table Id,ProcessName,StartTime -AutoSize

Write-Host ""
$confirm = Read-Host "Остановить все процессы Python? (y/n)"

if ($confirm -eq "y" -or $confirm -eq "Y") {
    Write-Host "Останавливаю процессы..." -ForegroundColor Yellow
    try {
        Stop-Process -Name python -Force -ErrorAction Stop
        Write-Host "✅ Все процессы Python остановлены" -ForegroundColor Green
    } catch {
        Write-Host "❌ Ошибка при остановке процессов: $_" -ForegroundColor Red
        Write-Host "Попробуйте запустить от имени администратора:" -ForegroundColor Yellow
        Write-Host "taskkill /f /im python.exe" -ForegroundColor White
    }
} else {
    Write-Host "Отменено" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Проверка после остановки..." -ForegroundColor Cyan
Start-Sleep -Seconds 2
$remaining = Get-Process python -ErrorAction SilentlyContinue
if ($remaining) {
    Write-Host "⚠️  Остались процессы: $($remaining.Count)" -ForegroundColor Yellow
    Write-Host "Попробуйте остановить вручную:" -ForegroundColor Yellow
    $remaining | Format-Table Id,ProcessName -AutoSize
} else {
    Write-Host "✅ Все процессы остановлены" -ForegroundColor Green
}
