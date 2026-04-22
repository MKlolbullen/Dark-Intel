"""Entry point for the PySide6 operator console.

    python desktop.py

Spawns a local Flask server (subprocess) for the embedded Graph + Dashboard
views, then opens the Qt main window.
"""

from desktop.main import main

if __name__ == "__main__":
    main()
