from flask import Flask, render_template, request, jsonify, session, send_file, url_for
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from urllib.parse import urlparse, parse_qs
import os
import json
import csv
from io import StringIO
from datetime import datetime
from dotenv import load_dotenv
import threading
import webbrowser
import logging
import sys

# Set up logging to file
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('drive_viewer.log', mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')
if not app.secret_key:
    raise ValueError('FLASK_SECRET_KEY environment variable is not set')

# Configure Google OAuth2
CLIENT_SECRETS_FILE = "credentials.json"
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]

# OAuth2 configuration
PORT = 5006  # Main server port

def authenticate():
    """Retrieve credentials from session."""
    import json
    if 'token' not in session:
        raise Exception('authentication_required')
    token_data = json.loads(session['token'])
    return Credentials(
        token=token_data['token'],
        refresh_token=token_data['refresh_token'],
        token_uri=token_data['token_uri'],
        client_id=token_data['client_id'],
        client_secret=token_data['client_secret'],
        scopes=token_data['scopes']
    )

def get_folder_id_from_url(url):
    """Extract folder ID from Google Drive URL."""
    logging.debug(f"Extracting folder ID from URL: {url}")
    parsed_url = urlparse(url)
    folder_id = None
    
    if 'folders' in parsed_url.path:
        folder_id = parsed_url.path.split('/')[-1]
        logging.debug(f"Extracted folder ID from path: {folder_id}")
    else:
        query_params = parse_qs(parsed_url.query)
        if 'id' in query_params:
            folder_id = query_params['id'][0]
            logging.debug(f"Extracted folder ID from query params: {folder_id}")
        else:
            logging.warning(f"Could not extract folder ID from URL: {url}")
    
    # Check if folder_id contains any URL parameters we need to clean up
    if folder_id and '?' in folder_id:
        folder_id = folder_id.split('?')[0]
        logging.debug(f"Cleaned folder ID: {folder_id}")
        
    return folder_id

def get_folder_name(service, folder_id):
    """Get the name of a folder from its ID."""
    try:
        folder = service.files().get(
            fileId=folder_id,
            fields="name",
            supportsAllDrives=True
        ).execute()
        return folder.get('name')
    except Exception as e:
        print(f"Error getting folder name: {e}")
        return None

def list_files_in_folder(credentials, folder_id):
    """List all files and folders in the specified Google Drive folder."""
    try:
        logging.debug(f"===== LISTING FILES IN FOLDER =====\nFolder ID: {folder_id}")
        if not folder_id:
            logging.error(f"Invalid folder ID: {folder_id}")
            return {'error': 'Invalid folder ID'}
            
        logging.debug(f"Building Google Drive service with credentials: {credentials}")
        service = build('drive', 'v3', credentials=credentials)
        
        # Get folder name for breadcrumb
        folder_name = get_folder_name(service, folder_id)
        logging.debug(f"Folder name for ID {folder_id}: {folder_name}")
        
        # First, try to access the folder to verify permissions
        try:
            folder_info = service.files().get(
                fileId=folder_id,
                fields="name,mimeType",
                supportsAllDrives=True
            ).execute()
            logging.debug(f"Successfully accessed folder: {folder_info}")
            
            # Verify it's actually a folder
            if folder_info.get('mimeType') != 'application/vnd.google-apps.folder':
                logging.error(f"ID {folder_id} is not a folder. MimeType: {folder_info.get('mimeType')}")
                return {'error': f"The ID {folder_id} is not a folder"}
                
        except Exception as folder_error:
            logging.error(f"Error accessing folder {folder_id}: {folder_error}")
            return {'error': f"Cannot access folder: {str(folder_error)}"}
            
        # List files and folders
        try:
            query = f"'{folder_id}' in parents and trashed=false"
            logging.debug(f"Querying Drive API with: {query}")
            results = service.files().list(
                q=query,
                pageSize=100,
                fields="files(id, name, mimeType, webViewLink, parents)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
        except Exception as list_error:
            logging.error(f"Error listing files in folder {folder_id}: {list_error}")
            return {'error': f"Error listing files: {str(list_error)}"}
        logging.debug(f"Raw API results: {results}")
        
        files = results.get('files', [])
        logging.debug(f"Found {len(files)} files in folder {folder_id}")
        
        # Process files and folders
        processed_items = []
        for item in files:
            is_folder = item['mimeType'] == 'application/vnd.google-apps.folder'
            processed_items.append({
                'id': item['id'],
                'name': item['name'],
                'type': 'folder' if is_folder else 'file',
                'webViewLink': item['webViewLink'],
                'parentId': item.get('parents', [None])[0]
            })
        logging.debug(f"Processed items: {processed_items}")
        
        # Sort items: folders first, then by name
        processed_items.sort(key=lambda x: (x['type'] != 'folder', x['name'].lower()))
        logging.debug(f"Sorted items: {processed_items}")
        
        return {
            'items': processed_items,
            'folderName': folder_name,
            'folderId': folder_id
        }
    except Exception as e:
        logging.error(f"Error listing files: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        return {'error': str(e)}

@app.route('/')
def index():
    return render_template('index.html', main_app_url='http://localhost:5006')

@app.route('/authorize')
def authorize():
    try:
        print(f"Starting authorization process...")
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri="http://localhost:5000/authorize/callback"
        )
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        print(f"Generated authorization URL: {authorization_url}")
        return jsonify({'auth_url': authorization_url})
    except Exception as e:
        print(f"Error in authorize: {str(e)}")
        return jsonify({'error': str(e)})

@app.route('/list-files', methods=['POST'])
def list_files():
    print('[DEBUG] list_files: Session keys:', list(session.keys()), flush=True)
    print('[DEBUG] list_files: Session token:', session.get('token'), flush=True)
    try:
        print("\n=== Received list-files request ===")
        print("Request data:", request.get_data(as_text=True))
        
        # Get folder ID either from URL or direct ID
        folder_url = request.json.get('folder_url')
        folder_id = request.json.get('folder_id')
        
        # If we have a URL, extract folder ID from it
        if folder_url:
            logging.debug(f"Processing folder URL: {folder_url}")
            extracted_id = get_folder_id_from_url(folder_url)
            logging.debug(f"Extracted folder ID: {extracted_id}")
            if not extracted_id:
                return jsonify({'error': 'Invalid folder URL'})
            
            # If we already have a folder ID and it matches the extracted one,
            # use that to avoid duplicate requests
            if folder_id and folder_id == extracted_id:
                logging.debug(f"Using provided folder ID: {folder_id}")
            else:
                folder_id = extracted_id
        
        if not folder_id:
            return jsonify({'error': 'No folder ID provided'})
            
        # Check if we have a token in the session
        try:
            credentials = authenticate()
        except Exception as e:
            print(f"Authentication required: {str(e)}")
            print("Starting authentication...")
            
            # Save the folder ID in the session for later use
            session['folder_id'] = folder_id
            if folder_url:
                session['folder_url'] = folder_url
            
            # Start OAuth flow
            flow = Flow.from_client_secrets_file(
                CLIENT_SECRETS_FILE,
                scopes=SCOPES,
                redirect_uri="http://127.0.0.1:5006/oauth2callback"
            )
            
            auth_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )
            session['state'] = state
            logging.debug(f"Generated new state {state}.")
            return jsonify({'auth_url': auth_url})
        
        print("Listing files...")
        result = list_files_in_folder(credentials, folder_id)
        
        if 'error' in result:
            return jsonify({'error': result['error']})
            
        print(f"Found {len(result['items'])} items in folder {result['folderName']}")
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in list_files: {str(e)}")
        return jsonify({'error': str(e)})

def get_all_files_recursive(service, folder_id, folder_path="Root"):
    """Recursively get all files and folders from Google Drive"""
    items = []
    page_token = None
    
    while True:
        try:
            query = f"'{folder_id}' in parents and trashed=false"
            results = service.files().list(
                q=query,
                pageSize=1000,
                fields="nextPageToken, files(id, name, mimeType, webViewLink)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageToken=page_token
            ).execute()
            
            for item in results.get('files', []):
                is_folder = item['mimeType'] == 'application/vnd.google-apps.folder'
                
                if is_folder:
                    # Add folder itself
                    items.append({
                        'folder_path': folder_path,
                        'name': item['name'],
                        'is_folder': True
                    })
                    # Recursively get items in this folder
                    sub_items = get_all_files_recursive(
                        service,
                        item['id'],
                        f"{folder_path}/{item['name']}"
                    )
                    items.extend(sub_items)
                else:
                    items.append({
                        'folder_path': folder_path,
                        'name': item['name'],
                        'is_folder': False,
                        'webViewLink': item.get('webViewLink', '')
                    })
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
                
        except Exception as e:
            print(f"Error getting files: {e}")
            break
            
    return items

@app.route('/export-csv', methods=['POST'])
def export_csv():
    """Export file list as CSV"""
    print('[DEBUG] export_csv: Session keys:', list(session.keys()), flush=True)
    print('[DEBUG] export_csv: Session token:', session.get('token'), flush=True)
    try:
        folder_url = request.json.get('folder_url')
        if not folder_url:
            return jsonify({'error': 'No folder URL provided'}), 400
            
        folder_id = get_folder_id_from_url(folder_url)
        if not folder_id:
            return jsonify({'error': 'Invalid folder URL'}), 400
            
        creds = authenticate()
        service = build('drive', 'v3', credentials=creds)
        
        # Get all files recursively
        items = get_all_files_recursive(service, folder_id)
        
        # Create CSV in memory
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Number', 'Folder Name', 'File Name', 'File URL'])
        
        # Write items
        for i, item in enumerate(items, 1):
            if not item['is_folder']:  # Only include files, not folders
                writer.writerow([
                    i,
                    item['folder_path'],
                    item['name'],
                    item.get('webViewLink', '')
                ])
        
        # Convert StringIO to BytesIO for send_file
        csv_string = output.getvalue()
        output.close()
        bytes_io = io.BytesIO(csv_string.encode('utf-8'))
        bytes_io.seek(0)
        timestamp = datetime.now().strftime('%Y_%m_%d_%H%M%S')
        return send_file(
            bytes_io,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'drive_files_{timestamp}.csv'
        )
        
    except Exception as e:
        print(f"Error exporting CSV: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/oauth2callback')
def oauth2callback():
    """OAuth2 callback to fetch token and store in session."""
    import json
    logging.debug(f"OAuth2 callback received with URL: {request.url}")
    state = session.get('state')
    logging.debug(f"State from session: {state}")
    
    if not state:
        logging.error("No state found in session")
        return "Error: No state found in session. Please try again.", 400
    
    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, SCOPES,
            state=state,
            redirect_uri="http://127.0.0.1:5006/oauth2callback"
        )
        
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        
        token_json = json.dumps({
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        })
        
        session['token'] = token_json
        logging.debug(f"Token saved to session. Keys: {list(session.keys())}")
        
        # Export token to debug_token.json for testing
        with open('debug_token.json', 'w') as f:
            f.write(token_json)
        logging.debug("Exported token to debug_token.json successfully")
        
        # Return HTML with JavaScript to close the window and notify the opener
        return """<html><head><script>
        window.opener.postMessage('authentication_complete','*');
        window.close();
        </script></head><body>Authentication complete.</body></html>"""
    except Exception as e:
        logging.error(f"Error in OAuth callback: {str(e)}")
        return f"Error: {str(e)}", 400

if __name__ == '__main__':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # For development only
    # --- DEBUG: Run Drive API query directly ---
    try:
        from google.oauth2.credentials import Credentials
        import json
        logging.debug("Starting manual Drive API test")
        
        # Load credentials from file for testing
        if os.path.exists('debug_token.json'):
            with open('debug_token.json') as f:
                token_data = json.loads(f.read())
                logging.debug(f"Loaded token data from debug_token.json")
            
            creds = Credentials(
                token=token_data['token'],
                refresh_token=token_data['refresh_token'],
                token_uri=token_data['token_uri'],
                client_id=token_data['client_id'],
                client_secret=token_data['client_secret'],
                scopes=token_data['scopes']
            )
            logging.debug("Successfully created credentials from token file")
            service = build('drive', 'v3', credentials=creds)
            # Test both folder IDs to see which one works
            folder_ids = [
                '17j90tqpf39MPepHfGFztOSUX6py4tIQ8',  # Original folder ID
                '194Cfu68_w6qhGtqR7MHhhvncNFzY0X78'   # New folder ID from screenshot
            ]
            
            for folder_id in folder_ids:
                query = f"'{folder_id}' in parents and trashed=false"
                print(f"[DEBUG] Running manual Drive API query: {query}", flush=True)
                results = service.files().list(
                    q=query,
                    pageSize=100,
                    fields="files(id, name, mimeType, webViewLink, parents)",
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()
                print(f"[DEBUG] Manual query results for folder {folder_id}: {json.dumps(results, indent=2)}", flush=True)
        else:
            print("[DEBUG] No debug_token.json found. Please export your token for standalone testing.", flush=True)
    except Exception as e:
        print(f"[ERROR] Manual Drive API test failed: {e}", flush=True)
    # --- END DEBUG ---
    app.run(port=PORT, debug=True)
