"""
WireGuard manager service for Telegram WireGuard Bot
"""
import asyncio
import logging
import qrcode
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from ..config.settings import settings
from ..config.logging_config import structured_logger
from ..bot.utils.validators import ConfigNameValidator, SystemLimitValidator


class WireGuardManager:
    """WireGuard manager service - main business logic"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.wg_manager_path = settings.WG_MANAGER_PATH
    
    async def add_client(self, name: str, user_id: int) -> Tuple[bool, str, Optional[dict]]:
        """Add new VPN client with validation"""
        try:
            # Validate name
            is_valid, error_msg = ConfigNameValidator.validate(name)
            if not is_valid:
                return False, error_msg, None
            
            # Execute wg-manager add with retry
            success, output = await self._execute_wg_command(['add', name], retries=3)
            
            if not success:
                return False, f"Ошибка создания клиента: {output}", None
            
            return True, "Клиент успешно создан", {'name': name}
            
        except Exception as e:
            self.logger.error(f"Error adding client {name}: {e}")
            return False, f"Системная ошибка: {str(e)}", None
    
    async def list_clients(self) -> List[dict]:
        """List all VPN clients"""
        try:
            success, output = await self._execute_wg_command(['list'])
            
            if not success:
                return []
            
            # Parse output and return client list
            clients = []
            for line in output.strip().split('\n'):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        clients.append({
                            'name': parts[0],
                            'ip_address': parts[1] if len(parts) > 1 else None,
                            'created_at': datetime.utcnow(),
                            'is_active': True
                        })
            
            return clients
            
        except Exception as e:
            self.logger.error(f"Error listing clients: {e}")
            return []
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get WireGuard system status"""
        try:
            success, output = await self._execute_wg_command(['status'])
            
            # Parse WireGuard status
            status_data = {
                'interface': settings.WG_INTERFACE,
                'status': 'running' if success else 'stopped',
                'server_ip': settings.SERVER_IP,
                'port': settings.VPN_PORT,
                'clients_count': len(await self.list_clients()),
                'max_clients': settings.MAX_CLIENTS,
                'last_check': datetime.now().isoformat()
            }
            
            if success and output:
                # Add more details from wg status output
                status_data['details'] = output.strip()
            
            return status_data
            
        except Exception as e:
            self.logger.error(f"Error getting system status: {e}")
            return {
                'interface': settings.WG_INTERFACE,
                'status': 'error',
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
    
    async def _execute_wg_command(self, args: List[str], retries: int = 1) -> Tuple[bool, str]:
        """Execute wg-manager command with retries"""
        command = [self.wg_manager_path] + args
        
        for attempt in range(retries):
            try:
                # Create process without timeout
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # Use asyncio.wait_for for timeout
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=settings.COMMAND_TIMEOUT
                )
                
                if process.returncode == 0:
                    return True, stdout.decode('utf-8').strip()
                else:
                    error = stderr.decode('utf-8').strip()
                    if attempt == retries - 1:
                        return False, error
                    await asyncio.sleep(1)
                
            except Exception as e:
                if attempt == retries - 1:
                    return False, str(e)
                await asyncio.sleep(1)
        
        return False, "Все попытки исчерпаны"


