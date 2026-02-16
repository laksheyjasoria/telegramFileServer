import requests
import mimetypes
from typing import Optional, Tuple
from abc import ABC, abstractmethod

from models import FileMetadata, FileStatus, FileType
from storage import TelegramStorageBackend  # ✅ Updated import
from utils import generate_file_id, detect_file_type, get_mime_type

class FileProcessor(ABC):
    """Abstract file processor"""
    
    @abstractmethod
    def process(self, source: any, filename: Optional[str] = None) -> Tuple[FileMetadata, Optional[bytes]]:
        pass

class URLImportProcessor(FileProcessor):
    """Process files from URLs"""
    
    def __init__(self, storage: TelegramStorageBackend, max_size: int = 2000 * 1024 * 1024):  # ✅ Updated type
        self.storage = storage
        self.max_size = max_size
        self._session = requests.Session()
    
    def process(self, url: str, filename: Optional[str] = None) -> Tuple[FileMetadata, Optional[bytes]]:
        try:
            response = self._session.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            content_length = int(response.headers.get('content-length', 0))
            if content_length > self.max_size:
                raise Exception(f"File too large: {content_length} bytes")
            
            if not filename:
                filename = url.split('/')[-1].split('?')[0]
                if not filename:
                    filename = f"download_{generate_file_id()}"
            
            data = response.content
            mime_type = response.headers.get('content-type') or get_mime_type(filename)
            
            result = self.storage.save(data, filename)
            
            metadata = FileMetadata(
                file_id=generate_file_id(),
                filename=filename,
                size=len(data),
                mime_type=result['mime_type'],
                file_type=detect_file_type(result['mime_type']),
                telegram_file_id=result['telegram_id'],
                url=url,
                view_url=result['view_url'],
                download_url=result['download_url'],
                status=FileStatus.COMPLETED,
                metadata={'source_url': url}
            )
            
            return metadata, None
            
        except Exception as e:
            raise Exception(f"URL import failed: {e}")

class DirectUploadProcessor(FileProcessor):
    """Process direct file uploads"""
    
    def __init__(self, storage: TelegramStorageBackend, max_size: int = 2000 * 1024 * 1024):  # ✅ Updated type
        self.storage = storage
        self.max_size = max_size
    
    def process(self, data: bytes, filename: str, mime_type: Optional[str] = None) -> Tuple[FileMetadata, bytes]:
        if len(data) > self.max_size:
            raise Exception(f"File too large. Max: {self.max_size/(1024*1024)}MB")
        
        if not mime_type:
            mime_type = get_mime_type(filename)
        
        file_type = detect_file_type(mime_type)
        file_id = generate_file_id()
        
        print(f"📝 Processing upload: {filename}")
        print(f"   📦 Size: {len(data)} bytes")
        print(f"   🏷️ MIME: {mime_type}")
        print(f"   🎯 Type: {file_type.value}")
        print(f"   🆔 ID: {file_id}")
        
        metadata = FileMetadata(
            file_id=file_id,
            filename=filename,
            size=len(data),
            mime_type=mime_type,
            file_type=file_type,
            status=FileStatus.PROCESSING
        )
        
        return metadata, data