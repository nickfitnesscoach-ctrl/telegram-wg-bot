"""
VPN commands handlers for Telegram WireGuard Bot
"""
import logging
import tempfile
from io import BytesIO
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from ...services.wg_manager import WireGuardManager
from ...services.backup_service import BackupService
from ...bot.utils.validators import CommandValidator
from ...bot.utils.formatters import MessageFormatter, ProgressFormatter, ConfigFileFormatter
from ...bot.middlewares.logging import monitor_performance, LoggingHelper
from ...database.models import get_db_session, VPNClient, User

# Create router for VPN commands
router = Router(name='vpn')

# Initialize services
wg_manager = WireGuardManager()
backup_service = BackupService()
logger = logging.getLogger(__name__)


@router.message(Command('newconfig'))
@monitor_performance('newconfig_command')
async def cmd_newconfig(message: Message, **kwargs) -> None:
    """
    Create new VPN configuration
    Implements TZ section 3.2: /newconfig <имя>
    """
    try:
        user = kwargs.get('user')
        if not user:
            await message.answer("⚠️ Ошибка авторизации")
            return
            
        # Parse command arguments
        args = message.text.split()[1:] if message.text else []
        
        if not args:
            await message.answer(
                "❌ <b>Неверный формат команды</b>\n\n"
                "📝 <b>Использование:</b> <code>/newconfig &lt;имя&gt;</code>\n\n"
                "📋 <b>Требования к имени:</b>\n"
                "• Длина: 3-20 символов\n"
                "• Символы: a-z, A-Z, 0-9, -, _\n\n"
                "💡 <b>Пример:</b> <code>/newconfig iPhone-John</code>",
                parse_mode="HTML"
            )
            return
        
        client_name = args[0]
        
        # Show progress message
        progress_msg = await message.answer(
            ProgressFormatter.format_loading_message("Создание конфигурации"),
            parse_mode="HTML"
        )
        
        # Create backup before operation
        backup_success, backup_msg, backup_id = await backup_service.create_backup('pre_operation', user.telegram_id)
        if not backup_success:
            await progress_msg.edit_text(
                f"⚠️ <b>Предупреждение</b>\n\n"
                f"Не удалось создать резервную копию: {backup_msg}\n"
                f"Продолжить создание клиента?",
                parse_mode="HTML"
            )
        
        # Create client
        success, result_msg, client_info = await wg_manager.add_client(client_name, user.telegram_id)
        
        if not success:
            await progress_msg.edit_text(
                MessageFormatter.format_error_message('wg_error', result_msg),
                parse_mode="HTML"
            )
            
            LoggingHelper.log_vpn_operation(
                user_id=user.telegram_id,
                operation='create_config',
                client_name=client_name,
                success=False,
                error=result_msg
            )
            return
        
        # Store client in database
        try:
            async with await get_db_session() as session:
                vpn_client = VPNClient(
                    name=client_name,
                    user_id=user.id,
                    public_key=client_info.get('public_key', ''),
                    private_key=client_info.get('private_key', ''),
                    ip_address=client_info.get('ip_address', '')
                )
                session.add(vpn_client)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to store client in database: {e}")
        
        # Export configuration
        config_files = await wg_manager.export_config(client_name)
        
        if not config_files:
            await progress_msg.edit_text(
                MessageFormatter.format_error_message('wg_error', "Не удалось экспортировать конфигурацию"),
                parse_mode="HTML"
            )
            return
        
        # Send configuration files
        try:
            # Send QR code
            if config_files.qr_code_bytes:
                qr_file = BufferedInputFile(
                    config_files.qr_code_bytes,
                    filename=f"{client_name}_qr.png"
                )
                await message.answer_photo(
                    photo=qr_file,
                    caption=f"🔗 <b>QR-код для {client_name}</b>",
                    parse_mode="HTML"
                )
            
            # Send config file
            if config_files.config_content:
                config_file = BufferedInputFile(
                    config_files.config_content.encode('utf-8'),
                    filename=f"{client_name}.conf"
                )
                await message.answer_document(
                    document=config_file,
                    caption=ConfigFileFormatter.format_instructions(client_name),
                    parse_mode="HTML"
                )
            
            # Update progress message with success
            await progress_msg.edit_text(
                MessageFormatter.format_success_message(
                    'config_created',
                    f"Клиент <b>{client_name}</b> успешно создан!\n\n"
                    f"📱 QR-код и файл конфигурации отправлены выше.\n"
                    f"📋 Используйте /list для просмотра всех клиентов."
                ),
                parse_mode="HTML"
            )
            
            LoggingHelper.log_vpn_operation(
                user_id=user.telegram_id,
                operation='create_config',
                client_name=client_name,
                success=True,
                ip_address=client_info.get('ip_address')
            )
            
        except TelegramBadRequest as e:
            logger.error(f"Failed to send files: {e}")
            await progress_msg.edit_text(
                "✅ Конфигурация создана, но произошла ошибка при отправке файлов.\n"
                f"Используйте /getconfig для получения файлов.",
                parse_mode="HTML"
            )
        
    except Exception as e:
        logger.error(f"Error in newconfig command: {e}")
        await message.answer(
            MessageFormatter.format_error_message('system_error', str(e)),
            parse_mode="HTML"
        )


@router.message(Command('list'))
@monitor_performance('list_command')
async def cmd_list(message: Message, **kwargs) -> None:
    """
    List all VPN clients
    Implements TZ section 3.2: /list with formatted output
    """
    try:
        user = kwargs.get('user')
        if not user:
            await message.answer("⚠️ Ошибка авторизации")
            return
            
        # Get clients from WireGuard
        clients = await wg_manager.list_clients()
        
        # Format and send response
        formatted_list = MessageFormatter.format_client_list(clients, len(clients))
        
        await message.answer(formatted_list, parse_mode="HTML")
        
        LoggingHelper.log_vpn_operation(
            user_id=user.telegram_id,
            operation='list_clients',
            success=True,
            client_count=len(clients)
        )
        
    except Exception as e:
        logger.error(f"Error in list command: {e}")
        await message.answer(
            MessageFormatter.format_error_message('system_error', str(e)),
            parse_mode="HTML"
        )


@router.message(Command('getconfig'))
@monitor_performance('getconfig_command')
async def cmd_getconfig(message: Message, **kwargs) -> None:
    """
    Get configuration by number
    Implements TZ section 3.2: /getconfig <номер>
    """
    try:
        user = kwargs.get('user')
        if not user:
            await message.answer("⚠️ Ошибка авторизации")
            return
            
        # Parse arguments
        args = message.text.split()[1:] if message.text else []
        
        if not args:
            await message.answer(
                "❌ <b>Неверный формат команды</b>\n\n"
                "📝 <b>Использование:</b> <code>/getconfig &lt;номер&gt;</code>\n\n"
                "💡 Сначала используйте /list для просмотра списка клиентов",
                parse_mode="HTML"
            )
            return
        
        # Get current client list
        clients = await wg_manager.list_clients()
        
        if not clients:
            await message.answer(
                "📋 <b>Список клиентов пуст</b>\n\n"
                "💡 Используйте /newconfig для создания нового клиента",
                parse_mode="HTML"
            )
            return
        
        # Validate number
        is_valid, error_msg, number = CommandValidator.validate_config_number(args[0], len(clients))
        
        if not is_valid:
            await message.answer(
                MessageFormatter.format_error_message('invalid_command', error_msg),
                parse_mode="HTML"
            )
            return
        
        # Get client by number (1-based indexing)
        client = clients[number - 1]
        client_name = client['name']
        
        # Show progress
        progress_msg = await message.answer(
            ProgressFormatter.format_loading_message("Получение конфигурации"),
            parse_mode="HTML"
        )
        
        # Export configuration
        config_files = await wg_manager.export_config(client_name)
        
        if not config_files:
            await progress_msg.edit_text(
                MessageFormatter.format_error_message('wg_error', "Не удалось получить конфигурацию"),
                parse_mode="HTML"
            )
            return
        
        try:
            # Send QR code
            if config_files.qr_code_bytes:
                qr_file = BufferedInputFile(
                    config_files.qr_code_bytes,
                    filename=f"{client_name}_qr.png"
                )
                await message.answer_photo(
                    photo=qr_file,
                    caption=f"🔗 <b>QR-код для {client_name}</b>",
                    parse_mode="HTML"
                )
            
            # Send config file
            if config_files.config_content:
                config_file = BufferedInputFile(
                    config_files.config_content.encode('utf-8'),
                    filename=f"{client_name}.conf"
                )
                await message.answer_document(
                    document=config_file,
                    caption=ConfigFileFormatter.format_instructions(client_name),
                    parse_mode="HTML"
                )
            
            # Update progress message
            await progress_msg.edit_text(
                f"✅ <b>Конфигурация для {client_name}</b>\n\n"
                f"📱 QR-код и файл конфигурации отправлены выше.",
                parse_mode="HTML"
            )
            
            LoggingHelper.log_vpn_operation(
                user_id=user.telegram_id,
                operation='get_config',
                client_name=client_name,
                success=True
            )
            
        except TelegramBadRequest as e:
            logger.error(f"Failed to send config files: {e}")
            await progress_msg.edit_text(
                "⚠️ Ошибка отправки файлов конфигурации",
                parse_mode="HTML"
            )
        
    except Exception as e:
        logger.error(f"Error in getconfig command: {e}")
        await message.answer(
            MessageFormatter.format_error_message('system_error', str(e)),
            parse_mode="HTML"
        )


@router.message(Command('delete'))
@monitor_performance('delete_command')
async def cmd_delete(message: Message, **kwargs) -> None:
    """
    Delete client configuration
    Implements TZ section 3.2: /delete <номер> with two-step confirmation
    """
    try:
        user = kwargs.get('user')
        if not user:
            await message.answer("⚠️ Ошибка авторизации")
            return
            
        # Parse arguments
        args = message.text.split()[1:] if message.text else []
        
        if not args:
            await message.answer(
                "❌ <b>Неверный формат команды</b>\n\n"
                "📝 <b>Использование:</b> <code>/delete &lt;номер&gt;</code>\n\n"
                "💡 Сначала используйте /list для просмотра списка клиентов",
                parse_mode="HTML"
            )
            return
        
        # Get current client list
        clients = await wg_manager.list_clients()
        
        if not clients:
            await message.answer(
                "📋 <b>Список клиентов пуст</b>\n\n"
                "💡 Нет клиентов для удаления",
                parse_mode="HTML"
            )
            return
        
        # Validate number
        is_valid, error_msg, number = CommandValidator.validate_config_number(args[0], len(clients))
        
        if not is_valid:
            await message.answer(
                MessageFormatter.format_error_message('invalid_command', error_msg),
                parse_mode="HTML"
            )
            return
        
        # Get client by number
        client = clients[number - 1]
        client_name = client['name']
        
        # Create confirmation keyboard
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"delete_confirm:{client_name}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="delete_cancel")
            ]
        ])
        
        # Show client info and confirmation
        client_info_text = MessageFormatter.format_client_info(client)
        confirmation_text = (
            f"{client_info_text}\n\n"
            f"⚠️ <b>Подтверждение удаления</b>\n\n"
            f"Вы действительно хотите удалить клиента <b>{client_name}</b>?\n"
            f"Это действие нельзя отменить!"
        )
        
        await message.answer(
            confirmation_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in delete command: {e}")
        await message.answer(
            MessageFormatter.format_error_message('system_error', str(e)),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith('delete_confirm:'))
async def callback_delete_confirm(callback: CallbackQuery, **kwargs) -> None:
    """Handle delete confirmation"""
    try:
        user = kwargs.get('user')
        if not user:
            await callback.answer("⚠️ Ошибка авторизации")
            return
            
        client_name = callback.data.split(':', 1)[1]
        
        # Show progress
        await callback.message.edit_text(
            ProgressFormatter.format_loading_message("Удаление клиента"),
            parse_mode="HTML"
        )
        
        # Create backup before deletion
        backup_success, backup_msg, backup_id = await backup_service.create_backup('pre_delete', user.telegram_id)
        
        # Delete client
        success, result_msg = await wg_manager.remove_client(client_name, user.telegram_id)
        
        if success:
            # Remove from database
            try:
                async with await get_db_session() as session:
                    from sqlalchemy import select, delete
                    
                    # Find and delete VPN client record
                    result = await session.execute(
                        select(VPNClient).where(VPNClient.name == client_name)
                    )
                    vpn_client = result.scalar_one_or_none()
                    
                    if vpn_client:
                        await session.delete(vpn_client)
                        await session.commit()
                        
            except Exception as e:
                logger.error(f"Failed to remove client from database: {e}")
            
            await callback.message.edit_text(
                MessageFormatter.format_success_message(
                    'config_deleted',
                    f"Клиент <b>{client_name}</b> успешно удален.\n\n"
                    f"📋 Используйте /list для просмотра оставшихся клиентов."
                ),
                parse_mode="HTML"
            )
            
            LoggingHelper.log_vpn_operation(
                user_id=user.telegram_id,
                operation='delete_config',
                client_name=client_name,
                success=True
            )
        else:
            await callback.message.edit_text(
                MessageFormatter.format_error_message('wg_error', result_msg),
                parse_mode="HTML"
            )
            
            LoggingHelper.log_vpn_operation(
                user_id=user.telegram_id,
                operation='delete_config',
                client_name=client_name,
                success=False,
                error=result_msg
            )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in delete confirmation: {e}")
        await callback.message.edit_text(
            MessageFormatter.format_error_message('system_error', str(e)),
            parse_mode="HTML"
        )
        await callback.answer()


@router.callback_query(F.data == 'delete_cancel')
async def callback_delete_cancel(callback: CallbackQuery) -> None:
    """Handle delete cancellation"""
    await callback.message.edit_text(
        "❌ <b>Удаление отменено</b>\n\n"
        "💡 Используйте /list для просмотра клиентов",
        parse_mode="HTML"
    )
    await callback.answer("Удаление отменено")
