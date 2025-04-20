import unittest
import sys
import os
from unittest.mock import patch, MagicMock, call

# Add the parent directory to the path so we can import the app module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import (generate_file_summary, initialize_summarizer, download_file_content, 
                list_files_in_folder, recursive_summarize, generate_metadata_summary)

class TestSummaryFeature(unittest.TestCase):
    
    def test_dummy_pipeline(self):
        # Create a test environment where transformers is not available
        with patch.dict('sys.modules', {'transformers': None}):
            # Re-import app to trigger the ImportError for transformers
            import importlib
            import app as test_app
            importlib.reload(test_app)
            
            # Verify SUMMARIZER_AVAILABLE is False
            self.assertFalse(test_app.SUMMARIZER_AVAILABLE)
            
            # Call the dummy pipeline function
            result = test_app.pipeline("summarization", model="facebook/bart-large-cnn")
            
            # Verify the function returns None
            self.assertIsNone(result)
    
    def test_initialize_summarizer(self):
        # Reset the app module state
        import importlib
        import app
        importlib.reload(app)
        
        # Make sure SUMMARIZER_AVAILABLE is True
        with patch('app.SUMMARIZER_AVAILABLE', True):
            # Set up the mock for pipeline
            with patch('app.pipeline') as mock_pipeline:
                # Set up the mock
                mock_summarizer = MagicMock()
                mock_pipeline.return_value = mock_summarizer
                
                # Reset the summarizer
                app.summarizer = None
                
                # Call the function
                result = app.initialize_summarizer()
                
                # Verify the pipeline was called with the correct arguments
                mock_pipeline.assert_called_once_with(
                    "summarization", 
                    model="facebook/bart-large-cnn", 
                    max_length=25, 
                    min_length=10
                )
                
                # Verify the function returns True (success)
                self.assertTrue(result)
    
    @patch('app.summarizer', None)  # Reset the global summarizer
    @patch('app.SUMMARIZER_AVAILABLE', True)
    @patch('app.pipeline')
    def test_generate_file_summary_text_file(self, mock_pipeline):
        # Set up the mock
        mock_summarizer = MagicMock()
        mock_summarizer.return_value = [{'summary_text': 'This is a summary.'}]
        mock_pipeline.return_value = mock_summarizer
        
        # Call the function with text content
        summary = generate_file_summary("This is some text content for a file.", "test.txt")
        
        # Verify the function returns the expected summary
        self.assertEqual(summary, "This is a summary.")
    
    @patch('app.summarizer', None)  # Reset the global summarizer
    @patch('app.SUMMARIZER_AVAILABLE', True)
    @patch('app.pipeline')
    def test_generate_file_summary_large_content(self, mock_pipeline):
        # Set up the mock
        mock_summarizer = MagicMock()
        mock_summarizer.return_value = [{'summary_text': 'This is a summary.'}]
        mock_pipeline.return_value = mock_summarizer
        
        # Create a large content (more than 10,000 characters)
        large_content = "A" * 15000
        
        # Call the function with large content
        summary = generate_file_summary(large_content, "large_file.txt")
        
        # Verify the function returns the expected summary
        self.assertEqual(summary, "This is a summary.")
        
        # In the new implementation, we don't truncate the content before passing to recursive_summarize
        # Instead we clean it and count words, so we don't need to check for truncation anymore
        # The test should just verify the summary was generated correctly
    
    @patch('app.SUMMARIZER_AVAILABLE', False)
    def test_generate_file_summary_model_not_available(self):
        # Call the function when the model is not available
        summary = generate_file_summary("Some content", "test.txt")
        
        # Verify the function returns the expected message
        self.assertEqual(summary, "Summary not available (model not installed)")
    
    @patch('app.summarizer', None)  # Reset the global summarizer
    @patch('app.SUMMARIZER_AVAILABLE', True)
    @patch('app.initialize_summarizer')
    def test_generate_file_summary_initialization_failed(self, mock_initialize):
        # Set up the mock to return False (initialization failed)
        mock_initialize.return_value = False
        
        # Call the function
        summary = generate_file_summary("Some content", "test.txt")
        
        # Verify the function returns the expected message
        self.assertEqual(summary, "Summary not available (model initialization failed)")
    
    @patch('app.summarizer', None)  # Reset the global summarizer
    @patch('app.SUMMARIZER_AVAILABLE', True)
    @patch('app.pipeline')
    def test_generate_file_summary_empty_content(self, mock_pipeline):
        # Set up the mock
        mock_summarizer = MagicMock()
        mock_pipeline.return_value = mock_summarizer
        
        # Call the function with empty content
        summary = generate_file_summary("", "empty.txt")
        
        # Verify the summarizer was not called
        mock_summarizer.assert_not_called()
        
        # Verify the function returns the expected message
        self.assertEqual(summary, "No content to summarize")
    
    @patch('app.build')
    def test_download_file_content(self, mock_build):
        # Set up the mocks for regular file download
        mock_service = MagicMock()
        mock_files = MagicMock()
        mock_service.files.return_value = mock_files
        mock_get_media = MagicMock()
        mock_files.get_media.return_value = mock_get_media
        
        # Set up the mock for MediaIoBaseDownload
        with patch('app.MediaIoBaseDownload') as mock_download:
            mock_downloader = MagicMock()
            mock_download.return_value = mock_downloader
            
            # Create a mock status object with a progress method
            mock_status = MagicMock()
            mock_status.progress.return_value = 0.5  # 50% progress
            
            # Mock the next_chunk method to return done=True and the mock status
            mock_downloader.next_chunk.return_value = (mock_status, True)
            
            # Mock BytesIO
            with patch('app.BytesIO') as mock_bytesio:
                mock_file_content = MagicMock()
                mock_bytesio.return_value = mock_file_content
                mock_file_content.getvalue.return_value = b'File content'
                
                # Call the function with a regular file mime type
                content = download_file_content(mock_service, "file_id", "text/plain")
                
                # Verify the drive API was called correctly for regular files
                mock_files.get_media.assert_called_once_with(fileId="file_id")
                mock_download.assert_called_once()
                mock_downloader.next_chunk.assert_called_once()
                mock_file_content.getvalue.assert_called_once()
                
                # Verify the function returns the expected content
                self.assertEqual(content, "File content")
    
    @patch('app.build')
    def test_download_google_doc(self, mock_build):
        # Set up the mocks for Google Doc export
        mock_service = MagicMock()
        mock_files = MagicMock()
        mock_service.files.return_value = mock_files
        mock_export = MagicMock()
        mock_files.export.return_value = mock_export
        mock_export.execute.return_value = "Google Doc content"
        
        # Call the function with a Google Doc mime type
        content = download_file_content(mock_service, "file_id", "application/vnd.google-apps.document")
        
        # Verify the drive API was called correctly for Google Docs
        mock_files.export.assert_called_once_with(fileId="file_id", mimeType="text/plain")
        mock_export.execute.assert_called_once()
        
        # Verify the function returns the expected content
        self.assertEqual(content, "Google Doc content")
    
    @patch('app.build')
    def test_download_file_content_error(self, mock_build):
        # Set up the mocks to raise an exception
        mock_service = MagicMock()
        mock_files = MagicMock()
        mock_service.files.return_value = mock_files
        mock_get = MagicMock()
        mock_files.get.side_effect = Exception("Test error")
        
        # Call the function
        content = download_file_content(mock_service, "file_id", "text/plain")
        
        # Verify the function returns None on error
        self.assertIsNone(content)

    @patch('app.build')
    def test_list_files_in_folder_with_summaries(self, mock_build):
        # Set up the mocks
        mock_credentials = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # Mock the folder validation check
        mock_get = MagicMock()
        mock_service.files.return_value.get.return_value = mock_get
        mock_get.execute.return_value = {
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        # Mock the files().list().execute() call
        mock_list = MagicMock()
        mock_service.files.return_value.list.return_value = mock_list
        mock_list.execute.return_value = {
            'files': [
                {
                    'id': 'file1',
                    'name': 'test.txt',
                    'mimeType': 'text/plain',
                    'webViewLink': 'https://drive.google.com/file/d/file1/view'
                },
                {
                    'id': 'folder1',
                    'name': 'Test Folder',
                    'mimeType': 'application/vnd.google-apps.folder',
                    'webViewLink': 'https://drive.google.com/drive/folders/folder1'
                }
            ]
        }
        
        # Mock the get_folder_name function
        with patch('app.get_folder_name') as mock_get_folder_name:
            mock_get_folder_name.return_value = 'Test Root Folder'
            
            # Mock the download_file_content function to return content
            with patch('app.download_file_content') as mock_download:
                mock_download.return_value = 'This is test file content.'
                
                # Mock the generate_file_summary function
                with patch('app.generate_file_summary') as mock_generate_summary:
                    mock_generate_summary.return_value = 'This is a test summary.'
                    
                    # Set SUMMARIZER_AVAILABLE to True for this test
                    with patch('app.SUMMARIZER_AVAILABLE', True):
                        # Call the function with generate_summaries=True
                        result = list_files_in_folder(mock_credentials, 'root_folder', generate_summaries=True)
                        
                        # Verify the result structure
                        self.assertEqual(result['folderName'], 'Test Root Folder')
                        self.assertEqual(result['folderId'], 'root_folder')
                        self.assertEqual(len(result['items']), 2)
                        
                        # Verify file item has a summary
                        file_item = next(item for item in result['items'] if item['id'] == 'file1')
                        self.assertEqual(file_item['summary'], 'This is a test summary.')
                        
                        # Verify folder item doesn't have a summary key
                        folder_item = next(item for item in result['items'] if item['id'] == 'folder1')
                        self.assertNotIn('summary', folder_item)
                        
                        # Verify the download and summary functions were called
                        mock_download.assert_called_once()
    
    @patch('app.build')
    def test_list_files_in_folder_with_binary_files(self, mock_build):
        """Test listing files with summaries for binary files."""
        # Set up the mocks
        mock_credentials = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # Mock the folder validation check
        mock_get = MagicMock()
        mock_service.files.return_value.get.return_value = mock_get
        mock_get.execute.return_value = {
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        # Mock the files().list().execute() call with binary files
        mock_list = MagicMock()
        mock_service.files.return_value.list.return_value = mock_list
        mock_list.execute.return_value = {
            'files': [
                {
                    'id': 'image1',
                    'name': 'test.jpg',
                    'mimeType': 'image/jpeg',
                    'webViewLink': 'https://drive.google.com/file/d/image1/view',
                    'size': '1048576'  # 1MB
                }
            ]
        }
        
        # Mock the get_folder_name function
        with patch('app.get_folder_name') as mock_get_folder_name:
            mock_get_folder_name.return_value = 'Test Root Folder'
            
            # Mock the download_file_content function
            with patch('app.download_file_content') as mock_download:
                mock_download.return_value = b'binary content'
                
                # Mock the generate_file_summary function
                with patch('app.generate_file_summary') as mock_generate_summary:
                    mock_generate_summary.return_value = 'Image file (1.0 MB).'
                    
                    # Set SUMMARIZER_AVAILABLE to True for this test
                    with patch('app.SUMMARIZER_AVAILABLE', True):
                        # Call the function with generate_summaries=True
                        result = list_files_in_folder(mock_credentials, 'root_folder', generate_summaries=True)
                        
                        # Verify the result structure
                        self.assertIn('items', result)
                        self.assertEqual(len(result['items']), 1)
                        
                        # Verify image item has a metadata-based summary
                        image_item = result['items'][0]
                        self.assertEqual(image_item['summary'], 'Image file (1.0 MB).')
        
    @patch('app.build')
    def test_list_files_in_folder_metadata_error(self, mock_build):
        """Test handling of metadata retrieval errors."""
        # Set up the mocks
        mock_credentials = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # Mock the folder validation check
        mock_get = MagicMock()
        mock_service.files.return_value.get.return_value = mock_get
        mock_get.execute.return_value = {
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        # Mock the files().list().execute() call
        mock_list = MagicMock()
        mock_service.files.return_value.list.return_value = mock_list
        mock_list.execute.return_value = {
            'files': [
                {
                    'id': 'file1',
                    'name': 'test.txt',
                    'mimeType': 'text/plain',
                    'webViewLink': 'https://drive.google.com/file/d/file1/view'
                }
            ]
        }
        
        # Mock the get_folder_name function
        with patch('app.get_folder_name') as mock_get_folder_name:
            mock_get_folder_name.return_value = 'Test Root Folder'
            
            # Mock the download_file_content function
            with patch('app.download_file_content') as mock_download:
                mock_download.return_value = 'This is test file content.'
                
                # Mock the generate_file_summary function
                with patch('app.generate_file_summary') as mock_generate_summary:
                    mock_generate_summary.return_value = 'Summary without metadata.'
                    
                    # Set SUMMARIZER_AVAILABLE to True for this test
                    with patch('app.SUMMARIZER_AVAILABLE', True):
                        # Call the function with generate_summaries=True
                        result = list_files_in_folder(mock_credentials, 'root_folder', generate_summaries=True)
                        
                        # Verify the result structure
                        self.assertIn('items', result)
                        self.assertEqual(len(result['items']), 1)
                        
                        # Verify file item has a summary
                        file_item = result['items'][0]
                        self.assertEqual(file_item['summary'], 'Summary without metadata.')
    
    @patch('app.build')
    def test_list_files_in_folder_error(self, mock_build):
        # Set up the mocks to raise an exception
        mock_credentials = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # Mock the folder validation check
        mock_get = MagicMock()
        mock_service.files.return_value.get.return_value = mock_get
        mock_get.execute.return_value = {
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        # Mock the files().list().execute() call to raise an exception
        mock_list = MagicMock()
        mock_service.files.return_value.list.return_value = mock_list
        mock_list.execute.side_effect = Exception('Test error')
        
        # Call the function
        result = list_files_in_folder(mock_credentials, 'root_folder')
        
        # Verify the result is an error
        self.assertEqual(result['error'], 'Test error')
    
    @patch('app.build')
    def test_list_files_in_folder_summary_error(self, mock_build):
        # Set up the mocks
        mock_credentials = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # Mock the folder validation check
        mock_get = MagicMock()
        mock_service.files.return_value.get.return_value = mock_get
        mock_get.execute.return_value = {
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        # Mock the files().list().execute() call
        mock_list = MagicMock()
        mock_service.files.return_value.list.return_value = mock_list
        mock_list.execute.return_value = {
            'files': [
                {
                    'id': 'file1',
                    'name': 'test.txt',
                    'mimeType': 'text/plain',
                    'webViewLink': 'https://drive.google.com/file/d/file1/view'
                }
            ]
        }
        
        # Mock the get_folder_name function
        with patch('app.get_folder_name') as mock_get_folder_name:
            mock_get_folder_name.return_value = 'Test Root Folder'
            
            # Mock the download_file_content function to return content
            with patch('app.download_file_content') as mock_download:
                mock_download.return_value = 'This is test file content.'
                
                # Mock the generate_file_summary function to raise an exception
                with patch('app.generate_file_summary') as mock_generate_summary:
                    mock_generate_summary.side_effect = Exception('Summary error')
                    
                    # Set SUMMARIZER_AVAILABLE to True for this test
                    with patch('app.SUMMARIZER_AVAILABLE', True):
                        # Call the function with generate_summaries=True
                        result = list_files_in_folder(mock_credentials, 'root_folder', generate_summaries=True)
                        
                        # Verify the result structure
                        self.assertEqual(result['folderName'], 'Test Root Folder')
                        self.assertEqual(result['folderId'], 'root_folder')
                        self.assertEqual(len(result['items']), 1)
                        
                        # Verify file item has error summary
                        file_item = result['items'][0]
                        self.assertTrue(file_item['summary'].startswith('Error generating summary:'))
                        self.assertIn('Summary error', file_item['summary'])

    @patch('app.summarizer')
    def test_recursive_summarize_base_case(self, mock_summarizer):
        """Test recursive summarization when text is short enough (base case)."""
        # Set up the mock
        mock_summarizer.return_value = [{'summary_text': 'Base case summary.'}]
        
        # Call with text that's under the max_length
        text = "This is a short text that should be summarized directly."
        result = recursive_summarize(text, "test.txt", max_length=900, depth=0, max_depth=3)
        
        # Verify the result
        self.assertEqual(result, "Base case summary.")
        
        # Verify summarizer was called with the right parameters
        mock_summarizer.assert_called_once()
        args, kwargs = mock_summarizer.call_args
        self.assertEqual(args[0], text)
        self.assertEqual(kwargs['max_length'], 25)
        self.assertEqual(kwargs['min_length'], 10)
    
    @patch('app.summarizer')
    def test_recursive_summarize_recursive_case(self, mock_summarizer):
        """Test recursive summarization when text is long and needs chunking."""
        # Set up the mock to return different summaries for chunks and combined text
        def mock_summarize_side_effect(*args, **kwargs):
            if len(args[0].split()) > 100:  # If it's a chunk
                return [{'summary_text': f"Chunk summary for: {args[0][:20]}..."}]
            else:  # If it's the combined summaries
                return [{'summary_text': "Final combined summary."}]
        
        mock_summarizer.side_effect = mock_summarize_side_effect
        
        # Create a long text that will need to be chunked
        words = ["word" + str(i) for i in range(1000)]
        long_text = " ".join(words)
        
        # Call recursive_summarize
        result = recursive_summarize(long_text, "long_doc.txt", max_length=100, depth=0, max_depth=3)
        
        # Verify the result
        self.assertEqual(result, "Final combined summary.")
        
        # Verify summarizer was called multiple times (for chunks and final)
        self.assertTrue(mock_summarizer.call_count > 1)
        
    @patch('app.summarizer')
    def test_recursive_summarize_chunk_error(self, mock_summarizer):
        """Test recursive summarization when some chunks fail to summarize."""
        # Set up the mock to succeed for some chunks and fail for others
        call_count = 0
        def mock_summarize_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Make the second chunk fail
                raise Exception("Error summarizing chunk")
            return [{'summary_text': f"Summary for chunk {call_count}"}]
        
        mock_summarizer.side_effect = mock_summarize_side_effect
        
        # Create a long text that will need to be chunked
        words = ["word" + str(i) for i in range(2000)]
        long_text = " ".join(words)
        
        # Call recursive_summarize
        result = recursive_summarize(long_text, "long_doc.txt", max_length=100, depth=0, max_depth=3)
        
        # Verify we got a result despite the error in one chunk
        self.assertTrue(result.startswith("Summary for chunk"))
        
    @patch('app.summarizer')
    def test_recursive_summarize_no_summaries(self, mock_summarizer):
        """Test recursive summarization when all chunks fail to summarize."""
        # Set up the mock to fail for all chunks
        mock_summarizer.side_effect = Exception("Error summarizing all chunks")
        
        # Create a long text that will need to be chunked
        words = ["word" + str(i) for i in range(1000)]
        long_text = " ".join(words)
        
        # Call recursive_summarize
        result = recursive_summarize(long_text, "long_doc.txt", max_length=100, depth=0, max_depth=3)
        
        # Verify we got an error message
        self.assertTrue(result.startswith("Could not generate summary for any chunk"))
    
    @patch('app.summarizer')
    def test_recursive_summarize_max_depth(self, mock_summarizer):
        """Test recursive summarization when max depth is reached."""
        # Set up the mock
        mock_summarizer.return_value = [{'summary_text': 'Max depth summary.'}]
        
        # Create a long text
        words = ["word" + str(i) for i in range(1000)]
        long_text = " ".join(words)
        
        # Call with max_depth already reached
        result = recursive_summarize(long_text, "test.txt", max_length=100, depth=3, max_depth=3)
        
        # Verify the result
        self.assertEqual(result, "Max depth summary.")
        
        # Verify summarizer was called with truncated text
        mock_summarizer.assert_called_once()
        args, _ = mock_summarizer.call_args
        self.assertEqual(len(args[0].split()), 100)  # Should truncate to max_length
    
    @patch('app.summarizer')
    def test_recursive_summarize_error_handling(self, mock_summarizer):
        """Test error handling in recursive summarization."""
        # Set up the mock to raise an exception
        mock_summarizer.side_effect = Exception("Test summarization error")
        
        # Call with text
        result = recursive_summarize("Some text", "test.txt", max_length=900, depth=0, max_depth=3)
        
        # Verify the result contains the error message
        self.assertTrue(result.startswith("Could not summarize:"))
        self.assertIn("Test summarization error", result)
    
    def test_generate_metadata_summary(self):
        """Test metadata-based summary generation for different file types."""
        # Test image file
        summary = generate_metadata_summary("photo.jpg", "image/jpeg", 1024 * 1024)
        self.assertEqual(summary, "Image file (1.0 MB).")
        
        # Test video file
        summary = generate_metadata_summary("video.mp4", "video/mp4", 10 * 1024 * 1024)
        self.assertEqual(summary, "Video file (10.0 MB).")
        
        # Test audio file
        summary = generate_metadata_summary("audio.mp3", "audio/mpeg", 5 * 1024 * 1024)
        self.assertEqual(summary, "Audio file (5.0 MB).")
        
        # Test PDF file
        summary = generate_metadata_summary("document.pdf", "application/pdf", 2 * 1024 * 1024)
        self.assertEqual(summary, "PDF document (2.0 MB).")
        
        # Test Excel file
        summary = generate_metadata_summary("spreadsheet.xlsx", 
                                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                                         500 * 1024)
        self.assertEqual(summary, "Excel spreadsheet (500.0 KB).")
        
        # Test PowerPoint file
        summary = generate_metadata_summary("presentation.pptx", 
                                         "application/vnd.openxmlformats-officedocument.presentationml.presentation", 
                                         3 * 1024 * 1024)
        self.assertEqual(summary, "PowerPoint presentation (3.0 MB).")
        
        # Test ZIP file
        summary = generate_metadata_summary("archive.zip", "application/zip", 4 * 1024 * 1024)
        self.assertEqual(summary, "ZIP archive (4.0 MB).")
        
        # Test unknown file type
        summary = generate_metadata_summary("unknown.xyz", "application/octet-stream", 1024)
        self.assertEqual(summary, "XYZ file (1.0 KB).")
        
        # Test file with no size information
        summary = generate_metadata_summary("nosize.txt", "text/plain")
        self.assertEqual(summary, "TXT file.")
    
    @patch('app.SUMMARIZER_AVAILABLE', True)
    @patch('app.summarizer', None)  # Reset the global summarizer
    @patch('app.initialize_summarizer')
    def test_generate_file_summary_binary_file(self, mock_initialize):
        """Test summary generation for binary files using metadata."""
        # Set up the mock
        mock_initialize.return_value = True
        
        # Call the function with a binary file type
        summary = generate_file_summary("binary content", "image.jpg", "image/jpeg", 1024 * 1024)
        
        # Verify the result is a metadata-based summary
        self.assertEqual(summary, "Image file (1.0 MB).")
        
        # Verify initialize_summarizer was not called (shouldn't need the model for binary files)
        mock_initialize.assert_not_called()
    
    @patch('app.SUMMARIZER_AVAILABLE', True)
    @patch('app.summarizer', None)  # Reset the global summarizer
    @patch('app.initialize_summarizer')
    @patch('app.recursive_summarize')
    def test_generate_file_summary_long_text(self, mock_recursive, mock_initialize):
        """Test summary generation for long text that requires recursive summarization."""
        # Set up the mocks
        mock_initialize.return_value = True
        mock_recursive.return_value = "Recursive summary result"
        
        # Create a long text
        long_text = "word " * 1000
        
        # Call the function
        summary = generate_file_summary(long_text, "long_document.txt")
        
        # Verify recursive_summarize was called
        mock_recursive.assert_called_once()
        # Verify the result
        self.assertEqual(summary, "Recursive summary result")
    
    @patch('app.SUMMARIZER_AVAILABLE', True)
    @patch('app.summarizer')
    @patch('app.initialize_summarizer')
    def test_generate_file_summary_direct_summarization(self, mock_initialize, mock_summarizer):
        """Test direct summarization for shorter text."""
        # Set up the mocks
        mock_initialize.return_value = True
        mock_summarizer.return_value = [{'summary_text': 'Direct summary result'}]
        
        # Call the function with short text
        summary = generate_file_summary("This is a short text.", "short.txt")
        
        # Verify the summarizer was called directly
        mock_summarizer.assert_called_once()
        # Verify the result
        self.assertEqual(summary, "Direct summary result")
    
    @patch('app.SUMMARIZER_AVAILABLE', True)
    @patch('app.summarizer', None)  # Reset the global summarizer
    @patch('app.initialize_summarizer')
    def test_generate_file_summary_empty_result(self, mock_initialize):
        """Test handling of empty summarization results."""
        # Set up the mocks
        mock_initialize.return_value = True
        # Create a mock summarizer that returns an empty result
        with patch('app.summarizer') as mock_summarizer:
            mock_summarizer.return_value = []
            
            # Call the function
            summary = generate_file_summary("Text content", "test.txt")
            
            # Verify the result contains the error message
            self.assertEqual(summary, "Could not generate summary for test.txt")
    
    def test_generate_file_summary_with_all_metadata(self):
        """Test summary generation with all metadata parameters."""
        # Call the function with all metadata parameters
        summary = generate_file_summary(
            "file content", 
            "document.pdf", 
            "application/pdf", 
            1024 * 1024, 
            "2025-04-20T10:00:00Z", 
            "2025-04-20T10:10:00Z"
        )
        
        # Verify the result is a metadata-based summary
        self.assertEqual(summary, "PDF document (1.0 MB).")

if __name__ == '__main__':
    unittest.main()
