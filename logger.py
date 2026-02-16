"""
Telegram logger service with service-based pool and TTL (Time To Live)
"""
import requests
import threading
import json
import traceback
import uuid
import time
from queue import Queue, Empty
from datetime import datetime, timedelta
from typing import Dict, Optional
from dataclasses import dataclass, field

@dataclass
class LogEntry:
    """Log entry structure"""
    level: str
    message: str
    service: Optional[str] = None
    metadata: Optional[Dict] = None
    timestamp: datetime = None
    traceback: Optional[str] = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now()

@dataclass
class LoggerConfig:
    """Logger configuration per service"""
    service_name: str
    debug_enabled: bool = False
    warning_enabled: bool = True
    info_enabled: bool = True
    error_enabled: bool = True  # Always true
    critical_enabled: bool = True  # Always true
    
    def is_level_enabled(self, level: str) -> bool:
        """Check if a log level is enabled for this service"""
        level_map = {
            'debug': self.debug_enabled,
            'info': self.info_enabled,
            'warning': self.warning_enabled,
            'error': self.error_enabled,
            'critical': self.critical_enabled
        }
        return level_map.get(level, False)
    
    def to_dict(self) -> Dict:
        """Convert config to dictionary"""
        return {
            'service_name': self.service_name,
            'debug_enabled': self.debug_enabled,
            'warning_enabled': self.warning_enabled,
            'info_enabled': self.info_enabled,
            'error_enabled': self.error_enabled,
            'critical_enabled': self.critical_enabled
        }

@dataclass
class PooledLogger:
    """Logger entry in the pool with metadata"""
    logger_id: str
    config: LoggerConfig
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'logger_id': self.logger_id,
            'service_name': self.config.service_name,
            'config': self.config.to_dict(),
            'created_at': self.created_at.isoformat(),
            'last_used': self.last_used.isoformat(),
            'age_seconds': (datetime.now() - self.created_at).total_seconds(),
            'message_count': self.message_count
        }

class ServiceLogger:
    """Service-specific logger wrapper with configuration"""
    
    def __init__(self, config: LoggerConfig, queue: Queue, lock: threading.RLock, pool_entry: 'PooledLogger' = None):
        self.config = config
        self.queue = queue
        self.lock = lock
        self.pool_entry = pool_entry  # Reference to pool entry for updating metadata
    
    def _should_log(self, level: str) -> bool:
        """Check if this level should be logged"""
        return self.config.is_level_enabled(level)
    
    def _update_pool_entry(self):
        """Update last_used time in pool entry"""
        if self.pool_entry:
            self.pool_entry.last_used = datetime.now()
    
    def debug(self, message: str, metadata: Dict = None):
        if self._should_log('debug'):
            self._update_pool_entry()
            self.queue.put(LogEntry('debug', message, self.config.service_name, metadata))
            if self.pool_entry:
                self.pool_entry.message_count += 1
    
    def info(self, message: str, metadata: Dict = None):
        if self._should_log('info'):
            self._update_pool_entry()
            self.queue.put(LogEntry('info', message, self.config.service_name, metadata))
            if self.pool_entry:
                self.pool_entry.message_count += 1
    
    def warning(self, message: str, metadata: Dict = None):
        if self._should_log('warning'):
            self._update_pool_entry()
            self.queue.put(LogEntry('warning', message, self.config.service_name, metadata))
            if self.pool_entry:
                self.pool_entry.message_count += 1
    
    def error(self, message: str, metadata: Dict = None, exc_info: bool = False):
        if self._should_log('error'):
            self._update_pool_entry()
            trace = traceback.format_exc() if exc_info else None
            self.queue.put(LogEntry('error', message, self.config.service_name, metadata, traceback=trace))
            if self.pool_entry:
                self.pool_entry.message_count += 1
    
    def critical(self, message: str, metadata: Dict = None, exc_info: bool = False):
        if self._should_log('critical'):
            self._update_pool_entry()
            trace = traceback.format_exc() if exc_info else None
            self.queue.put(LogEntry('critical', message, self.config.service_name, metadata, traceback=trace))
            if self.pool_entry:
                self.pool_entry.message_count += 1
    
    def set_level(self, level: str, enabled: bool):
        """Enable/disable a specific log level"""
        level_attr = f"{level}_enabled"
        if hasattr(self.config, level_attr) and level not in ['error', 'critical']:
            with self.lock:
                setattr(self.config, level_attr, enabled)
    
    def get_config(self) -> Dict:
        """Get current configuration"""
        return self.config.to_dict()

class TelegramLogger:
    """Telegram Logger with logger pool and TTL management"""
    
    def __init__(self, bot_token: str, chat_id: str, service_name: str = "file-server", ttl_seconds: int = 3600, enable_ttl_cleanup: bool = True):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.default_service_name = service_name
        self.ttl_seconds = ttl_seconds  # Time to live for loggers (default 1 hour)
        self.enable_ttl_cleanup = enable_ttl_cleanup  # Enable/disable TTL-based removal
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.log_queue = Queue(maxsize=10000)
        self.running = True
        self._lock = threading.RLock()
        self._stats = {'sent': 0, 'failed': 0, 'queued': 0, 'pool_size': 0}
        
        # Logger pool: logger_id -> ServiceLogger
        self._logger_pool: Dict[str, ServiceLogger] = {}
        self._pool_metadata: Dict[str, PooledLogger] = {}
        self._service_to_logger_id: Dict[str, str] = {}  # service name -> logger_id mapping
        
        # Start worker threads
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()
        
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        
        # Create default service logger
        default_logger_id = self._create_pooled_logger(service_name)
        self._service_to_logger_id[service_name] = default_logger_id
        
        # Test connection
        self._test_connection()
    
    def _worker(self):
        """Worker thread to process log entries"""
        while self.running:
            try:
                entry = self.log_queue.get(timeout=1)
                if entry:
                    self._send_log(entry)
            except Empty:
                continue
    
    def _cleanup_worker(self):
        """Worker thread to clean up expired loggers (only if TTL cleanup is enabled)"""
        while self.running:
            try:
                time.sleep(60)  # Check every minute
                
                # Only run cleanup if enabled
                if not self.enable_ttl_cleanup:
                    continue
                
                expired_ids = []
                
                with self._lock:
                    current_time = datetime.now()
                    for logger_id, pool_entry in self._pool_metadata.items():
                        age = (current_time - pool_entry.last_used).total_seconds()
                        if age > self.ttl_seconds:
                            expired_ids.append(logger_id)
                
                # Remove expired loggers
                for logger_id in expired_ids:
                    self._remove_logger(logger_id)
                    
            except Exception as e:
                print(f"⚠️ Cleanup error: {e}")
    
    def _test_connection(self):
        """Test Telegram connection"""
        try:
            response = requests.get(f"{self.api_url}/getMe", timeout=5)
            if response.ok:
                bot_info = response.json()['result']
                default_logger_id = self._service_to_logger_id.get(self.default_service_name)
                if default_logger_id and default_logger_id in self._logger_pool:
                    default_logger = self._logger_pool[default_logger_id]
                    default_logger.info("Logger initialized", metadata={'bot': bot_info['username']})
                print(f"✅ Logger connected to @{bot_info['username']}")
        except Exception as e:
            print(f"⚠️ Logger connection failed: {e}")
    
    def _create_pooled_logger(self, service_name: str, debug: bool = False, warning: bool = False, info: bool = False) -> str:
        """Create a new logger and add to pool, return logger_id"""
        with self._lock:
            logger_id = str(uuid.uuid4())
            
            config = LoggerConfig(
                service_name=service_name,
                debug_enabled=debug,
                warning_enabled=warning,
                info_enabled=info,
                error_enabled=True,
                critical_enabled=True
            )
            
            pool_entry = PooledLogger(logger_id=logger_id, config=config)
            service_logger = ServiceLogger(config, self.log_queue, self._lock, pool_entry)
            
            self._logger_pool[logger_id] = service_logger
            self._pool_metadata[logger_id] = pool_entry
            
            # Update pool size stat
            self._stats['pool_size'] = len(self._logger_pool)
            
            return logger_id
    
    def get_logger(self, logger_id: str) -> Optional[ServiceLogger]:
        """Get logger from pool by ID"""
        with self._lock:
            if logger_id in self._pool_metadata:
                self._pool_metadata[logger_id].last_used = datetime.now()
            return self._logger_pool.get(logger_id)
    
    def get_logger_info(self, logger_id: str) -> Optional[Dict]:
        """Get logger pool entry information"""
        return self.get_pool_logger_info(logger_id)
    
    def get_logger_config(self, logger_id: str) -> Optional[Dict]:
        """Get logger configuration"""
        with self._lock:
            if logger_id in self._logger_pool:
                logger_obj = self._logger_pool[logger_id]
                return logger_obj.config.to_dict()
            return None
    
    def update_logger_config(self, logger_id: str, debug: bool = None, warning: bool = None, info: bool = None) -> Optional[Dict]:
        """Update logger configuration"""
        return self.configure_pool_logger(logger_id, debug, warning, info)
    
    def get_all_loggers_info(self) -> list:
        """Get information about all active loggers"""
        with self._lock:
            return [metadata.to_dict() for metadata in self._pool_metadata.values()]
    
    def get_pool_stats(self) -> Dict:
        """Get logger pool statistics"""
        with self._lock:
            loggers_data = []
            for logger_id, metadata in self._pool_metadata.items():
                loggers_data.append(metadata.to_dict())
            
            return {
                'pool_size': len(self._logger_pool),
                'total_services': len(self._service_to_logger_id),
                'ttl_seconds': self.ttl_seconds,
                'messages_sent': self._stats.get('sent', 0),
                'messages_failed': self._stats.get('failed', 0),
                'queue_size': self.log_queue.qsize(),
                'loggers': loggers_data
            }
    
    def remove_logger(self, logger_id: str) -> bool:
        """Public method to remove logger from pool"""
        return self._remove_logger(logger_id)
    
    def _remove_logger(self, logger_id: str) -> bool:
        """Remove logger from pool"""
        with self._lock:
            if logger_id in self._logger_pool:
                del self._logger_pool[logger_id]
                del self._pool_metadata[logger_id]
                
                # Check if this was a service mapping
                for service_name, lid in list(self._service_to_logger_id.items()):
                    if lid == logger_id:
                        del self._service_to_logger_id[service_name]
                
                # Update pool size stat
                self._stats['pool_size'] = len(self._logger_pool)
                return True
            return False
    
    def list_pool_loggers(self) -> Dict:
        """List all loggers in pool with metadata"""
        with self._lock:
            return {
                logger_id: metadata.to_dict()
                for logger_id, metadata in self._pool_metadata.items()
            }
    
    def get_pool_logger_info(self, logger_id: str) -> Optional[Dict]:
        """Get detailed info for a specific logger in pool"""
        with self._lock:
            if logger_id in self._pool_metadata:
                return self._pool_metadata[logger_id].to_dict()
            return None
    
    def configure_pool_logger(self, logger_id: str, debug: bool = None, warning: bool = None, info: bool = None) -> Dict:
        """Configure logging levels for a pooled logger"""
        with self._lock:
            if logger_id not in self._logger_pool:
                return None
            
            logger = self._logger_pool[logger_id]
            
            if debug is not None:
                logger.config.debug_enabled = debug
            if warning is not None:
                logger.config.warning_enabled = warning
            if info is not None:
                logger.config.info_enabled = info
            
            return logger.get_config()
    
    # Backward compatibility methods
    def get_service_logger(self, service_name: str) -> ServiceLogger:
        """Get or create a service logger (backward compatible)"""
        with self._lock:
            if service_name not in self._service_to_logger_id:
                logger_id = self._create_pooled_logger(service_name)
                self._service_to_logger_id[service_name] = logger_id
            
            logger_id = self._service_to_logger_id[service_name]
            return self._logger_pool[logger_id]
    
    def configure_service(self, service_name: str, debug: bool = None, warning: bool = None, info: bool = None) -> Dict:
        """Configure logging levels for a service (backward compatible)"""
        logger = self.get_service_logger(service_name)
        if debug is not None:
            logger.config.debug_enabled = debug
        if warning is not None:
            logger.config.warning_enabled = warning
        if info is not None:
            logger.config.info_enabled = info
        return logger.get_config()
    
    def get_service_config(self, service_name: str) -> Optional[Dict]:
        """Get configuration for a service (backward compatible)"""
        with self._lock:
            if service_name not in self._service_to_logger_id:
                return None
            logger_id = self._service_to_logger_id[service_name]
            return self._pool_metadata[logger_id].config.to_dict()
    
    def list_services(self) -> Dict:
        """List services with their logger IDs and configs (backward compatible)"""
        with self._lock:
            return {
                service_name: {
                    'logger_id': logger_id,
                    'config': self._pool_metadata[logger_id].config.to_dict()
                }
                for service_name, logger_id in self._service_to_logger_id.items()
            }
    
    def _send_log(self, entry: LogEntry):
        """Send log entry to Telegram"""
        try:
            emoji = {
                'debug': '🔍', 'info': 'ℹ️', 'warning': '⚠️',
                'error': '❌', 'critical': '🔥'
            }.get(entry.level, '📝')
            
            lines = [
                f"{emoji} *{entry.level.upper()}* - {entry.service or self.default_service_name}",
                f"📌 {entry.message}"
            ]
            
            if entry.metadata:
                meta_str = json.dumps(entry.metadata, indent=2)
                lines.append(f"📊 ```json\n{meta_str}\n```")
            
            if entry.traceback:
                lines.append(f"🔍 ```\n{entry.traceback[:1000]}\n```")
            
            lines.append(f"🕐 {entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            
            text = '\n'.join(lines)
            
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json={
                    'chat_id': self.chat_id,
                    'text': text,
                    'parse_mode': 'Markdown'
                },
                timeout=5
            )
            
            if response.ok:
                with self._lock:
                    self._stats['sent'] += 1
            else:
                with self._lock:
                    self._stats['failed'] += 1
                    
        except Exception as e:
            with self._lock:
                self._stats['failed'] += 1
    
    # Backward compatibility: Direct logging methods for default service
    def debug(self, message: str, service: str = None, metadata: Dict = None):
        """Log debug message (backward compatible)"""
        service_name = service or self.default_service_name
        logger = self.get_service_logger(service_name)
        if logger:
            logger.debug(message, metadata)
    
    def info(self, message: str, service: str = None, metadata: Dict = None):
        """Log info message (backward compatible)"""
        service_name = service or self.default_service_name
        logger = self.get_service_logger(service_name)
        if logger:
            logger.info(message, metadata)
    
    def warning(self, message: str, service: str = None, metadata: Dict = None):
        """Log warning message (backward compatible)"""
        service_name = service or self.default_service_name
        logger = self.get_service_logger(service_name)
        if logger:
            logger.warning(message, metadata)
    
    def error(self, message: str, service: str = None, metadata: Dict = None, exc_info: bool = False):
        """Log error message (backward compatible)"""
        service_name = service or self.default_service_name
        logger = self.get_service_logger(service_name)
        if logger:
            logger.error(message, metadata, exc_info)
    
    def critical(self, message: str, service: str = None, metadata: Dict = None, exc_info: bool = False):
        """Log critical message (backward compatible)"""
        service_name = service or self.default_service_name
        logger = self.get_service_logger(service_name)
        if logger:
            logger.critical(message, metadata, exc_info)
    
    def get_stats(self) -> Dict:
        """Get logger statistics including pool info"""
        with self._lock:
            stats = {
                **self._stats,
                'queue_size': self.log_queue.qsize(),
                'ttl_seconds': self.ttl_seconds,
                'ttl_cleanup_enabled': self.enable_ttl_cleanup
            }
            stats['pool'] = {
                'total_loggers': len(self._logger_pool),
                'loggers': self.list_pool_loggers()
            }
            stats['services'] = self.list_services()
            return stats
    
    def set_ttl_cleanup(self, enabled: bool) -> bool:
        """Enable or disable TTL-based cleanup of loggers
        
        Args:
            enabled: True to enable cleanup, False to disable
            
        Returns:
            bool: Status after setting
        """
        with self._lock:
            old_state = self.enable_ttl_cleanup
            self.enable_ttl_cleanup = enabled
            return enabled
    
    def get_ttl_cleanup_status(self) -> Dict:
        """Get TTL cleanup status and settings
        
        Returns:
            dict: TTL settings and status
        """
        with self._lock:
            return {
                'enabled': self.enable_ttl_cleanup,
                'ttl_seconds': self.ttl_seconds,
                'pool_size': len(self._logger_pool)
            }