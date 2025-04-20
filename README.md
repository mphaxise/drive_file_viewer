# Google Drive Viewer

A Flask web application that allows users to view files and folders from their Google Drive by providing a folder URL.

## Features

- View files and folders from Google Drive
- Authentication via Google OAuth2
- Export file listings to CSV
- Responsive UI with modern design

## Requirements

- Python 3.8+
- Google Cloud Platform account with Drive API enabled
- OAuth 2.0 credentials configured

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd drive_file_viewer
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file in the project root with the following content:
```
FLASK_SECRET_KEY=your_secret_key_here
```

4. Set up Google OAuth credentials:
   - Create a project in the [Google Cloud Console](https://console.cloud.google.com/)
   - Enable the Google Drive API
   - Create OAuth 2.0 credentials (Web application type)
   - Set the redirect URI to `http://127.0.0.1:5006/oauth2callback`
   - Download the credentials JSON file and save it as `credentials.json` in the project root

## Usage

1. Start the application:
```bash
python app.py
```

2. Open your browser and navigate to:
```
http://localhost:5006
```

3. Enter a Google Drive folder URL in the input field and click "View Files"

4. Authenticate with your Google account when prompted

5. Browse your files and folders

## Development

### Running Tests

Run tests with pytest:
```bash
python -m pytest
```

Run tests with coverage:
```bash
python -m pytest --cov=app --cov-report=term-missing
```

### Project Structure

- `app.py`: Main application file with Flask routes and Google Drive API integration
- `templates/`: HTML templates for the web interface
- `test_app.py`: Test suite for the application
- `.coveragerc`: Configuration for code coverage analysis

## Code Coverage

Current code coverage: 91%

## License

[MIT License](LICENSE)
