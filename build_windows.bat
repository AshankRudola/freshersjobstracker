@echo off
echo Building Freshers Jobs Tracker for Windows...
echo.

:: Clean previous builds
rmdir /s /q build
rmdir /s /q dist
del /q "Freshers Jobs Tracker.spec"

:: Build with PyInstaller
venv\Scripts\pyinstaller --noconfirm --onefile --windowed --icon=NONE --name "Freshers Jobs Tracker" launcher_gui.py

echo.
echo Packaging into ZIP folder...
mkdir dist\Freshers_Jobs_Tracker_Windows
move "dist\Freshers Jobs Tracker.exe" dist\Freshers_Jobs_Tracker_Windows\
xcopy templates dist\Freshers_Jobs_Tracker_Windows\templates\ /E /I /Y
copy config.yaml dist\Freshers_Jobs_Tracker_Windows\
copy README_WINDOWS.txt dist\Freshers_Jobs_Tracker_Windows\

echo.
echo Done! Output is in dist\Freshers_Jobs_Tracker_Windows
pause
