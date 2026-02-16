import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List, Dict, Set

from models import FileMetadata, FileType, FileStatus
from repository import FileRepository
from storage import TelegramStorageBackend  # ✅ Updated import
from logger import TelegramLogger
from processors import DirectUploadProcessor, URLImportProcessor
from utils import detect_file_type

class FileManager:
    """Main file manager"""
    
    def __init__(self, storage: TelegramStorageBackend, logger: TelegramLogger, data_dir: str):
        self.storage = storage
        self.logger = logger
        self.repository = FileRepository(data_dir)
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=5)
        
        # Initialize processors
        self.upload_processor = DirectUploadProcessor(storage)
        self.url_processor = URLImportProcessor(storage)
        
        self.logger.info("File manager initialized", metadata={'files': len(self.repository.list_all())})
    
    def upload_file(self, file_data: bytes, filename: str, mime_type: str = None) -> FileMetadata:
        """Upload file directly"""
        try:
            metadata, data = self.upload_processor.process(file_data, filename, mime_type)
            self.repository.add(metadata)
            
            self.logger.info(f"File upload initiated: {filename} ({metadata.file_id}) - Type: {metadata.file_type.value}")
            
            def process_upload():
                try:
                    result = self.storage.save(data, filename)
                    
                    # Only update fields from storage, preserve mime_type from original upload
                    metadata.update(
                        telegram_file_id=result['telegram_id'],
                        download_url=result['download_url'],
                        view_url=result['view_url'],
                        status=FileStatus.COMPLETED
                    )
                    
                    self.repository.add(metadata)
                    self.logger.info(f"File upload completed: {filename} ({metadata.file_id})")
                    
                except Exception as e:
                    metadata.update(status=FileStatus.FAILED, metadata={'error': str(e)})
                    self.repository.add(metadata)
                    self.logger.error(f"Upload failed: {filename} ({metadata.file_id})", exc_info=True)
            
            self._executor.submit(process_upload)
            return metadata
            
        except Exception as e:
            self.logger.error(f"Upload initiation failed: {e}", exc_info=True)
            raise
    
    def import_from_url(self, url: str, filename: str = None) -> FileMetadata:
        """Import file from URL"""
        try:
            metadata, _ = self.url_processor.process(url, filename)
            self.repository.add(metadata)
            self.logger.info(f"File imported from URL: {metadata.filename}")
            return metadata
            
        except Exception as e:
            self.logger.error(f"URL import failed: {e}")
            raise
    
    def get_file(self, identifier: str) -> Optional[FileMetadata]:
        return self.repository.get(identifier)
    
    def list_files(self, file_type: FileType = None, limit: int = 100, include_pending: bool = False) -> List[FileMetadata]:
        """List files with optional filtering
        
        Args:
            file_type: Optional file type filter
            limit: Maximum files to return
            include_pending: If True, include PENDING and PROCESSING files. If False, only COMPLETED.
        """
        if include_pending:
            # Return all non-failed files
            files = self.repository.list_all_by_type(file_type=file_type, limit=limit)
        else:
            # Return only completed files
            files = self.repository.list_all(file_type=file_type, status=FileStatus.COMPLETED, limit=limit)
        
        return files
    
    def delete_file(self, identifier: str) -> bool:
        metadata = self.get_file(identifier)
        if not metadata:
            return False
        
        if metadata.telegram_file_id:
            self.storage.delete(metadata.telegram_file_id)
        
        result = self.repository.delete(identifier)
        
        if result:
            self.logger.info(f"File deleted: {metadata.filename}")
        
        return result
    
    def get_stats(self) -> Dict:
        return self.repository.get_stats()