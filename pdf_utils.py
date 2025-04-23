"""
Local PDF text extraction using PyMuPDF
"""
import io
import logging
try:
    import fitz  # PyMuPDF
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    logging.warning("PyMuPDF not available - PDF text extraction disabled")

def extract_text_locally(pdf_bytes: bytes) -> str:
    if not PDF_SUPPORT:
        return ""
    
    try:
        with io.BytesIO(pdf_bytes) as stream:
            doc = fitz.open(stream=stream)
            return "\n".join(page.get_text() for page in doc)
    except Exception as e:
        logging.error(f"PDF extraction failed: {str(e)}")
        return ""
