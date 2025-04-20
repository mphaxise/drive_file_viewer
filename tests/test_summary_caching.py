import unittest
import json
import os
import pickle
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from app import app, TEMP_DIR, get_all_files_recursive
from io import StringIO

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

    def test_reuse_summaries_for_csv_export(self):
        """Test that summaries are reused when exporting to CSV."""
        # Mock session with cached result
        with patch('app.session', {'last_folder_result_id': 'test_id', 'last_folder_id': 'folder_id'}):
            # Mock the temporary file
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            with patch('app.TEMP_DIR') as mock_temp_dir:
                mock_temp_dir.__truediv__.return_value = mock_file
                
                # Mock pickle.load to return cached results with valid summaries
                cached_result = {
                    'folderName': 'Test Folder',
                    'items': [
                        {
                            'type': 'file',
                            'name': 'test.txt',
                            'webViewLink': 'https://example.com',
                            'summary': 'This is a test summary'
                        }
                    ]
                }
                
                # Create a StringIO object to capture the CSV output
                output_buffer = StringIO()
                
                # Mock get_folder_id_from_url to return a consistent folder_id
                with patch('app.get_folder_id_from_url', return_value='folder_id'):
                    with patch('pickle.load', return_value=cached_result):
                        with patch('builtins.open', mock_open()) as mock_file_open:
                            # Mock send_file to capture the CSV content
                            with patch('app.send_file') as mock_send_file:
                                # Mock io.BytesIO to capture the CSV content
                                with patch('io.BytesIO', return_value=output_buffer) as mock_bytes_io:
                                    # Call export_csv
                                    with app.test_request_context():
                                        with patch('app.request', json={'folder_url': 'https://drive.google.com/drive/folders/folder_id', 'include_summaries': True}):
                                            # Mock get_all_files_recursive to verify it's not called
                                            with patch('app.get_all_files_recursive') as mock_get_files:
                                                # Import the export_csv function directly
                                                from app import export_csv
                                                export_csv()
                                                
                                                # Verify that get_all_files_recursive was not called
                                                mock_get_files.assert_not_called()
                                            
                                            # Verify that send_file was called
                                            mock_send_file.assert_called_once()
                                                
    def test_get_all_files_recursive_with_cache(self):
        """Test that get_all_files_recursive uses cached results when available."""
        # Mock session with cached result
        with patch('app.session', {'last_folder_result_id': 'test_id', 'last_folder_id': 'folder_id'}):
            # Mock the temporary file
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            with patch('app.TEMP_DIR') as mock_temp_dir:
                mock_temp_dir.__truediv__.return_value = mock_file
                
                # Mock pickle.load to return cached results with valid summaries
                cached_result = {
                    'folderName': 'Test Folder',
                    'items': [
                        {
                            'type': 'file',
                            'id': 'file1',
                            'name': 'test.txt',
                            'webViewLink': 'https://example.com',
                            'summary': 'This is a test summary'
                        },
                        {
                            'type': 'folder',
                            'id': 'subfolder1',
                            'name': 'Subfolder'
                        }
                    ]
                }
                
                with patch('pickle.load', return_value=cached_result):
                    with patch('builtins.open', mock_open()) as mock_file_open:
                        # Set up mock for the service.files().list() call
                        mock_service = MagicMock()
                        mock_files = MagicMock()
                        mock_service.files.return_value = mock_files
                        mock_list = MagicMock()
                        mock_files.list.return_value = mock_list
                        
                        # Mock the execute method to return empty results
                        # This ensures we're using the cache, not the API
                        mock_list.execute.return_value = {'files': []}
                        
                        # Create a mock for recursive calls to handle the subfolder
                        subfolder_items = [{
                            'folder_path': 'Root/Subfolder',
                            'name': 'subfile.txt',
                            'is_folder': False,
                            'webViewLink': 'https://example.com/sub',
                            'summary': 'Subfolder file summary',
                            'notes': ''
                        }]
                        
                        # We need to patch the recursive call separately
                        with patch('app.get_all_files_recursive', return_value=subfolder_items) as mock_recursive:
                            # Call the function directly
                            result = get_all_files_recursive(mock_service, 'folder_id', include_summaries=True)
                            
                            # Verify that the recursive function was called for the subfolder
                            mock_recursive.assert_called_once_with(
                                mock_service, 'subfolder1', 'Root/Subfolder', True
                            )
                            
                            # Verify we got the expected results
                            # We should have the file from cache and the subfolder items
                            self.assertEqual(len(result), 3)  # 1 file + 1 folder + 1 subfolder item
                            
                            # Check file names
                            file_names = [item.get('name') for item in result]
                            self.assertIn('test.txt', file_names)
                            self.assertIn('subfile.txt', file_names)
                            
    def test_get_all_files_recursive_without_summaries(self):
        """Test that get_all_files_recursive skips cache when summaries are not requested."""
        # Mock session with cached result
        with patch('app.session', {'last_folder_result_id': 'test_id', 'last_folder_id': 'folder_id'}):
            # Set up mock service and files
            mock_service = MagicMock()
            mock_files = MagicMock()
            mock_service.files.return_value = mock_files
            mock_list = MagicMock()
            mock_files.list.return_value = mock_list
            
            # Mock the execute method to return file results
            mock_list.execute.return_value = {
                'files': [
                    {
                        'id': 'file1',
                        'name': 'test.txt',
                        'mimeType': 'text/plain',
                        'webViewLink': 'https://example.com'
                    }
                ]
            }
            
            # Call the function without requesting summaries
            from app import get_all_files_recursive
            result = get_all_files_recursive(mock_service, 'folder_id', include_summaries=False)
            
            # Verify the results
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['name'], 'test.txt')
            self.assertEqual(result[0]['summary'], 'Summary generation disabled')
            
            # Verify the API was called (cache was not used)
            mock_files.list.assert_called_once()
            
    def test_get_all_files_recursive_cache_error(self):
        """Test that get_all_files_recursive handles cache errors gracefully."""
        # Mock session with cached result
        with patch('app.session', {'last_folder_result_id': 'test_id', 'last_folder_id': 'folder_id'}):
            # Mock the temporary file
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            with patch('app.TEMP_DIR') as mock_temp_dir:
                mock_temp_dir.__truediv__.return_value = mock_file
                
                # Mock pickle.load to raise an exception
                with patch('pickle.load', side_effect=Exception('Test error')):
                    with patch('builtins.open', mock_open()) as mock_file_open:
                        # Set up mock service and files
                        mock_service = MagicMock()
                        mock_files = MagicMock()
                        mock_service.files.return_value = mock_files
                        mock_list = MagicMock()
                        mock_files.list.return_value = mock_list
                        
                        # Mock the execute method to return file results
                        mock_list.execute.return_value = {
                            'files': [
                                {
                                    'id': 'file1',
                                    'name': 'test.txt',
                                    'mimeType': 'text/plain',
                                    'webViewLink': 'https://example.com'
                                }
                            ]
                        }
                        
                        # Call the function
                        from app import get_all_files_recursive
                        result = get_all_files_recursive(mock_service, 'folder_id', include_summaries=True)
                        
                        # Verify the results
                        self.assertEqual(len(result), 1)
                        self.assertEqual(result[0]['name'], 'test.txt')
                        
                        # Verify the API was called (fallback to API after cache error)
                        mock_files.list.assert_called_once()

if __name__ == '__main__':
    unittest.main()
