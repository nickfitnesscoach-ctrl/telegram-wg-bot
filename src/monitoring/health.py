"""
Health check endpoint and monitoring utilities
"""
import json
import logging
import psutil
from datetime import datetime
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from ..config.settings import settings
from ..services.wg_manager import WireGuardManager
from ..database.models import get_db_session, SystemStatus


class HealthChecker:
    """Advanced health checking with HTTP endpoint"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.wg_manager = WireGuardManager()
        self.app = FastAPI(title="WireGuard Bot Health Check")
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup FastAPI routes for health checks"""
        
        @self.app.get("/health")
        async def health_check():
            """Main health check endpoint"""
            try:
                health_data = await self.perform_comprehensive_check()
                status_code = 200 if health_data['status'] == 'healthy' else 503
                
                return JSONResponse(
                    content=health_data,
                    status_code=status_code
                )
            except Exception as e:
                self.logger.error(f"Health check failed: {e}")
                raise HTTPException(status_code=500, detail="Health check failed")
        
        @self.app.get("/metrics")
        async def get_metrics():
            """Prometheus-style metrics endpoint"""
            try:
                metrics = await self.get_prometheus_metrics()
                return JSONResponse(content=metrics)
            except Exception as e:
                self.logger.error(f"Metrics collection failed: {e}")
                raise HTTPException(status_code=500, detail="Metrics collection failed")
        
        @self.app.get("/status")
        async def get_status():
            """Detailed system status"""
            try:
                status = await self.get_detailed_status()
                return JSONResponse(content=status)
            except Exception as e:
                self.logger.error(f"Status check failed: {e}")
                raise HTTPException(status_code=500, detail="Status check failed")
    
    async def perform_comprehensive_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        checks = {
            'database': await self._check_database(),
            'wireguard': await self._check_wireguard(),
            'disk_space': await self._check_disk_space(),
            'memory': await self._check_memory(),
            'cpu': await self._check_cpu()
        }
        
        # Determine overall status
        failed_checks = [name for name, result in checks.items() if not result['healthy']]
        overall_status = 'healthy' if not failed_checks else 'unhealthy'
        
        return {
            'status': overall_status,
            'timestamp': datetime.utcnow().isoformat(),
            'checks': checks,
            'failed_checks': failed_checks,
            'version': '1.0.0'
        }
    
    async def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity"""
        try:
            async with await get_db_session() as session:
                # Simple query to test connectivity
                await session.execute("SELECT 1")
                return {
                    'healthy': True,
                    'message': 'Database connection successful',
                    'response_time_ms': 0  # Could measure actual time
                }
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Database connection failed: {str(e)}',
                'error': str(e)
            }
    
    async def _check_wireguard(self) -> Dict[str, Any]:
        """Check WireGuard service"""
        try:
            success, output = await self.wg_manager._execute_wg_command(['status'])
            return {
                'healthy': success,
                'message': 'WireGuard service operational' if success else 'WireGuard service failed',
                'details': output if success else None,
                'error': output if not success else None
            }
        except Exception as e:
            return {
                'healthy': False,
                'message': f'WireGuard check failed: {str(e)}',
                'error': str(e)
            }
    
    async def _check_disk_space(self) -> Dict[str, Any]:
        """Check disk space"""
        try:
            disk_usage = psutil.disk_usage('/')
            free_gb = disk_usage.free / (1024**3)
            
            return {
                'healthy': free_gb > settings.MIN_FREE_SPACE_GB,
                'message': f'Free space: {free_gb:.1f} GB',
                'free_space_gb': round(free_gb, 1),
                'used_space_gb': round(disk_usage.used / (1024**3), 1),
                'total_space_gb': round(disk_usage.total / (1024**3), 1),
                'usage_percent': round((disk_usage.used / disk_usage.total) * 100, 1)
            }
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Disk check failed: {str(e)}',
                'error': str(e)
            }
    
    async def _check_memory(self) -> Dict[str, Any]:
        """Check memory usage"""
        try:
            memory = psutil.virtual_memory()
            
            return {
                'healthy': memory.percent < 90,  # Alert if >90% usage
                'message': f'Memory usage: {memory.percent}%',
                'usage_percent': memory.percent,
                'available_gb': round(memory.available / (1024**3), 1),
                'total_gb': round(memory.total / (1024**3), 1),
                'used_gb': round(memory.used / (1024**3), 1)
            }
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Memory check failed: {str(e)}',
                'error': str(e)
            }
    
    async def _check_cpu(self) -> Dict[str, Any]:
        """Check CPU usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            
            return {
                'healthy': cpu_percent < 90,  # Alert if >90% usage
                'message': f'CPU usage: {cpu_percent}%',
                'usage_percent': cpu_percent,
                'core_count': psutil.cpu_count(),
                'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
            }
        except Exception as e:
            return {
                'healthy': False,
                'message': f'CPU check failed: {str(e)}',
                'error': str(e)
            }
    
    async def get_prometheus_metrics(self) -> Dict[str, Any]:
        """Get metrics in Prometheus format"""
        try:
            # Collect metrics
            disk_usage = psutil.disk_usage('/')
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # WireGuard metrics
            clients = await self.wg_manager.list_clients()
            active_clients = len([c for c in clients if c.get('is_active', True)])
            
            return {
                'wireguard_clients_total': len(clients),
                'wireguard_clients_active': active_clients,
                'system_disk_usage_percent': round((disk_usage.used / disk_usage.total) * 100, 1),
                'system_memory_usage_percent': memory.percent,
                'system_cpu_usage_percent': cpu_percent,
                'system_disk_free_bytes': disk_usage.free,
                'system_memory_available_bytes': memory.available,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Metrics collection failed: {e}")
            return {'error': str(e)}
    
    async def get_detailed_status(self) -> Dict[str, Any]:
        """Get detailed system status"""
        try:
            # System information
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            
            # WireGuard information
            clients = await self.wg_manager.list_clients()
            
            return {
                'system': {
                    'boot_time': boot_time.isoformat(),
                    'uptime_seconds': (datetime.now() - boot_time).total_seconds(),
                    'platform': psutil.os.name,
                },
                'wireguard': {
                    'total_clients': len(clients),
                    'active_clients': len([c for c in clients if c.get('is_active', True)]),
                    'interface': settings.WG_INTERFACE,
                    'port': settings.VPN_PORT
                },
                'configuration': {
                    'max_clients': settings.MAX_CLIENTS,
                    'command_timeout': settings.COMMAND_TIMEOUT,
                    'health_check_interval': settings.HEALTH_CHECK_INTERVAL,
                    'log_level': settings.LOG_LEVEL
                },
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Status collection failed: {e}")
            return {'error': str(e)}


# Global health checker instance
health_checker = HealthChecker()
