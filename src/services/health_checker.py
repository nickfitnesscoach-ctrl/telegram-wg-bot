"""
Health monitoring service for Telegram WireGuard Bot
"""
import asyncio
import logging
import psutil
from datetime import datetime
from typing import Dict, Any

from ..config.settings import settings
from ..config.logging_config import structured_logger


class HealthChecker:
    """Health monitoring service - checks system health every 30 seconds"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.is_running = False
        self.check_task = None
        self.last_check_time = None
    
    async def start(self) -> None:
        """Start health monitoring"""
        if self.is_running:
            return
        
        self.is_running = True
        self.check_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("Health checker started")
    
    async def stop(self) -> None:
        """Stop health monitoring"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.check_task:
            self.check_task.cancel()
            try:
                await self.check_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Health checker stopped")
    
    async def perform_health_check(self) -> Dict[str, Any]:
        """Perform a single health check"""
        try:
            health_data = {
                'timestamp': datetime.utcnow(),
                'wireguard': await self._check_wireguard_health(),
                'disk_space': await self._check_disk_space(),
                'memory': await self._check_memory_usage(),
                'cpu': await self._check_cpu_usage()
            }
            
            self.last_check_time = health_data['timestamp']
            return health_data
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {e}")
            return {'error': str(e), 'timestamp': datetime.utcnow()}
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop"""
        while self.is_running:
            try:
                await self.perform_health_check()
                await asyncio.sleep(settings.HEALTH_CHECK_INTERVAL)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)
    
    async def _check_wireguard_health(self) -> Dict[str, Any]:
        """Check WireGuard service health"""
        try:
            process = await asyncio.create_subprocess_exec(
                'systemctl', 'is-active', f'wg-quick@{settings.WG_INTERFACE}',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            is_active = process.returncode == 0 and b'active' in stdout
            
            return {
                'status': 'healthy' if is_active else 'unhealthy',
                'service_active': is_active
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def _check_disk_space(self) -> Dict[str, Any]:
        """Check disk space"""
        try:
            disk_usage = psutil.disk_usage('/')
            free_gb = disk_usage.free / (1024**3)
            usage_percent = (disk_usage.used / disk_usage.total) * 100
            
            status = 'critical' if free_gb < settings.MIN_FREE_SPACE_GB else 'healthy'
            
            return {
                'status': status,
                'free_gb': round(free_gb, 1),
                'usage_percent': round(usage_percent, 1)
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def _check_memory_usage(self) -> Dict[str, Any]:
        """Check memory usage"""
        try:
            memory = psutil.virtual_memory()
            usage_percent = memory.percent
            
            status = 'critical' if usage_percent > 95 else 'healthy'
            
            return {
                'status': status,
                'usage_percent': round(usage_percent, 1)
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def _check_cpu_usage(self) -> Dict[str, Any]:
        """Check CPU usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            status = 'critical' if cpu_percent > 90 else 'healthy'
            
            return {
                'status': status,
                'usage_percent': round(cpu_percent, 1)
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}


# Global health checker instance
health_checker = HealthChecker()


