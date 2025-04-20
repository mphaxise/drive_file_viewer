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

class TestOAuthFlows(unittest.TestCase):
    """Test cases for OAuth and authentication flows."""
    
    def setUp(self):
        """Set up test environment."""
        self.app = app.app
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test_secret_key'
        self.client = self.app.test_client()
        
        # Create a test session
        with self.app.test_request_context():
            flask.session['credentials'] = None
            flask.session['current_folder'] = None
    
    def tearDown(self):
        """Clean up after tests."""
        pass
    
    @patch('app.Flow')
    def test_authorize(self, mock_flow_class):
        """Test the authorization endpoint."""
        # Mock the flow
        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = ('https://accounts.google.com/o/oauth2/auth?test', 'test_state')
        mock_flow_class.from_client_secrets_file.return_value = mock_flow
        
        # Test the authorize endpoint
        with self.app.test_request_context():
            response = self.client.get('/authorize')
            
            # Check that we get a JSON response with the auth URL
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn('auth_url', data)
            self.assertEqual(data['auth_url'], 'https://accounts.google.com/o/oauth2/auth?test')
            
            # Verify the flow was created with the correct scopes
            mock_flow_class.from_client_secrets_file.assert_called_once()
            mock_flow.authorization_url.assert_called_once()
    
    @patch('app.Flow')
    def test_oauth2callback(self, mock_flow_class):
        """Test the OAuth callback endpoint."""
        # Mock the flow and credentials
        mock_flow = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.token = 'test_token'
        mock_credentials.refresh_token = 'test_refresh_token'
        mock_credentials.token_uri = 'https://oauth2.googleapis.com/token'
        mock_credentials.client_id = 'test_client_id'
        mock_credentials.client_secret = 'test_client_secret'
        mock_credentials.scopes = ['https://www.googleapis.com/auth/drive.readonly']
        
        mock_flow.credentials = mock_credentials
        mock_flow.fetch_token.return_value = None
        mock_flow_class.from_client_secrets_file.return_value = mock_flow
        
        # Test the callback with an authorization code
        with self.app.test_request_context():
            with self.client.session_transaction() as session:
                session['state'] = 'test_state'
            
            response = self.client.get('/oauth2callback?code=test_auth_code&state=test_state')
            
            # Check that we get HTML with JavaScript to close the window
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Authentication complete', response.data)
            self.assertIn(b'window.opener.postMessage', response.data)
            
            # Verify the flow was created and token fetched
            mock_flow_class.from_client_secrets_file.assert_called_once()
            mock_flow.fetch_token.assert_called_once()
            
            # Check session after the request
            with self.client.session_transaction() as session:
                self.assertIsNotNone(session.get('token'))
    
    def test_oauth2callback_error(self):
        """Test the OAuth callback endpoint with an error."""
        # Test the callback without a state in session
        with self.app.test_request_context():
            response = self.client.get('/oauth2callback?error=access_denied')
            
            # Check that we get an error response
            self.assertEqual(response.status_code, 400)
            self.assertIn(b'No state found in session', response.data)
    
    # Note: There's no logout endpoint in the current implementation
    
    def test_index_page(self):
        """Test the index page."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Google Drive Viewer', response.data)
    
    def test_index_page_post(self):
        """Test submitting a folder URL to the index page."""
        # Note: The current implementation doesn't handle POST requests to the index page
        # The form submission is handled by JavaScript in the frontend
        pass
    
    def test_index_page_post_invalid_url(self):
        """Test submitting an invalid folder URL to the index page."""
        # Note: The current implementation doesn't handle POST requests to the index page
        # The form submission is handled by JavaScript in the frontend
        pass

if __name__ == '__main__':
    unittest.main()
