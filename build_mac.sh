#!/bin/bash
echo "Building Freshers Jobs Tracker for macOS..."
echo ""

# Clean previous builds
rm -rf build dist Freshers Jobs Tracker.spec

# Build with PyInstaller
# Using --windowed to avoid opening a terminal window when double-clicked on Mac
python3 -m PyInstaller --noconfirm --onefile --windowed --icon=NONE --name "Freshers Jobs Tracker" launcher_gui.py

echo ""
echo "Packaging into zip-friendly folder..."
mkdir -p dist/Freshers_Jobs_Tracker_Mac

# Copy the generated .app bundle
cp -R dist/Freshers_Jobs_Tracker.app dist/Freshers_Jobs_Tracker_Mac/

# Copy resources
cp -R templates dist/Freshers_Jobs_Tracker_Mac/
cp config.yaml dist/Freshers_Jobs_Tracker_Mac/
cp README_MAC.txt dist/Freshers_Jobs_Tracker_Mac/

echo ""
echo "Done! Output is in dist/Freshers_Jobs_Tracker_Mac"
echo "You can zip this folder and share it with Mac users."
