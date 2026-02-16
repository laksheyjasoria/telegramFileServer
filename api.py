"""
Flask API routes - Simplified with file_id only (no short codes)
File Upload, Multi-Upload, URL Import, File Info, View URL, Download URL
"""
import hmac
from functools import wraps
from datetime import datetime
from flask import Flask, request, jsonify, abort, send_file, Response
from werkzeug.utils import secure_filename
import requests
from io import BytesIO

from models import FileType, FileStatus

def create_app(config, logger, file_manager):
    """Create Flask app with all routes"""
    
    app = Flask(__name__)
    
    # ========== AUTHENTICATION ==========
    def require_api_key(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            api_key = request.headers.get('X-API-Key')
            valid_key = config.get_api_key()
            
            if not api_key or not hmac.compare_digest(api_key, valid_key):
                logger.warning("Invalid API key attempt", metadata={'ip': request.remote_addr})
                abort(401, "Invalid API key")
            
            return f(*args, **kwargs)
        return decorated
    
    # ========== FILE UPLOAD ENDPOINTS ==========
    
    @app.route('/api/upload', methods=['POST'])
    @require_api_key
    def upload_file():
        """Upload single file - return file_id with status 200 on success, null on failure"""
        if 'file' not in request.files:
            logger.warning("Upload failed: No file provided")
            return jsonify(None), 400
        
        file = request.files['file']
        if file.filename == '':
            logger.warning("Upload failed: No file selected")
            return jsonify(None), 400
        
        try:
            file_data = file.read()
            filename = secure_filename(file.filename)
            
            metadata = file_manager.upload_file(
                file_data=file_data,
                filename=filename,
                mime_type=file.mimetype
            )
            
            logger.info(f"File uploaded: {metadata.file_id}")
            return jsonify({'file_id': metadata.file_id, 'status': 'pending'}), 200
            
        except Exception as e:
            logger.error(f"Upload failed: {e}", exc_info=True)
            return jsonify(None), 500
    
    @app.route('/api/upload/multiple', methods=['POST'])
    @require_api_key
    def upload_multiple_files():
        """Upload multiple files - return array of file_ids"""
        files = request.files.getlist('files')
        if not files:
            logger.warning("Multiple upload failed: No files provided")
            return jsonify({'file_ids': [], 'errors': ['No files provided']}), 400
        
        file_ids = []
        errors = []
        
        for file in files:
            if file and file.filename:
                try:
                    metadata = file_manager.upload_file(
                        file_data=file.read(),
                        filename=secure_filename(file.filename),
                        mime_type=file.mimetype
                    )
                    file_ids.append(metadata.file_id)
                    logger.info(f"File uploaded: {metadata.file_id}")
                except Exception as e:
                    errors.append({'filename': file.filename, 'error': str(e)})
                    logger.error(f"Upload failed for {file.filename}: {e}")
        
        return jsonify({'file_ids': file_ids, 'errors': errors}), 200
    
    @app.route('/api/upload/audio', methods=['POST'])
    @require_api_key
    def upload_audio_from_url():
        """Upload audio file from playable URL - return file_id on success"""
        data = request.json
        if not data or 'url' not in data:
            logger.warning("Audio upload failed: URL required")
            return jsonify({'error': 'URL required'}), 400
        
        try:
            url = data.get('url')
            filename = data.get('filename', 'audio_file')
            
            metadata = file_manager.import_from_url(url, filename)
            
            logger.info(f"Audio imported from URL: {metadata.file_id}")
            return jsonify({'file_id': metadata.file_id, 'status': 'pending'}), 200
            
        except Exception as e:
            logger.error(f"Audio URL import failed: {e}", exc_info=True)
            return jsonify(None), 500
    
    # ========== FILE INFO ENDPOINTS ==========
    
    @app.route('/api/file/<file_id>/info', methods=['GET'])
    @require_api_key
    def get_file_info(file_id):
        """Get complete file information"""
        metadata = file_manager.get_file(file_id)
        if not metadata:
            logger.warning(f"File info not found: {file_id}")
            return jsonify({'error': 'File not found'}), 404
        
        logger.info(f"File info retrieved: {file_id}")
        return jsonify(metadata.to_dict()), 200
    
    @app.route('/api/file/<file_id>/view-url', methods=['GET'])
    @require_api_key
    def get_view_url(file_id):
        """Get viewable file URL"""
        metadata = file_manager.get_file(file_id)
        if not metadata:
            logger.warning(f"View URL not found: {file_id}")
            return jsonify({'error': 'File not found'}), 404
        
        if metadata.status != FileStatus.COMPLETED:
            return jsonify({'error': f'File not ready: {metadata.status.value}'}), 202
        
        logger.info(f"View URL retrieved: {file_id}")
        return jsonify({'view_url': metadata.view_url}), 200
    
    @app.route('/api/file/<file_id>/download-url', methods=['GET'])
    @require_api_key
    def get_download_url(file_id):
        """Get download file URL"""
        metadata = file_manager.get_file(file_id)
        if not metadata:
            logger.warning(f"Download URL not found: {file_id}")
            return jsonify({'error': 'File not found'}), 404
        
        if metadata.status != FileStatus.COMPLETED:
            return jsonify({'error': f'File not ready: {metadata.status.value}'}), 202
        
        logger.info(f"Download URL retrieved: {file_id}")
        return jsonify({'download_url': metadata.download_url}), 200
    
    @app.route('/api/files', methods=['GET'])
    @require_api_key
    def list_files():
        """List all files with optional filtering"""
        try:
            file_type = request.args.get('type')
            limit = request.args.get('limit', 100, type=int)
            include_pending = request.args.get('pending', 'false').lower() == 'true'
            
            type_filter = None
            if file_type:
                try:
                    type_filter = FileType(file_type)
                except ValueError:
                    logger.warning(f"Invalid file type filter: {file_type}")
                    return jsonify({'error': f'Invalid file type. Valid types: audio, video, image, document, other'}), 400
            
            files = file_manager.list_files(file_type=type_filter, limit=limit, include_pending=include_pending)
            
            logger.info(f"Files listed: {len(files)} - Filter: {file_type or 'none'}, Pending: {include_pending}")
            print(f"📋 Listing files: {len(files)} total (pending: {include_pending})")
            for f in files:
                print(f"   - {f.file_id}: {f.filename} ({f.file_type.value}) - {f.status.value}")
            
            return jsonify({'total': len(files), 'files': [f.to_dict() for f in files]}), 200
        
        except Exception as e:
            logger.error(f"List files failed: {e}", exc_info=True)
            print(f"❌ List files error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/file/<file_id>', methods=['DELETE'])
    @require_api_key
    def delete_file(file_id):
        """Delete a file"""
        success = file_manager.delete_file(file_id)
        if not success:
            logger.warning(f"File delete failed: {file_id} not found")
            return jsonify({'error': 'File not found'}), 404
        
        logger.info(f"File deleted: {file_id}")
        return jsonify({'success': True, 'message': f'File {file_id} deleted'}), 200
    
    @app.route('/api/stats', methods=['GET'])
    @require_api_key
    def get_stats():
        """Get file server statistics"""
        stats = file_manager.get_stats()
        logger.info("Stats retrieved")
        return jsonify(stats), 200
    
    # ========== LOGGER ENDPOINTS ==========
    
    @app.route('/api/logger/create', methods=['POST'])
    @require_api_key
    def create_logger():
        """Create a new logger instance
        
        Request body:
        {
            "service_name": "my_service",
            "debug": false,
            "warning": true,
            "info": true
        }
        """
        try:
            data = request.json or {}
            service_name = data.get('service_name', 'unknown_service')
            debug = data.get('debug', False)
            warning = data.get('warning', False)
            info = data.get('info', False)
            
            logger_id = logger._create_pooled_logger(
                service_name=service_name,
                debug=debug,
                warning=warning,
                info=info
            )
            
            logger.info(f"Logger created: {logger_id} for {service_name}")
            return jsonify({
                'logger_id': logger_id,
                'service_name': service_name,
                'status': 'created'
            }), 200
        
        except Exception as e:
            logger.error(f"Failed to create logger: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/logger/<logger_id>', methods=['GET'])
    @require_api_key
    def get_logger_info(logger_id):
        """Get logger information"""
        try:
            pool_entry = logger.get_logger_info(logger_id)
            if not pool_entry:
                return jsonify({'error': 'Logger not found'}), 404
            
            logger.debug(f"Logger info retrieved: {logger_id}")
            return jsonify(pool_entry.to_dict()), 200
        
        except Exception as e:
            logger.error(f"Failed to get logger info: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/logger/<logger_id>/config', methods=['GET'])
    @require_api_key
    def get_logger_config(logger_id):
        """Get logger configuration"""
        try:
            config = logger.get_logger_config(logger_id)
            if not config:
                return jsonify({'error': 'Logger not found'}), 404
            
            return jsonify(config), 200
        
        except Exception as e:
            logger.error(f"Failed to get logger config: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/logger/<logger_id>/config', methods=['PUT'])
    @require_api_key
    def update_logger_config(logger_id):
        """Update logger configuration
        
        Request body:
        {
            "debug": true,
            "warning": true,
            "info": false
        }
        """
        try:
            data = request.json or {}
            debug = data.get('debug')
            warning = data.get('warning')
            info = data.get('info')
            
            updated_config = logger.update_logger_config(
                logger_id,
                debug=debug,
                warning=warning,
                info=info
            )
            
            if not updated_config:
                return jsonify({'error': 'Logger not found'}), 404
            
            logger.info(f"Logger config updated: {logger_id}")
            return jsonify(updated_config), 200
        
        except Exception as e:
            logger.error(f"Failed to update logger config: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/logger/<logger_id>/log', methods=['POST'])
    @require_api_key
    def log_message(logger_id):
        """Log a message to specific logger
        
        Request body:
        {
            "level": "info",
            "message": "Hello from external service",
            "metadata": {"key": "value"}
        }
        """
        try:
            data = request.json or {}
            level = data.get('level', 'info').lower()
            message = data.get('message', '')
            metadata = data.get('metadata', {})
            
            if not message:
                return jsonify({'error': 'Message required'}), 400
            
            if level not in ['debug', 'info', 'warning', 'error', 'critical']:
                return jsonify({'error': 'Invalid log level'}), 400
            
            service_logger = logger.get_logger(logger_id)
            if not service_logger:
                return jsonify({'error': 'Logger not found'}), 404
            
            # Log via service logger
            if level == 'debug':
                service_logger.debug(message, metadata=metadata)
            elif level == 'info':
                service_logger.info(message, metadata=metadata)
            elif level == 'warning':
                service_logger.warning(message, metadata=metadata)
            elif level == 'error':
                service_logger.error(message, metadata=metadata)
            elif level == 'critical':
                service_logger.critical(message, metadata=metadata)
            
            return jsonify({
                'logger_id': logger_id,
                'level': level,
                'message': message,
                'status': 'logged'
            }), 200
        
        except Exception as e:
            logger.error(f"Failed to log message: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/logger/list', methods=['GET'])
    @require_api_key
    def list_loggers():
        """List all active loggers in pool"""
        try:
            loggers_info = logger.get_all_loggers_info()
            
            logger.debug(f"Listed {len(loggers_info)} loggers")
            return jsonify({
                'total': len(loggers_info),
                'loggers': loggers_info
            }), 200
        
        except Exception as e:
            logger.error(f"Failed to list loggers: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/logger/stats', methods=['GET'])
    @require_api_key
    def get_logger_stats():
        """Get logger pool statistics"""
        try:
            stats = logger.get_pool_stats()
            
            return jsonify(stats), 200
        
        except Exception as e:
            logger.error(f"Failed to get logger stats: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/logger/ttl/status', methods=['GET'])
    @require_api_key
    def get_ttl_status():
        """Get TTL cleanup status"""
        try:
            status = logger.get_ttl_cleanup_status()
            return jsonify(status), 200
        except Exception as e:
            logger.error(f"Failed to get TTL status: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/logger/ttl/toggle', methods=['POST'])
    @require_api_key
    def toggle_ttl_cleanup():
        """Toggle TTL cleanup on/off
        
        Request body:
        {
            "enabled": true
        }
        """
        try:
            data = request.json or {}
            enabled = data.get('enabled')
            
            if enabled is None:
                # Toggle current state if not specified
                current_enabled = logger.enable_ttl_cleanup
                enabled = not current_enabled
            
            new_state = logger.set_ttl_cleanup(enabled)
            
            status_msg = "enabled" if new_state else "disabled"
            logger.info(f"TTL cleanup {status_msg}")
            
            return jsonify({
                'enabled': new_state,
                'message': f'TTL cleanup {status_msg}',
                'ttl_seconds': logger.ttl_seconds,
                'active_loggers': len(logger._logger_pool)
            }), 200
        
        except Exception as e:
            logger.error(f"Failed to toggle TTL cleanup: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/logger/<logger_id>/test', methods=['POST'])
    @require_api_key
    def test_logger(logger_id):
        """Send test message to logger"""
        try:
            service_logger = logger.get_logger(logger_id)
            if not service_logger:
                return jsonify({'error': 'Logger not found'}), 404
            
            service_logger.info(f"Test message from API at {datetime.now()}", metadata={'test': True})
            
            return jsonify({
                'logger_id': logger_id,
                'status': 'test_message_sent',
                'timestamp': datetime.now().isoformat()
            }), 200
        
        except Exception as e:
            logger.error(f"Failed to test logger: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/logger/<logger_id>', methods=['DELETE'])
    @require_api_key
    def delete_logger(logger_id):
        """Delete a logger from pool"""
        try:
            success = logger.remove_logger(logger_id)
            
            if not success:
                return jsonify({'error': 'Logger not found'}), 404
            
            logger.info(f"Logger deleted: {logger_id}")
            return jsonify({
                'logger_id': logger_id,
                'status': 'deleted'
            }), 200
        
        except Exception as e:
            logger.error(f"Failed to delete logger: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ========== FILE VIEW/STREAM ENDPOINTS ==========
    
    @app.route('/view/<identifier>', methods=['GET'])
    def view_file(identifier):
        """Stream file for playing in browser (audio/video/image)
        
        Works with both file_id and telegram_file_id
        """
        try:
            # Try to find file by file_id first
            metadata = file_manager.get_file(identifier)
            
            # If not found by file_id, try to find by telegram_file_id
            if not metadata:
                for file_info in file_manager.repository._files.values():
                    if file_info.telegram_file_id == identifier:
                        metadata = file_info
                        break
            
            if not metadata:
                logger.warning(f"View failed: File not found - {identifier}")
                return jsonify({'error': 'File not found'}), 404
            
            logger.info(f"View file requested: {metadata.file_id} - {metadata.filename}")
            
            # Get Telegram bot token from config
            bot_token = config.get('server_bot_token')
            
            # Get file path from Telegram
            api_url = f"https://api.telegram.org/bot{bot_token}"
            try:
                file_info_response = requests.get(
                    f"{api_url}/getFile",
                    params={'file_id': metadata.telegram_file_id},
                    timeout=10
                )
                file_info_data = file_info_response.json()
                
                if not file_info_data.get('ok'):
                    logger.error(f"Failed to get file info from Telegram: {file_info_data}")
                    return jsonify({'error': 'Failed to retrieve file'}), 500
                
                file_path = file_info_data['result']['file_path']
                download_url = f"{api_url}/file/{file_path}"
                
                # Stream the file from Telegram
                file_response = requests.get(download_url, stream=True, timeout=30)
                
                if file_response.status_code != 200:
                    logger.error(f"Failed to download file from Telegram: {file_response.status_code}")
                    return jsonify({'error': 'Failed to download file'}), 500
                
                # Create response with proper headers for streaming
                def generate():
                    for chunk in file_response.iter_content(chunk_size=8192):
                        if chunk:
                            yield chunk
                
                response = Response(generate(), mimetype=metadata.mime_type)
                response.headers['Content-Length'] = file_response.headers.get('Content-Length')
                response.headers['Accept-Ranges'] = 'bytes'
                response.headers['Cache-Control'] = 'public, max-age=86400'
                
                # Don't force download - let browser handle it
                response.headers['Content-Disposition'] = f'inline; filename="{metadata.filename}"'
                
                logger.info(f"File viewed: {metadata.filename} ({metadata.file_id})")
                return response
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Telegram request failed: {e}")
                return jsonify({'error': 'Failed to retrieve file from storage'}), 500
        
        except Exception as e:
            logger.error(f"View file failed: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    # ========== HEALTH CHECK ==========
    
    @app.route('/health')
    def health():
        """Health check endpoint"""
        return jsonify({
            'status': 'healthy',
            'service': config.get('service_name'),
            'timestamp': datetime.now().isoformat()
        }), 200
    
    return app