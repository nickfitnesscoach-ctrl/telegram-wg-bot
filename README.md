# Telegram WireGuard Bot

Telegram бот для управления WireGuard VPN сервером.

## Локальная установка

```bash
pip install -r requirements.txt
set BOT_TOKEN=123:ABC   # Windows
python -m src
```

## Deployment

См. [ULTIMATE_DEPLOYMENT_GUIDE.md](ULTIMATE_DEPLOYMENT_GUIDE.md) для полных инструкций по развертыванию.

## Важно

- `.env` не коммитим
- Все секреты — через EnvironmentFile 
- Запуск только через `python -m src`

## Поддержка

- Python 3.8+
- aiogram 3.10.0
- SQLite база данных