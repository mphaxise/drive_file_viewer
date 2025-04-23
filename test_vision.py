"""
Test script for Google Cloud Vision credentials
"""
import os
from vision_processor import VisionProcessor

def test_credentials():
    try:
        # Initialize with your credentials path
        processor = VisionProcessor("vision_credentials.json")
        print("✅ Credentials validated successfully")
        return True
    except Exception as e:
        print(f"❌ Credential validation failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_credentials()
