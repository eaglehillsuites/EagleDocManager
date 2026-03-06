"""
Gmail Client - Creates email drafts with attachments using Gmail API.
"""

import base64
import os
import json
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from typing import Optional

import config_manager

SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]

# Fix: credentials live in the top-level config/ folder, not inside gmail/
CREDENTIALS_FILE = Path(__file__).parent.parent / "config" / "gmail_credentials.json"
TOKEN_FILE = config_manager.GMAIL_TOKEN_FILE

REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"


def get_credentials():
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow

        creds = None
        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not CREDENTIALS_FILE.exists():
                    raise FileNotFoundError(
                        f"gmail_credentials.json not found at:\n{CREDENTIALS_FILE}\n\n"
                        "Please place your Google OAuth credentials file there."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CREDENTIALS_FILE), SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())

        return creds
    except ImportError:
        raise RuntimeError(
            "Google API libraries not installed.\n"
            "Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )


def get_gmail_service():
    from googleapiclient.discovery import build
    creds = get_credentials()
    return build("gmail", "v1", credentials=creds)


def create_draft_with_attachment(file_path: str, unit_id: str, form_type: str = "") -> dict:
    service = get_gmail_service()

    subject = f"{unit_id}"
    if form_type:
        subject += f" - {form_type}"

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["To"] = ""

    filename = Path(file_path).name
    with open(file_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
    msg.attach(part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    draft = service.users().drafts().create(
        userId="me",
        body={"message": {"raw": raw}}
    ).execute()

    return draft


def create_drafts_for_batch(results: list) -> list[dict]:
    drafts = []
    for r in results:
        if r.get("generated_path") and Path(r["generated_path"]).exists():
            try:
                draft = create_draft_with_attachment(
                    file_path=r["generated_path"],
                    unit_id=r.get("unit", ""),
                    form_type=r.get("form_type", "")
                )
                drafts.append(draft)
            except Exception as e:
                print(f"[Gmail] Error creating draft for {r.get('generated_file')}: {e}")
    return drafts


def is_connected() -> bool:
    try:
        if not TOKEN_FILE.exists():
            return False
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        return creds and creds.valid
    except Exception:
        return False


def try_silent_reconnect() -> bool:
    """
    Attempt to silently refresh an existing token on startup.
    Returns True if the token is now valid, False if a manual re-auth is needed.
    Does NOT open a browser window.
    """
    try:
        if not TOKEN_FILE.exists():
            return False
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if creds and creds.valid:
            return True
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
            return True
        return False
    except Exception:
        return False


def disconnect():
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
