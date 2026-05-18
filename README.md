# Freshers Jobs Tracker — Job Search & Tracking Suite

Built by **Ashank Rudola**

A comprehensive cross-platform tool to search, track, and manage job opportunities across multiple portals (LinkedIn, Naukri, Indeed, Unstop, Shine) with a beautiful web dashboard and a standalone Windows application.

---

## 📋 Overview

**Freshers Jobs Tracker** was built to solve the frustration of modern job searching. Instead of manually scrolling through sponsored listings and losing track of what you've applied to, this tool automates the hunt. It scrapes your preferred portals in the background and organizes everything into a clean, searchable dashboard.

### 🌟 Key Enhancements
- **Views System:** Create multiple custom search views (e.g., "Full Stack", "Bangalore Tech", "Remote Internships") with independent keywords and scraper settings.
- **Windows Standalone App:** No Python knowledge required. Run the provided `.exe` to start the server and dashboard instantly.
- **Real-time Monitoring:** A live "Scraping Progress" modal shows you exactly what the scrapers are doing as they find new jobs.
- **Automated Scheduling:** Set per-view polling intervals to keep your list fresh 24/7 without lifting a finger.

---

## 🚀 Getting Started

### **Option 1: Windows Standalone (No Setup Required)**
1. Download the latest release ZIP.
2. Extract the folder and run `Freshers Jobs Tracker.exe`.
3. The dashboard will automatically open in your browser at `http://127.0.0.1:5001`.

### **Option 2: Developer / Manual Setup**
1. **Clone the project:**
   ```bash
   git clone https://github.com/ashankrudola/JobsScraper.git
   cd JobsScraper
   ```
2. **Install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Start the app:**
   ```bash
   python app.py
   ```
4. **Access the UI:** [http://127.0.0.1:5001](http://127.0.0.1:5001)

---

## 🛠️ Features

| Category | Description |
|----------|-------------|
| **Multi-Portal** | Native support for **LinkedIn**, **Naukri**, **Indeed**, **Unstop**, and **Shine**. |
| **Views System** | Organize searches by categories. Each view has its own keyword list, locations, and enabled scrapers. |
| **Smart Tracking** | Mark jobs as **Reviewed** (✓) or **Interested** (★). Add personal notes/comments to any listing. |
| **Real-time Logs** | Live feedback during scraping cycles via an overlay modal. |
| **Advanced Filtering** | Filter by portal, experience level (Entry/Junior), and remote-only status. |
| **Local SQLite DB** | Your data is yours. All jobs are stored locally in `jobs.db`. |

---

## 🗂️ Project Architecture

```
Freshers Jobs Tracker/
├── app.py                 # Core Flask Server & Background Scheduler
├── storage.py             # SQLite Database & Migration Logic
├── launcher_gui.py        # Windows GUI Wrapper (Tkinter)
├── manage.py              # CLI Utility (Start/Stop/Build)
├── config.yaml            # Global App Configuration
├── scrapers/              # Scraper Modules (Selenium & Requests)
│   ├── linkedin.py
│   ├── naukri.py
│   ├── indeed.py
│   ├── unstop.py
│   └── shine.py
├── templates/             # Dashboard UI
│   └── index.html
│   └── settings.html
└── build_windows.bat      # PyInstaller Build Script
```

---

## ⚙️ Configuration & Settings

You can manage all settings directly from the Web UI by clicking the **⚙️ Settings** icon:
- **Keywords/Locations:** Add search terms for each view.
- **Auto-Scrape:** Toggle background scraping on/off per view.
- **Poll Interval:** Set how often (in minutes) each view should refresh.
- **Platform Selection:** Enable or disable specific scrapers for specific views.

---

## 🔍 Troubleshooting

### **Naukri/Indeed returning 0 jobs?**
- **Browser Detection:** These sites use advanced bot detection. Ensure you have Google Chrome installed on your system.
- **Logs:** Check `debug_scrape.log` or `scraper_errors.log` in the application folder for detailed error reports.
- **Headless Mode:** The app runs Chrome in headless mode. If it's failing, try running the project via `python app.py` to see console output.

### **Database issues?**
If you experience "Locked Database" errors, ensure only one instance of `Freshers Jobs Tracker.exe` or `python app.py` is running. Use `Task Manager` to kill any lingering `python.exe` or `Freshers Jobs Tracker.exe` processes.

---

## ⚖️ Legal Notice

This is a personal search tool. Please respect the Terms of Service of the targeted job portals. The author (**Ashank Rudola**) assumes no liability for any misuse of this tool, including rate limiting or account restrictions.

## 📄 License

**MIT License** — Use it, tweak it, share it. Keep the credits intact!

---

**Happy Hunting! 🚀**
