import logging
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logging.warning("python-dotenv not installed; skipping .env load")

from flask import Flask, render_template, request, jsonify, session, send_file, redirect, url_for
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from urllib.parse import urlparse, parse_qs
import os
import json
import csv
from io import BytesIO
import threading
import webbrowser
import sys
import time
import tempfile
import uuid
import pickle
from pathlib import Path
from datetime import datetime
from ocr_utils import extract_text_from_file_bytes

# Import for GenAI model
try:
    from transformers import pipeline
    SUMMARIZER_AVAILABLE = True
    logging.info("Transformers library is available. File summaries are enabled.")
except ImportError:
    SUMMARIZER_AVAILABLE = False
    logging.warning("Transformers library not available. File summaries will be disabled.")
    
    # Create a dummy pipeline function for graceful degradation
    def pipeline(*args, **kwargs):
        logging.info("Using dummy pipeline function")
        return None


# Set up logging to file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('drive_viewer.log', mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Initialize the summarizer
summarizer = None

def initialize_summarizer():
    """Initialize the text summarizer model."""
    global summarizer
    if SUMMARIZER_AVAILABLE and summarizer is None:
        try:
            logging.info("Initializing file summarizer model...")
            # Use a small, efficient model for summarization
            summarizer = pipeline("summarization", model="facebook/bart-large-cnn", max_length=25, min_length=10)
            logging.info("Summarizer model initialized successfully.")
            return True
        except Exception as e:
            logging.error(f"Error initializing summarizer: {e}")
            return False
    return SUMMARIZER_AVAILABLE

def recursive_summarize(text, file_name, max_length=900, depth=0, max_depth=3):
    """Recursively summarize text until it's short enough."""
    global summarizer
    words = text.split()
    
    # Base case: text is short enough or max recursion depth reached
    if len(words) <= max_length or depth >= max_depth:
        logging.info(f"[Depth {depth}] Text length {len(words)} words is within limit or max depth reached")
        try:
            summary = summarizer(' '.join(words[:max_length]), max_length=25, min_length=10, do_sample=False)
            if summary and len(summary) > 0:
                result = summary[0]['summary_text']
                logging.info(f"[Depth {depth}] Generated summary: {result}")
                return result
            return "Could not generate summary"
        except Exception as e:
            logging.error(f"[Depth {depth}] Error in final summarization: {e}")
            return f"Could not summarize: {str(e)[:50]}"
    
    # Split text into chunks and summarize each
    logging.info(f"[Depth {depth}] Text too long ({len(words)} words), splitting into chunks")
    chunk_size = 800
    chunks = []
    
    # Create chunks
    for i in range(0, len(words), chunk_size):
        chunk = ' '.join(words[i:i + chunk_size])
        chunks.append(chunk)
    
    logging.info(f"[Depth {depth}] Split into {len(chunks)} chunks")
    
    # Summarize each chunk
    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        try:
            logging.info(f"[Depth {depth}] Summarizing chunk {i+1}/{len(chunks)}")
            summary = summarizer(chunk, max_length=25, min_length=10, do_sample=False)
            if summary and len(summary) > 0:
                chunk_summaries.append(summary[0]['summary_text'])
                logging.info(f"[Depth {depth}] Chunk {i+1} summary: {summary[0]['summary_text'][:50]}...")
            else:
                logging.warning(f"[Depth {depth}] Could not summarize chunk {i+1}")
        except Exception as e:
            logging.error(f"[Depth {depth}] Error summarizing chunk {i+1}: {e}")
            # Skip this chunk if there's an error
            continue
    
    # If no summaries were generated, return an error
    if not chunk_summaries:
        logging.error(f"[Depth {depth}] No chunk summaries were generated")
        return "Could not generate summary for any chunk"
    
    # Combine chunk summaries and recursively summarize
    combined_text = ' '.join(chunk_summaries)
    logging.info(f"[Depth {depth}] Combined {len(chunk_summaries)} chunk summaries, total length: {len(combined_text.split())} words")
    
    # Recursive call
    return recursive_summarize(combined_text, file_name, max_length, depth + 1, max_depth)

def generate_metadata_summary(file_name, file_type, file_size=None, created_date=None, modified_date=None):
    """Generate a descriptive summary based on file metadata for non-text files."""
    file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
    
    # Format file size if available
    size_info = ""
    if file_size:
        # Convert bytes to appropriate unit
        if file_size < 1024:
            size_info = f"{file_size} bytes"
        elif file_size < 1024 * 1024:
            size_info = f"{file_size/1024:.1f} KB"
        else:
            size_info = f"{file_size/(1024*1024):.1f} MB"
    
    # Create summaries based on file type
    if file_type.startswith('image/'):
        return f"Image file{' (' + size_info + ')' if size_info else ''}."
    
    elif file_type.startswith('video/'):
        return f"Video file{' (' + size_info + ')' if size_info else ''}."
    
    elif file_type.startswith('audio/'):
        return f"Audio file{' (' + size_info + ')' if size_info else ''}."
    
    elif file_type == 'application/pdf':
        return f"PDF document{' (' + size_info + ')' if size_info else ''}."
    
    elif file_type in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
        return f"Excel spreadsheet{' (' + size_info + ')' if size_info else ''}."
    
    elif file_type in ['application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation']:
        return f"PowerPoint presentation{' (' + size_info + ')' if size_info else ''}."
    
    elif file_type in ['application/zip', 'application/x-zip-compressed']:
        return f"ZIP archive{' (' + size_info + ')' if size_info else ''}."
    
    else:
        # Generic summary for other file types
        return f"{file_ext.upper() if file_ext else 'Unknown'} file{' (' + size_info + ')' if size_info else ''}."

def generate_file_summary(file_content, file_name, file_type=None, file_size=None, created_date=None, modified_date=None):
    """Generate a summary for the given file content or metadata."""
    global summarizer
    
    # Check if content is empty
    content_length = len(file_content) if file_content else 0
    logging.info(f"File {file_name} has {content_length} characters")
    
    if content_length == 0:
        logging.warning(f"No content to summarize for {file_name}")
        return "No content to summarize"
    
    # Determine file extension
    file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
    
    # File types that don't have extractable text content
    binary_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'mp4', 'avi', 'mov',
                         'wmv', 'mp3', 'wav', 'ogg', 'pdf', 'zip', 'exe', 'dll']
    # OCR-capable extensions should bypass metadata summary when text is provided via OCR
    ocr_exts = ['pdf']
    # Use metadata-based summary for binary files not covered by OCR
    if (file_ext in binary_extensions and file_ext not in ocr_exts) or \
       (file_type and not file_type.startswith('text/') and 
        'document' not in file_type and 'sheet' not in file_type):
        return generate_metadata_summary(file_name, file_type or 'application/octet-stream',
                                        file_size, created_date, modified_date)
    
    # For text-based files, use the transformer model
    if not SUMMARIZER_AVAILABLE:
        logging.warning(f"Summary not available for {file_name} (model not installed)")
        return "Summary not available (model not installed)"
    
    try:
        # Initialize summarizer if not already done
        if summarizer is None:
            logging.info(f"Initializing summarizer for {file_name}...")
            success = initialize_summarizer()
            if not success:
                logging.error(f"Failed to initialize summarizer for {file_name}")
                return "Summary not available (model initialization failed)"
        
        # Clean the input text to remove any problematic characters
        # Replace tabs, multiple spaces, and other whitespace with a single space
        cleaned_content = ' '.join(file_content.split())
        
        # Use recursive summarization for long content
        word_count = len(cleaned_content.split())
        logging.info(f"File {file_name} has {word_count} words")
        
        max_direct_words = 900  # Maximum words for direct summarization
        
        if word_count > max_direct_words:
            logging.info(f"Using recursive summarization for {file_name} ({word_count} words)")
            return recursive_summarize(cleaned_content, file_name)
        else:
            # For shorter content, use direct summarization
            logging.info(f"Using direct summarization for {file_name} ({word_count} words)")
            summary = summarizer(cleaned_content, max_length=25, min_length=10, do_sample=False)
            
            if summary and len(summary) > 0:
                summary_text = summary[0]['summary_text']
                logging.info(f"Summary generated for {file_name}: {summary_text}")
                return summary_text
            else:
                logging.warning(f"Could not generate summary for {file_name} - empty result")
                return f"Could not generate summary for {file_name}"

    except Exception as e:
        logging.error(f"Error generating summary for {file_name}: {e}", exc_info=True)
        return f"Error generating summary: {str(e)[:50]}"

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev_key_for_testing')
PORT = 5006

# Create a temp directory for storing summaries
TEMP_DIR = Path(tempfile.gettempdir()) / 'drive_viewer_summaries'
TEMP_DIR.mkdir(exist_ok=True)

# Configure Google OAuth2
CLIENT_SECRETS_FILE = os.environ.get("GOOGLE_CLIENT_SECRETS", "credentials.json")
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

def download_file_content(service, file_id, mime_type):
    """Download content from a Google Drive file."""
    try:
        logging.info(f"Attempting to download file {file_id} with mime type {mime_type}")
        
        if 'google-apps' in mime_type:
            # For Google Docs, export as plain text
            logging.debug(f"File {file_id} is a Google Doc, exporting as text/plain")
            export_mime_type = 'text/plain'
            response = service.files().export(fileId=file_id, mimeType=export_mime_type).execute()
            content = response.decode('utf-8') if isinstance(response, bytes) else response
            logging.info(f"Successfully exported Google Doc {file_id}, size: {len(content)} bytes")
            return content
        else:
            # For regular files, download the content
            logging.debug(f"File {file_id} is a regular file, downloading content")
            request = service.files().get_media(fileId=file_id)
            file_content = BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            logging.debug(f"Downloader created for {file_id}")
            
            done = False
            while not done:
                logging.debug(f"Downloading chunk for {file_id}...")
                status, done = downloader.next_chunk()
                logging.debug(f"Download progress: {int(status.progress() * 100)}%")
            
            content = file_content.getvalue().decode('utf-8', errors='replace')
            logging.info(f"Successfully downloaded file {file_id}, size: {len(content)} bytes")
            return content
    except Exception as e:
        logging.error(f"Error downloading file {file_id}: {e}", exc_info=True)
        return None

def download_file_bytes(service, file_id):
    """Download raw bytes of a file from Drive."""
    try:
        request = service.files().get_media(fileId=file_id)
        bytes_io = BytesIO()
        downloader = MediaIoBaseDownload(bytes_io, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return bytes_io.getvalue()
    except Exception as e:
        logging.error(f"Error downloading raw bytes for {file_id}: {e}")
        return None

def list_files_in_folder(credentials, folder_id, generate_summaries=False):
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
            
        # List files in the folder
        query = f"'{folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query,
            pageSize=100,
            fields="nextPageToken, files(id, name, mimeType, webViewLink, size)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        items = results.get('files', [])
        logging.debug(f"Found {len(items)} items in folder")
        
        processed_items = []
        for item in items:
            is_folder = item['mimeType'] == 'application/vnd.google-apps.folder'
            file_item = {
                'id': item['id'],
                'name': item['name'],
                'type': 'folder' if is_folder else 'file',
                'mimeType': item['mimeType'],
                'webViewLink': item.get('webViewLink', ''),
                'size': item.get('size', '0')
            }
            
            # Generate summary for files if requested and not a folder
            if generate_summaries and not is_folder and SUMMARIZER_AVAILABLE:
                try:
                    # Get additional file metadata
                    file_size = None
                    created_date = None
                    modified_date = None
                    
                    try:
                        file_metadata = service.files().get(
                            fileId=item['id'], 
                            fields='size,createdTime,modifiedTime',
                            supportsAllDrives=True
                        ).execute()
                        
                        if 'size' in file_metadata:
                            file_size = int(file_metadata['size'])
                        if 'createdTime' in file_metadata:
                            created_date = file_metadata['createdTime']
                        if 'modifiedTime' in file_metadata:
                            modified_date = file_metadata['modifiedTime']
                    except Exception as e:
                        logging.warning(f"Could not get detailed metadata for {item['name']}: {e}")
                    
                    # OCR-based summarization
                    file_ext = item['name'].split('.')[-1].lower()
                    ocr_exts = ['pdf']
                    if file_ext in ocr_exts:
                        logging.debug(f"OCR summarization for {item['name']}")
                        raw_bytes = download_file_bytes(service, item['id'])
                        try:
                            extracted_text = extract_text_from_file_bytes(raw_bytes, item['name'])
                        except Exception as ocr_err:
                            logging.error(f"OCR extraction failed for {item['name']}: {ocr_err}")
                            extracted_text = ''
                        if extracted_text.strip():
                            summary = generate_file_summary(
                                extracted_text,
                                item['name'],
                                item['mimeType'],
                                file_size,
                                created_date,
                                modified_date
                            )
                        else:
                            summary = generate_metadata_summary(
                                item['name'],
                                item['mimeType'],
                                file_size,
                                created_date,
                                modified_date
                            )
                    else:
                        # Download file content for summary generation
                        logging.debug(f"Downloading content for {item['name']} (mime type: {item['mimeType']})")
                        file_content = download_file_content(service, item['id'], item['mimeType'])
                        summary = generate_file_summary(
                            file_content,
                            item['name'],
                            item['mimeType'],
                            file_size,
                            created_date,
                            modified_date
                        )
                    file_item['summary'] = summary
                    logging.info(f"Summary for {item['name']}: {summary[:100]}...")
                except Exception as e:
                    logging.error(f"Error generating summary for {item['name']}: {e}")
                    file_item['summary'] = f"Error generating summary: {str(e)[:50]}"
            elif not is_folder:
                file_item['summary'] = "Summary generation disabled"
                
            processed_items.append(file_item)
        
        logging.debug(f"Processed items: {len(processed_items)}")
        
        # Sort items: folders first, then by name
        processed_items.sort(key=lambda x: (x['type'] != 'folder', x['name'].lower()))
        
        return {
            'items': processed_items,
            'folderName': folder_name,
            'folderId': folder_id,
            'summaries_enabled': generate_summaries and SUMMARIZER_AVAILABLE,
            'summaries_available': SUMMARIZER_AVAILABLE
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
        # Use correct callback URI and store state for token exchange
        redirect_uri = url_for('oauth2callback', _external=True)
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        session['state'] = state
        print(f"Generated authorization URL: {authorization_url}")
        return jsonify({'auth_url': authorization_url})
    except Exception as e:
        print(f"Error in authorize: {str(e)}")
        return jsonify({'error': str(e)})

@app.route('/list-files', methods=['POST'])
def list_files():
    try:
        logging.info("Received list-files request")
        
        # Get folder ID either from URL or direct ID
        folder_url = request.json.get('folder_url')
        folder_id = request.json.get('folder_id')
        generate_summaries = request.json.get('generate_summaries', False)
        
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
            # Only enforce refresh-capable credentials when real Credentials instance
            if isinstance(credentials, Credentials) and not all([
                credentials.refresh_token,
                credentials.token_uri,
                credentials.client_id,
                credentials.client_secret
            ]):
                raise Exception('authentication_required')
        except Exception as e:
            print(f"Authentication required: {str(e)}")
            print("Starting authentication...")
            
            # Save the folder ID in the session for later use
            session['folder_id'] = folder_id
            if folder_url:
                session['folder_url'] = folder_url
            
            # Start OAuth flow
            redirect_uri = url_for('oauth2callback', _external=True)
            flow = Flow.from_client_secrets_file(
                CLIENT_SECRETS_FILE,
                scopes=SCOPES,
                redirect_uri=redirect_uri
            )
            
            auth_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            session['state'] = state
            logging.debug(f"Generated new state {state}.")
            return jsonify({'auth_url': auth_url})
        
        logging.info("Listing files...")
        result = list_files_in_folder(credentials, folder_id, generate_summaries)
        
        if 'error' in result:
            return jsonify({'error': result['error']})
        
        # Store the result in a temporary file for later use in CSV export
        # Generate a unique ID for this result
        result_id = str(uuid.uuid4())
        
        # Store just the ID in the session
        session['last_folder_result_id'] = result_id
        session['last_folder_id'] = folder_id
        
        # Save the result to a temporary file
        result_file = TEMP_DIR / f"{result_id}.pickle"
        with open(result_file, 'wb') as f:
            pickle.dump(result, f)
            
        logging.info(f"Found {len(result['items'])} items in folder {result['folderName']}")
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error in list_files: {str(e)}")
        return jsonify({'error': str(e)})

def get_all_files_recursive(service, folder_id, folder_path="Root", include_summaries=False):
    """Recursively get all files and folders from Google Drive"""
    items = []
    page_token = None
    
    # First check if we have cached results for this folder
    if include_summaries and 'last_folder_result_id' in session and 'last_folder_id' in session:
        if session['last_folder_id'] == folder_id:
            try:
                # Try to use the stored results from the temporary file
                result_id = session['last_folder_result_id']
                result_file = TEMP_DIR / f"{result_id}.pickle"
                logging.info(f"Looking for cached results in: {result_file}")
                
                if result_file.exists():
                    with open(result_file, 'rb') as f:
                        cached_result = pickle.load(f)
                    
                    folder_name = cached_result.get('folderName', 'Root')
                    
                    if 'items' in cached_result:
                        # Check if summaries exist in the cached results
                        has_summaries = any(item.get('summary') and 
                                           item.get('summary') != "Summary generation disabled" and
                                           not item.get('summary', '').startswith("Error generating summary")
                                           for item in cached_result['items'] if item.get('type') == 'file')
                        
                        if has_summaries:
                            logging.info(f"Using cached summaries for folder {folder_id}")
                            # Convert cached items to the format expected by get_all_files_recursive
                            for item in cached_result['items']:
                                if item.get('type') == 'file':
                                    # Only use items with valid summaries
                                    summary = item.get('summary', '')
                                    valid_summary = (summary and 
                                                    summary != "Summary generation disabled" and
                                                    not summary.startswith("Error generating summary"))
                                    
                                    items.append({
                                        'folder_path': folder_name,
                                        'name': item['name'],
                                        'is_folder': False,
                                        'webViewLink': item.get('webViewLink', ''),
                                        'summary': summary if valid_summary else "Summary generation disabled",
                                        'notes': ''
                                    })
                                elif item.get('type') == 'folder':
                                    # For folders, we need to recursively get their contents
                                    # First add the folder itself
                                    items.append({
                                        'folder_path': folder_name,
                                        'name': item['name'],
                                        'is_folder': True
                                    })
                                    
                                    # Then recursively get its contents
                                    # Note: This is a simplification - in a real implementation, 
                                    # you'd want to check if the subfolder's contents are also cached
                                    sub_items = get_all_files_recursive(
                                        service,
                                        item['id'],
                                        f"{folder_path}/{item['name']}",
                                        include_summaries
                                    )
                                    items.extend(sub_items)
                            
                            # Return early with cached results
                            logging.info(f"Successfully reused {len(items)} cached items")
                            return items
            except Exception as e:
                logging.error(f"Error using cached results: {e}", exc_info=True)
                # Fall back to fetching from Drive API
    
    # If we don't have cached results or couldn't use them, fetch from Drive API
    logging.info(f"Fetching files from Drive API for folder {folder_id}")
    
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
                        f"{folder_path}/{item['name']}",
                        include_summaries
                    )
                    items.extend(sub_items)
                else:
                    file_item = {
                        'folder_path': folder_path,
                        'name': item['name'],
                        'is_folder': False,
                        'webViewLink': item.get('webViewLink', ''),
                        'id': item['id'],
                        'mimeType': item['mimeType']
                    }
                    
                    # Generate summary if requested
                    if include_summaries and SUMMARIZER_AVAILABLE:
                        try:
                            # Get additional file metadata
                            file_size = None
                            created_date = None
                            modified_date = None
                            
                            try:
                                file_metadata = service.files().get(
                                    fileId=item['id'], 
                                    fields='size,createdTime,modifiedTime',
                                    supportsAllDrives=True
                                ).execute()
                                
                                if 'size' in file_metadata:
                                    file_size = int(file_metadata['size'])
                                if 'createdTime' in file_metadata:
                                    created_date = file_metadata['createdTime']
                                if 'modifiedTime' in file_metadata:
                                    modified_date = file_metadata['modifiedTime']
                            except Exception as e:
                                logging.warning(f"Could not get detailed metadata for {item['name']}: {e}")
                            
                            # OCR-based summarization
                            file_ext = item['name'].split('.')[-1].lower()
                            ocr_exts = ['pdf']
                            if file_ext in ocr_exts:
                                logging.debug(f"OCR summarization for {item['name']}")
                                raw_bytes = download_file_bytes(service, item['id'])
                                try:
                                    extracted_text = extract_text_from_file_bytes(raw_bytes, item['name'])
                                except Exception as ocr_err:
                                    logging.error(f"OCR extraction failed for {item['name']}: {ocr_err}")
                                    extracted_text = ''
                                if extracted_text.strip():
                                    summary = generate_file_summary(
                                        extracted_text,
                                        item['name'],
                                        item['mimeType'],
                                        file_size,
                                        created_date,
                                        modified_date
                                    )
                                else:
                                    summary = generate_metadata_summary(
                                        item['name'],
                                        item['mimeType'],
                                        file_size,
                                        created_date,
                                        modified_date
                                    )
                            else:
                                # Download file content for summary generation
                                logging.debug(f"Downloading content for {item['name']} (mime type: {item['mimeType']})")
                                file_content = download_file_content(service, item['id'], item['mimeType'])
                                summary = generate_file_summary(
                                    file_content,
                                    item['name'],
                                    item['mimeType'],
                                    file_size,
                                    created_date,
                                    modified_date
                                )
                            file_item['summary'] = summary
                        except Exception as e:
                            logging.error(f"Error generating summary for {item['name']}: {e}")
                            file_item['summary'] = f"Error generating summary: {str(e)[:50]}"
                    elif not include_summaries:
                        file_item['summary'] = "Summary generation disabled"
                    
                    # Add empty notes field
                    file_item['notes'] = ""
                    
                    items.append(file_item)
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
                
        except Exception as e:
            logging.error(f"Error getting files: {e}")
            break
            
    return items

@app.route('/export-csv', methods=['POST'])
def export_csv():
    """Export file list as CSV"""
    logging.info("Received export-csv request")
    try:
        folder_url = request.json.get('folder_url')
        if not folder_url:
            return jsonify({'error': 'No folder URL provided'}), 400
            
        folder_id = get_folder_id_from_url(folder_url)
        if not folder_id:
            return jsonify({'error': 'Invalid folder URL'}), 400
            
        # Check if summaries should be included
        include_summaries = request.json.get('include_summaries', False)
        
        # Check if we already have the results in a temporary file
        reuse_summaries = False
        items = []
        folder_name = "Root"
        
        if 'last_folder_result_id' in session and 'last_folder_id' in session:
            if session['last_folder_id'] == folder_id:
                try:
                    # Try to use the stored results from the temporary file
                    result_id = session['last_folder_result_id']
                    result_file = TEMP_DIR / f"{result_id}.pickle"
                    
                    if result_file.exists():
                        with open(result_file, 'rb') as f:
                            last_result = pickle.load(f)
                        
                        folder_name = last_result.get('folderName', 'Root')
                        
                        if 'items' in last_result:
                            # For CSV export, we always want to use cached results if available
                            # If summaries are requested, check if they exist
                            has_summaries = not include_summaries or any(
                                item.get('summary') and 
                                item.get('summary') != "Summary generation disabled" and
                                not item.get('summary', '').startswith("Error generating summary")
                                for item in last_result['items'] if item.get('type') == 'file'
                            )
                            
                            if has_summaries:
                                logging.info("Reusing existing results from temporary file")
                                # Convert the items to the format expected by the CSV export
                                # First, extract all file items directly
                                for item in last_result['items']:
                                    if item.get('type') == 'file':
                                        items.append({
                                            'folder_path': folder_name,
                                            'name': item['name'],
                                            'is_folder': False,
                                            'webViewLink': item.get('webViewLink', ''),
                                            'summary': item.get('summary', '') if include_summaries else 'Summary generation disabled',
                                            'notes': ''
                                        })
                                
                                # Now we need to get files from subfolders
                                # Since we don't store the full hierarchy in the cache,
                                # we'll need to make API calls for the subfolders
                                creds = authenticate()
                                service = build('drive', 'v3', credentials=creds)
                                
                                # Process all folder items
                                for item in last_result['items']:
                                    if item.get('type') == 'folder':
                                        subfolder_path = f"{folder_name}/{item['name']}"
                                        # Get files from this subfolder recursively
                                        subfolder_items = get_all_files_recursive(
                                            service,
                                            item['id'],
                                            subfolder_path,
                                            include_summaries
                                        )
                                        # Add all file items (not folders) to our result
                                        items.extend([i for i in subfolder_items if not i.get('is_folder', False)])
                                
                                reuse_summaries = True
                except Exception as e:
                    logging.error(f"Error reusing summaries: {e}")
                    # Fall back to regenerating summaries
                    reuse_summaries = False
        
        if not reuse_summaries:
            logging.info("Generating new file list for CSV export")
            creds = authenticate()
            service = build('drive', 'v3', credentials=creds)
            
            # Get folder ID from the URL for the API call
            folder_id_for_api = get_folder_id_from_url(folder_url) if folder_url else folder_id
            
            # Get all files recursively with summaries if requested
            items = get_all_files_recursive(service, folder_id_for_api, include_summaries=include_summaries)
        
        # Create CSV in memory
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header with additional columns for summary and notes
        writer.writerow(['Number', 'Folder Name', 'File Name', 'File URL', 'Summary', 'Notes'])
        
        # Write items
        for i, item in enumerate(items, 1):
            if not item['is_folder']:  # Only include files, not folders
                writer.writerow([
                    i,
                    item['folder_path'],
                    item['name'],
                    item.get('webViewLink', ''),
                    item.get('summary', ''),
                    item.get('notes', '')
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
        logging.error(f"Error exporting CSV: {e}")
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
        with open('debug_token.json', 'w') as f:
            f.write(token_json)
        logging.debug(f"Token saved to session. Keys: {list(session.keys())}")
        
        # Token saved to session
        
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
    app.run(port=PORT, debug=True)
