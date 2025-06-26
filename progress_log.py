import json
import os
from datetime import datetime, timezone
import hashlib


class ProgressLog:
    def __init__(self, log_file="progress_log.json"):
        """
        Initializes the ProgressLog.
        Loads the log file and increments the run counter.
        """
        self.log_file = log_file
        self.log_data = self._load_log()
        self.log_data["run_counter"] += 1

    def _load_log(self):
        """Loads the log file or creates a new one if it doesn't exist."""
        if os.path.exists(self.log_file):
            with open(self.log_file, "r") as f:
                try:
                    data = json.load(f)
                    data.setdefault("run_counter", 0)
                    data.setdefault("total_completed_recordings", {})
                    data.setdefault("daily_completed_recordings", {})
                    data.setdefault("total_completed_gb", 0.0)
                    return data
                except json.JSONDecodeError:
                    return self._create_new_log()
        else:
            return self._create_new_log()

    def _create_new_log(self):
        """Creates a new, empty log structure with the new data format."""
        return {
            "last_run_utc": None,
            "total_completed_recordings": {},
            "daily_completed_recordings": {},
            "run_counter": 0,
            "total_completed_gb": 0.0,
        }

    def save(self):
        """Explicitly saves the current log data, updating the timestamp."""
        self.log_data["last_run_utc"] = datetime.now(timezone.utc).isoformat()
        self.log_data["total_completed_gb"] = sum(
            self.log_data["total_completed_recordings"].values()
        )
        with open(self.log_file, "w") as f:
            json.dump(self.log_data, f, indent=4)

    def is_completed(self, recording_file_id):
        """
        Checks if a specific recording FILE ID has already been logged as completed.

        Args:
            recording_file_id (str): The unique ID of the individual file (not the meeting).

        Returns:
            bool: True if the file ID is in the completed list, False otherwise.
        """
        return str(recording_file_id) in self.log_data["total_completed_recordings"]

    def log_completed(self, recording_file_id, file_size_gb):
        """
        Logs an individual file as completed and stores its size.

        Args:
            recording_file_id (str): The unique ID of the file.
            file_size_gb (float): The size of the file in GB.
        """
        if not self.is_completed(recording_file_id):
            self.log_data["total_completed_recordings"][str(recording_file_id)] = file_size_gb
            self.log_data["daily_completed_recordings"][str(recording_file_id)] = file_size_gb
            self.save()

    def get_batch_size(self):
        """
        Calculates and returns the current batch size by summing the sizes of all
        individually completed files.
        """
        return sum(self.log_data["daily_completed_recordings"].values())

    def get_last_run_date(self):
        """Gets the date of the last run from the log."""
        last_run_str = self.log_data.get("last_run_utc")
        if last_run_str:
            return datetime.fromisoformat(last_run_str).date()
        return None

    def reset_batch_size(self):
        """
        Resets the daily batch by clearing the dictionary of daily completed recordings.
        This should be used when starting a new day's batch.
        """
        self.log_data["daily_completed_recordings"] = {}
        self.save()


def create_row_hash(row):
    """Creates a unique and stable hash for a given CSV row."""
    # Using a combination of fields that should uniquely identify a recording session
    # We use .get() to avoid errors if a column is missing for some reason.
    unique_string = (
        f"{row.get('Host', '')}-{row.get('Topic', '')}-{row.get('id', '')}-"
        f"{row.get('Start Time', '')}-{row.get('File Count', '')}"
    )
    return hashlib.md5(unique_string.encode("utf-8")).hexdigest()
