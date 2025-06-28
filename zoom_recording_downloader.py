#!/usr/bin/env python3

# Program Name: zoom-recording-downloader.py
# Description:  Zoom Recording Downloader is a cross-platform Python script
#               that uses Zoom's API (v2) to download and organize all
#               cloud recordings from a Zoom account onto local storage.
#               This Python script uses the OAuth method of accessing the Zoom API
# Created:      2020-04-26
# Author:       Ricardo Rodrigues
# Website:      https://github.com/ricardorodrigues-ca/zoom-recording-downloader
# Forked from:  https://gist.github.com/danaspiegel/c33004e52ffacb60c24215abf8301680

# System modules
import base64
import json
import os
import re as regex
import signal
import sys as system
import time
from datetime import datetime, date, timezone, timedelta
import argparse
import pandas as pd
from progress_log import ProgressLog, create_row_hash

# Installed modules
import dateutil.parser as parser
import pathvalidate as path_validate
import requests
import tqdm as progress_bar
from zoneinfo import ZoneInfo
from google_drive_client import GoogleDriveClient

os.environ["FORCE_COLOR"] = "1"  # Force color output in terminals


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


CONF_PATH = "zoom-recording-downloader.conf"

# Load configuration file and check for proper JSON syntax
try:
    with open(CONF_PATH, encoding="utf-8-sig") as json_file:
        CONF = json.loads(json_file.read())
except json.JSONDecodeError as e:
    print(f"{Color.RED}### Error parsing JSON in {CONF_PATH}: {e}")
    system.exit(1)
except FileNotFoundError:
    print(f"{Color.RED}### Configuqration file {CONF_PATH} not found")
    system.exit(1)
except Exception as e:
    print(f"{Color.RED}### Unexpected error: {e}")
    system.exit(1)


def config(section, key, default=""):
    try:
        return CONF[section][key]
    except KeyError:
        if default == LookupError:
            print(
                f"{Color.RED}### No value provided for {section}:{key} in {CONF_PATH}"
            )
            system.exit(1)
        else:
            return default


ACCOUNT_ID = config("OAuth", "account_id", LookupError)
CLIENT_ID = config("OAuth", "client_id", LookupError)
CLIENT_SECRET = config("OAuth", "client_secret", LookupError)

APP_VERSION = "3.1 (Google Drive Edition)"

API_ENDPOINT_USER_LIST = "https://api.zoom.us/v2/users"

RECORDING_START_YEAR = config("Recordings", "start_year", date.today().year)
RECORDING_START_MONTH = config("Recordings", "start_month", 1)
RECORDING_START_DAY = config("Recordings", "start_day", 1)
RECORDING_START_DATE = parser.parse(
    config(
        "Recordings",
        "start_date",
        f"{RECORDING_START_YEAR}-{RECORDING_START_MONTH}-{RECORDING_START_DAY}",
    )
).replace(tzinfo=timezone.utc)
RECORDING_END_DATE = parser.parse(
    config("Recordings", "end_date", str(date.today()))
).replace(tzinfo=timezone.utc)
DOWNLOAD_DIRECTORY = config("Storage", "download_dir", "downloads")
COMPLETED_MEETING_IDS_LOG = config(
    "Storage", "completed_log", "completed-downloads.log"
)
VERBOSE_URL = config("Storage", "verbose_url", False)
COMPLETED_MEETING_IDS = set()

MEETING_TIMEZONE = ZoneInfo(config("Recordings", "timezone", "UTC"))
MEETING_STRFTIME = config("Recordings", "strftime", "%Y.%m.%d - %I.%M %p UTC")
MEETING_FILENAME = config(
    "Recordings",
    "filename",
    "{meeting_time} - {topic} - {rec_type} - {recording_id}.{file_extension}",
)
MEETING_FOLDER = config("Recordings", "folder", "{topic} - {meeting_time}")

# Google Drive configuration
GDRIVE_ENABLED = False
GDRIVE_CREDENTIALS_FILE = config(
    "GoogleDrive", "credentials_file", "service-account.json"
)
GDRIVE_ROOT_FOLDER = config(
    "GoogleDrive", "root_folder_name", "zoom-recording-downloader"
)
GDRIVE_RETRY_DELAY = int(config("GoogleDrive", "retry_delay", "5"))
GDRIVE_MAX_RETRIES = int(config("GoogleDrive", "max_retries", "3"))
GDRIVE_FAILED_LOG = config("GoogleDrive", "failed_log", "failed-uploads.log")

# new: should we delete Zoom cloud recordings once downloaded?
DELETE_AFTER_DOWNLOAD = config("Storage", "delete_after_download", False)

ACCESS_TOKEN = None
AUTHORIZATION_HEADER = {}


def setup_google_drive():
    """Initialize Google Drive client with OAuth authentication"""
    try:
        drive_client = GoogleDriveClient(CONF.get("GoogleDrive", {}))
        if not drive_client.authenticate():
            choice = input(
                "Would you like to continue with local storage instead? (y/n): "
            )
            if choice.lower() != "y":
                system.exit(1)
            return None

        if not drive_client.initialize_root_folder():
            print(
                f"{Color.RED}### Failed to create root folder in Google Drive{Color.END}"
            )
            choice = input(
                "Would you like to continue with local storage instead? (y/n): "
            )
            if choice.lower() != "y":
                system.exit(1)
            return None

        return drive_client
    except Exception as e:
        print(f"{Color.RED}### Google Drive initialization failed: {str(e)}{Color.END}")
        choice = input("Would you like to continue with local storage instead? (y/n): ")
        if choice.lower() != "y":
            system.exit(1)
        return None


def load_access_token():
    """OAuth function, thanks to https://github.com/freelimiter"""
    url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={ACCOUNT_ID}"

    client_cred = f"{CLIENT_ID}:{CLIENT_SECRET}"
    client_cred_base64_string = base64.b64encode(client_cred.encode("utf-8")).decode(
        "utf-8"
    )

    headers = {
        "Authorization": f"Basic {client_cred_base64_string}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    response = json.loads(requests.request("POST", url, headers=headers).text)

    global ACCESS_TOKEN
    global AUTHORIZATION_HEADER

    try:
        ACCESS_TOKEN = response["access_token"]
        AUTHORIZATION_HEADER = {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

    except KeyError:
        print(f"{Color.RED}### The key 'access_token' wasn't found.{Color.END}")
        print(f"Response: {response}")
        system.exit(1)


def get_users():
    """loop through pages and return all users"""
    page_data = make_zoom_api_request("GET", API_ENDPOINT_USER_LIST)
    total_pages = int(page_data["page_count"]) + 1
    all_users = []

    for page in range(1, total_pages):
        user_data = make_zoom_api_request(
            "GET", API_ENDPOINT_USER_LIST, params={"page_number": str(page)}
        )
        users = [
            (
                user["email"],
                user["id"],
                user.get("first_name", ""),  # Use .get() with a default value
                user.get("last_name", ""),  # Use .get() with a default value
            )
            for user in user_data["users"]
        ]

        all_users.extend(users)

    return all_users


def format_filename(params):
    file_extension = params["file_extension"].lower()
    recording = params["recording"]
    recording_id = params["recording_id"]
    recording_type = params["recording_type"]

    invalid_chars_pattern = r'[<>:"/\\|?*\x00-\x1F]'
    topic = regex.sub(invalid_chars_pattern, "", recording["topic"])
    rec_type = recording_type.replace("_", " ").title()
    meeting_time_utc = parser.parse(recording["start_time"]).replace(
        tzinfo=timezone.utc
    )
    meeting_time_local = meeting_time_utc.astimezone(MEETING_TIMEZONE)
    year = meeting_time_local.strftime("%Y")
    month = meeting_time_local.strftime("%m")
    day = meeting_time_local.strftime("%d")
    meeting_time = meeting_time_local.strftime(MEETING_STRFTIME)

    filename = MEETING_FILENAME.format(**locals())
    folder = MEETING_FOLDER.format(**locals())
    return (filename, folder)


def get_downloads(recording):
    if not recording.get("recording_files"):
        raise Exception

    downloads = []
    for download in recording["recording_files"]:
        file_type = download["file_type"]
        file_extension = download["file_extension"]
        recording_id = download["id"]

        if file_type == "":
            recording_type = "incomplete"
        elif file_type != "TIMELINE":
            recording_type = download["recording_type"]
        else:
            recording_type = download["file_type"]

        # must append access token to download_url
        download_url = f"{download['download_url']}?access_token={ACCESS_TOKEN}"
        downloads.append(
            (file_type, file_extension, download_url, recording_type, recording_id)
        )

    return downloads


def get_recordings(email, page_size, rec_start_date, rec_end_date):
    # Format dates as YYYY-MM-DD for Zoom API
    start_date_formatted = rec_start_date.strftime("%Y-%m-%d")
    end_date_formatted = rec_end_date.strftime("%Y-%m-%d")

    return {
        "userId": email,
        "page_size": page_size,
        "from": start_date_formatted,
        "to": end_date_formatted,
    }


def per_delta(start, end, delta):
    """Generator used to create deltas for recording start and end dates"""
    curr = start
    while curr < end:
        yield curr, min(curr + delta, end)
        curr += delta


def list_recordings(email):
    """Start date now split into YEAR, MONTH, and DAY variables (Within 6 month range)
    then get recordings within that range
    """

    recordings = []

    for start, end in per_delta(
        RECORDING_START_DATE, RECORDING_END_DATE, timedelta(days=30)
    ):
        post_data = get_recordings(email, 300, start, end)
        print(
            f"    > Requesting recordings from {post_data['from']} to {post_data['to']}"
        )

        recordings_data = make_zoom_api_request(
            "GET", f"https://api.zoom.us/v2/users/{email}/recordings", params=post_data
        )

        if "meetings" in recordings_data:
            chunk_recordings = recordings_data["meetings"]
            print(f"    > Found {len(chunk_recordings)} recordings in this date range")
            recordings.extend(chunk_recordings)
        else:
            print(
                f"    > No recordings found in this date range. Response: {recordings_data}"
            )

    return recordings


def download_recording(download_url, email, filename, folder_name):
    dl_dir = os.sep.join([DOWNLOAD_DIRECTORY, folder_name])
    sanitized_download_dir = path_validate.sanitize_filepath(dl_dir)
    sanitized_filename = path_validate.sanitize_filename(filename)
    full_filename = os.sep.join([sanitized_download_dir, sanitized_filename])

    os.makedirs(sanitized_download_dir, exist_ok=True)

    response = requests.get(download_url, stream=True)

    # total size in bytes.
    total_size = int(response.headers.get("content-length", 0))
    block_size = 32 * 1024  # 32 Kibibytes

    # create TQDM progress bar
    prog_bar = progress_bar.tqdm(
        dynamic_ncols=True, total=total_size, unit="iB", unit_scale=True
    )
    try:
        with open(full_filename, "wb") as fd:
            for chunk in response.iter_content(block_size):
                prog_bar.update(len(chunk))
                fd.write(chunk)  # write video chunk to disk
        prog_bar.close()

        return True

    except Exception as e:
        print(
            f"{Color.RED}### The video recording with filename '{filename}' for user with email "
            f"'{email}' could not be downloaded because {Color.END}'{e}'"
        )

        return False


def load_completed_meeting_ids():
    try:
        with open(COMPLETED_MEETING_IDS_LOG, "r") as fd:
            [COMPLETED_MEETING_IDS.add(line.strip()) for line in fd]

    except FileNotFoundError:
        print(
            f"{Color.DARK_CYAN}Log file not found. Creating new log file: {Color.END}"
            f"{COMPLETED_MEETING_IDS_LOG}\n"
        )


def handle_graceful_shutdown(signal_received, frame):
    print(
        f"\n{Color.DARK_CYAN}SIGINT or CTRL-C detected. system.exiting gracefully.{Color.END}"
    )

    system.exit(0)


def delete_recording(meeting_id: str, recording_id: str):
    """Delete the cloud recording for a given meeting ID."""
    try:
        url = f"https://api.zoom.us/v2/meetings/{meeting_id}/recordings/{recording_id}"
        make_zoom_api_request("DELETE", url)
        print(
            f"{Color.GREEN}### Deleted cloud recording RecordingID {recording_id} for MeetingID {meeting_id}{Color.END}"
        )
    except requests.exceptions.HTTPError as e:
        # The wrapper raises errors, so we catch them here.
        print(
            f"{Color.RED}### Failed to delete cloud recording {recording_id} for MeetingID {meeting_id}: "
            f"{e.response.status_code} {e.response.text}{Color.END}"
        )


def log(message):
    with open(COMPLETED_MEETING_IDS_LOG, "a") as log_file:
        log_file.write(message)
        log_file.flush()


# A cache to store user recordings to avoid repeated API calls for the same user
USER_RECORDINGS_CACHE = {}


def make_zoom_api_request(method, url, params=None, data=None):
    """
    A generic wrapper for making requests to the Zoom API.
    Handles automatic token refresh and retries the request upon a 401 error.
    Supports different HTTP methods (GET, DELETE, POST, etc.).
    """
    # Create a request session to persist headers
    session = requests.Session()
    session.headers.update(AUTHORIZATION_HEADER)

    # Prepare the request arguments
    request_args = {"url": url, "params": params, "json": data}

    # First attempt
    response = session.request(method, **request_args)

    # Check if the token has expired
    if response.status_code == 401:
        print(f"    {Color.YELLOW}> Access token expired. Refreshing...{Color.END}")

        # Refresh the token and update the global header
        load_access_token()
        # Update the session header with the new token for the retry
        session.headers.update(AUTHORIZATION_HEADER)

        print(f"    {Color.YELLOW}> Retrying API request...{Color.END}")
        response = session.request(method, **request_args)

    response.raise_for_status()

    # For DELETE requests with a 204 status, there is no JSON body.
    if response.status_code == 204:
        return None

    return response.json()


def get_recordings_for_user(user_id, start_date, end_date):
    """
    Fetches all recordings for a specific user within a date range.
    Results are cached to minimize API calls.
    """
    cache_key = (
        f"{user_id}_{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}"
    )
    if cache_key in USER_RECORDINGS_CACHE:
        return USER_RECORDINGS_CACHE[cache_key]

    print(
        f"    > Fetching recordings for user '{user_id}' from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    )

    all_meetings = []
    next_page_token = ""
    while True:
        params = {
            "page_size": 300,
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date.strftime("%Y-%m-%d"),
            "next_page_token": next_page_token,
        }
        data = make_zoom_api_request(
            "GET", f"https://api.zoom.us/v2/users/{user_id}/recordings", params=params
        )

        all_meetings.extend(data.get("meetings", []))

        next_page_token = data.get("next_page_token")
        if not next_page_token:
            break

    USER_RECORDINGS_CACHE[cache_key] = all_meetings
    return all_meetings


def find_matching_recording(csv_row, user_recordings):
    """
    Finds a recording from the API response that matches the data in a CSV row.
    Matching is based on topic and start time, now with proper timezone handling and
    topic string normalization.
    """
    csv_start_time_utc = csv_row.get("Start Time UTC")
    if pd.isna(csv_start_time_utc):
        return None

    csv_topic = csv_row.get("Topic")

    # --- FIX: Normalize the CSV topic string ---
    # This checks if the topic string from the CSV starts with a single quote
    # followed by a dash, which is the pattern you identified.
    # If it does, we strip the leading single quote before comparison.
    if csv_topic and csv_topic.startswith("'-"):
        # Slicing the string from the second character onwards
        csv_topic = csv_topic[1:]
        print(f"    > Normalized topic from CSV: '{csv_topic}'")

    for recording in user_recordings:
        api_start_time_utc = parser.parse(recording["start_time"])
        time_difference = abs(csv_start_time_utc - api_start_time_utc)

        # Match if the (now normalized) topics are the same and the start time
        # is within a 5-minute tolerance.
        if recording["topic"] == csv_topic and time_difference < timedelta(minutes=5):
            print(
                f"    > Found a matching recording in Zoom API. Topic: '{recording['topic']}'"
            )
            return recording

    return None


# ################################################################
# #                        MAIN                                  #
# ################################################################


def main():
    """
    Main function to run the downloader. Now driven by command-line arguments
    and a CSV file for large-scale, batch-based migration.
    """
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(
        description="Zoom Recording Downloader for large-scale migration.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "csv_file",
        type=str,
        help="Path to the CSV file containing the list of recordings.",
    )
    parser.add_argument(
        "--batch-size-gb",
        type=int,
        default=500,
        help="Maximum size of recordings to process in a single run (in GB).\n"
        "Defaults to 500 to stay under Google Drive's 750GB daily limit.",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="progress_log.json",
        help="Path to the progress log file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the process without downloading or uploading files.\n"
        "Useful for checking which recordings will be processed.",
    )
    args = parser.parse_args()

    # clear the screen buffer
    os.system("cls" if os.name == "nt" else "clear")

    # show the logo
    print(
        f"""
        {Color.DARK_CYAN}
        {Color.BOLD}
                             ,*****************.
                          *************************
                        *****************************
                      *********************************
                      ******               ******* ******
                     *******                .**    ******
                     *******                       ******/
                     *******                       /******
                     ///////                 //    //////
                     ///////*              ./////.//////
                     ////////////////////////////////*
                       /////////////////////////////
                          /////////////////////////
                             ,/////////////////

                        Zoom Recording Downloader

                        V{APP_VERSION} - Batch Migration Mode

        {Color.END}
    """
    )

    if args.dry_run:
        print(f"{Color.YELLOW}*** DRY RUN MODE ENABLED ***{Color.END}")
        print(f"{Color.YELLOW}No files will be downloaded or uploaded.{Color.END}\n")

    # --- Setup ---
    progress = ProgressLog(args.log_file)
    print(f"{Color.BOLD}Starting Run #{progress.log_data['run_counter']}{Color.END}\n")
    load_access_token()

    # --- Google Drive Setup ---
    global GDRIVE_ENABLED  # Declare intention to modify the global variable
    GDRIVE_ENABLED = False
    drive_service = None
    if not args.dry_run:
        print(f"{Color.BOLD}Setting up Google Drive...{Color.END}")
        drive_service = setup_google_drive()
        if not drive_service:
            print(f"{Color.RED}Failed to setup Google Drive. Exiting.{Color.END}")
            system.exit(1)
        GDRIVE_ENABLED = True
        print(
            f"{Color.GREEN}✓ Google Drive setup complete. Uploads are enabled.{Color.END}"
        )

    # --- Load and Prepare CSV Data ---
    try:
        print(f"{Color.BOLD}Loading CSV file: {args.csv_file}{Color.END}")
        df = pd.read_csv(args.csv_file)
        # Standardize column names
        df.rename(columns={"File Size (MB)": "file_size_mb", "ID": "id"}, inplace=True)
        # Create the unique hash for each row
        df["row_hash"] = df.apply(create_row_hash, axis=1)

        # 1. Parse the local time from the CSV as a naive datetime object.
        df["Start Time"] = pd.to_datetime(
            df["Start Time"], format="%b %d, %Y %I:%M:%S %p", errors="coerce"
        )

        # 2. Localize the naive datetime to a specific timezone (e.g., 'America/Sao_Paulo').
        #    This tells pandas the original timezone of the data.
        #    Note: This assumes all times in the CSV are from this timezone.
        #    Using .dt accessor for Series operations.
        df["Start Time Localized"] = df["Start Time"].dt.tz_localize(
            "America/Sao_Paulo", ambiguous="infer"
        )

        # 3. Convert the localized time to UTC and store it in a new column.
        #    This is the column we will use for comparison with the API data.
        df["Start Time UTC"] = df["Start Time Localized"].dt.tz_convert("UTC")

        # Sort by the original start time to process chronologically
        df.sort_values(by="Start Time", inplace=True)
        print(
            f"==> Found {len(df)} total recordings in the CSV. Sorted by start date.\n"
        )
    except Exception as e:
        print(f"{Color.RED}Error reading or processing CSV file: {e}{Color.END}")
        system.exit(1)

    # --- Main Processing Loop ---
    # Get the current date in UTC to compare with the last run date.
    today_utc = datetime.now(timezone.utc).date()
    last_run_date = progress.get_last_run_date()

    # This is the new, corrected batch handling logic.
    # If the script was last run on a day before today, it's a new day.
    # Reset the batch counter to start fresh for the day.
    if last_run_date and last_run_date < today_utc:
        print(
            f"{Color.YELLOW}Last run was on {last_run_date}. This is a new day.{Color.END}"
        )
        print(f"{Color.YELLOW}Resetting daily batch counter to 0.{Color.END}\n")
        progress.reset_batch_size()

    try:
        for index, row in df.iterrows():
            print(
                f"\n==> Checking Meeting from {row['Start Time'].strftime('%Y-%m-%d %H:%M')} | Host: {row['Host']}"
            )
            print(f"    Topic: {row['Topic']}")

            if args.dry_run:
                print(
                    f"    > [DRY RUN] Would check this meeting for unprocessed files."
                )
                continue
            try:
                # Find the matching recording session from the Zoom API
                start_date = row["Start Time UTC"].date() - timedelta(days=1)
                end_date = row["Start Time UTC"].date() + timedelta(days=1)
                user_recordings = get_recordings_for_user(
                    row["Host"], start_date, end_date
                )
                matching_recording = find_matching_recording(row, user_recordings)

                if not matching_recording:
                    print(
                        f"    {Color.YELLOW}> Warning: Could not find a matching recording on Zoom. Skipping.{Color.END}"
                    )
                    continue

                # Get all downloadable files for this recording session
                downloads = get_downloads(matching_recording)

                # Loop through each individual file and check its status
                for (
                    file_type,
                    file_extension,
                    download_url,
                    recording_type,
                    recording_file_id,  # This is the unique ID for the individual file
                ) in downloads:

                    # Skip this file if it's already completed
                    if progress.is_completed(recording_file_id):
                        continue

                    # Get file size and check against batch limit
                    # We need to find the file_size from the 'downloads' list, which requires a small lookup
                    file_info = next(
                        (
                            f
                            for f in matching_recording["recording_files"]
                            if f["id"] == recording_file_id
                        ),
                        None,
                    )
                    if not file_info:
                        continue

                    file_size_bytes = file_info.get("file_size", 0)
                    file_size_gb = file_size_bytes / (1024 * 1024 * 1024)

                    if progress.get_batch_size() + file_size_gb > args.batch_size_gb:
                        print(f"\n{Color.GREEN}{'='*60}{Color.END}")
                        print(
                            f"{Color.GREEN}Daily batch limit of {args.batch_size_gb} GB reached. Halting.{Color.END}"
                        )
                        print(
                            f"{Color.GREEN}Current batch size: {progress.get_batch_size():.2f} GB. Re-run to continue.{Color.END}"
                        )
                        print(f"{Color.GREEN}{'='*60}{Color.END}")
                        # Use a more robust way to exit the entire script
                        raise SystemExit("Batch limit reached")

                    # Process the file
                    params = {
                        "file_extension": file_extension,
                        "recording": matching_recording,
                        "recording_id": recording_file_id,
                        "recording_type": recording_type,
                    }
                    filename, folder_name = format_filename(params)

                    print(
                        f"    > Processing file: {filename} | Size: {(file_size_bytes / (1024*1024)):.2f} MB"
                    )

                    sanitized_download_dir = path_validate.sanitize_filepath(
                        os.sep.join([DOWNLOAD_DIRECTORY, folder_name])
                    )
                    sanitized_filename = path_validate.sanitize_filename(filename)
                    full_filename = os.sep.join(
                        [sanitized_download_dir, sanitized_filename]
                    )

                    if download_recording(
                        download_url,
                        matching_recording.get("host_email", "N/A"),
                        filename,
                        folder_name,
                    ):
                        if GDRIVE_ENABLED and drive_service:
                            print(f"      > Uploading to Google Drive...")
                            success = drive_service.upload_file(
                                full_filename, folder_name, sanitized_filename
                            )
                            if success and os.path.exists(full_filename):
                                os.remove(full_filename)
                                if not os.listdir(sanitized_download_dir):
                                    os.rmdir(sanitized_download_dir)

                        # Log this specific file as complete
                        progress.log_completed(recording_file_id, file_size_gb)
                        print(
                            f"      {Color.GREEN}> Successfully processed and logged file ID: {recording_file_id}{Color.END}"
                        )
                        print(
                            f"      > Current batch size: {progress.get_batch_size():.2f} / {args.batch_size_gb} GB"
                        )

            except SystemExit as e:
                # Catch the SystemExit to stop processing gracefully
                raise e  # Re-raise to exit the script
            except Exception as e:
                print(
                    f"{Color.RED}### An error occurred while processing meeting: {e}{Color.END}"
                )
                print(
                    f"{Color.RED}### Skipping this meeting for now. It will be retried on the next run.{Color.END}"
                )
                continue

    except SystemExit as e:
        print(f"\n{e}")
    finally:
        print("\nSaving final progress log...")
        progress.save()
        print("Done.")


if __name__ == "__main__":
    # tell Python to shutdown gracefully when SIGINT is received
    signal.signal(signal.SIGINT, handle_graceful_shutdown)

    main()
