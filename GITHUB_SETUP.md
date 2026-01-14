# Пошаговая инструкция: Выгрузка проекта на GitHub

## Предварительные требования

1. ✅ Установлен Git на Windows
2. ✅ Создан репозиторий `silent-couple-bot` на GitHub
3. ✅ У вас есть доступ к репозиторию (права на запись)

## Шаг 1: Проверка установки Git

Откройте PowerShell или Git Bash и выполните:

```powershell
git --version
```

Если Git не установлен, скачайте с [git-scm.com](https://git-scm.com/download/win)

## Шаг 2: Настройка Git (если еще не настроен)

```powershell
# Укажите ваше имя (замените на ваше имя)
git config --global user.name "Ваше Имя"

# Укажите ваш email (замените на ваш email)
git config --global user.email "your.email@example.com"
```

## Шаг 3: Инициализация Git репозитория

Откройте PowerShell в директории проекта:

```powershell
# Перейдите в директорию проекта (если еще не там)
cd C:\Silent-Couple-Bot

# Инициализируйте Git репозиторий
git init
```

## Шаг 4: Проверка .gitignore

Убедитесь, что файл `.gitignore` существует и содержит `.env`:

```powershell
# Проверьте содержимое .gitignore
cat .gitignore
```

Должна быть строка `.env` - это важно, чтобы секретные данные не попали в репозиторий!

## Шаг 5: Добавление файлов в Git

```powershell
# Добавьте все файлы (кроме тех, что в .gitignore)
git add .

# Проверьте, что будет добавлено (опционально)
git status
```

**Важно:** Убедитесь, что `.env` файл НЕ добавлен! Проверьте:

```powershell
git status | Select-String ".env"
```

Если `.env` не отображается в `git status` - все правильно!

## Шаг 6: Первый коммит

```powershell
# Создайте первый коммит
git commit -m "Initial commit: Silent Couple Bot"
```

## Шаг 7: Добавление remote репозитория

**Вариант A: Если вы используете HTTPS (рекомендуется для начала)**

```powershell
# Замените YOUR_USERNAME на ваш GitHub username
git remote add origin https://github.com/YOUR_USERNAME/silent-couple-bot.git
```

**Вариант B: Если вы используете SSH**

```powershell
# Замените YOUR_USERNAME на ваш GitHub username
git remote add origin git@github.com:YOUR_USERNAME/silent-couple-bot.git
```

**Как узнать ваш GitHub username:**
- Зайдите на GitHub.com
- В правом верхнем углу нажмите на ваш аватар
- Ваш username отображается в меню

## Шаг 8: Переименование ветки в main (если нужно)

```powershell
# Переименуйте ветку в main (современный стандарт)
git branch -M main
```

## Шаг 9: Отправка кода на GitHub

```powershell
# Отправьте код на GitHub
git push -u origin main
```

Если используете HTTPS, Git попросит ввести:
- **Username**: ваш GitHub username
- **Password**: используйте Personal Access Token (не обычный пароль!)

### Как создать Personal Access Token (если нужно):

1. Зайдите на GitHub.com
2. Нажмите на ваш аватар → Settings
3. В левом меню: Developer settings
4. Personal access tokens → Tokens (classic)
5. Generate new token (classic)
6. Выберите срок действия и права доступа (минимум `repo`)
7. Скопируйте токен (он показывается только один раз!)
8. Используйте этот токен как пароль при `git push`

## Шаг 10: Проверка

Откройте браузер и перейдите на:
```
https://github.com/YOUR_USERNAME/silent-couple-bot
```

Вы должны увидеть все файлы проекта!

## Дальнейшая работа с Git

### После изменений в коде:

```powershell
# 1. Проверьте изменения
git status

# 2. Добавьте измененные файлы
git add .

# 3. Создайте коммит с описанием изменений
git commit -m "Описание изменений"

# 4. Отправьте изменения на GitHub
git push
```

### Получение изменений с сервера:

```powershell
# Если код был изменен на сервере и запушен в GitHub
git pull
```

## Важные замечания

⚠️ **НИКОГДА не коммитьте:**
- `.env` файл (содержит секретные данные)
- Файлы с паролями и токенами
- Локальные базы данных
- Логи с чувствительной информацией

✅ **Всегда проверяйте перед коммитом:**
```powershell
git status
```

## Troubleshooting

### Ошибка: "remote origin already exists"

Если remote уже добавлен, удалите и добавьте заново:

```powershell
git remote remove origin
git remote add origin https://github.com/YOUR_USERNAME/silent-couple-bot.git
```

### Ошибка: "failed to push some refs"

Если на GitHub уже есть файлы (например, README), сначала получите их:

```powershell
git pull origin main --allow-unrelated-histories
git push -u origin main
```

### Ошибка: "Authentication failed"

1. Проверьте правильность username
2. Используйте Personal Access Token вместо пароля
3. Для SSH: убедитесь, что SSH ключ добавлен в GitHub

### Проверка remote URL

```powershell
git remote -v
```

Должно показать:
```
origin  https://github.com/YOUR_USERNAME/silent-couple-bot.git (fetch)
origin  https://github.com/YOUR_USERNAME/silent-couple-bot.git (push)
```

## Быстрая команда для копирования

Если вы уже знаете ваш GitHub username, выполните все команды одной строкой:

```powershell
cd C:\Silent-Couple-Bot
git init
git add .
git commit -m "Initial commit: Silent Couple Bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/silent-couple-bot.git
git push -u origin main
```

**Не забудьте заменить `YOUR_USERNAME` на ваш реальный GitHub username!**
