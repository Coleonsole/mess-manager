MESS MANAGER
============

A file manager for a messy folder.


MAKING IT ONE APP
-----------------
Mac:     install Python from python.org, then double-click "Build Mac App.command".
         A few minutes later "Mess Manager.app" appears in this folder. Drag it into Applications.
         The first time you open it: right-click it > Open > Open (it isn't from the App Store).
Windows: install Python from python.org, then double-click "Build Windows App.bat".
         You get "Mess Manager.exe".
The build needs the internet once. After that the app doesn't need Python or this folder.


RUNNING IT WITHOUT BUILDING
---------------------------
You need Python 3.8 or newer. Nothing else has to be installed.

Windows
  1. Install Python from python.org (tick "Add Python to PATH").
  2. Double-click "Mess Manager.pyw".

Mac
  1. Install Python from python.org (it includes Tkinter).
     If you use Homebrew's Python instead:  brew install python-tk
  2. Double-click "Start Mess Manager (Mac).command".
     (If the Mac says it can't be opened, right-click it, choose Open, then Open again.
     If it asks whether Python can use your Desktop folder, say yes: Mess lives there.)

Linux
  1. sudo apt install python3-tk      (Fedora: sudo dnf install python3-tkinter)
  2. ./start_linux.sh    or    python3 run_mess_manager.py

Optional: "pip install Pillow" lets Mess Manager show JPG and WEBP thumbnails
and read their colours. PNG and GIF work without it.


WHERE THINGS ARE
----------------
- On the first run you choose where Mess lives. The default is a folder called Mess on your
  Desktop. If you pick a folder that already has things in it, Mess is made INSIDE it
  (Mess never takes over your other files).
- Mess is a real folder. Open it in Explorer / Finder / Files whenever you like:
  everything you do there counts, even while Mess Manager is closed.
- Mess Manager's own settings: a .messmanager folder in your home folder.
  Delete config.json in there to see the opening screen again and choose a new place for Mess.
- Everything about the people in Mess is saved in Mess/System.

THE AI (Ollama)
---------------
The people in Mess never talk to you. They talk to each other - about what happens to them,
about each other, about the files they can see - and you overhear it in the "Overheard"
panel on the right. Every word they say is written by an AI running on your own computer.

1. Install Ollama from ollama.com/download (Mac: drag it into Applications, then open it;
   a llama icon appears in the menu bar).
2. In Mess Manager click "AI...", choose "Ollama (on this computer)" and press "Download model"
   (a few GB, only once). For pictures too, type llava as the Model before downloading.
3. Press Test, then Save.

Mess Manager starts Ollama by itself when it opens. Without it, they still live, move, love and change,
but their words can't be written: you only see that they're talking.

Chance: the slider in the AI window (also "Chance:" in World/Stats.txt) sets how
unpredictable Mess is.

How to play is inside the game: open "How To Play.txt".
