# Telegram WireGuard Bot

Telegram бот для управления WireGuard VPN сервером.

## Локальная установка

```bash
# Установка зависимостей
pip install -r requirements.txt

# Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env файл с вашими настройками

# Запуск
python -m src
```

## Переменные окружения

- `BOT_TOKEN` - токен Telegram бота от @BotFather
- `ALLOWED_USERS` - список ID пользователей (через запятую)
- `RATE_LIMIT_PER_MIN` - лимит команд в минуту (по умолчанию 10)
- `LOG_LEVEL` - уровень логирования (INFO, DEBUG, ERROR)

## Deployment

См. [ULTIMATE_DEPLOYMENT_GUIDE.md](ULTIMATE_DEPLOYMENT_GUIDE.md) для полных инструкций по развертыванию на production сервере.

## Важно

- `.env` не коммитим в git
- Все секреты только через переменные окружения
- Запуск только через `python -m src`

## Поддержка

- Python 3.8+
- aiogram 3.10.0
- SQLite база данных