"""
Google Drive integration with hybrid processing
"""
from auth import get_credentials
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from file_type import detect_filetype
from file_processor import FileProcessor
import io
import logging

class DriveService:
    def __init__(self, vision_creds_path: str):
        self.creds = get_credentials()
        self.service = build('drive', 'v3', credentials=self.creds)
        self.processor = FileProcessor(vision_creds_path)

    def process_folder(self, folder_id: str) -> list:
        """Process all files in a Drive folder"""
        files = self._list_files(folder_id)
        results = []
        
        for file in files:
            try:
                file_bytes = self._download_file(file['id'])
                file_type = detect_filetype(file['name'], file.get('mimeType', ''))
                summary = self.processor.process(file_bytes, file_type)
                
                results.append({
                    'name': file['name'],
                    'type': file_type.name,
                    'summary': summary,
                    'webViewLink': file.get('webViewLink')
                })
            except Exception as e:
                logging.error(f"Failed to process {file['name']}: {str(e)}")
                
        return results

    def _list_files(self, folder_id: str) -> list:
        """List all files in a Drive folder"""
        results = self.service.files().list(
            q=f"'{folder_id}' in parents",
            fields="files(id,name,mimeType,webViewLink)"
        ).execute()
        return results.get('files', [])

    def _download_file(self, file_id: str) -> bytes:
        """Download file content as bytes"""
        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while not done:
            _, done = downloader.next_chunk()
            
        return fh.getvalue()
