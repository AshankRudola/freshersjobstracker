Freshers Jobs Tracker - Windows Setup
Built by Ashank Rudola
=========================

This folder contains the Freshers Jobs Tracker application. It is completely standalone and does not require Python to be installed.

Prerequisites:
-------------
- You MUST have Google Chrome installed on your computer.
- Use the tracker responsibily. It has inbuilt mechanisms to ensure that scraping is done by mimicking human behaviour, but too many requests can trigger IP ban/restrictions.
- Patience. To keep platforms from detecting the bot and blocking your IP, the code has built-in pauses. After clicking "Next Page," the script intentionally does absolutely nothing for 4 to 7 seconds to mimic a human
reading the screen.  

How to Run:
----------
1. Extract this entire folder (Freshers_Jobs_Tracker_Windows) somewhere on your computer (e.g., Desktop or Documents). DO NOT just drag the .exe out of the folder.
2. Double-click "Freshers Jobs Tracker.exe" to start the server.
3. A small window will appear saying "Freshers Jobs Tracker is Running".
4. Your default web browser will automatically open to http://127.0.0.1:5001.
5. If the browser doesn't open automatically, click the "Open in Browser" button in the small window.

How to Use:
----------
- The app allows you to scrape job postings from various platforms (LinkedIn, Naukri, Indeed, Shine, Unstop).
- Go to "Settings" (gear icon) to configure your keywords, locations, and enable/disable specific scrapers.
- Click "Refresh/Scrape" to start searching for new jobs. A progress modal will show you what is happening.

Troubleshooting:
---------------
- If the browser doesn't open or shows an error, ensure the small window says "Status: RUNNING".
- Windows Defender or your antivirus might show a warning like "Windows protected your PC" because this is an unrecognized app. Click "More info" and then "Run anyway".
- Ensure the "templates" folder and "config.yaml" file are in the same directory as "Freshers Jobs Tracker.exe".

How to Stop:
-----------
- Click "Stop & Exit" in the small Freshers Jobs Tracker window, or simply close the small window using the 'X' button.
