"""
Telegram storage backend with separate view/download URLs
"""
import requests
import threading
import json
from typing import Dict, Optional
from abc import ABC, abstractmethod

class StorageBackend(ABC):
    """Abstract storage backend"""
    
    @abstractmethod
    def save(self, data: bytes, filename: str) -> Dict[str, str]:
        """Save file and return identifiers"""
        pass
    
    @abstractmethod
    def delete(self, identifier: str) -> bool:
        """Delete file"""
        pass

class TelegramStorageBackend(StorageBackend):
    """Telegram-based storage backend"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        self._session = requests.Session()
        self._lock = threading.RLock()
    
    def save(self, data: bytes, filename: str) -> Dict[str, str]:
        """Save file to Telegram and return IDs with separate view/download URLs"""
        try:
            print(f"📤 Uploading to Telegram: {filename} ({len(data)} bytes)")
            
            # Upload to Telegram
            files = {'document': (filename, data)}
            response = self._session.post(
                f"{self.api_url}/sendDocument",
                data={'chat_id': self.chat_id},
                files=files,
                timeout=300
            )
            
            print(f"📡 Telegram response status: {response.status_code}")
            
            if not response.ok:
                print(f"❌ Upload failed with status: {response.status_code}")
                print(f"Response text: {response.text[:500]}")
                raise Exception(f"Upload failed: {response.status_code}")
            
            result = response.json()
            
            if not result.get('ok'):
                print(f"❌ Telegram error: {result}")
                raise Exception(f"Telegram error: {result}")
            
            # Extract file info from message
            message = result['result']
            file_info, file_type = self._extract_file_info(message)
            
            if not file_info:
                print(f"❌ Could not extract file info from: {list(message.keys())}")
                raise Exception("Could not extract file info")
            
            telegram_file_id = file_info['file_id']
            print(f"✅ Got Telegram file ID: {telegram_file_id}")
            
            # Get download URL
            file_data = self._session.get(
                f"{self.api_url}/getFile",
                params={'file_id': telegram_file_id}
            ).json()
            
            if not file_data.get('ok'):
                print(f"❌ Failed to get file URL: {file_data}")
                raise Exception("Failed to get file URL")
            
            file_path = file_data['result']['file_path']
            print(f"✅ Got file path: {file_path}")
            
            # Generate URLs
            base_url = f"https://api.telegram.org/file/bot{self.bot_token}"
            download_url = f"{base_url}/{file_path}"
            
            # Get mime type
            mime_type = file_info.get('mime_type', 'application/octet-stream')
            
            # Create different view and download URLs
            # View URL will be our own endpoint that properly displays content
            view_url = f"/view/{telegram_file_id}"  # This will be handled by our API
            
            print(f"✅ Upload successful!")
            print(f"📥 Download URL: {download_url}")
            print(f"👁️ View URL: {view_url}")
            
            return {
                'telegram_id': telegram_file_id,
                'download_url': download_url,
                'view_url': view_url,
                'mime_type': mime_type,
                'file_type': file_type
            }
            
        except Exception as e:
            print(f"❌ Telegram storage failed: {e}")
            import traceback
            traceback.print_exc()
            raise Exception(f"Telegram storage failed: {e}")
    
    def _extract_file_info(self, message: Dict) -> tuple:
        """Extract file info from Telegram message and determine file type"""
        print(f"🔍 Extracting file info from: {list(message.keys())}")
        
        # Check all possible locations
        locations = {
            'document': 'document',
            'audio': 'audio',
            'voice': 'audio',
            'video': 'video',
            'photo': 'image',
            'sticker': 'image',
            'animation': 'video',
            'video_note': 'video'
        }
        
        for loc, file_type in locations.items():
            if loc in message:
                print(f"✅ Found file in '{loc}' (type: {file_type})")
                if loc == 'photo':
                    # Photos come in array, get largest
                    return message[loc][-1], file_type
                return message[loc], file_type
        
        print(f"❌ No file info found in message")
        return None, None
    
    def delete(self, identifier: str) -> bool:
        """Delete from Telegram (not directly supported)"""
        return False