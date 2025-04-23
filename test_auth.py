from auth import get_credentials
import logging
logging.basicConfig(level=logging.DEBUG)
print("Starting OAuth flow test...")
creds = get_credentials()
print("Auth successful!" if creds and creds.valid else "Auth failed")
