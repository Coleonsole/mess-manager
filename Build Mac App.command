#!/bin/bash
# Builds "Mess Manager.app" from these files. Needs Python from python.org and an internet connection (once).
cd "$(dirname "$0")"
echo "Building Mess Manager.app ..."
python3 -m pip install --user --upgrade pyinstaller pillow certifi || { echo "Couldn't install the build tools."; read -p "Press Enter to close."; exit 1; }
python3 -m PyInstaller --noconfirm --clean --windowed --name "Mess Manager" \
    --collect-submodules messmanager --hidden-import PIL._tkinter_finder run_mess_manager.py \
    || { echo "The build failed."; read -p "Press Enter to close."; exit 1; }
rm -rf "Mess Manager.app"
mv "dist/Mess Manager.app" "Mess Manager.app"
rm -rf build dist "Mess Manager.spec"
echo
echo "Done: Mess Manager.app is in this folder. Drag it into Applications."
open -R "Mess Manager.app"
read -p "Press Enter to close."
