"""
System commands handlers for Telegram WireGuard Bot
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from ...services.wg_manager import WireGuardManager
from ...services.health_checker import health_checker
from ...bot.utils.formatters import MessageFormatter
from ...bot.middlewares.logging import monitor_performance, LoggingHelper
from ...database.models import get_db_session, CommandLog, User

# Create router for system commands
router = Router(name='system')

# Initialize services
wg_manager = WireGuardManager()
# health_checker imported from module
logger = logging.getLogger(__name__)


@router.message(Command('start'))
@monitor_performance('start_command')
async def cmd_start(message: Message, **kwargs) -> None:
    """
    Start command - welcome message
    """
    try:
        user = kwargs.get('user')
        
        welcome_text = (
            f"👋 <b>Добро пожаловать, {user.first_name if user else 'пользователь'}!</b>\n\n"
            f"🤖 <b>Telegram WireGuard Bot</b> готов к работе.\n\n"
            f"🔐 <b>Ваш статус:</b> {'👑 Администратор' if user and user.is_admin else '👤 Пользователь'}\n\n"
            f"💡 Используйте /help для списка доступных команд."
        )
        
        await message.answer(welcome_text, parse_mode="HTML")
        
        if user:
            LoggingHelper.log_vpn_operation(
                user_id=user.telegram_id,
                operation='start',
                success=True
            )
        
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await message.answer(
            "⚠️ Произошла ошибка при обработке команды",
            parse_mode="HTML"
        )


@router.message(Command('help'))
@monitor_performance('help_command')
async def cmd_help(message: Message, **kwargs) -> None:
    """
    Help command - show available commands
    Implements TZ section 3.4: help with examples
    """
    try:
        user = kwargs.get('user')
        help_text = MessageFormatter.format_help_message()
        
        # Add admin commands if user is admin
        if user and user.is_admin:
            admin_commands = (
                "\n<b>👑 Команды администратора:</b>\n"
                "• <code>/restart</code> - Перезапуск WireGuard\n"
                "• <code>/cleanup</code> - Очистка старых логов\n"
                "• <code>/health</code> - Детальная проверка системы"
            )
            help_text += admin_commands
        
        await message.answer(help_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await message.answer(
            MessageFormatter.format_error_message('system_error', str(e)),
            parse_mode="HTML"
        )


@router.message(Command('about'))
@monitor_performance('about_command')
async def cmd_about(message: Message, **kwargs) -> None:
    """
    About command - bot information
    Implements TZ section 3.4: information about bot and system
    """
    try:
        about_text = MessageFormatter.format_about_message()
        await message.answer(about_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error in about command: {e}")
        await message.answer(
            MessageFormatter.format_error_message('system_error', str(e)),
            parse_mode="HTML"
        )


@router.message(Command('status'))
@monitor_performance('status_command')
async def cmd_status(message: Message, **kwargs) -> None:
    """
    System status command
    Implements TZ section 3.3: server status with formatted output
    """
    try:
        user = kwargs.get('user')
        # Show loading message
        status_msg = await message.answer(
            "⏳ <b>Получение статуса системы...</b>",
            parse_mode="HTML"
        )
        
        # Get system status
        system_status = await wg_manager.get_system_status()
        
        # Format and send status
        status_text = MessageFormatter.format_system_status(system_status)
        
        await status_msg.edit_text(status_text, parse_mode="HTML")
        
        if user:
            LoggingHelper.log_vpn_operation(
                user_id=user.telegram_id,
                operation='get_status',
                success=True
            )
        
    except Exception as e:
        logger.error(f"Error in status command: {e}")
        await message.answer(
            MessageFormatter.format_error_message('system_error', str(e)),
            parse_mode="HTML"
        )


@router.message(Command('logs'))
@monitor_performance('logs_command')
async def cmd_logs(message: Message, **kwargs) -> None:
    """
    Show command logs
    Implements TZ section 3.3: logs with filtering
    """
    try:
        user = kwargs.get('user')
        # Parse arguments for log count
        args = message.text.split()[1:] if message.text else []
        log_count = 10  # Default
        
        if args:
            try:
                log_count = min(int(args[0]), 50)  # Max 50 logs
            except ValueError:
                await message.answer(
                    "❌ <b>Неверный формат</b>\n\n"
                    "📝 <b>Использование:</b> <code>/logs [количество]</code>\n"
                    "💡 <b>Пример:</b> <code>/logs 20</code>",
                    parse_mode="HTML"
                )
                return
        
        # Get logs from database
        if user:
            logs = await get_recent_command_logs(user.telegram_id, log_count)
        else:
            logs = []
        
        # Format and send logs
        logs_text = MessageFormatter.format_logs(logs, log_count)
        
        await message.answer(logs_text, parse_mode="HTML")
        
        if user:
            LoggingHelper.log_vpn_operation(
                user_id=user.telegram_id,
                operation='get_logs',
                success=True,
                log_count=len(logs)
            )
        
    except Exception as e:
        logger.error(f"Error in logs command: {e}")
        await message.answer(
            MessageFormatter.format_error_message('system_error', str(e)),
            parse_mode="HTML"
        )


# Helper functions

async def get_recent_command_logs(user_telegram_id: int, count: int) -> List[Dict[str, Any]]:
    """Get recent command logs for user"""
    try:
        async with await get_db_session() as session:
            from sqlalchemy import select, desc
            
            # Get user
            user_result = await session.execute(
                select(User).where(User.telegram_id == user_telegram_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                return []
            
            # Get recent command logs
            result = await session.execute(
                select(CommandLog)
                .where(CommandLog.user_id == user.id)
                .order_by(desc(CommandLog.created_at))
                .limit(count)
            )
            
            command_logs = result.scalars().all()
            
            # Convert to dict format
            logs = []
            for log in command_logs:
                logs.append({
                    'command': log.command,
                    'status': log.status,
                    'created_at': log.created_at,
                    'execution_time_ms': log.execution_time_ms,
                    'error_message': log.error_message,
                    'user_id': user.telegram_id,
                    'username': user.username
                })
            
            return logs
            
    except Exception as e:
        logger.error(f"Error getting command logs: {e}")
        return []


async def get_system_metrics() -> Dict[str, Any]:
    """Get system metrics for status display"""
    try:
        # Get health data
        health_data = await health_checker.perform_health_check()
        
        # Get WireGuard specific data
        clients = await wg_manager.list_clients()
        active_clients = len([c for c in clients if c.get('is_active', True)])
        
        return {
            'wireguard_status': health_data.get('wireguard', {}).get('status', 'unknown'),
            'active_clients': active_clients,
            'total_clients': len(clients),
            'uptime_seconds': health_data.get('process', {}).get('create_time', datetime.now()),
            'disk_used_gb': health_data.get('disk_space', {}).get('used_gb', 0),
            'disk_total_gb': health_data.get('disk_space', {}).get('total_gb', 50),
            'memory_usage_mb': health_data.get('memory', {}).get('usage_percent', 0),
            'cpu_usage_percent': health_data.get('cpu', {}).get('usage_percent', 0),
            'traffic_today_gb': 0  # Will be implemented with actual traffic monitoring
        }
        
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        return {
            'wireguard_status': 'error',
            'active_clients': 0,
            'total_clients': 0,
            'uptime_seconds': 0,
            'disk_used_gb': 0,
            'disk_total_gb': 50,
            'memory_usage_mb': 0,
            'cpu_usage_percent': 0,
            'traffic_today_gb': 0
        }
