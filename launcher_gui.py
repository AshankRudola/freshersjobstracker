import os
import sys
import threading
import time
import webbrowser
import socket
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

# Adjust working directory for PyInstaller
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Now import the app
from app import app

class FreshersJobsTrackerLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Freshers Jobs Tracker Server")
        self.root.geometry("400x250")
        self.root.resizable(False, False)
        
        # Center window
        self.root.eval('tk::PlaceWindow . center')
        
        self.server_thread = None
        self.is_running = False
        self.server_error = None
        
        self.setup_ui()
        self.start_server()
        
    def setup_ui(self):
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(frame, text="Freshers Jobs Tracker is Running", font=("Segoe UI", 16, "bold")).pack(pady=(0, 5))
        ttk.Label(frame, text="The local server is active in the background.", font=("Segoe UI", 10)).pack(pady=(0, 20))
        
        # Status
        self.status_label = ttk.Label(frame, text="Status: Starting...", foreground="blue", font=("Segoe UI", 10, "bold"))
        self.status_label.pack(pady=(0, 20))
        
        # Buttons
        self.btn_frame = ttk.Frame(frame)
        self.btn_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.btn_open = ttk.Button(self.btn_frame, text="Open in Browser", command=self.open_browser)
        self.btn_open.pack(side=tk.LEFT, expand=True, padx=5)
        
        ttk.Button(self.btn_frame, text="Stop & Exit", command=self.stop_server).pack(side=tk.RIGHT, expand=True, padx=5)

    def is_port_in_use(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return False
            except OSError:
                return True

    def kill_zombie_processes(self):
        try:
            if sys.platform == 'win32':
                subprocess.run('taskkill /F /IM chromedriver.exe', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
        except Exception:
            pass

    def start_server(self):
        # 1. Check if port is already in use
        if self.is_port_in_use(5001):
            # Attempt to clear lingering chromdrivers
            self.kill_zombie_processes()
            time.sleep(0.5)
            
            # Check again
            if self.is_port_in_use(5001):
                self.status_label.config(text="Status: PORT 5001 BLOCKED", foreground="red")
                messagebox.showerror(
                    "Port Blocked", 
                    "Port 5001 is already in use by another process.\n\n"
                    "Please close any other running Freshers Jobs Tracker instances, or wait a minute for the port to release, then try again."
                )
                self.btn_open.config(state=tk.DISABLED)
                return

        self.is_running = True
        self.status_label.config(text="Status: RUNNING", foreground="green")
        
        # Start Flask in a background thread
        self.server_thread = threading.Thread(target=self.run_flask, daemon=True)
        self.server_thread.start()
        
        # Monitor the thread startup
        self.root.after(1000, self.check_server_startup)

    def run_flask(self):
        # Disable Flask's default output to prevent clutter
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
        try:
            app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)
        except Exception as e:
            self.server_error = str(e)
            print(f"Server error: {e}")

    def check_server_startup(self):
        if self.server_error:
            self.status_label.config(text="Status: FAILED TO START", foreground="red")
            messagebox.showerror("Server Error", f"Failed to start local web server:\n\n{self.server_error}")
            self.btn_open.config(state=tk.DISABLED)
        else:
            # Server is up! Open browser
            self.open_browser()

    def open_browser(self):
        webbrowser.open('http://127.0.0.1:5001')

    def stop_server(self):
        self.root.destroy()
        sys.exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    
    # Try to set a nice theme if available (Windows)
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
        
    app_launcher = FreshersJobsTrackerLauncher(root)
    
    # Handle window close (X button)
    root.protocol("WM_DELETE_WINDOW", app_launcher.stop_server)
    
    root.mainloop()
