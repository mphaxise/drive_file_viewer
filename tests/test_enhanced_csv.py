import unittest
import json
import io
from unittest.mock import patch, MagicMock
from app import app

class TestEnhancedCSVExport(unittest.TestCase):
    """Test cases for the enhanced CSV export functionality."""
    
    def setUp(self):
        """Set up test client and other test variables."""
        self.client = app.test_client()
        self.client.testing = True
        
        # Create patchers
        self.auth_patcher = patch('app.authenticate')
        self.build_patcher = patch('app.build')
        self.get_folder_id_patcher = patch('app.get_folder_id_from_url')
        
        # Start patchers
        self.mock_authenticate = self.auth_patcher.start()
        self.mock_build = self.build_patcher.start()
        self.mock_get_folder_id = self.get_folder_id_patcher.start()
        
        # Set up mock returns
        self.mock_get_folder_id.return_value = 'test_folder_id'
        self.mock_service = MagicMock()
        self.mock_build.return_value = self.mock_service
    
    def tearDown(self):
        """Clean up after tests."""
        self.auth_patcher.stop()
        self.build_patcher.stop()
        self.get_folder_id_patcher.stop()
    
    @patch('app.get_all_files_recursive')
    @patch('app.send_file')
    def test_export_csv_with_summaries(self, mock_send_file, mock_get_all_files):
        """Test exporting CSV with summaries."""
        # Mock file data with summaries
        mock_get_all_files.return_value = [
            {
                'folder_path': 'Test Folder',
                'name': 'test.txt',
                'is_folder': False,
                'webViewLink': 'https://drive.google.com/file/d/file1/view',
                'summary': 'This is a test file summary.',
                'notes': ''
            }
        ]
        
        # Mock send_file to return a response
        mock_csv_data = "Number,Folder Name,File Name,File URL,Summary,Notes\n1,Test Folder,test.txt,https://drive.google.com/file/d/file1/view,This is a test file summary.,"
        mock_response = app.response_class(
            response=mock_csv_data,
            status=200,
            mimetype='text/csv'
        )
        mock_send_file.return_value = mock_response
        
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
        
        # Test the export-csv endpoint with summaries
        response = self.client.post('/export-csv', 
                                   json={'folder_url': 'https://drive.google.com/drive/folders/test_folder_id',
                                         'include_summaries': True})
        
        # Check the response
        self.assertEqual(response.status_code, 200)
        self.assertTrue('text/csv' in response.headers['Content-Type'])
        
        # Verify the CSV content includes summaries
        csv_content = response.data.decode('utf-8')
        self.assertIn('Summary', csv_content)
        self.assertIn('Notes', csv_content)
        self.assertIn('This is a test file summary.', csv_content)
        
        # Verify the mock was called with include_summaries=True
        mock_get_all_files.assert_called_once()
        args, kwargs = mock_get_all_files.call_args
        self.assertEqual(args[1], 'test_folder_id')
        self.assertTrue(kwargs.get('include_summaries'))
    
    @patch('app.get_all_files_recursive')
    @patch('app.send_file')
    def test_export_csv_without_summaries(self, mock_send_file, mock_get_all_files):
        """Test exporting CSV without summaries."""
        # Mock file data without summaries
        mock_get_all_files.return_value = [
            {
                'folder_path': 'Test Folder',
                'name': 'test.txt',
                'is_folder': False,
                'webViewLink': 'https://drive.google.com/file/d/file1/view',
                'summary': 'Summary generation disabled',
                'notes': ''
            }
        ]
        
        # Mock send_file to return a response
        mock_csv_data = "Number,Folder Name,File Name,File URL,Summary,Notes\n1,Test Folder,test.txt,https://drive.google.com/file/d/file1/view,Summary generation disabled,"
        mock_response = app.response_class(
            response=mock_csv_data,
            status=200,
            mimetype='text/csv'
        )
        mock_send_file.return_value = mock_response
        
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
        
        # Test the export-csv endpoint without summaries
        response = self.client.post('/export-csv', 
                                   json={'folder_url': 'https://drive.google.com/drive/folders/test_folder_id',
                                         'include_summaries': False})
        
        # Check the response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'text/csv; charset=utf-8')
        
        # Verify the CSV content includes the summary and notes columns but with default values
        csv_content = response.data.decode('utf-8')
        self.assertIn('Summary', csv_content)
        self.assertIn('Notes', csv_content)
        self.assertIn('Summary generation disabled', csv_content)
        
        # Verify the mock was called with include_summaries=False
        mock_get_all_files.assert_called_once()
        args, kwargs = mock_get_all_files.call_args
        self.assertEqual(args[1], 'test_folder_id')
        self.assertFalse(kwargs.get('include_summaries'))

if __name__ == '__main__':
    unittest.main()
