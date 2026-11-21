@echo off
rem Builds "Mess Manager.exe". Needs Python from python.org and an internet connection (once).
cd /d "%~dp0"
py -m pip install --upgrade pyinstaller pillow certifi || goto fail
py -m PyInstaller --noconfirm --clean --windowed --onefile --name "Mess Manager" --collect-submodules messmanager --hidden-import PIL._tkinter_finder run_mess_manager.py || goto fail
move /Y "dist\Mess Manager.exe" "Mess Manager.exe" >nul
rmdir /S /Q build dist & del "Mess Manager.spec"
echo Done: Mess Manager.exe is in this folder.
pause
exit /b
:fail
echo The build failed.
pause
