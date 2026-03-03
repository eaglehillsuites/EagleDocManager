"""
setup_windows.py - Windows setup helper.
Run this once after installation to:
1. Verify all dependencies
2. Create AppData config directory
3. Optionally add to Windows startup
"""

import os
import sys
import subprocess
from pathlib import Path


def check_poppler():
    """Check if Poppler is available (required by pdf2image)."""
    try:
        from pdf2image import convert_from_path
        # Test with a tiny operation
        print("✓ pdf2image available")
        return True
    except Exception as e:
        print(f"✗ pdf2image issue: {e}")
        print("  → Download Poppler for Windows from: https://github.com/oschwartz10612/poppler-windows/releases")
        print("  → Extract and add the 'bin' folder to your PATH")
        return False


def check_pylibdmtx():
    """Check if pylibdmtx is working."""
    try:
        from pylibdmtx.pylibdmtx import decode
        print("✓ pylibdmtx available")
        return True
    except Exception as e:
        print(f"✗ pylibdmtx issue: {e}")
        print("  → Install Visual C++ Redistributable from Microsoft")
        print("  → Or: pip install pylibdmtx --no-binary :all:")
        return False


def check_pyside6():
    try:
        from PySide6.QtWidgets import QApplication
        print("✓ PySide6 available")
        return True
    except Exception as e:
        print(f"✗ PySide6 issue: {e}")
        return False


def setup_appdata():
    """Create AppData directory and default configs."""
    import config_manager
    app_dir = config_manager.get_app_data_dir()
    config_manager.load_config()  # Creates defaults
    config_manager.load_forms()
    config_manager.load_naming_profiles()
    print(f"✓ AppData directory: {app_dir}")
    return True


def add_to_startup():
    """Add app to Windows startup via registry."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        app_path = Path(sys.executable).parent / "pythonw.exe"
        main_path = Path(__file__).parent / "main.py"
        cmd = f'"{app_path}" "{main_path}"'
        winreg.SetValueEx(key, "EagleDocManager", 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        print("✓ Added to Windows startup")
        return True
    except Exception as e:
        print(f"✗ Could not add to startup: {e}")
        return False


def remove_from_startup():
    """Remove from Windows startup."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, "EagleDocManager")
        winreg.CloseKey(key)
        print("✓ Removed from Windows startup")
    except Exception:
        pass


def create_desktop_shortcut():
    """Create a desktop shortcut."""
    try:
        import winshell
        from win32com.client import Dispatch
        desktop = winshell.desktop()
        path = os.path.join(desktop, "Eagle Doc Manager.lnk")
        shell = Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(path)
        shortcut.Targetpath = sys.executable
        shortcut.Arguments = f'"{Path(__file__).parent / "main.py"}"'
        shortcut.WorkingDirectory = str(Path(__file__).parent)
        shortcut.Description = "Eagle Doc Manager"
        shortcut.save()
        print(f"✓ Desktop shortcut created: {path}")
    except Exception as e:
        print(f"  Note: Could not create desktop shortcut: {e}")
        print("  → Install pywin32 and winshell for shortcut support")


if __name__ == "__main__":
    print("=" * 50)
    print("EagleDocManager - Windows Setup")
    print("=" * 50)
    print()

    all_ok = True

    print("Checking dependencies...")
    all_ok &= check_pyside6()
    all_ok &= check_poppler()
    check_pylibdmtx()  # Non-blocking

    print()
    print("Setting up configuration...")
    setup_appdata()

    print()
    if all_ok:
        print("✅ Setup complete! You can now run: python main.py")
    else:
        print("⚠️  Some dependencies need attention. See messages above.")

    print()
    startup = input("Add EagleDocManager to Windows startup? (y/n): ").strip().lower()
    if startup == "y":
        add_to_startup()

    shortcut = input("Create desktop shortcut? (y/n): ").strip().lower()
    if shortcut == "y":
        create_desktop_shortcut()

    print()
    print("Done.")
