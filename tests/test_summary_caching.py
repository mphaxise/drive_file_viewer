import unittest
import json
import os
import pickle
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from app import app, TEMP_DIR

class TestSummaryCaching(unittest.TestCase):
    """Test cases for the summary caching functionality."""
    
    def setUp(self):
        """Set up test client and other test variables."""
        self.client = app.test_client()
        self.client.testing = True
        
        # Create patchers
        self.auth_patcher = patch('app.authenticate')
        self.build_patcher = patch('app.build')
        self.get_folder_id_patcher = patch('app.get_folder_id_from_url')
        self.list_files_patcher = patch('app.list_files_in_folder')
        self.uuid_patcher = patch('uuid.uuid4')
        self.pickle_dump_patcher = patch('pickle.dump')
        self.pickle_load_patcher = patch('pickle.load')
        self.path_exists_patcher = patch('pathlib.Path.exists')
        self.open_patcher = patch('builtins.open', new_callable=mock_open)
        
        # Start patchers
        self.mock_authenticate = self.auth_patcher.start()
        self.mock_build = self.build_patcher.start()
        self.mock_get_folder_id = self.get_folder_id_patcher.start()
        self.mock_list_files = self.list_files_patcher.start()
        self.mock_uuid = self.uuid_patcher.start()
        self.mock_pickle_dump = self.pickle_dump_patcher.start()
        self.mock_pickle_load = self.pickle_load_patcher.start()
        self.mock_path_exists = self.path_exists_patcher.start()
        self.mock_open = self.open_patcher.start()
        
        # Set up mock returns
        self.mock_get_folder_id.return_value = 'test_folder_id'
        self.mock_service = MagicMock()
        self.mock_build.return_value = self.mock_service
        self.mock_uuid.return_value = 'test-uuid'
        self.mock_path_exists.return_value = True
        
        # Test data
        self.test_folder_result = {
            'folderName': 'Test Folder',
            'folderId': 'test_folder_id',
            'items': [
                {
                    'id': 'file1',
                    'name': 'test.txt',
                    'type': 'file',
                    'mimeType': 'text/plain',
                    'webViewLink': 'https://drive.google.com/file/d/file1/view',
                    'summary': 'This is a test file summary.'
                }
            ]
        }
        
    def tearDown(self):
        """Clean up after tests."""
        self.auth_patcher.stop()
        self.build_patcher.stop()
        self.get_folder_id_patcher.stop()
        self.list_files_patcher.stop()
        self.uuid_patcher.stop()
        self.pickle_dump_patcher.stop()
        self.pickle_load_patcher.stop()
        self.path_exists_patcher.stop()
        self.open_patcher.stop()
    
    def test_store_summaries_in_file(self):
        """Test that summaries are stored in a temporary file."""
        # Mock the list_files_in_folder function to return test data
        self.mock_list_files.return_value = self.test_folder_result
        
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
        
        # Call the list-files endpoint with summaries enabled
        response = self.client.post('/list-files', 
                                   json={'folder_url': 'https://drive.google.com/drive/folders/test_folder_id',
                                         'generate_summaries': True})
        
        # Check that the response is successful
        self.assertEqual(response.status_code, 200)
        
        # Check that the result was stored in a temporary file
        expected_file_path = TEMP_DIR / 'test-uuid.pickle'
        self.mock_open.assert_any_call(expected_file_path, 'wb')
        self.mock_pickle_dump.assert_called_once()
        
        # Check that the session contains the correct values
        with self.client.session_transaction() as session:
            self.assertEqual(session['last_folder_result_id'], 'test-uuid')
            self.assertEqual(session['last_folder_id'], 'test_folder_id')
    
    @patch('app.get_all_files_recursive')
    @patch('app.send_file')
    def test_reuse_summaries_for_csv_export(self, mock_send_file, mock_get_all_files):
        """Test that summaries are reused when exporting to CSV."""
        # Mock the pickle.load function to return test data
        self.mock_pickle_load.return_value = self.test_folder_result
        
        # Set up mock for send_file
        mock_send_file.return_value = app.response_class(
            response="CSV content",
            status=200,
            mimetype='text/csv'
        )
        
        # Set up a session with token and last folder result
        with self.client.session_transaction() as session:
            session['token'] = json.dumps({
                'token': 'test_token',
                'refresh_token': 'test_refresh_token',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'client_id': 'test_client_id',
                'client_secret': 'test_client_secret',
                'scopes': ['https://www.googleapis.com/auth/drive.readonly']
            })
            session['last_folder_result_id'] = 'test-uuid'
            session['last_folder_id'] = 'test_folder_id'
        
        # Call the export-csv endpoint with summaries enabled
        response = self.client.post('/export-csv', 
                                   json={'folder_url': 'https://drive.google.com/drive/folders/test_folder_id',
                                         'include_summaries': True})
        
        # Check that the response is successful
        self.assertEqual(response.status_code, 200)
        
        # Check that the temporary file was opened for reading
        expected_file_path = TEMP_DIR / 'test-uuid.pickle'
        self.mock_open.assert_any_call(expected_file_path, 'rb')
        self.mock_pickle_load.assert_called_once()
        
        # Verify that get_all_files_recursive was not called (summaries were reused)
        mock_get_all_files.assert_not_called()
    
    @patch('app.get_all_files_recursive')
    @patch('app.send_file')
    def test_fallback_to_regenerate_summaries(self, mock_send_file, mock_get_all_files):
        """Test that summaries are regenerated if the cache file doesn't exist."""
        # Mock the path.exists function to return False
        self.mock_path_exists.return_value = False
        
        # Set up mock for send_file
        mock_send_file.return_value = app.response_class(
            response="CSV content",
            status=200,
            mimetype='text/csv'
        )
        
        # Mock get_all_files_recursive to return test data
        mock_get_all_files.return_value = [
            {
                'folder_path': 'Test Folder',
                'name': 'test.txt',
                'is_folder': False,
                'webViewLink': 'https://drive.google.com/file/d/file1/view',
                'summary': 'Regenerated summary'
            }
        ]
        
        # Set up a session with token and last folder result
        with self.client.session_transaction() as session:
            session['token'] = json.dumps({
                'token': 'test_token',
                'refresh_token': 'test_refresh_token',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'client_id': 'test_client_id',
                'client_secret': 'test_client_secret',
                'scopes': ['https://www.googleapis.com/auth/drive.readonly']
            })
            session['last_folder_result_id'] = 'test-uuid'
            session['last_folder_id'] = 'test_folder_id'
        
        # Call the export-csv endpoint with summaries enabled
        response = self.client.post('/export-csv', 
                                   json={'folder_url': 'https://drive.google.com/drive/folders/test_folder_id',
                                         'include_summaries': True})
        
        # Check that the response is successful
        self.assertEqual(response.status_code, 200)
        
        # Verify that get_all_files_recursive was called (summaries were regenerated)
        mock_get_all_files.assert_called_once()

if __name__ == '__main__':
    unittest.main()
