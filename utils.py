import random
import string
import secrets
import mimetypes
from typing import Optional, Set
from models import FileType

def generate_short_code(length: int = 6, existing_codes: Set[str] = None) -> str:
    """Generate unique short code"""
    chars = string.ascii_letters + string.digits
    existing = existing_codes or set()
    
    while True:
        code = ''.join(random.choices(chars, k=length))
        if code not in existing:
            return code

def generate_file_id() -> str:
    """Generate unique file ID"""
    return secrets.token_hex(4)

def detect_file_type(mime_type: str) -> FileType:
    """Detect file type from mime type"""
    if not mime_type:
        return FileType.OTHER
    
    mime_lower = mime_type.lower()
    
    if mime_lower.startswith('audio/'):
        return FileType.AUDIO
    elif mime_lower.startswith('video/'):
        return FileType.VIDEO
    elif mime_lower.startswith('image/'):
        return FileType.IMAGE
    elif 'pdf' in mime_lower or 'word' in mime_lower or 'document' in mime_lower or 'text' in mime_lower:
        return FileType.DOCUMENT
    else:
        return FileType.OTHER

def secure_filename(filename: str) -> str:
    """Make filename safe for filesystem"""
    return ''.join(c for c in filename if c.isalnum() or c in '._-').strip()

def format_size(size_bytes: int) -> str:
    """Format file size human readable"""
    size = size_bytes
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

def get_mime_type(filename: str) -> str:
    """Guess mime type from filename"""
    return mimetypes.guess_type(filename)[0] or 'application/octet-stream'