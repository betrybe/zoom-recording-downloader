from setuptools import setup

# Read from requirements.txt
with open("requirements.txt") as f:
    required = f.read().splitlines()

setup(
    name='zoom-recording-downloader',
    version='0.1',
    py_modules=['zoom_recording_downloader', 'google_drive_client'],  # ✅ Include both files
    install_requires=required,
    entry_points={
        'console_scripts': [
            'zoom-recording-downloader=zoom_recording_downloader:main',
        ],
    },
)
