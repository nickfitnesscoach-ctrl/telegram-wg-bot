"""
Admin commands handlers for Telegram WireGuard Bot
"""
import logging
from datetime import datetime
from typing import List, Dict, Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram import F

from ...services.wg_manager import WireGuardManager
from ...services.backup_service import BackupService, BackupHelper
from ...services.health_checker import health_checker
from ...bot.utils.formatters import MessageFormatter, ProgressFormatter
from ...bot.middlewares.auth import require_admin
from ...bot.middlewares.logging import monitor_performance, LoggingHelper
from ...database.models import get_db_session, CommandLog, BackupRecord

# Create router for admin commands
router = Router(name='admin')

# Initialize services
wg_manager = WireGuardManager()
backup_service = BackupService()
# health_checker imported from module
logger = logging.getLogger(__name__)


@router.message(Command('backup'))
@require_admin
@monitor_performance('backup_command')
async def cmd_backup(message: Message, **kwargs) -> None:
    """
    Create backup command
    Implements TZ section 3.4: backup functionality
    """
    try:
        user = kwargs.get('user')
        if not user:
            await message.answer("⚠️ Ошибка авторизации")
            return
            
        # Show progress
        progress_msg = await message.answer(
            ProgressFormatter.format_loading_message("Создание резервной копии"),
            parse_mode="HTML"
        )
        
        # Create backup
        success, result_msg, backup_id = await backup_service.create_backup('manual', user.telegram_id)
        
        if success:
            await progress_msg.edit_text(
                MessageFormatter.format_success_message(
                    'backup_created',
                    f"Резервная копия создана: <code>{backup_id}</code>\n\n"
                    f"📋 Используйте /restore для восстановления"
                ),
                parse_mode="HTML"
            )
            
            LoggingHelper.log_system_operation(
                operation='create_backup',
                success=True,
                backup_id=backup_id
            )
        else:
            await progress_msg.edit_text(
                MessageFormatter.format_error_message('system_error', result_msg),
                parse_mode="HTML"
            )
            
            LoggingHelper.log_system_operation(
                operation='create_backup',
                success=False,
                error=result_msg
            )
        
    except Exception as e:
        logger.error(f"Error in backup command: {e}")
        await message.answer(
            MessageFormatter.format_error_message('system_error', str(e)),
            parse_mode="HTML"
        )


@router.message(Command('restore'))
@require_admin
@monitor_performance('restore_command')
async def cmd_restore(message: Message, **kwargs) -> None:
    """
    Restore from backup command
    Implements TZ section 3.4: restore with backup list
    """
    try:
        user = kwargs.get('user')
        if not user:
            await message.answer("⚠️ Ошибка авторизации")
            return
            
        # Get available backups
        backups = await backup_service.list_backups()
        
        if not backups:
            await message.answer(
                "📋 <b>Нет доступных резервных копий</b>\n\n"
                "💡 Используйте /backup для создания резервной копии",
                parse_mode="HTML"
            )
            return
        
        # Create keyboard with backup options
        keyboard_buttons = []
        
        for i, backup in enumerate(backups[:10]):  # Show max 10 backups
            backup_age = BackupHelper.get_backup_age_string(backup['created_at'])
            backup_size = BackupHelper.format_file_size(backup['size_bytes'])
            
            button_text = f"{backup['type']} ({backup_age}, {backup_size})"
            callback_data = f"restore:{backup['id']}"
            
            keyboard_buttons.append([
                InlineKeyboardButton(text=button_text, callback_data=callback_data)
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="❌ Отмена", callback_data="restore_cancel")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        backup_list_text = (
            "📋 <b>Доступные резервные копии</b>\n\n"
            "Выберите резервную копию для восстановления:\n\n"
            "⚠️ <b>Внимание!</b> Восстановление заменит текущие конфигурации."
        )
        
        await message.answer(
            backup_list_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in restore command: {e}")
        await message.answer(
            MessageFormatter.format_error_message('system_error', str(e)),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith('restore:'))
async def callback_restore_confirm(callback: CallbackQuery, user) -> None:
    """Handle backup restore confirmation"""
    try:
        backup_id = callback.data.split(':', 1)[1]
        
        # Get backup info
        backup_info = await backup_service.get_backup_info(backup_id)
        
        if not backup_info:
            await callback.message.edit_text(
                "❌ Резервная копия не найдена",
                parse_mode="HTML"
            )
            await callback.answer()
            return
        
        # Show final confirmation
        confirmation_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, восстановить", callback_data=f"restore_execute:{backup_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="restore_cancel")
            ]
        ])
        
        backup_age = BackupHelper.get_backup_age_string(backup_info['created_at'])
        backup_size = BackupHelper.format_file_size(backup_info['size_bytes'])
        
        confirmation_text = (
            f"📋 <b>Подтверждение восстановления</b>\n\n"
            f"<b>Резервная копия:</b> {backup_info['id']}\n"
            f"<b>Тип:</b> {backup_info['type']}\n"
            f"<b>Создана:</b> {backup_age}\n"
            f"<b>Размер:</b> {backup_size}\n\n"
            f"⚠️ <b>Внимание!</b>\n"
            f"Текущие конфигурации будут заменены.\n"
            f"Автоматически будет создана резервная копия перед восстановлением.\n\n"
            f"Продолжить?"
        )
        
        await callback.message.edit_text(
            confirmation_text,
            parse_mode="HTML",
            reply_markup=confirmation_keyboard
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in restore confirmation: {e}")
        await callback.message.edit_text(
            MessageFormatter.format_error_message('system_error', str(e)),
            parse_mode="HTML"
        )
        await callback.answer()


@router.callback_query(F.data.startswith('restore_execute:'))
async def callback_restore_execute(callback: CallbackQuery, user) -> None:
    """Execute backup restore"""
    try:
        backup_id = callback.data.split(':', 1)[1]
        
        # Show progress
        await callback.message.edit_text(
            ProgressFormatter.format_loading_message("Восстановление из резервной копии"),
            parse_mode="HTML"
        )
        
        # Execute restore
        success, result_msg = await backup_service.restore_backup(backup_id, user.telegram_id)
        
        if success:
            await callback.message.edit_text(
                MessageFormatter.format_success_message(
                    'backup_restored',
                    f"Конфигурация восстановлена из резервной копии.\n\n"
                    f"📋 Используйте /status для проверки системы"
                ),
                parse_mode="HTML"
            )
            
            LoggingHelper.log_system_operation(
                operation='restore_backup',
                success=True,
                backup_id=backup_id
            )
        else:
            await callback.message.edit_text(
                MessageFormatter.format_error_message('system_error', result_msg),
                parse_mode="HTML"
            )
            
            LoggingHelper.log_system_operation(
                operation='restore_backup',
                success=False,
                error=result_msg,
                backup_id=backup_id
            )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error executing restore: {e}")
        await callback.message.edit_text(
            MessageFormatter.format_error_message('system_error', str(e)),
            parse_mode="HTML"
        )
        await callback.answer()


@router.callback_query(F.data == 'restore_cancel')
async def callback_restore_cancel(callback: CallbackQuery) -> None:
    """Handle restore cancellation"""
    await callback.message.edit_text(
        "❌ <b>Восстановление отменено</b>\n\n"
        "💡 Используйте /backup для создания новой резервной копии",
        parse_mode="HTML"
    )
    await callback.answer("Восстановление отменено")


@router.message(Command('restart'))
@require_admin
@monitor_performance('restart_command')
async def cmd_restart(message: Message, **kwargs) -> None:
    """
    Restart WireGuard service
    Admin-only command for service management
    """
    try:
        user = kwargs.get('user')
        if not user:
            await message.answer("⚠️ Ошибка авторизации")
            return
            
        # Show confirmation
        confirmation_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, перезапустить", callback_data="restart_confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="restart_cancel")
            ]
        ])
        
        await message.answer(
            "⚠️ <b>Подтверждение перезапуска</b>\n\n"
            "Вы действительно хотите перезапустить WireGuard сервис?\n"
            "Это временно прервет все VPN подключения.",
            parse_mode="HTML",
            reply_markup=confirmation_keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in restart command: {e}")
        await message.answer(
            MessageFormatter.format_error_message('system_error', str(e)),
            parse_mode="HTML"
        )


@router.callback_query(F.data == 'restart_confirm')
async def callback_restart_confirm(callback: CallbackQuery, user) -> None:
    """Execute WireGuard restart"""
    try:
        # Show progress
        await callback.message.edit_text(
            ProgressFormatter.format_loading_message("Перезапуск WireGuard"),
            parse_mode="HTML"
        )
        
        # Execute restart
        success, result_msg = await wg_manager.restart_wireguard()
        
        if success:
            await callback.message.edit_text(
                "✅ <b>WireGuard перезапущен</b>\n\n"
                "🔄 Сервис успешно перезапущен.\n"
                "💡 Используйте /status для проверки состояния.",
                parse_mode="HTML"
            )
            
            LoggingHelper.log_system_operation(
                operation='restart_wireguard',
                success=True
            )
        else:
            await callback.message.edit_text(
                MessageFormatter.format_error_message('system_error', result_msg),
                parse_mode="HTML"
            )
            
            LoggingHelper.log_system_operation(
                operation='restart_wireguard',
                success=False,
                error=result_msg
            )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error restarting WireGuard: {e}")
        await callback.message.edit_text(
            MessageFormatter.format_error_message('system_error', str(e)),
            parse_mode="HTML"
        )
        await callback.answer()


@router.callback_query(F.data == 'restart_cancel')
async def callback_restart_cancel(callback: CallbackQuery) -> None:
    """Handle restart cancellation"""
    await callback.message.edit_text(
        "❌ <b>Перезапуск отменен</b>\n\n"
        "💡 Используйте /status для проверки текущего состояния",
        parse_mode="HTML"
    )
    await callback.answer("Перезапуск отменен")


@router.message(Command('health'))
@require_admin
@monitor_performance('health_command')
async def cmd_health(message: Message, **kwargs) -> None:
    """
    Detailed health check command
    Admin-only command for system diagnostics
    """
    try:
        user = kwargs.get('user')
        if not user:
            await message.answer("⚠️ Ошибка авторизации")
            return
            
        # Show progress
        health_msg = await message.answer(
            ProgressFormatter.format_loading_message("Проверка состояния системы"),
            parse_mode="HTML"
        )
        
        # Perform detailed health check
        health_data = await health_checker.perform_health_check()
        
        # Format detailed health report
        health_report = format_detailed_health_report(health_data)
        
        await health_msg.edit_text(health_report, parse_mode="HTML")
        
        LoggingHelper.log_system_operation(
            operation='health_check',
            success=True
        )
        
    except Exception as e:
        logger.error(f"Error in health command: {e}")
        await message.answer(
            MessageFormatter.format_error_message('system_error', str(e)),
            parse_mode="HTML"
        )


@router.message(Command('cleanup'))
@require_admin
@monitor_performance('cleanup_command')
async def cmd_cleanup(message: Message, **kwargs) -> None:
    """
    Cleanup old logs and backups
    Admin-only maintenance command
    """
    try:
        user = kwargs.get('user')
        if not user:
            await message.answer("⚠️ Ошибка авторизации")
            return
            
        # Show progress
        cleanup_msg = await message.answer(
            ProgressFormatter.format_loading_message("Очистка системы"),
            parse_mode="HTML"
        )
        
        # Cleanup old backups
        deleted_backups, freed_space = await backup_service.cleanup_old_backups()
        freed_space_str = BackupHelper.format_file_size(freed_space)
        
        cleanup_report = (
            "🧹 <b>Очистка завершена</b>\n\n"
            f"📦 <b>Резервные копии:</b> удалено {deleted_backups} файлов\n"
            f"💾 <b>Освобождено места:</b> {freed_space_str}\n\n"
            "✅ Система очищена от устаревших данных"
        )
        
        await cleanup_msg.edit_text(cleanup_report, parse_mode="HTML")
        
        LoggingHelper.log_system_operation(
            operation='cleanup',
            success=True,
            deleted_backups=deleted_backups,
            freed_space_bytes=freed_space
        )
        
    except Exception as e:
        logger.error(f"Error in cleanup command: {e}")
        await message.answer(
            MessageFormatter.format_error_message('system_error', str(e)),
            parse_mode="HTML"
        )


# Helper functions

def format_detailed_health_report(health_data: Dict[str, Any]) -> str:
    """Format detailed health report for admin"""
    if 'error' in health_data:
        return f"❌ <b>Ошибка проверки здоровья</b>\n\n{health_data['error']}"
    
    # WireGuard status
    wg_data = health_data.get('wireguard', {})
    wg_status = wg_data.get('status', 'unknown')
    wg_emoji = "🟢" if wg_status == 'healthy' else "🔴"
    
    # Disk status
    disk_data = health_data.get('disk_space', {})
    disk_status = disk_data.get('status', 'unknown')
    disk_emoji = "🟢" if disk_status == 'healthy' else "🔴"
    
    # Memory status
    memory_data = health_data.get('memory', {})
    memory_status = memory_data.get('status', 'unknown')
    memory_emoji = "🟢" if memory_status == 'healthy' else "🔴"
    
    # CPU status
    cpu_data = health_data.get('cpu', {})
    cpu_status = cpu_data.get('status', 'unknown')
    cpu_emoji = "🟢" if cpu_status == 'healthy' else "🔴"
    
    timestamp = health_data.get('timestamp', datetime.now()).strftime("%H:%M:%S")
    
    return (
        f"🏥 <b>Детальная проверка системы</b>\n\n"
        f"{wg_emoji} <b>WireGuard:</b> {wg_status}\n"
        f"   Сервис активен: {wg_data.get('service_active', 'unknown')}\n\n"
        f"{disk_emoji} <b>Диск:</b> {disk_status}\n"
        f"   Свободно: {disk_data.get('free_gb', 0):.1f}GB\n"
        f"   Использовано: {disk_data.get('usage_percent', 0):.1f}%\n\n"
        f"{memory_emoji} <b>Память:</b> {memory_status}\n"
        f"   Использование: {memory_data.get('usage_percent', 0):.1f}%\n\n"
        f"{cpu_emoji} <b>CPU:</b> {cpu_status}\n"
        f"   Загрузка: {cpu_data.get('usage_percent', 0):.1f}%\n\n"
        f"⏰ <b>Проверено:</b> {timestamp}"
    )
