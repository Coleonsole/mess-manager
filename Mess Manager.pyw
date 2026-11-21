#!/usr/bin/env python3
"""Start Mess Manager.  Windows: double-click "Mess Manager.pyw".  Mac/Linux: python3 run_mess_manager.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import tkinter  # noqa: F401
except ImportError:
    sys.stderr.write(
        "Mess Manager needs Tkinter, which is part of Python but missing here.\n"
        "  Linux (Debian/Ubuntu): sudo apt install python3-tk\n"
        "  Linux (Fedora):        sudo dnf install python3-tkinter\n"
        "  Mac (Homebrew Python): brew install python-tk\n"
        "  Windows / Mac python.org installer: Tkinter is already included.\n")
    sys.exit(1)

from messmanager.ui import main

if __name__ == "__main__":
    main()
