"""
Configuration management
"""
import os
import json
import secrets
import threading
from typing import Any, Dict, Optional

class ConfigError(Exception):
    """Configuration error"""
    pass

class ConfigManager:
    """Thread-safe configuration manager"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = False
            self._config = {}
            self._config_lock = threading.RLock()
            self._init_config()
    
    def _init_config(self):
        """Initialize configuration"""
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(self.base_dir, "enterprise_config.json")
        self.data_dir = os.path.join(self.base_dir, "data")
        self.temp_dir = os.path.join(self.base_dir, "temp")
        
        # Create directories
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Load or create config
        self._config = self._load_or_create()
        self._initialized = True
    
    def _load_or_create(self) -> Dict:
        """Load existing config or create new one"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        
        # Generate secure API key
        api_key = secrets.token_urlsafe(32)
        
        # Default configuration
        config = {
            "logger_bot_token": "YOUR_LOGGER_BOT_TOKEN",
            "logger_chat_id": "YOUR_LOGGER_CHAT_ID",
            "server_bot_token": "YOUR_SERVER_BOT_TOKEN",
            "server_chat_id": "YOUR_SERVER_CHAT_ID",
            "api_key": api_key,
            "service_name": "enterprise-file-server",
            "environment": "production",
            "max_file_size_mb": 2000,
            "max_workers": 5
        }
        
        # Save config
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        print("\n" + "="*60)
        print("🎯 FIRST TIME SETUP")
        print("="*60)
        print(f"\n🔑 API KEY: {api_key}")
        print(f"\n📁 Config file: {self.config_file}")
        print("\n⚠️  Add your bot tokens to the config file!\n")
        
        return config
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        with self._config_lock:
            return self._config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set configuration value and save"""
        with self._config_lock:
            self._config[key] = value
            self._save()
    
    def _save(self):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self._config, f, indent=2)
    
    def get_api_key(self) -> str:
        """Get API key"""
        return self.get('api_key', '')
    
    def get_paths(self) -> Dict:
        """Get system paths"""
        return {
            'base_dir': self.base_dir,
            'data_dir': self.data_dir,
            'temp_dir': self.temp_dir,
            'config_file': self.config_file
        }

# Global config instance
config = ConfigManager()