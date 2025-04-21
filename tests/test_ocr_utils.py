import io
import pytest
from PIL import Image
import ocr_utils

# Test preprocess_image without OpenCV
def test_preprocess_image_no_cv(monkeypatch):
    # Simulate OpenCV not installed
    monkeypatch.setattr(ocr_utils, 'cv2', None)
    monkeypatch.setattr(ocr_utils, 'np', None)
    img = Image.new('RGB', (10, 10), color='white')
    result = ocr_utils.preprocess_image(img)
    assert isinstance(result, Image.Image)
    # Should be grayscale
    assert result.mode == 'L'

# Test extract_text_from_image using pytesseract mock
def test_extract_text_from_image(monkeypatch):
    img = Image.new('RGB', (5, 5), color='white')
    monkeypatch.setattr(ocr_utils.pytesseract, 'image_to_string', lambda im: 'dummy-text')
    text = ocr_utils.extract_text_from_image(img)
    assert text == 'dummy-text'

# Test PDF OCR extraction
def test_extract_text_from_pdf_bytes(monkeypatch):
    dummy_pdf = b'%PDF-1.4 fake content'
    img1 = Image.new('RGB', (3, 3), color='white')
    img2 = Image.new('RGB', (2, 2), color='white')
    # Mock pdf2image
    monkeypatch.setattr(ocr_utils, 'convert_from_bytes', lambda b: [img1, img2])
    # Mock per-image OCR
    calls = []
    def fake_extract(im):
        calls.append(im.size)
        return f'text{len(calls)}'
    monkeypatch.setattr(ocr_utils, 'extract_text_from_image', fake_extract)
    combined = ocr_utils.extract_text_from_pdf_bytes(dummy_pdf)
    assert combined == 'text1\ntext2'

# Test dispatch for file bytes
def test_extract_text_from_file_bytes_pdf(monkeypatch):
    dummy_pdf = b'%PDF data'
    img = Image.new('RGB', (4, 4), color='white')
    monkeypatch.setattr(ocr_utils, 'convert_from_bytes', lambda b: [img])
    monkeypatch.setattr(ocr_utils, 'extract_text_from_image', lambda im: 'page-text')
    result = ocr_utils.extract_text_from_file_bytes(dummy_pdf, 'doc.PDF')
    assert result == 'page-text'

# Test image dispatch
def test_extract_text_from_file_bytes_image(monkeypatch):
    dummy = b'fake-image-bytes'
    img = Image.new('RGB', (6, 6), color='white')
    # Mock PIL.Image.open
    monkeypatch.setattr(ocr_utils.Image, 'open', lambda fp: img)
    monkeypatch.setattr(ocr_utils, 'extract_text_from_image', lambda im: 'img-text')
    result = ocr_utils.extract_text_from_file_bytes(dummy, 'photo.jpg')
    assert result == 'img-text'

# Test unsupported extension
def test_extract_text_from_file_bytes_unsupported():
    with pytest.raises(ValueError):
        ocr_utils.extract_text_from_file_bytes(b'data', 'file.unsupported')
