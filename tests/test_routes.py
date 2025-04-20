import unittest
from unittest.mock import patch, MagicMock
import os
import json
import sys
import flask
from io import BytesIO

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app

class TestWebRoutes(unittest.TestCase):
    """Test cases for web routes and API endpoints."""
    
    def setUp(self):
        """Set up test environment."""
        self.app = app.app
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test_secret_key'
        self.client = self.app.test_client()
        
        # Create a test session
        with self.app.test_request_context():
            flask.session['credentials'] = 'test_credentials'
            flask.session['current_folder'] = 'test_folder_id'
    
    def tearDown(self):
        """Clean up after tests."""
        pass
    
    @patch('app.build')
    @patch('app.list_files_in_folder')
    @patch('app.get_folder_name')
    def test_list_files_endpoint(self, mock_get_folder_name, mock_list_files, mock_build):
        """Test the list-files endpoint."""
        # Mock the folder name and file listing
        mock_get_folder_name.return_value = 'Test Folder'
        mock_list_files.return_value = {
            'folderName': 'Test Folder',
            'items': [
                {
                    'id': 'file1',
                    'name': 'test.txt',
                    'mimeType': 'text/plain',
                    'webViewLink': 'https://drive.google.com/file/d/file1/view',
                    'summary': 'This is a test file.'
                }
            ],
            'folders': [
                {
                    'id': 'folder1',
                    'name': 'Subfolder',
                    'mimeType': 'application/vnd.google-apps.folder'
                }
            ]
        }
        
        # Set up a session with token
        with self.client.session_transaction() as session:
            session['token'] = json.dumps({
                'token': 'test_token',
                'refresh_token': 'test_refresh_token',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'client_id': 'test_client_id',
                'client_secret': 'test_client_secret',
                'scopes': ['https://www.googleapis.com/auth/drive.readonly']
            })
        
        # Test the list-files endpoint
        response = self.client.post('/list-files', 
                                   json={'folder_url': 'https://drive.google.com/drive/folders/test_folder_id'})
        
        # Check the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['folderName'], 'Test Folder')
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(data['items'][0]['name'], 'test.txt')
        self.assertEqual(len(data['folders']), 1)
        self.assertEqual(data['folders'][0]['name'], 'Subfolder')
        
        # Verify the mocks were called correctly
        mock_list_files.assert_called_once()
    
    @patch('app.build')
    @patch('app.list_files_in_folder')
    def test_list_files_with_summaries(self, mock_list_files, mock_build):
        """Test the list-files endpoint with summaries enabled."""
        # Mock the file listing
        mock_list_files.return_value = {
            'folderName': 'Test Folder',
            'items': [
                {
                    'id': 'file1',
                    'name': 'test.txt',
                    'mimeType': 'text/plain',
                    'webViewLink': 'https://drive.google.com/file/d/file1/view',
                    'summary': 'This is a test file.'
                }
            ],
            'folders': []
        }
        
        # Set up a session with token
        with self.client.session_transaction() as session:
            session['token'] = json.dumps({
                'token': 'test_token',
                'refresh_token': 'test_refresh_token',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'client_id': 'test_client_id',
                'client_secret': 'test_client_secret',
                'scopes': ['https://www.googleapis.com/auth/drive.readonly']
            })
        
        # Test the list-files endpoint with summaries
        response = self.client.post('/list-files', 
                                   json={'folder_url': 'https://drive.google.com/drive/folders/test_folder_id',
                                         'generate_summaries': True})
        
        # Check the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['items'][0]['summary'], 'This is a test file.')
        
        # Verify list_files_in_folder was called with the right arguments
        # The exact call might vary, so we just check that it was called once
        mock_list_files.assert_called_once()
        # Check that generate_summaries=True was passed
        args, kwargs = mock_list_files.call_args
        self.assertTrue(kwargs.get('generate_summaries') or args[2] if len(args) > 2 else False)
    
    # Note: There's no download_file endpoint in the current implementation
    
    # Note: There's no view_file endpoint in the current implementation
    
    # Note: There's no view_file endpoint in the current implementation
    
    # Note: There's no search_files endpoint in the current implementation
    
    # Note: There's no API endpoint for listing files in the current implementation

if __name__ == '__main__':
    unittest.main()
