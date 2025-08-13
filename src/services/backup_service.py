"""
Backup service for Telegram WireGuard Bot
"""
import asyncio
import logging
import shutil
import tarfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from ..config.settings import settings
from ..config.logging_config import structured_logger


class BackupService:
    """
    Backup service for WireGuard configurations
    Implements TZ requirements from section 3.4 and 4.3
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.backup_path = Path(settings.BACKUP_PATH)
        # Use /etc/wireguard/ as default config path
        self.config_path = Path("/etc/wireguard/")
        self.clients_path = Path(settings.WG_CLIENTS_PATH)
        
        # Ensure backup directory exists
        self.backup_path.mkdir(parents=True, exist_ok=True)
    
    async def create_backup(self, backup_type: str = 'manual', user_id: int = None) -> Tuple[bool, str, Optional[str]]:
        """
        Create backup of WireGuard configurations
        Returns: (success, message, backup_id)
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_id = f"{backup_type}_{timestamp}"
            backup_file = self.backup_path / f"{backup_id}.tar.gz"
            
            self.logger.info(f"Creating backup: {backup_id}")
            
            # Create tar.gz archive
            with tarfile.open(backup_file, "w:gz") as tar:
                # Add main WireGuard config
                if self.config_path.exists():
                    tar.add(self.config_path, arcname="wireguard")
                
                # Add client configs
                if self.clients_path.exists():
                    tar.add(self.clients_path, arcname="clients")
            
            # Verify backup was created
            if not backup_file.exists():
                return False, "Файл резервной копии не был создан", None
            
            file_size = backup_file.stat().st_size
            
            # Log successful backup
            structured_logger.log_system_event(
                event='backup_created',
                backup_type=backup_type,
                backup_id=backup_id,
                file_size=file_size,
                user_id=user_id
            )
            
            # Store backup record in database
            await self._store_backup_record(backup_id, backup_type, str(backup_file), file_size)
            
            return True, f"Резервная копия создана: {backup_id}", backup_id
            
        except Exception as e:
            self.logger.error(f"Error creating backup: {e}")
            return False, f"Ошибка создания резервной копии: {str(e)}", None
    
    async def restore_backup(self, backup_id: str, user_id: int = None) -> Tuple[bool, str]:
        """
        Restore from backup
        """
        try:
            backup_file = self.backup_path / f"{backup_id}.tar.gz"
            
            if not backup_file.exists():
                return False, f"Резервная копия {backup_id} не найдена"
            
            self.logger.info(f"Restoring backup: {backup_id}")
            
            # Create pre-restore backup
            pre_restore_success, pre_restore_msg, _ = await self.create_backup('pre_restore', user_id)
            if not pre_restore_success:
                return False, f"Не удалось создать резервную копию перед восстановлением: {pre_restore_msg}"
            
            # Stop WireGuard service
            await self._stop_wireguard()
            
            # Extract backup
            with tarfile.open(backup_file, "r:gz") as tar:
                tar.extractall(path=self.config_path.parent)
            
            # Start WireGuard service
            await self._start_wireguard()
            
            # Log successful restore
            structured_logger.log_system_event(
                event='backup_restored',
                backup_id=backup_id,
                user_id=user_id
            )
            
            return True, f"Конфигурация восстановлена из {backup_id}"
            
        except Exception as e:
            self.logger.error(f"Error restoring backup {backup_id}: {e}")
            return False, f"Ошибка восстановления: {str(e)}"
    
    async def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups"""
        try:
            backups = []
            
            for backup_file in self.backup_path.glob("*.tar.gz"):
                try:
                    stat = backup_file.stat()
                    backup_info = {
                        'id': backup_file.stem,
                        'filename': backup_file.name,
                        'size_bytes': stat.st_size,
                        'created_at': datetime.fromtimestamp(stat.st_ctime),
                        'type': self._extract_backup_type(backup_file.stem)
                    }
                    backups.append(backup_info)
                except Exception as e:
                    self.logger.warning(f"Error getting info for backup {backup_file}: {e}")
            
            # Sort by creation date (newest first)
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            
            return backups
            
        except Exception as e:
            self.logger.error(f"Error listing backups: {e}")
            return []
    
    async def cleanup_old_backups(self) -> Tuple[int, int]:
        """
        Clean up old backup files
        Returns: (deleted_count, total_size_freed)
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=settings.BACKUP_RETENTION_DAYS)
            deleted_count = 0
            total_size_freed = 0
            
            for backup_file in self.backup_path.glob("*.tar.gz"):
                try:
                    file_stat = backup_file.stat()
                    created_date = datetime.fromtimestamp(file_stat.st_ctime)
                    
                    if created_date < cutoff_date:
                        file_size = file_stat.st_size
                        backup_file.unlink()
                        
                        deleted_count += 1
                        total_size_freed += file_size
                        
                        self.logger.info(f"Deleted old backup: {backup_file.name}")
                        
                except Exception as e:
                    self.logger.warning(f"Error deleting backup {backup_file}: {e}")
            
            if deleted_count > 0:
                structured_logger.log_system_event(
                    event='backups_cleaned',
                    deleted_count=deleted_count,
                    size_freed_bytes=total_size_freed
                )
            
            return deleted_count, total_size_freed
            
        except Exception as e:
            self.logger.error(f"Error during backup cleanup: {e}")
            return 0, 0
    
    async def get_backup_info(self, backup_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed backup information"""
        try:
            backup_file = self.backup_path / f"{backup_id}.tar.gz"
            
            if not backup_file.exists():
                return None
            
            stat = backup_file.stat()
            
            # Get contents list
            contents = []
            try:
                with tarfile.open(backup_file, "r:gz") as tar:
                    contents = [member.name for member in tar.getmembers()[:10]]  # First 10 files
            except Exception:
                contents = ["Не удалось прочитать содержимое"]
            
            return {
                'id': backup_id,
                'filename': backup_file.name,
                'size_bytes': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_ctime),
                'type': self._extract_backup_type(backup_id),
                'contents': contents
            }
            
        except Exception as e:
            self.logger.error(f"Error getting backup info for {backup_id}: {e}")
            return None
    
    # Private helper methods
    
    async def _store_backup_record(self, backup_id: str, backup_type: str, file_path: str, file_size: int):
        """Store backup record in database"""
        try:
            from ..database.models import get_db_session, BackupRecord
            
            async with await get_db_session() as session:
                backup_record = BackupRecord(
                    backup_type=backup_type,
                    file_path=file_path,
                    file_size_bytes=file_size,
                    status='success',
                    expires_at=datetime.now() + timedelta(days=settings.BACKUP_RETENTION_DAYS)
                )
                
                session.add(backup_record)
                await session.commit()
                
        except Exception as e:
            self.logger.warning(f"Failed to store backup record: {e}")
    
    def _extract_backup_type(self, backup_id: str) -> str:
        """Extract backup type from backup ID"""
        parts = backup_id.split('_')
        return parts[0] if parts else 'unknown'
    
    async def _stop_wireguard(self) -> bool:
        """Stop WireGuard service"""
        try:
            process = await asyncio.create_subprocess_exec(
                'systemctl', 'stop', f'wg-quick@{settings.WG_INTERFACE}',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            return process.returncode == 0
            
        except Exception as e:
            self.logger.error(f"Error stopping WireGuard: {e}")
            return False
    
    async def _start_wireguard(self) -> bool:
        """Start WireGuard service"""
        try:
            process = await asyncio.create_subprocess_exec(
                'systemctl', 'start', f'wg-quick@{settings.WG_INTERFACE}',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            return process.returncode == 0
            
        except Exception as e:
            self.logger.error(f"Error starting WireGuard: {e}")
            return False


class BackupHelper:
    """Helper class for backup operations"""
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    @staticmethod
    def get_backup_age_string(created_at: datetime) -> str:
        """Get human-readable backup age"""
        now = datetime.now()
        age = now - created_at
        
        if age.days > 0:
            return f"{age.days} дн. назад"
        elif age.seconds > 3600:
            hours = age.seconds // 3600
            return f"{hours} ч. назад"
        elif age.seconds > 60:
            minutes = age.seconds // 60
            return f"{minutes} мин. назад"
        else:
            return "только что"