# 🦅 Eagle Doc Manager

A professional Windows desktop application for automatically sorting, renaming, and organizing scanned PDF documents based on QR codes and Data Matrix barcodes.

---

## Features

- **Automatic document sorting** via QR codes (unit/building number) and Data Matrix barcodes (form type)
- **3 scan modes** for different scanning workflows
- **Background folder watcher** that processes new PDFs automatically
- **Manual processing** of any folder on demand
- **Duplicate detection** with side-by-side preview
- **Undo** any processing within 24 hours
- **Gmail draft creation** — one draft per file, pre-addressed with unit number
- **Print queue** after processing
- **Audit log CSV** saved per source folder
- **Out-inspection automation** — moves tenant folder to Previous Tenants
- **Fully configurable** naming conventions, form types, and folder rules

---

## Installation

### 1. Install Python 3.11+
Download from [python.org](https://www.python.org)

### 2. Install Poppler for Windows
Required by `pdf2image` for PDF-to-image conversion.

1. Download from: https://github.com/oschwartz10612/poppler-windows/releases
2. Extract the ZIP file
3. Add the `bin` folder to your Windows PATH
   - Search "Environment Variables" in Start Menu
   - Edit `Path` under System Variables
   - Add the path to the Poppler `bin` folder

### 3. Install Python dependencies
```
pip install -r requirements.txt
```

### 4. Run Setup
```
python setup_windows.py
```

---

## Running the App
```
python main.py
```

---

## Configuration

All settings are saved to:
```
C:\Users\<YourUser>\AppData\Local\EagleDocManager\
```

### First-Time Setup (Settings > General)
1. Set your **Tenant Folder Root** (e.g., `C:\Tenants`)
2. Set your **Previous Tenants Path** (e.g., `C:\Tenants\Previous Tenants`)
3. Connect **Gmail** (optional)

---

## QR Code Format

QR codes on documents should contain:
```
BLDG:216|UNIT:101
```

This will be formatted as `101-216` in all filenames and folder names.

---

## Data Matrix Format

Data Matrix barcodes on your forms should contain:
```
FORM:Maintenance
FORM:OutInspection
FORM:RentalIncrease
FORM:InInspection
FORM:NoticeEntry
FORM:LeaseRenewal
```

Add and manage form types in **Settings > Forms**.

---

## Scan Modes

### Mode 1 — One Document Per PDF
- QR sticker on the first page of the physical document
- Entire PDF = one document

### Mode 2 — Multiple Documents Per PDF
- QR sticker on the first page of each new document
- Program detects new document when it finds a QR or Data Matrix code

### Mode 3 — Separator Pages (Recommended)
- A blank separator page with:
  - Data Matrix containing `SEPARATOR`
  - QR code with unit/building number
- Placed before each document
- Separator pages are excluded from the output files

---

## Naming Convention Tokens

In the **Naming Conventions** tab, you can build filenames from these parts:

| Part Type | Result |
|-----------|--------|
| Unit # | `101-216` |
| Form Name | `Maintenance` |
| Today's Date | `2026-02-26` (using your date format) |
| Date (Renewal) | Month/year picker popup at processing time |
| Date (Custom) | Text input popup at processing time |
| Plain Text | Whatever you type |

### Date Format Patterns

| Pattern | Output |
|---------|--------|
| `yyyy-mm-dd` | `2026-02-26` |
| `mmmYYYY` | `Feb2026` |
| `dd-mmm-yyyy` | `26-Feb-2026` |
| `mm/dd/yyyy` | `02/26/2026` |

---

## Gmail Integration

1. Go to **Settings > General** → click **Connect Gmail**
2. A browser window will open to authorize
3. Credentials are saved locally in AppData
4. After processing, use the **Create Gmail Drafts** button in the completion popup
5. Each file gets its own draft with subject: `101-216 - Maintenance`

### Gmail Setup (First Time)
You need a `credentials.json` file from Google Cloud Console:
1. Go to https://console.cloud.google.com
2. Create a project → Enable Gmail API
3. Create OAuth 2.0 credentials (Desktop app)
4. Download `credentials.json`
5. Place it at: `EagleDocManager/config/gmail_credentials.json`

---

## File Structure (AppData)

```
C:\Users\<You>\AppData\Local\EagleDocManager\
├── config.json              ← General settings
├── forms.json               ← Form type definitions
├── naming_profiles.json     ← Naming convention profiles
├── undo_log.json            ← Last 24 hours of operations
├── gmail_token.json         ← Saved Gmail credentials
└── logs\                    ← Application logs
```

---

## Project Code Structure

```
EagleDocManager/
├── main.py                  ← Entry point
├── watcher.py               ← Background folder watcher
├── config_manager.py        ← Config file I/O
├── requirements.txt
├── setup_windows.py
│
├── processor/
│   ├── barcode_reader.py    ← QR & Data Matrix detection
│   ├── splitter.py          ← PDF splitting (Modes 1-3)
│   ├── naming_engine.py     ← Filename generation
│   ├── duplicate_checker.py ← Duplicate detection
│   ├── mover.py             ← File moving & folder management
│   ├── archiver.py          ← (see splitter.py archive_original)
│   ├── audit_logger.py      ← CSV audit log
│   ├── undo_manager.py      ← Undo tracking & execution
│   ├── hooks.py             ← Extensible hook system
│   └── engine.py            ← Main processing pipeline
│
├── ui/
│   ├── main_window.py       ← Main application window
│   ├── completion_dialog.py ← Post-processing popup
│   ├── duplicate_dialog.py  ← Duplicate preview dialog
│   ├── date_popups.py       ← Renewal/custom date dialogs
│   ├── out_inspection_dialog.py
│   ├── part_editor.py       ← Naming part editor
│   └── settings_tabs/
│       └── tabs.py          ← All 5 settings tabs
│
└── gmail/
    └── gmail_client.py      ← Gmail API integration
```

---

## Extending the App

The codebase uses a **plugin hook system**. To add new features after processing:

```python
from processor.hooks import hooks

def my_custom_hook(file_info: dict):
    print(f"Processed: {file_info['generated_file']}")

hooks.register("after_move", my_custom_hook)
```

Available hooks:
- `after_rename(file_info)`
- `after_move(file_info)`
- `after_batch_complete(batch_results)`
- `on_error(error_info)`
- `on_out_inspection(unit, file_path)`

---

## Troubleshooting

**pdf2image fails**: Poppler not in PATH. See Installation step 2.

**pylibdmtx fails**: Install Visual C++ Redistributable from Microsoft.

**pyzbar fails on Windows**: `pip install pyzbar` sometimes needs the ZBar DLL. Download from https://zbar.sourceforge.net

**Gmail auth fails**: Make sure `credentials.json` is in the `config/` folder.
