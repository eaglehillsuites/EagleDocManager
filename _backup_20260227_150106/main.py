"""
EagleDocManager - Main Entry Point
"""

import sys
import os

# Ensure the app directory is on the path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtCore import Qt

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("EagleDocManager")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("EagleProperties")

    # Set application-wide font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Force a light palette so Windows dark mode doesn't break the UI.
    # Without this, dark mode causes white text on white inputs, invisible labels, etc.
    palette = QPalette()
    palette.setColor(QPalette.Window,          QColor("#f8f9fa"))
    palette.setColor(QPalette.WindowText,      QColor("#212529"))
    palette.setColor(QPalette.Base,            QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase,   QColor("#f0f0f0"))
    palette.setColor(QPalette.Text,            QColor("#212529"))
    palette.setColor(QPalette.BrightText,      QColor("#ffffff"))
    palette.setColor(QPalette.Button,          QColor("#e9ecef"))
    palette.setColor(QPalette.ButtonText,      QColor("#212529"))
    palette.setColor(QPalette.Highlight,       QColor("#2c7be5"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipBase,     QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipText,     QColor("#212529"))
    palette.setColor(QPalette.PlaceholderText, QColor("#6c757d"))
    palette.setColor(QPalette.Disabled, QPalette.Text,       QColor("#adb5bd"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#adb5bd"))
    app.setPalette(palette)

    # Apply global stylesheet
    app.setStyleSheet("""
        * { color: #212529; }

        QMainWindow, QDialog, QWidget {
            background-color: #f8f9fa;
            color: #212529;
        }

        QGroupBox {
            font-weight: bold;
            border: 1px solid #ced4da;
            border-radius: 6px;
            margin-top: 10px;
            padding: 10px 8px 8px 8px;
            background-color: #f8f9fa;
            color: #212529;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
            color: #212529;
            background-color: #f8f9fa;
        }

        QLabel {
            color: #212529;
            background-color: transparent;
        }

        QListWidget {
            border: 1px solid #ced4da;
            border-radius: 4px;
            background-color: #ffffff;
            color: #212529;
        }
        QListWidget::item { color: #212529; padding: 3px; }
        QListWidget::item:selected {
            background-color: #cce5ff;
            color: #004085;
        }
        QListWidget::item:hover { background-color: #e9ecef; }

        QLineEdit {
            border: 1px solid #ced4da;
            border-radius: 4px;
            padding: 4px 8px;
            background-color: #ffffff;
            color: #212529;
        }
        QLineEdit:focus { border-color: #80bdff; }
        QLineEdit:disabled {
            background-color: #e9ecef;
            color: #6c757d;
        }
        QLineEdit[readOnly="true"] {
            background-color: #e9ecef;
            color: #495057;
        }

        QTextEdit {
            border: 1px solid #ced4da;
            border-radius: 4px;
            background-color: #ffffff;
            color: #212529;
        }

        QComboBox {
            border: 1px solid #ced4da;
            border-radius: 4px;
            padding: 4px 8px;
            background-color: #ffffff;
            color: #212529;
        }
        QComboBox:disabled {
            background-color: #e9ecef;
            color: #6c757d;
        }
        QComboBox QAbstractItemView {
            background-color: #ffffff;
            color: #212529;
            selection-background-color: #cce5ff;
            selection-color: #004085;
            border: 1px solid #ced4da;
        }

        QSpinBox {
            border: 1px solid #ced4da;
            border-radius: 4px;
            padding: 4px 8px;
            background-color: #ffffff;
            color: #212529;
        }

        QCheckBox {
            color: #212529;
            background-color: transparent;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border: 1px solid #ced4da;
            border-radius: 3px;
            background-color: #ffffff;
        }
        QCheckBox::indicator:checked {
            background-color: #2c7be5;
            border-color: #2c7be5;
        }

        QRadioButton {
            color: #212529;
            background-color: transparent;
        }

        QTabWidget::pane {
            background-color: #ffffff;
            border: 1px solid #dee2e6;
        }
        QTabBar::tab {
            background-color: #e9ecef;
            color: #495057;
            padding: 10px 20px;
            font-size: 13px;
            border: 1px solid #dee2e6;
            border-bottom: none;
        }
        QTabBar::tab:selected {
            background-color: #ffffff;
            color: #212529;
            border-bottom: 3px solid #2c7be5;
            font-weight: bold;
        }
        QTabBar::tab:hover:!selected { background-color: #dee2e6; }

        QScrollArea { border: none; background-color: transparent; }
        QScrollArea > QWidget > QWidget { background-color: transparent; }

        QScrollBar:vertical {
            background-color: #f0f0f0;
            width: 10px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical {
            background-color: #adb5bd;
            border-radius: 5px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover { background-color: #6c757d; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

        QStatusBar {
            background-color: #e9ecef;
            color: #495057;
            border-top: 1px solid #dee2e6;
        }

        QMessageBox { background-color: #ffffff; color: #212529; }
        QMessageBox QLabel { color: #212529; }

        QInputDialog QLabel { color: #212529; }
        QInputDialog QLineEdit { background-color: #ffffff; color: #212529; }

        QFrame { background-color: transparent; }

        QProgressDialog { background-color: #ffffff; color: #212529; }
    """)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
