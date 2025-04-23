"""
Google Drive OAuth authentication
"""
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import json

SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]

def get_credentials():
    client_secrets_path = 'credentials.json'
    token_path = 'token.json'
    
    if not os.path.exists(client_secrets_path):
        raise FileNotFoundError(f"Google API credentials not found at {client_secrets_path}")
    
    creds = None
    if os.path.exists(token_path):
        with open(token_path, 'r') as token:
            creds = json.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_path, SCOPES, redirect_uri='http://localhost:5006/oauth2callback')
            creds = flow.run_local_server(port=5006)
        
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    
    return creds
