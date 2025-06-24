# ⚡️ zoom-recording-downloader ⚡️ 
## ☁️ Now with Google Drive support ☁️

[![Python 3.11](https://img.shields.io/badge/python-3.11%20%2B-blue.svg)](https://www.python.org/) [![License](https://img.shields.io/badge/license-MIT-brown.svg)](https://raw.githubusercontent.com/ricardorodrigues-ca/zoom-recording-downloader/master/LICENSE)

**Zoom Recording Downloader** is a cross-platform Python app that utilizes Zoom's API (v2) to download and organize all cloud recordings from a Zoom Business account to local storage or Google Drive.

## Screenshot
![screenshot](screenshot.png)

# Installation

_Attention: You will need [Python 3.11](https://www.python.org/downloads/) or greater_

```sh
$ git clone https://github.com/ricardorodrigues-ca/zoom-recording-downloader
$ cd zoom-recording-downloader
$ pip3 install -r requirements.txt
```

# Install via pipx
1. Install [pipx](https://pypa.github.io/pipx/installation/) if you haven't already
2. Run pipx.sh to install the script globally
```sh pipx.sh```
4. Run ```zoom-recording-downloader``` from anywhere in your terminal

> To uninstall via pipx run ```pipx uninstall zoom-recording-downloader```

# Install and Run via python venv
1. Run ```zoom-recording-downloader.sh``` to create a virtual environment and install the required packages
2. Then run ```zoom-recording-downloader.sh``` to run the script

> The shell script will create a virtual environment in the current directory and install the required packages. It will also activate the virtual environment and run the script. You can run the script again by running ```zoom-recording-downloader.sh``` again.

# Usage

_Attention: You will need a [Zoom Developer account](https://marketplace.zoom.us/) in order to create a [Server-to-Server OAuth app](https://developers.zoom.us/docs/internal-apps) with the required credentials_

## 1. Create a [server-to-server OAuth app](https://marketplace.zoom.us/user/build)
   - Go to [Zoom Marketplace](https://marketplace.zoom.us/)
   - Sign in with your Zoom account
   - Click on "Develop" > "Build App"
   - Choose "Server-to-Server OAuth" and click "Create"
   - Fill in the required information (app name, company name, etc.)
   - Click "Create" to create the app
Set up your app and collect your credentials (`Account ID`, `Client ID`, `Client Secret`). For questions on this, [reference the docs](https://developers.zoom.us/docs/internal-apps/create/) on creating a server-to-server app. Make sure you activate the app. 

Follow Zoom's [set up documentation](https://marketplace.zoom.us/docs/guides/build/server-to-server-oauth-app/) or [this video](https://www.youtube.com/watch?v=OkBE7CHVzho) for a more complete walk through.

## 2. Add the necessary scopes to your app. 
In your app's _Scopes_ tab, add the following scopes:

   > `cloud_recording:read:list_user_recordings:admin`, `user:read:user:admin`, `user:read:list_users:admin`.

## 3. Add Delete Scopes
If you want to delete the downloaded recordings from Zoom's cloud, add the following scopes:

   > `cloud_recording:delete:recording_file, cloud_recording:delete:recording_file:admin`

## 4. Create configuration file
Copy **zoom-recording-downloader.conf.template** to a new file named *zoom-recording-downloader.conf** and fill in your Server-to-Server OAuth app credentials:
```
      {
	      "OAuth": {
		      "account_id": "<ACCOUNT_ID>",
		      "client_id": "<CLIENT_ID>",
		      "client_secret": "<CLIENT_SECRET>"
	      }
      }
```
# Optional Configurations
## Storage Configurations
- Specify the base **download_dir** under which the recordings will be downloaded (default is 'downloads')
- Specify the **completed_log** log file that will store the ID's of downloaded recordings (default is 'completed-downloads.log')

```
      {
              "Storage": {
                      "download_dir": "downloads",
                      "completed_log": "completed-downloads.log"
              }
      }
```

## Recording Configurations
- Specify the **start_date** from which to start downloading meetings (default is Jan 1 of this year)
- Specify the **end_date** at which to stop downloading meetings (default is today)
- Dates are specified as YYYY-MM-DD

```
      {
              "Recordings": {
                      "start_date": "2024-01-01",
                      "end_date": "2024-12-31"
              }
      }
```

- If you don't specify the **start_date** you can specify the year, month, and day seperately
- Specify the day of the month to start as **start_day** (default is 1)
- Specify the month to start as **start_month** (default is 1)
- Specify the year to start as **start_year** (default is this year)

```
      {
              "Recordings": {
                      "start_year": "2024",
                      "start_month": "1",
                      "start_day": "1"
              }
      }
```

- Specify the timezone for the saved meeting times saved in the filenames (default is 'UTC')
- You can use any timezone supported by [ZoneInfo](https://docs.python.org/3/library/zoneinfo.html)
- Specify the time format for the saved meeting times in the filenames (default is '%Y.%m.%d - %I.%M %p UTC')
- You can use any of the [strftime format codes](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes) supported by datetime

```
      {
              "Recordings": {
                      "timezone": "America/New_York",
                      "strftime": "%Y.%m.%d-%H.%M%z"
              }
      }
```

- Specify the format for the filenames of saved meetings (default is '{meeting_time} - {topic} - {rec_type} - {recording_id}.{file_extension}')
- Specify the format for the folder name (under the download folder) for saved meetings (default is '{topic} - {meeting_time}')

```
      {
              "Recordings": {
                      "filename": "{meeting_time}-{topic}-{rec_type}-{recording_id}.{file_extension}",
                      "folder": "{year}/{month}/{meeting_time}-{topic}"
              }
      }
```

## File and Folder Format Placeholders
The following placeholders are available for the **filename** and **folder** formats:
  - **{file_extension}** is the lowercase version of the file extension
  - **{meeting_time}** is the time in the format of **strftime** and **timezone**
  - **{day}** is the day from **meeting_time**
  - **{month}** is the month from **meeting_time**
  - **{year}** is the year from **meeting_time**
  - **{recording_id}** is the recording id from zoom
  - **{rec_type}** is the type of the recording
  - **{topic}** is the title of the zoom meeting

# Google Drive Setup (Optional)

To enable Google Drive upload support:

## 1. Create a Google Cloud Project:
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project or select an existing one
   - Enable the Google Drive API for your project ([Click to enable ↗](https://console.cloud.google.com/flows/enableapi?apiid=drive.googleapis.com))

## 2. Create OAuth 2.0 credentials:
	- In Cloud Console, go to "APIs & Services" > "Credentials"
	- Click "Create Credentials" > "OAuth client ID"
	- Choose "Desktop application" as the application type
	- Give it a name (e.g., "Zoom Recording Downloader")
	- Download the JSON file and save as `client_secrets.json` in the script directory

## 3. Configure OAuth consent screen:
	- Go to "OAuth consent screen"
	- Select "External" user type
	- Set application name to "Zoom Recording Downloader"
	- Add required scopes:
		- https://www.googleapis.com/auth/drive.file
		- https://www.googleapis.com/auth/drive.metadata
		- https://www.googleapis.com/auth/drive.appdata

## 4. Update your config:
	```json
	{
		"GoogleDrive": {
			"client_secrets_file": "client_secrets.json",
			"token_file": "token.json",
			"root_folder_name": "zoom-recording-downloader",
			"retry_delay": 5,
			"max_retries": 3,
			"failed_log": "failed-uploads.log"
        }
	}
	```

**Important:** Keep your OAuth credentials file secure and never commit it to version control.
Consider adding `client_secrets.json` to your .gitignore file.

Note: When you first run the script with Google Drive enabled, it will open your default browser for authentication. After authorizing the application, the token will be saved locally and reused for future runs.

## 5. Run command:

```$ python zoom-recording-downloader.py```

When prompted, choose your preferred storage method:
1. Local Storage - Saves recordings to your local machine
2. Google Drive - Uploads recordings to your Google Drive account

Note: For Google Drive uploads, files are temporarily downloaded to local storage before being uploaded, then automatically deleted after successful upload.

-----
-----

## Migration Usage (Batch Processing)

This script is designed for large-scale migrations and is intended to be run on a server (e.g., an AWS EC2 instance) where it can operate for extended periods.

It expects a CSV file containing Zoom recording metadata, which can be generated from the Zoom API or exported from the Zoom web interface. The script will read this file, download the recordings, and upload them to Google Drive in batches.

A sample file is provided in the repository as `zoomus_recordings.csv`. You can use this as a template for your own recordings file.

### 1\. Initial Setup

Before the first run, you need to prepare your environment.

#### a. Local Machine Setup (One-Time Only)

1.  **Authenticate with Google Drive:** Run the script on your local machine one time to perform the initial, interactive authentication with Google.
    ```bash
    python zoom_recording_downloader.py path/to/your/recordings.csv
    ```
2.  Follow the browser-based login prompts to authorize the application. This will create a `token.json` file in your project directory. This file stores your credentials securely for non-interactive use on the server.

#### b. Server (EC2) Setup

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/ricardorodrigues-ca/zoom-recording-downloader
    cd zoom-recording-downloader
    git checkout download-from-file
    ```
2.  **Install Dependencies:** Ensure Python 3 is installed, then install the required packages.
    ```bash
    pip install -r requirements.txt
    ```
3.  **Upload Necessary Files:** Transfer the following files to the script's directory on your server:
      * `client_secrets.json` (Your Google application credentials)
      * `token.json` (The token file you generated locally)
      * The CSV file containing the list of recordings to migrate (e.g., `zoomus_recordings.csv`).

### 2\. Running the Migration

It is highly recommended to use a terminal multiplexer like `screen` or `tmux` to ensure the script continues to run even if your connection to the server is interrupted.

1.  **Start a `screen` Session:**

    ```bash
    # Start a new session named 'migration'
    screen -S migration
    ```

2.  **Execute the Script:** Run the script, providing the path to your recordings CSV file.

    ```bash
    python zoom_recording_downloader.py path/to/your/zoomus_recordings.csv
    ```

3.  **Detach and Monitor:** You can safely detach from the `screen` session by pressing `Ctrl+A` followed by `D`. The script will continue running in the background. To re-attach to the session later and check the progress, use `screen -r migration`.

### 3\. Daily Execution and Batching

The script is designed to be run daily until the migration is complete.

  * It will automatically process recordings in batches up to the daily limit (default 700GB) and then stop.
  * The `progress_log.json` file keeps track of all completed recordings.
  * The next day, simply re-run the **exact same command**. The script will read the log, skip the recordings that have already been uploaded, and start a new batch from where it left off.

### 4\. Optional Command-Line Arguments

You can customize the script's behavior with these optional arguments:

  * **Dry Run:** Simulate the entire process without downloading or uploading any files. This is useful for verifying your configuration and seeing which recordings will be processed in the next batch.

    ```bash
    python zoom_recording_downloader.py path/to/your/zoomus_recordings.csv --dry-run
    ```

  * **Custom Batch Size:** Set a different daily upload limit in Gigabytes.

    ```bash
    # Set a batch size of 50 GB for testing
    python zoom_recording_downloader.py path/to/your/zoomus_recordings.csv --batch-size-gb 50
    ```

  * **Custom Log File:** Specify a different name or path for the progress log file.

    ```bash
    python zoom_recording_downloader.py path/to/your/zoomus_recordings.csv --log-file my_migration_log.json
    ```
