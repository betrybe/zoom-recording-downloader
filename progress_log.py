import json
import os
from datetime import datetime, timezone
import hashlib


class ProgressLog:
    def __init__(self, log_file="progress_log.json"):
        self.log_file = log_file
        self.log_data = self._load_log()
        self.log_data["run_counter"] += 1

    def _load_log(self):
        if os.path.exists(self.log_file):
            with open(self.log_file, "r") as f:
                try:
                    data = json.load(f)
                    data.setdefault("run_counter", 0)
                    return data
                except json.JSONDecodeError:
                    return self._create_new_log()
        else:
            return self._create_new_log()

    def _create_new_log(self):
        return {
            "last_run_utc": None,
            "completed_row_hashes": [],
            "current_batch_size_gb": 0,
            "run_counter": 0,
        }

    def save(self):
        """
        Explicitly saves the current log data to the file, updating the timestamp.
        This should be called at the end of the script's execution.
        """
        self.log_data["last_run_utc"] = datetime.now(timezone.utc).isoformat()
        with open(self.log_file, "w") as f:
            json.dump(self.log_data, f, indent=4)

    def is_completed(self, row_hash):
        """Checks if a row hash has already been logged as completed."""
        return row_hash in self.log_data["completed_row_hashes"]

    def log_completed(self, row_hash, file_size_gb):
        """Logs a row as completed and updates the batch size."""
        if not self.is_completed(row_hash):
            self.log_data["completed_row_hashes"].append(row_hash)
            self.log_data["current_batch_size_gb"] += file_size_gb
            self.save()

    def get_last_run_date(self):
        """
        Gets the date of the last run from the log.

        Returns:
            datetime.date or None: The date of the last run, or None if never run.
        """
        last_run_str = self.log_data.get("last_run_utc")
        if last_run_str:
            return datetime.fromisoformat(last_run_str).date()
        return None

    def get_batch_size(self):
        """Gets the current size of the processed batch in GB."""
        return self.log_data["current_batch_size_gb"]

    def reset_batch_size(self):
        """Resets the batch size counter to 0 for a new day's run."""
        self.log_data["current_batch_size_gb"] = 0
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
