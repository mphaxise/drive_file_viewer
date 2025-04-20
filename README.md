# Google Drive Viewer (v1.0)

A Flask web application that allows users to view files and folders from their Google Drive by providing a folder URL.

## Features

- View files and folders from Google Drive
- Authentication via Google OAuth2
- Export file listings to CSV with optional summaries and notes
- Generate comprehensive file summaries for all file types using AI
- Recursive summarization for long documents
- Metadata-based summaries for non-text files
- Responsive UI with modern design
- Notes column in CSV exports for user annotations
- High-performance summary caching system for instant CSV exports
- Complete subfolder support in CSV exports

## Requirements

- Python 3.8+
- Google Cloud Platform account with Drive API enabled
- OAuth 2.0 credentials configured
- For file summaries: transformers, torch, and sentencepiece libraries

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

6. Export files to CSV with optional summaries and notes:
   - Click the "Export to CSV" button
   - Check the "Include summaries" option if desired
   - Click "Download" to get the CSV file
   - Summaries are cached for performance - no need to regenerate them
   - All files from subfolders are automatically included in the export

## File Summary Feature

The application includes an AI-powered file summary feature that generates concise summaries for all file types in your Google Drive. These summaries are cached for performance and can be included in CSV exports.

### How It Works

1. Enable the "Generate Summaries" checkbox before clicking "View Files"
2. For text-based files:
   - The application downloads the content of text-based files
   - The content is processed using Facebook's BART model (facebook/bart-large-cnn)
   - For long documents, a recursive summarization approach is used to handle large texts
   - A concise summary (maximum 25 words) is generated for each file
3. For non-text files (images, videos, PDFs, etc.):
   - The application generates metadata-based summaries
   - Summaries include file type, size, and other relevant metadata

### Supported File Types

- **Text-based files**:
  - Text files (.txt, .md, .csv, etc.)
  - Google Docs
  - Source code files
  - Other text-based files
- **Binary files**:
  - Images (JPEG, PNG, GIF, etc.)
  - Videos (MP4, MOV, etc.)
  - Audio files (MP3, WAV, etc.)
  - Documents (PDF, DOCX, etc.)
  - Spreadsheets (XLSX, etc.)
  - Presentations (PPTX, etc.)
  - And all other file types

### Features

- **Recursive Summarization**: Handles large documents by breaking them into chunks, summarizing each chunk, and then summarizing the combined results
- **Metadata-based Summaries**: Generates descriptive summaries for non-text files based on file type, size, and other metadata
- **Concise Output**: All summaries are limited to a maximum of 25 words for quick scanning
- **Error Handling**: Graceful fallbacks when summarization fails or when files cannot be accessed
- **High-Performance Caching**: Summaries are cached on the server for instant reuse in CSV exports
- **Complete Subfolder Support**: CSV exports include all files from both the root folder and all subfolders

### Requirements

- Requires the transformers, torch, and sentencepiece libraries for text-based summarization
- Non-text file summaries work even without these dependencies

## Development

### Running Tests

Run tests with unittest:
```bash
python -m unittest discover tests
```

Run tests with coverage:
```bash
python -m coverage run -m unittest discover tests
python -m coverage report -m
```

### Project Structure

- `app.py`: Main application file with Flask routes and Google Drive API integration
- `templates/`: HTML templates for the web interface
- `tests/`: Test directory
  - `test_oauth.py`: Tests for OAuth and authentication flows
  - `test_routes.py`: Tests for web routes and API endpoints
  - `test_csv_export.py`: Tests for CSV export functionality
  - `test_summary.py`: Tests for file summarization features
  - `test_summary_caching.py`: Tests for the summary caching system and subfolder support in exports
- `.coveragerc`: Configuration for code coverage analysis

## Code Coverage

Current code coverage: 93%

## Version History

### v1.0 (April 20, 2025)
- Initial stable release
- Complete CSV export functionality with performance optimization
- Summary caching system for instant CSV exports
- Complete subfolder support in CSV exports
- Concise file summaries (25 words max) for all file types
- Code coverage: 93%

### Test Suites

- `test_oauth.py`: Tests for OAuth and authentication flows (100% coverage)
- `test_routes.py`: Tests for web routes and API endpoints (100% coverage)
- `test_csv_export.py`: Tests for CSV export functionality (97% coverage)
- `test_summary.py`: Tests for file summarization features (100% coverage)
- `test_summary_caching.py`: Tests for the summary caching system (100% coverage)

### Testing Strategy

The application follows a comprehensive testing strategy:

1. **Unit Tests**: Testing individual functions and components in isolation
2. **Integration Tests**: Testing interactions between components
3. **Mock-based Testing**: Using mocks to simulate external dependencies like Google Drive API
4. **Error Handling Tests**: Ensuring the application handles errors gracefully

### Test Workflow

When developing new features, follow this workflow:

1. Create a feature branch from the stable master branch
2. Implement the new feature with proper testing
3. Ensure code coverage remains at or above 90%
4. Document the new feature in the README
5. Update dependencies if needed
6. Run all tests before merging back to master
7. Merge the feature branch back to master when ready

## License

[MIT License](LICENSE)
