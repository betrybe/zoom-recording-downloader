import argparse
import os
import sys as system
from datetime import datetime, timedelta

import pandas as pd
import dateutil.parser as parser
from tqdm import tqdm

# --- Reused components from zoom_recording_downloader.py ---
# Note: In a larger project, these would be moved to a shared utility file.
from zoom_recording_downloader import (
    Color,
    config,
    load_access_token,
    setup_google_drive,
    get_recordings_for_user,
    find_matching_recording,
    format_filename,
)
from google_drive_client import GoogleDriveClient


def main():
    """
    Main function for the verification script. It compares Zoom recordings
    against files in Google Drive and generates a report.
    """
    parser = argparse.ArgumentParser(
        description="Verifies the Zoom to Google Drive migration.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "csv_file",
        type=str,
        help="Path to the original CSV file used for the migration.",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="verification_report.csv",
        help="Path to write the output verification report CSV file.",
    )
    args = parser.parse_args()

    print(f"{Color.BOLD}--- Starting Migration Verification ---{Color.END}\n")

    # --- Setup ---
    load_access_token()
    print(f"{Color.BOLD}Setting up Google Drive connection...{Color.END}")
    drive_service = setup_google_drive()
    if not drive_service:
        print(f"{Color.RED}Failed to setup Google Drive. Exiting.{Color.END}")
        system.exit(1)
    print(f"{Color.GREEN}✓ Google Drive setup complete.{Color.END}\n")

    # --- Load and Prepare CSV Data ---
    try:
        print(f"{Color.BOLD}Loading and preparing CSV: {args.csv_file}{Color.END}")
        df = pd.read_csv(args.csv_file)
        df.rename(columns={"ID": "id"}, inplace=True)
        df["Start Time"] = pd.to_datetime(
            df["Start Time"], format="%b %d, %Y %I:%M:%S %p", errors="coerce"
        )
        df["Start Time Localized"] = df["Start Time"].dt.tz_localize(
            "America/Sao_Paulo", ambiguous="infer"
        )
        df["Start Time UTC"] = df["Start Time Localized"].dt.tz_convert("UTC")
        print(f"==> Found {len(df)} total recordings to verify.\n")
    except Exception as e:
        print(f"{Color.RED}Error reading or processing CSV file: {e}{Color.END}")
        system.exit(1)

    verification_results = []

    # Use tqdm for a progress bar during the long verification process
    for index, row in tqdm(
        df.iterrows(), total=df.shape[0], desc="Verifying Recordings"
    ):
        row_dict = row.to_dict()
        try:
            start_date = row["Start Time UTC"].date() - timedelta(days=1)
            end_date = row["Start Time UTC"].date() + timedelta(days=1)

            user_recordings = get_recordings_for_user(row["Host"], start_date, end_date)
            matching_recording = find_matching_recording(row, user_recordings)

            if not matching_recording:
                row_dict["verification_status"] = "NO_MATCH_ON_ZOOM"
                row_dict["zoom_file_count"] = 0
                row_dict["drive_file_count"] = 0
                row_dict["zoom_meeting_uuid"] = None
                verification_results.append(row_dict)
                continue

            # Get the definitive list of downloadable files from the Zoom API
            row_dict["zoom_meeting_uuid"] = matching_recording.get("uuid")
            zoom_files = matching_recording.get("recording_files", [])
            zoom_file_count = len(zoom_files)
            drive_file_count = 0

            # For each file listed on Zoom, check if it exists in Google Drive
            for file_info in zoom_files:
                params = {
                    "file_extension": file_info["file_extension"],
                    "recording": matching_recording,
                    "recording_id": file_info["id"],
                    "recording_type": file_info["recording_type"],
                }
                expected_filename, expected_folder_path = format_filename(params)

                # Use the new find_file method
                if drive_service.find_file(expected_folder_path, expected_filename):
                    drive_file_count += 1

            # Determine the final status for the row
            row_dict["zoom_file_count"] = zoom_file_count
            row_dict["drive_file_count"] = drive_file_count
            if zoom_file_count == 0:
                row_dict["verification_status"] = "NO_FILES_ON_ZOOM"
            elif zoom_file_count == drive_file_count:
                row_dict["verification_status"] = "COMPLETE"
            else:
                row_dict["verification_status"] = "INCOMPLETE"

        except Exception as e:
            row_dict["verification_status"] = f"ERROR: {str(e)}"
            row_dict["zoom_meeting_uuid"] = None
            row_dict["zoom_file_count"] = -1
            row_dict["drive_file_count"] = -1

        verification_results.append(row_dict)

    # --- Save Report ---
    print(
        f"\n{Color.BOLD}Verification complete. Saving report to {args.output_csv}...{Color.END}"
    )
    report_df = pd.DataFrame(verification_results)
    report_df.to_csv(args.output_csv, index=False)
    print(f"{Color.GREEN}✓ Report saved successfully.{Color.END}")


if __name__ == "__main__":
    main()
