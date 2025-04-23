"""
Core file processing with type-aware handling
"""
from enum import Enum
from vision_processor import VisionProcessor
from typing import Optional
import logging
from pdf_utils import extract_text_locally

class FileType(Enum):
    TEXT = 1
    PDF = 2  
    SCANNED_DOC = 3
    PHOTO = 4
    OTHER = 5

class FileProcessor:
    def __init__(self, vision_creds_path: str):
        self.vision = VisionProcessor(vision_creds_path)
        
    def process(self, file_bytes: bytes, file_type: FileType) -> Optional[str]:
        try:
            if file_type == FileType.TEXT:
                return self._process_text(file_bytes)
            elif file_type == FileType.PDF:
                return self._process_pdf(file_bytes)
            elif file_type == FileType.SCANNED_DOC:
                return self.vision.extract_text(file_bytes)
            elif file_type == FileType.PHOTO:
                return ", ".join(self.vision.analyze_image(file_bytes))
            else:
                return None
                
        except Exception as e:
            logging.error(f"Processing failed: {str(e)}")
            return None

    def _process_text(self, file_bytes: bytes) -> str:
        return file_bytes.decode('utf-8')[:5000]  # Truncate long texts

    def _process_pdf(self, file_bytes: bytes) -> str:
        """Enhanced PDF processing with local+cloud fallback"""
        text = extract_text_locally(file_bytes)
        
        # If local extraction fails or returns empty, use Vision API
        if not text.strip():
            logging.info("Local PDF extraction failed, trying Vision API")
            text = self.vision.extract_text(file_bytes) or ""
            
        return text[:5000]  # Truncate long content
