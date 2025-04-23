"""
File type detection using MIME types and extensions
"""
import mimetypes
from enum import Enum
from pathlib import Path

class FileType(Enum):
    TEXT = 1
    PDF = 2  
    SCANNED_DOC = 3
    PHOTO = 4
    OTHER = 5

# Supported text extensions
TEXT_EXTS = {'.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm', '.log'}
# Supported image extensions
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.tiff', '.bmp'}

def detect_filetype(filename: str, mime_type: str = "") -> FileType:
    """Determine file type using extension + MIME type"""
    path = Path(filename)
    ext = path.suffix.lower()
    
    # Check MIME type first if available
    if mime_type:
        if 'pdf' in mime_type.lower():
            return FileType.PDF
        elif 'text' in mime_type.lower() and ext in TEXT_EXTS:
            return FileType.TEXT
        elif 'image' in mime_type.lower():
            return FileType.SCANNED_DOC if ext in {'.jpg', '.jpeg', '.tiff'} else FileType.PHOTO
    
    # Fallback to extension
    if ext == '.pdf':
        return FileType.PDF
    elif ext in TEXT_EXTS:
        return FileType.TEXT
    elif ext in IMAGE_EXTS:
        return FileType.SCANNED_DOC if ext in {'.jpg', '.jpeg', '.tiff'} else FileType.PHOTO
    
    return FileType.OTHER
