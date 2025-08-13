"""
Output formatting utilities for Telegram WireGuard Bot
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
# import humanize  # Commented out - not critical

from ...config.settings import settings


class MessageFormatter:
    """Formatter for Telegram messages"""
    
    @staticmethod
    def format_client_list(clients: List[Dict[str, Any]], current_count: int) -> str:
        """
        Format client list for /list command
        Implements TZ format from section 3.2
        """
        if not clients:
            return (
                "📋 <b>Список VPN-клиентов</b>\n\n"
                "❌ Нет активных клиентов\n\n"
                "💡 Используйте /newconfig &lt;имя&gt; для создания нового клиента"
            )
        
        header = f"📋 <b>Активные VPN-клиенты ({current_count}/{settings.MAX_CLIENTS})</b>\n\n"
        
        client_lines = []
        for i, client in enumerate(clients, 1):
            created_date = MessageFormatter._format_date(client.get('created_at'))
            status_emoji = "🟢" if client.get('is_active') else "🔴"
            
            client_lines.append(
                f"{MessageFormatter._number_emoji(i)} {status_emoji} <b>{client['name']}</b> "
                f"(создан: {created_date})"
            )
        
        footer = (
            "\n\n💾 Используйте <code>/getconfig &lt;номер&gt;</code> для получения конфига\n"
            "🗑 Используйте <code>/delete &lt;номер&gt;</code> для удаления"
        )
        
        return header + "\n".join(client_lines) + footer
    
    @staticmethod
    def format_system_status(status_data: Dict[str, Any]) -> str:
        """
        Format system status for /status command
        Implements TZ format from section 3.3
        """
        wg_status = status_data.get('wireguard_status', 'unknown')
        status_emoji = "🟢" if wg_status == 'active' else "🔴"
        
        # Format uptime
        uptime_seconds = status_data.get('uptime_seconds', 0)
        uptime_str = MessageFormatter._format_uptime(uptime_seconds)
        
        # Format traffic
        traffic_today = status_data.get('traffic_today_gb', 0)
        
        # Format disk usage
        disk_used = status_data.get('disk_used_gb', 0)
        disk_total = status_data.get('disk_total_gb', 50)
        
        # Last check time
        last_check = datetime.now().strftime("%H:%M:%S")
        
        return (
            f"{status_emoji} <b>WireGuard VPN Status</b>\n\n"
            f"📊 <b>Сервер:</b> {settings.SERVER_IP}:{settings.VPN_PORT}\n"
            f"👥 <b>Клиенты:</b> {status_data.get('active_clients', 0)}/{settings.MAX_CLIENTS}\n"
            f"💾 <b>Использование диска:</b> {disk_used:.1f}GB/{disk_total}GB\n"
            f"🔄 <b>Время работы:</b> {uptime_str}\n"
            f"📈 <b>Трафик сегодня:</b> {traffic_today:.1f}GB\n\n"
            f"⚙️ <b>Последняя проверка:</b> {last_check}"
        )
    
    @staticmethod
    def format_client_info(client_data: Dict[str, Any]) -> str:
        """Format detailed client information"""
        created_date = MessageFormatter._format_date(client_data.get('created_at'))
        last_connected = client_data.get('last_connected')
        last_connected_str = (
            MessageFormatter._format_date(last_connected) 
            if last_connected else "Никогда"
        )
        
        # Format traffic
        bytes_sent = client_data.get('bytes_sent', 0)
        bytes_received = client_data.get('bytes_received', 0)
        
        return (
            f"📱 <b>Информация о клиенте</b>\n\n"
            f"🏷 <b>Имя:</b> {client_data['name']}\n"
            f"🌐 <b>IP адрес:</b> <code>{client_data.get('ip_address')}</code>\n"
            f"📅 <b>Создан:</b> {created_date}\n"
            f"🔌 <b>Последнее подключение:</b> {last_connected_str}\n"
            f"📊 <b>Отправлено:</b> {MessageFormatter._format_bytes(bytes_sent)}\n"
            f"📊 <b>Получено:</b> {MessageFormatter._format_bytes(bytes_received)}\n"
            f"✅ <b>Статус:</b> {'Активен' if client_data.get('is_active') else 'Неактивен'}"
        )
    
    @staticmethod
    def format_logs(logs: List[Dict[str, Any]], count: int) -> str:
        """Format command logs for /logs command"""
        if not logs:
            return "📜 <b>Логи операций</b>\n\n❌ Нет записей"
        
        header = f"📜 <b>Последние {count} операций</b>\n\n"
        
        log_lines = []
        for log in logs:
            timestamp = MessageFormatter._format_time(log.get('created_at'))
            status_emoji = "✅" if log.get('status') == 'success' else "❌"
            command = log.get('command', 'unknown')
            user = log.get('username', f"user_{log.get('user_id', 'unknown')}")
            
            log_lines.append(
                f"{status_emoji} <code>{timestamp}</code> {command} - {user}"
            )
        
        return header + "\n".join(log_lines)
    
    @staticmethod
    def format_help_message() -> str:
        """Format help message with all available commands"""
        return (
            "🤖 <b>Telegram WireGuard Bot</b>\n\n"
            "<b>📱 Управление клиентами:</b>\n"
            "• <code>/newconfig &lt;имя&gt;</code> - Создать новую конфигурацию\n"
            "• <code>/list</code> - Список всех клиентов\n"
            "• <code>/getconfig &lt;номер&gt;</code> - Получить конфигурацию\n"
            "• <code>/delete &lt;номер&gt;</code> - Удалить клиента\n\n"
            "<b>📊 Мониторинг:</b>\n"
            "• <code>/status</code> - Статус системы\n"
            "• <code>/logs [количество]</code> - Логи операций\n\n"
            "<b>🔧 Администрирование:</b>\n"
            "• <code>/backup</code> - Создать резервную копию\n"
            "• <code>/restore</code> - Восстановить из копии\n\n"
            "<b>ℹ️ Информация:</b>\n"
            "• <code>/help</code> - Эта справка\n"
            "• <code>/about</code> - О боте\n\n"
            "💡 <b>Пример:</b> <code>/newconfig iPhone-John</code>"
        )
    
    @staticmethod
    def format_about_message() -> str:
        """Format about message with bot information"""
        return (
            "🤖 <b>Telegram WireGuard Bot</b>\n\n"
            "🔧 <b>Версия:</b> 1.0.0\n"
            f"🌐 <b>Сервер:</b> {settings.SERVER_IP}\n"
            f"👥 <b>Максимум клиентов:</b> {settings.MAX_CLIENTS}\n"
            f"⏱ <b>Лимит команд:</b> {settings.MAX_COMMANDS_PER_MINUTE}/мин\n\n"
            "📋 <b>Возможности:</b>\n"
            "• Автоматическое управление WireGuard\n"
            "• QR-коды для быстрой настройки\n"
            "• Мониторинг подключений\n"
            "• Резервное копирование\n"
            "• Аудит операций\n\n"
            "🛡 <b>Безопасность:</b>\n"
            "• Авторизация по whitelist\n"
            "• Rate limiting\n"
            "• Полное логирование\n\n"
            "💡 Используйте /help для списка команд"
        )
    
    @staticmethod
    def format_error_message(error_type: str, details: str = None) -> str:
        """Format error messages consistently"""
        error_messages = {
            'unauthorized': (
                "🚫 <b>Доступ запрещен</b>\n\n"
                "У вас нет прав для использования этого бота."
            ),
            'rate_limit': (
                f"⏱️ <b>Превышен лимит команд</b>\n\n"
                f"Максимум {settings.MAX_COMMANDS_PER_MINUTE} команд в минуту."
            ),
            'invalid_command': (
                "❌ <b>Неверная команда</b>\n\n"
                "Используйте /help для списка доступных команд."
            ),
            'system_error': (
                "⚠️ <b>Системная ошибка</b>\n\n"
                "Произошла ошибка при выполнении операции."
            ),
            'wg_error': (
                "🔧 <b>Ошибка WireGuard</b>\n\n"
                "Не удалось выполнить операцию с VPN сервером."
            )
        }
        
        base_message = error_messages.get(error_type, error_messages['system_error'])
        
        if details:
            return f"{base_message}\n\n<b>Детали:</b> {details}"
        
        return base_message
    
    @staticmethod
    def format_success_message(operation: str, details: str = None) -> str:
        """Format success messages consistently"""
        success_messages = {
            'config_created': "✅ <b>Конфигурация создана</b>",
            'config_deleted': "✅ <b>Конфигурация удалена</b>",
            'backup_created': "✅ <b>Резервная копия создана</b>",
            'backup_restored': "✅ <b>Конфигурация восстановлена</b>",
            'operation_completed': "✅ <b>Операция выполнена</b>"
        }
        
        base_message = success_messages.get(operation, success_messages['operation_completed'])
        
        if details:
            return f"{base_message}\n\n{details}"
        
        return base_message
    
    # Helper methods
    
    @staticmethod
    def _format_date(date_obj) -> str:
        """Format date for display"""
        if not date_obj:
            return "Неизвестно"
        
        if isinstance(date_obj, str):
            try:
                date_obj = datetime.fromisoformat(date_obj.replace('Z', '+00:00'))
            except:
                return date_obj
        
        return date_obj.strftime("%d.%m.%Y")
    
    @staticmethod
    def _format_time(datetime_obj) -> str:
        """Format datetime for display"""
        if not datetime_obj:
            return "Неизвестно"
        
        if isinstance(datetime_obj, str):
            try:
                datetime_obj = datetime.fromisoformat(datetime_obj.replace('Z', '+00:00'))
            except:
                return datetime_obj
        
        return datetime_obj.strftime("%H:%M")
    
    @staticmethod
    def _format_uptime(seconds: int) -> str:
        """Format uptime in human-readable format"""
        if seconds < 60:
            return f"{seconds} сек"
        elif seconds < 3600:
            return f"{seconds // 60} мин"
        elif seconds < 86400:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours} ч {minutes} мин"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            return f"{days} дн {hours} ч"
    
    @staticmethod
    def _format_bytes(bytes_count: int) -> str:
        """Format bytes in human-readable format"""
        if bytes_count == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.1f} {unit}"
            bytes_count /= 1024.0
        
        return f"{bytes_count:.1f} PB"
    
    @staticmethod
    def _number_emoji(number: int) -> str:
        """Convert number to emoji"""
        emoji_map = {
            1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣",
            6: "6️⃣", 7: "7️⃣", 8: "8️⃣", 9: "9️⃣", 10: "🔟"
        }
        
        return emoji_map.get(number, f"{number}️⃣")


class ProgressFormatter:
    """Formatter for progress indicators"""
    
    @staticmethod
    def format_progress_bar(current: int, total: int, width: int = 10) -> str:
        """Create progress bar"""
        if total == 0:
            return "█" * width
        
        filled = int((current / total) * width)
        bar = "█" * filled + "░" * (width - filled)
        percentage = (current / total) * 100
        
        return f"{bar} {percentage:.1f}%"
    
    @staticmethod
    def format_loading_message(operation: str) -> str:
        """Format loading message"""
        return f"⏳ <b>{operation}...</b>\n\nПожалуйста, подождите."


class ConfigFileFormatter:
    """Formatter for WireGuard configuration files"""
    
    @staticmethod
    def format_instructions(client_name: str) -> str:
        """Format setup instructions for client"""
        return (
            f"📱 <b>Инструкции для {client_name}</b>\n\n"
            "<b>🔧 Способ 1 - QR-код:</b>\n"
            "1. Установите WireGuard на устройство\n"
            "2. Отсканируйте QR-код выше\n"
            "3. Активируйте подключение\n\n"
            "<b>📁 Способ 2 - Файл конфигурации:</b>\n"
            "1. Скачайте файл .conf\n"
            "2. Импортируйте в приложение WireGuard\n"
            "3. Активируйте подключение\n\n"
            "<b>📱 Приложения WireGuard:</b>\n"
            "• Android: Google Play Store\n"
            "• iOS: App Store\n"
            "• Windows: wireguard.com\n"
            "• macOS: App Store\n\n"
            "❓ Нужна помощь? Используйте /help"
        )