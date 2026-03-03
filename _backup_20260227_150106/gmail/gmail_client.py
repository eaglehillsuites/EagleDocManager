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
CREDENTIALS_FILE = Path(__file__).parent.parent / "config" / "gmail_credentials.json"
TOKEN_FILE = config_manager.GMAIL_TOKEN_FILE

REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"  # Desktop app flow


def get_credentials():
    """Get valid credentials, refreshing or re-authenticating as needed."""
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
                        "Gmail credentials.json not found. Please add it to the config folder."
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
            "Google API libraries not installed. Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )


def get_gmail_service():
    """Build and return Gmail API service."""
    from googleapiclient.discovery import build
    creds = get_credentials()
    return build("gmail", "v1", credentials=creds)


def create_draft_with_attachment(file_path: str, unit_id: str, form_type: str = "") -> dict:
    """
    Create a Gmail draft with the given file attached.
    
    Subject format: "{unit_id} - {form_type}"
    Returns the created draft resource.
    """
    service = get_gmail_service()

    subject = f"{unit_id}"
    if form_type:
        subject += f" - {form_type}"

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["To"] = ""  # Empty - user will fill in recipient

    # Attach the file
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
    """
    Create one draft per processed file result.
    Returns list of created draft resources.
    """
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
    """Check if Gmail is connected (token exists and is valid)."""
    try:
        if not TOKEN_FILE.exists():
            return False
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        return creds and creds.valid
    except Exception:
        return False


def disconnect():
    """Remove stored token to disconnect Gmail."""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
