import os
import sys
import signal
import threading
import time
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import all modules
from config import config
from logger import TelegramLogger
from storage import TelegramStorageBackend  # ✅ Correct import
from file_manager import FileManager
from api import create_app

class FileServer:
    """Main application class"""
    
    def __init__(self):
        self.running = True
        self.logger = None
        self.file_manager = None
        self.flask_app = None
        self._init_components()
    
    def _init_components(self):
        """Initialize all components"""
        print("\n" + "="*70)
        print("🏢 FILE SERVER - INITIALIZING")
        print("="*70)
        
        # Get paths
        paths = config.get_paths()
        print(f"📁 Data directory: {paths['data_dir']}")
        print(f"📁 Temp directory: {paths['temp_dir']}")
        
        # Check bot tokens
        logger_token = config.get('logger_bot_token')
        server_token = config.get('server_bot_token')
        
        if logger_token == "YOUR_LOGGER_BOT_TOKEN" or server_token == "YOUR_SERVER_BOT_TOKEN":
            print("\n⚠️  WARNING: Bot tokens not configured!")
            print(f"📝 Please edit: {paths['config_file']}")
            print("Add your actual bot tokens and restart.\n")
            sys.exit(1)
        
        # Initialize logger
        print("\n📋 Initializing Telegram Logger...")
        self.logger = TelegramLogger(
            bot_token=config.get('logger_bot_token'),
            chat_id=config.get('logger_chat_id'),
            service_name=config.get('service_name'),
            ttl_seconds=3600  # 1 hour TTL for loggers
        )
        
        # Initialize storage
        print("💾 Initializing Storage Backend...")
        storage = TelegramStorageBackend(  # ✅ Correct class name
            bot_token=config.get('server_bot_token'),
            chat_id=config.get('server_chat_id')
        )
        
        # Initialize file manager
        print("📁 Initializing File Manager...")
        self.file_manager = FileManager(
            storage=storage,
            logger=self.logger,
            data_dir=paths['data_dir']
        )
        
        # Create Flask app
        print("🌐 Creating Flask Application...")
        self.flask_app = create_app(config, self.logger, self.file_manager)
        
        if self.flask_app is None:
            raise Exception("Failed to create Flask app")
        
        print("\n✅ All components initialized successfully!")
    
    def start(self, host='0.0.0.0', port=5000, debug=False):
        """Start the server"""
        print("\n" + "="*70)
        print("🚀 ENTERPRISE FILE SERVER - STARTING")
        print("="*70)
        print(f"\n🌍 Host: {host}")
        print(f"🔌 Port: {port}")
        print(f"🔑 API Key: {config.get_api_key()}")
        
        print("\n📡 Endpoints:")
        print("   ┌─ File Operations")
        print("   ├─ POST   /api/upload           - Upload file")
        print("   ├─ POST   /api/import           - Import from URL")
        print("   ├─ POST   /api/upload/multiple  - Upload multiple files")
        print("   ├─ GET    /api/file/<id>        - Get file info")
        print("   ├─ GET    /api/files             - List files")
        print("   ├─ DELETE /api/file/<id>        - Delete file")
        print("   ├─ GET    /api/stats             - Server statistics")
        print("   │")
        print("   ├─ Logger Management")
        print("   ├─ POST   /api/logger/create            - Create logger")
        print("   ├─ GET    /api/logger/<id>              - Logger info")
        print("   ├─ PUT    /api/logger/<id>/config       - Update config")
        print("   ├─ POST   /api/logger/<id>/log          - Send message")
        print("   ├─ GET    /api/logger/list              - List all loggers")
        print("   ├─ GET    /api/logger/stats             - Logger stats")
        print("   ├─ GET    /api/logger/ttl/status        - TTL status")
        print("   ├─ POST   /api/logger/ttl/toggle        - Toggle TTL cleanup")
        print("   ├─ POST   /api/logger/<id>/test         - Test logger")
        print("   ├─ DELETE /api/logger/<id>              - Delete logger")
        print("   │")
        print("   ├─ Public Access")
        print("   ├─ GET    /view/<code>           - View/play file")
        print("   ├─ GET    /download/<code>       - Download file")
        print("   ├─ GET    /<code>                - Smart access")
        print("   │")
        print("   ├─ System")
        print("   └─ GET    /health                 - Health check")
        
        print("\n" + "="*70)
        print("✅ Server is running! Press Ctrl+C to stop")
        print("="*70 + "\n")
        
        # Run the Flask app
        try:
            self.flask_app.run(host=host, port=port, debug=debug, threaded=True)
        except Exception as e:
            print(f"\n❌ Error running server: {e}")
            import traceback
            traceback.print_exc()
            self.shutdown()
    
    def shutdown(self):
        """Graceful shutdown"""
        print("\n\n🛑 Shutting down...")
        self.running = False
        if self.logger:
            self.logger.info("Server shutting down")
        print("✅ Shutdown complete")

# Global server instance
server = None

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\n📡 Received shutdown signal...")
    if server:
        server.shutdown()
    sys.exit(0)

if __name__ == '__main__':
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start server
    server = FileServer()
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Enterprise File Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    
    args = parser.parse_args()
    
    try:
        server.start(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        server.shutdown()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        if server:
            server.shutdown()
        sys.exit(1)