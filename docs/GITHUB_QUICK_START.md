# Быстрый старт: Выгрузка проекта на GitHub

## Самый простой способ (SSH - без токенов)

### 1. Проверьте, есть ли SSH ключ

```powershell
# В PowerShell
Test-Path $env:USERPROFILE\.ssh\id_ed25519.pub
```

Если выведет `False` - создайте ключ (шаг 2).  
Если `True` - переходите к шагу 3.

### 2. Создайте SSH ключ (если нет)

```powershell
ssh-keygen -t ed25519 -C "your.email@example.com"
```

Нажмите Enter для всех вопросов (или задайте пароль для ключа).

### 3. Скопируйте публичный ключ

```powershell
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub | Set-Clipboard
```

Ключ скопирован в буфер обмена!

### 4. Добавьте ключ в GitHub

1. Откройте: **https://github.com/settings/keys**
2. Нажмите **"New SSH key"**
3. Вставьте ключ (Ctrl+V)
4. Нажмите **"Add SSH key"**

### 5. Проверьте подключение

```powershell
ssh -T git@github.com
```

Должно вывести: `Hi YOUR_USERNAME! You've successfully authenticated...`

### 6. Выполните команды Git

```powershell
cd C:\Silent-Couple-Bot

# Добавьте файлы
git add .

# Создайте коммит
git commit -m "Initial commit: Silent Couple Bot"

# Добавьте remote (замените YOUR_USERNAME!)
git remote add origin git@github.com:YOUR_USERNAME/silent-couple-bot.git

# Переименуйте ветку
git branch -M main

# Отправьте код
git push -u origin main
```

Готово! 🎉

---

## Альтернатива: HTTPS (если SSH не работает)

### 1. Создайте токен

Откройте в браузере: **https://github.com/settings/tokens**

Нажмите **"Generate new token"** → выберите `repo` → создайте токен.

### 2. Выполните команды Git

```powershell
cd C:\Silent-Couple-Bot

git add .
git commit -m "Initial commit: Silent Couple Bot"
git remote add origin https://github.com/YOUR_USERNAME/silent-couple-bot.git
git branch -M main
git push -u origin main
```

При запросе пароля используйте токен (не обычный пароль!).

---

## Как узнать ваш GitHub username?

1. Зайдите на GitHub.com
2. В правом верхнем углу нажмите на аватар
3. Ваш username отображается в меню

Или просто посмотрите URL вашего профиля: `https://github.com/YOUR_USERNAME`
