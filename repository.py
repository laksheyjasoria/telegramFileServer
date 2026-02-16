"""
File repository for persistent storage
"""
import os
import json
import threading
from typing import Dict, Optional, List
from models import FileMetadata, FileType, FileStatus

class FileRepository:
    """File repository with JSON persistence"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.files_file = os.path.join(data_dir, 'files.json')
        self._files: Dict[str, FileMetadata] = {}
        self._lock = threading.RLock()
        
        # Load existing data
        self._load()
    
    def _load(self):
        """Load files from disk"""
        if os.path.exists(self.files_file):
            try:
                with open(self.files_file, 'r') as f:
                    data = json.load(f)
                    print(f"📂 Found {len(data)} files in storage")
                    loaded_count = 0
                    failed_count = 0
                    for file_id, file_data in data.items():
                        try:
                            metadata = FileMetadata.from_dict(file_data)
                            self._files[file_id] = metadata
                            loaded_count += 1
                            print(f"   ✅ Loaded: {file_id} - {metadata.filename} ({metadata.file_type.value})")
                        except Exception as e:
                            failed_count += 1
                            print(f"   ❌ Failed to load {file_id}: {e}")
                print(f"✅ Total loaded: {loaded_count}, Failed: {failed_count}")
            except Exception as e:
                print(f"❌ Failed to load files: {e}")
                import traceback
                traceback.print_exc()
    
    def _save(self):
        """Save files to disk"""
        try:
            temp_file = self.files_file + '.tmp'
            with open(temp_file, 'w') as f:
                data = {fid: meta.to_dict() for fid, meta in self._files.items()}
                json.dump(data, f, indent=2)
            os.replace(temp_file, self.files_file)
        except Exception as e:
            print(f"⚠️ Failed to save files: {e}")
    
    def add(self, metadata: FileMetadata):
        """Add or update file"""
        with self._lock:
            self._files[metadata.file_id] = metadata
            self._save()
    
    def get(self, identifier: str) -> Optional[FileMetadata]:
        """Get file by ID"""
        with self._lock:
            return self._files.get(identifier)
    
    def get_by_short_code(self, short_code: str) -> Optional[FileMetadata]:
        """Get file by short code (deprecated - always returns None)"""
        return None
    
    def delete(self, identifier: str) -> bool:
        """Delete file"""
        with self._lock:
            metadata = self.get(identifier)
            if not metadata:
                return False
            
            del self._files[metadata.file_id]
            self._save()
            return True
    
    def list_all(self, file_type: Optional[FileType] = None, 
                 status: Optional[FileStatus] = None,
                 limit: int = 100) -> List[FileMetadata]:
        """List files with optional filtering"""
        with self._lock:
            files = list(self._files.values())
            
            if file_type:
                files = [f for f in files if f.file_type == file_type]
            if status:
                files = [f for f in files if f.status == status]
            
            files.sort(key=lambda x: x.created_at, reverse=True)
            return files[:limit]
    
    def list_all_by_type(self, file_type: Optional[FileType] = None,
                        limit: int = 100) -> List[FileMetadata]:
        """List all non-failed files with optional type filtering"""
        with self._lock:
            files = list(self._files.values())
            
            # Filter out failed files
            files = [f for f in files if f.status != FileStatus.FAILED]
            
            if file_type:
                files = [f for f in files if f.file_type == file_type]
            
            files.sort(key=lambda x: x.created_at, reverse=True)
            return files[:limit]
    
    def get_all_short_codes(self) -> list:
        """Get all short codes (deprecated - returns empty list)"""
        return []
    
    def get_stats(self) -> Dict:
        """Get repository statistics"""
        with self._lock:
            total_size = 0
            type_counts = {}
            status_counts = {}
            
            for f in self._files.values():
                if f.status == FileStatus.COMPLETED:
                    total_size += f.size
                type_counts[f.file_type.value] = type_counts.get(f.file_type.value, 0) + 1
                status_counts[f.status.value] = status_counts.get(f.status.value, 0) + 1
            
            size_copy = total_size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_copy < 1024:
                    size_formatted = f"{size_copy:.1f} {unit}"
                    break
                size_copy /= 1024
            else:
                size_formatted = f"{size_copy:.1f} TB"
            
            return {
                'total_files': len(self._files),
                'completed_files': status_counts.get('completed', 0),
                'pending_files': status_counts.get('pending', 0) + status_counts.get('processing', 0),
                'failed_files': status_counts.get('failed', 0),
                'total_size': total_size,
                'total_size_formatted': size_formatted,
                'by_type': type_counts,
                'by_status': status_counts
            }