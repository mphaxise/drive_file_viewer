"""
Tests for file type detection
"""
import unittest
from file_type import detect_filetype, FileType

class TestFileType(unittest.TestCase):
    def test_pdf_detection(self):
        self.assertEqual(detect_filetype("doc.pdf"), FileType.PDF)
        self.assertEqual(detect_filetype("doc.pdf", "application/pdf"), FileType.PDF)
        
    def test_text_detection(self):
        self.assertEqual(detect_filetype("notes.txt"), FileType.TEXT)
        self.assertEqual(detect_filetype("data.csv", "text/csv"), FileType.TEXT)
        
    def test_image_detection(self):
        self.assertEqual(detect_filetype("scan.jpg"), FileType.SCANNED_DOC)
        self.assertEqual(detect_filetype("photo.png"), FileType.PHOTO)
        self.assertEqual(detect_filetype("doc.tiff", "image/tiff"), FileType.SCANNED_DOC)

if __name__ == "__main__":
    unittest.main()
