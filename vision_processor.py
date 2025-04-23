"""
Google Cloud Vision API integration for OCR and image analysis
"""
import os
import logging
from google.cloud import vision
from google.api_core.exceptions import GoogleAPICallError

class VisionProcessor:
    def __init__(self, credentials_path=None):
        """
        Initialize with path to service account JSON.
        Example: VisionProcessor("vision_credentials.json")
        """
        self.client = self._authenticate(credentials_path)
        
    def _authenticate(self, path):
        """Securely load Vision API credentials"""
        if not path or not os.path.exists(path):
            raise ValueError("Valid credentials path required")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
        return vision.ImageAnnotatorClient()

    def extract_text(self, image_bytes):
        """Extract text from image/PDF using OCR"""
        try:
            image = vision.Image(content=image_bytes)
            response = self.client.document_text_detection(image=image)
            return response.full_text_annotation.text
        except GoogleAPICallError as e:
            logging.error(f"Vision API error: {e.message}")
            return None
        
    def analyze_image(self, image_bytes):
        """Get labels/tags for photos"""
        try:
            image = vision.Image(content=image_bytes)
            response = self.client.label_detection(image=image)
            return [label.description for label in response.label_annotations]
        except GoogleAPICallError as e:
            logging.error(f"Vision API error: {e.message}")
            return []
