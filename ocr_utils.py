"""
ocr_utils.py: Helper functions to perform OCR on images and PDFs.
"""

import io
from pathlib import Path
from PIL import Image
import pytesseract

# Optional PDF conversion
try:
    from pdf2image import convert_from_bytes
except ImportError:
    convert_from_bytes = None

# Optional OpenCV for preprocessing
try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None


def preprocess_image(image: Image.Image) -> Image.Image:
    """Convert to grayscale and apply threshold for better OCR accuracy."""
    if cv2 and np is not None:
        img_np = np.array(image)
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        return Image.fromarray(thresh)
    else:
        return image.convert("L")


def extract_text_from_image(image: Image.Image) -> str:
    """
    Extract text from a PIL Image using pytesseract OCR.
    """
    processed = preprocess_image(image)
    return pytesseract.image_to_string(processed)


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """
    Convert PDF bytes into images and extract text from each page.
    """
    if convert_from_bytes is None:
        raise RuntimeError("pdf2image is not installed. Please add it to requirements.")
    images = convert_from_bytes(pdf_bytes)
    texts = []
    for img in images:
        texts.append(extract_text_from_image(img))
    return "\n".join(texts)


def extract_text_from_file_bytes(file_bytes: bytes, file_name: str) -> str:
    """
    Determine file type by extension and run appropriate OCR.
    """
    ext = Path(file_name).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf_bytes(file_bytes)
    elif ext in [".jpg", ".jpeg", ".png", ".tif", ".tiff"]:
        image = Image.open(io.BytesIO(file_bytes))
        return extract_text_from_image(image)
    else:
        raise ValueError(f"Unsupported file type for OCR: {ext}")
