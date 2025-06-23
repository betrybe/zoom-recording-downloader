import os
import json
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


class Color:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    DARK_CYAN = "\033[36m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


SUCCESS_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Authentication Successful</title>
</head>
<body>
    <h1>Zoom Recording Downloader</h1>
    <p>Authentication successful! You may close this window.</p>
</body>
</html>
"""


class GoogleDriveClient:
    SCOPES = [
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive.metadata",
        "https://www.googleapis.com/auth/drive.appdata",
        "https://www.googleapis.com/auth/drive",
    ]

    def __init__(self, config):
        self.config = config
        self.service = None
        self.credentials = None
        self.root_folder_id = None

    def authenticate(self):
        """Handle the OAuth flow and return True if successful."""
        print(
            f"{Color.DARK_CYAN}Initializing Google Drive authentication...{Color.END}"
        )

        creds = None
        token_file = self.config.get("token_file", "token.json")
        secrets_file = self.config.get("client_secrets_file", "client_secrets.json")

        if not os.path.exists(secrets_file):
            print(
                f"{Color.RED}Error: {secrets_file} not found. Please configure OAuth credentials.{Color.END}"
            )
            return False

        if os.path.exists(token_file):
            try:
                creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)
            except Exception as e:
                print(f"{Color.YELLOW}Error reading token file: {e}{Color.END}")

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print(f"{Color.DARK_CYAN}Refreshing expired token...{Color.END}")
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(
                        f"{Color.YELLOW}Token refresh failed: {e}. Initiating new authentication...{Color.END}"
                    )
                    creds = None

            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        secrets_file, self.SCOPES
                    )
                    print(
                        f"{Color.DARK_CYAN}Please login in your browser...{Color.END}"
                    )
                    creds = flow.run_local_server(port=0, success_message=SUCCESS_PAGE)
                except Exception as e:
                    print(f"{Color.RED}Authentication failed: {e}{Color.END}")
                    return False

            with open(token_file, "w") as token:
                token.write(creds.to_json())
                print(f"{Color.GREEN}Token saved to {token_file}{Color.END}")

        try:
            self.service = build("drive", "v3", credentials=creds)
            self.credentials = creds

            # Get user email
            user_info = self.service.about().get(fields="user").execute()
            email = user_info["user"]["emailAddress"]
            print(f"{Color.GREEN}Successfully authenticated as {email}{Color.END}")

            # Test API connection after successful authentication
            if self.service:
                if not self.test_api_connection():
                    print(
                        f"{Color.YELLOW}API connection test failed. Please check permissions.{Color.END}"
                    )
                    # Continue anyway, just as a warning

            return True
        except Exception as e:
            print(f"{Color.RED}Failed to initialize Drive service: {e}{Color.END}")
            return False

    def _handle_upload_with_refresh(self, request):
        """Execute request with token refresh handling."""
        try:
            return request.execute()
        except HttpError as e:
            if e.resp.status in [401, 403]:
                if self.credentials.refresh_token:
                    print(f"{Color.YELLOW}Token expired, refreshing...{Color.END}")
                    self.credentials.refresh(Request())
                    return self._handle_upload_with_refresh(request)
                else:
                    print(
                        f"{Color.YELLOW}Token refresh failed, re-authenticating...{Color.END}"
                    )
                    if self.authenticate():
                        return self._handle_upload_with_refresh(request)
            raise

    def find_folder(self, folder_name, parent_id=None):
        """Find a folder by name in Google Drive and return its ID, excluding trashed folders."""
        # Escape single quotes in folder name
        escaped_folder_name = folder_name.replace("'", "\\'")
        query = f"name='{escaped_folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        try:
            response = (
                self.service.files()
                .list(q=query, spaces="drive", fields="files(id, name)")
                .execute()
            )
            if response.get("files"):
                return response.get("files")[0].get("id")
        except Exception as e:
            print(
                f"{Color.RED}Failed to find folder {folder_name}: {str(e)}{Color.END}"
            )
        return None

    def create_folder(self, folder_name, parent_id=None):
        """Create a folder in Google Drive and return its ID."""
        file_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            file_metadata["parents"] = [parent_id]

        try:
            folder = self._handle_upload_with_refresh(
                self.service.files().create(body=file_metadata, fields="id")
            )
            return folder.get("id")
        except Exception as e:
            print(
                f"{Color.RED}Failed to create folder {folder_name}: {str(e)}{Color.END}"
            )
            return None

    def navigate_folders(self, folder_path):
        """Navigate through folder structure, creating folders if necessary"""
        print(f"  > Navigating to folder path: {folder_path}")

        parts = folder_path.split(os.sep)
        current_parent = self.root_folder_id

        for folder_name in parts:
            if not folder_name:
                continue

            folder_id = self.find_folder(folder_name, current_parent)

            if folder_id:
                current_parent = folder_id
                print(
                    f"    > Found existing folder: {folder_name} (ID: {current_parent})"
                )
            else:
                # Folder doesn't exist, create it
                new_folder_id = self.create_folder(folder_name, current_parent)
                if new_folder_id:
                    current_parent = new_folder_id
                    print(
                        f"    > Created new folder: {folder_name} (ID: {current_parent})"
                    )
                else:
                    print(
                        f"    {Color.RED}Failed to create folder: {folder_name}{Color.END}"
                    )
                    return None
        return current_parent

    def upload_file(self, local_path, folder_name, filename):
        """Upload file to Google Drive with retry logic and idempotency check, excluding trashed files."""
        try:
            print(f"    > Getting folder ID for path: {folder_name}")
            folder_id = self.navigate_folders(folder_name)
            if not folder_id:
                return False

            # Escape single quotes in filename
            escaped_filename = filename.replace("'", "\\'")
            # Check if file already exists and is not in the trash
            query = f"name='{escaped_filename}' and '{folder_id}' in parents and trashed = false"
            response = (
                self.service.files()
                .list(q=query, spaces="drive", fields="files(id)")
                .execute()
            )
            if response.get("files"):
                print(
                    f"    > File '{filename}' already exists in Google Drive. Skipping upload."
                )
                return True

            file_metadata = {"name": filename, "parents": [folder_id]}
            print(f"    > Uploading {filename} to folder ID: {folder_id}")

            media = MediaFileUpload(local_path, resumable=True)

            max_retries = int(self.config.get("max_retries", 3))
            retry_delay = int(self.config.get("retry_delay", 5))
            failed_log = self.config.get("failed_log", "failed-uploads.log")

            for attempt in range(max_retries):
                try:
                    print(f"    > Attempt {attempt + 1} of {max_retries}...")

                    # Add shared drive support for file creation
                    create_params = {
                        "body": file_metadata,
                        "media_body": media,
                        "fields": "id",
                    }

                    request = self.service.files().create(**create_params)
                    response = self._handle_upload_with_refresh(request)

                    print(
                        f"    {Color.GREEN}Success! File ID: {response.get('id')}{Color.END}"
                    )
                    return True

                except Exception as e:
                    if attempt < max_retries - 1:
                        print(
                            f"    {Color.YELLOW}Retry after {retry_delay} seconds...{Color.END}"
                        )
                        import time

                        time.sleep(retry_delay)
                    else:
                        print(f"{Color.RED}Upload failed: {str(e)}{Color.END}")
                        with open(failed_log, "a") as log:
                            log.write(
                                f"{datetime.now()}: Failed to upload {filename} - {str(e)}\n"
                            )
                        return False
        except Exception as e:
            print(f"{Color.RED}Upload preparation failed: {str(e)}{Color.END}")
            return False

    def initialize_root_folder(self):
        """Find or create the root folder."""
        root_folder_name = self.config.get(
            "root_folder_name", "zoom-recording-downloader"
        )
        folder_id = self.find_folder(root_folder_name)
        if folder_id:
            self.root_folder_id = folder_id
            print(f"Found root folder '{root_folder_name}' with ID: {folder_id}")
        else:
            self.root_folder_id = self.create_folder(root_folder_name)
            if self.root_folder_id:
                print(
                    f"Created root folder '{root_folder_name}' with ID: {self.root_folder_id}"
                )
        return self.root_folder_id is not None

    def test_api_connection(self):
        """Test the connection to the Google Drive API."""
        try:
            # Try to get Drive API information
            about = self.service.about().get(fields="user,storageQuota").execute()
            user_email = about["user"]["emailAddress"]
            quota = about["storageQuota"]

            used = int(quota.get("usage", 0)) / (1024 * 1024 * 1024)  # Convert to GB
            total = int(quota.get("limit", 0)) / (1024 * 1024 * 1024)  # Convert to GB

            print(
                f"{Color.GREEN}✓ Successfully connected to Google Drive API{Color.END}"
            )
            print(f"  User: {user_email}")
            print(f"  Storage: {used:.2f} GB used of {total:.2f} GB")

            # Test if we can list files (basic permission check)
            files = (
                self.service.files().list(pageSize=1, fields="files(name)").execute()
            )
            print(f"{Color.GREEN}✓ Successfully listed files in Drive{Color.END}")

            return True

        except Exception as e:
            print(f"{Color.RED}× API connection test failed: {str(e)}{Color.END}")
            return False
