"""
Data models with serialization support
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

class FileType(Enum):
    """File type categories"""
    AUDIO = "audio"
    VIDEO = "video"
    IMAGE = "image"
    DOCUMENT = "document"
    OTHER = "other"

class FileStatus(Enum):
    """File upload status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class FileMetadata:
    """File metadata with serialization support"""
    file_id: str
    filename: str
    size: int
    mime_type: str
    file_type: FileType
    telegram_file_id: Optional[str] = None
    url: Optional[str] = None
    view_url: Optional[str] = None
    download_url: Optional[str] = None
    status: FileStatus = FileStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        size_copy = self.size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_copy < 1024:
                size_formatted = f"{size_copy:.1f} {unit}"
                break
            size_copy /= 1024
        else:
            size_formatted = f"{size_copy:.1f} TB"
        
        return {
            'file_id': self.file_id,
            'filename': self.filename,
            'size': self.size,
            'size_formatted': size_formatted,
            'mime_type': self.mime_type,
            'file_type': self.file_type.value,
            'telegram_file_id': self.telegram_file_id,
            'url': self.url,
            'view_url': self.view_url,
            'download_url': self.download_url,
            'status': self.status.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FileMetadata':
        """Create from dictionary after JSON deserialization"""
        # Remove fields that don't exist in the dataclass
        data = {k: v for k, v in data.items() if k in ['file_id', 'filename', 'size', 'mime_type', 'file_type', 
                                                          'telegram_file_id', 'url', 'view_url', 'download_url',
                                                          'status', 'created_at', 'updated_at', 'metadata']}
        
        # Convert string enums back to Enum objects
        if 'file_type' in data and isinstance(data['file_type'], str):
            data['file_type'] = FileType(data['file_type'])
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = FileStatus(data['status'])
        
        # Convert string dates back to datetime
        if 'created_at' in data and data['created_at']:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and data['updated_at']:
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        
        return cls(**data)
    
    def update(self, **kwargs):
        """Update metadata fields"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now()