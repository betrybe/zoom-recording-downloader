import argparse
import sys as system

import pandas as pd
import requests
from tqdm import tqdm

# --- Reused components from the main downloader ---
from zoom_recording_downloader import (
    Color,
    load_access_token,
    make_zoom_api_request,
)


def delete_meeting_recordings(meeting_uuid):
    """
    Deletes an entire meeting's recording set from Zoom cloud storage.

    Args:
        meeting_uuid (str): The UUID of the meeting to delete.

    Returns:
        bool: True if deletion was successful (or a 404 not found), False otherwise.
    """
    if not meeting_uuid or pd.isna(meeting_uuid):
        print(
            f"    {Color.YELLOW}Skipping deletion due to missing meeting UUID.{Color.END}"
        )
        return False, "SKIPPED_NO_UUID"

    # Note: The 'action=trash' parameter can be used to move to trash instead of permanent deletion.
    # For this script, we perform a permanent deletion as requested.
    url = f"https://api.zoom.us/v2/meetings/{meeting_uuid}/recordings"
    try:
        # Use the wrapper for the DELETE request
        make_zoom_api_request("DELETE", url)
        return True, "DELETED"
    except requests.exceptions.HTTPError as e:
        # Check if the error is a 404 Not Found, which we treat as a success.
        if e.response.status_code == 404:
            return True, "ALREADY_DELETED_OR_NOT_FOUND"

        # Any other error is a failure.
        print(
            f"    {Color.RED}API Error: {e.response.status_code} - {e.response.text}{Color.END}"
        )
        return False, f"ERROR_{e.response.status_code}"


def main():
    parser = argparse.ArgumentParser(
        description="Deletes Zoom recordings based on a verification report.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "report_file", type=str, help="Path to the 'verification_report.csv' file."
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="deletion_report.csv",
        help="Path to write the output deletion report CSV file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the process without actually deleting any files from Zoom.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass the interactive confirmation prompt. Use with caution.",
    )
    args = parser.parse_args()

    print(f"{Color.BOLD}--- Starting Zoom Cloud Recording Deletion ---{Color.END}\n")

    # --- Load Verification Report ---
    try:
        print(f"{Color.BOLD}Loading verification report: {args.report_file}{Color.END}")
        df = pd.read_csv(args.report_file)
        # Filter for only completely migrated recordings
        to_delete_df = df[df["verification_status"] == "COMPLETE"].copy()
        if to_delete_df.empty:
            print(
                "No recordings marked as 'COMPLETE' found. Nothing to delete. Exiting."
            )
            system.exit(0)
    except (FileNotFoundError, KeyError) as e:
        print(
            f"{Color.RED}Error: Could not read the report file or find required columns.{Color.END}"
        )
        print(
            f"{Color.RED}Please ensure '{args.report_file}' is a valid verification report. Details: {e}{Color.END}"
        )
        system.exit(1)

    print(
        f"Found {len(to_delete_df)} recordings marked as 'COMPLETE' and eligible for deletion.\n"
    )

    # --- Safety Confirmation ---
    if not args.dry_run and not args.force:
        confirm = input(
            f"{Color.YELLOW}You are about to permanently delete {len(to_delete_df)} recording(s) from Zoom Cloud.\n"
            f"This action cannot be undone.\n"
            f"Type 'DELETE' to confirm: {Color.END}"
        )
        if confirm != "DELETE":
            print("Confirmation not received. Aborting.")
            system.exit(0)
    elif args.dry_run:
        print(f"{Color.YELLOW}*** DRY RUN MODE ENABLED ***{Color.END}")
        print(f"{Color.YELLOW}No recordings will be deleted.{Color.END}\n")

    # --- Setup and Deletion Loop ---
    load_access_token()
    deletion_statuses = []

    for index, row in tqdm(
        to_delete_df.iterrows(), total=to_delete_df.shape[0], desc="Deleting Recordings"
    ):
        status = "SKIPPED"
        if not args.dry_run:
            _, status = delete_meeting_recordings(row["zoom_meeting_uuid"])
        else:
            status = "DRY_RUN_SKIPPED"
        deletion_statuses.append(status)

    to_delete_df["deletion_status"] = deletion_statuses

    # --- Save Report ---
    print(
        f"\n{Color.BOLD}Deletion process complete. Saving report to {args.output_csv}...{Color.END}"
    )
    to_delete_df.to_csv(args.output_csv, index=False)
    print(f"{Color.GREEN}✓ Deletion report saved successfully.{Color.END}")


if __name__ == "__main__":
    main()
