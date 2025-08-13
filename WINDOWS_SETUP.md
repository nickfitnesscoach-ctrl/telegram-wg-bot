# 🪟 **WINDOWS DEVELOPMENT SETUP**

## 🚀 **Быстрая настройка для разработки на Windows**

### **Шаг 1: Создайте .env файл**

```bash
# Скопируйте Windows-совместимый шаблон
copy env.windows.example .env
```

Или создайте `.env` файл вручную с содержимым:
```env
BOT_TOKEN=your_bot_token_here
ALLOWED_USERS=123456789
MAX_COMMANDS_PER_MINUTE=10
SERVER_IP=127.0.0.1
WG_MANAGER_PATH=python mock-wg-manager.py
WG_CLIENTS_PATH=./mock-clients/
```

### **Шаг 2: Установите зависимости**

```bash
# Создайте виртуальное окружение
python -m venv venv

# Активируйте его
venv\Scripts\activate

# Установите зависимости
pip install -r requirements.txt
```

### **Шаг 3: Тест совместимости**

```bash
# Быстрый тест импортов
python test_windows.py
```

**Ожидаемый вывод:**
```
🚀 Windows Compatibility Test
========================================
🧪 Testing imports...
✅ Settings imported successfully
✅ FastRateLimit imported successfully
✅ GlobalErrorHandler imported successfully
✅ FastAuthMiddleware imported successfully
✅ AuditMiddleware imported successfully
✅ TelegramUtils imported successfully

⚙️ Testing settings...
✅ Rate limit: 10/min
✅ Command timeout: 30s
✅ Max clients: 50
✅ Log level: INFO

🔧 Testing middleware creation...
✅ FastRateLimit created
✅ GlobalErrorHandler created
✅ FastAuthMiddleware created
✅ AuditMiddleware created

========================================
📊 Results: 3/3 tests passed
🎉 All tests passed! Windows compatibility OK
```

### **Шаг 4: Запуск бота (с моками)**

```bash
# Основной способ
python main.py

# Как модуль
python -m src
```

---

## 🔧 **Устранение проблем**

### **Проблема: OSError [Errno 22] Invalid argument**

**Причина:** Некорректные символы в .env файле на Windows

**Решение:**
1. Удалите существующий `.env` файл
2. Используйте `env.windows.example` как шаблон
3. Убедитесь что в .env нет символов `__` в значениях

### **Проблема: ImportError**

**Причина:** Неправильные пути или отсутствующие зависимости

**Решение:**
```bash
# Переустановите зависимости
pip uninstall -r requirements.txt -y
pip install -r requirements.txt

# Проверьте Python версию
python --version  # Должно быть 3.8+
```

### **Проблема: ModuleNotFoundError**

**Причина:** Неправильная структура пакетов

**Решение:**
```bash
# Запускайте из корневой директории проекта
cd C:\path\to\telegram-wg-bot
python main.py
```

---

## 📝 **Windows-специфичные настройки**

### **Environment Variables (.env):**
```env
# Используйте обратные слеши для Windows путей (но лучше прямые)
WG_CLIENTS_PATH=./mock-clients/

# Логи в текущую директорию
LOG_FILE=./logs/bot.log

# Mock команды для разработки
WG_MANAGER_PATH=python mock-wg-manager.py
```

### **Создание mock-wg-manager.py:**
```python
#!/usr/bin/env python3
"""Mock WireGuard manager for Windows development"""
import sys
import json

if len(sys.argv) < 2:
    print("Usage: mock-wg-manager.py <command>")
    sys.exit(1)

command = sys.argv[1]

if command == "status":
    print("✅ WireGuard mock is running")
elif command == "list": 
    print("test_client 10.0.0.2")
elif command == "add":
    client_name = sys.argv[2] if len(sys.argv) > 2 else "default"
    print(f"✅ Mock client {client_name} added")
elif command == "remove":
    client_name = sys.argv[2] if len(sys.argv) > 2 else "default"
    print(f"✅ Mock client {client_name} removed")
elif command == "export":
    client_name = sys.argv[2] if len(sys.argv) > 2 else "default"
    print(f"""[Interface]
PrivateKey = mock_private_key
Address = 10.0.0.2/32
DNS = 1.1.1.1

[Peer]
PublicKey = mock_server_public_key
Endpoint = 127.0.0.1:51820
AllowedIPs = 0.0.0.0/0""")
else:
    print(f"Unknown command: {command}")
    sys.exit(1)
```

---

## ✅ **Готовность к разработке**

После выполнения всех шагов у вас должно быть:

- ✅ Рабочий .env файл
- ✅ Установленные зависимости  
- ✅ Успешный тест совместимости
- ✅ Возможность запуска бота с моками

**Бот готов к разработке на Windows!** 🎉
