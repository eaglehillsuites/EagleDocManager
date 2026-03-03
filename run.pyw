"""
EagleDocManager launcher — run with pythonw to suppress the console window.
This file is identical to main.py but uses the .pyw extension so Windows
associates it with pythonw.exe automatically, hiding the console.

Usage (double-click or shortcut):
    pythonw run.pyw
    
Or create a shortcut with target:
    pythonw "C:\Program Files\EagleDocManager\run.pyw"
"""
import runpy, os, sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Run main.py as a module
runpy.run_path(os.path.join(APP_DIR, "main.py"), run_name="__main__")
