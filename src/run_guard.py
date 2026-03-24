"""
Run guard: ensures only one successful digest is sent per day.
Uses a pharma_digest_state.json file on Google Drive as shared state
between the local launchd job and the GitHub Actions cloud job.

SCOPES: inherited from gmail_sender.get_credentials(), which includes
  - https://www.googleapis.com/auth/gmail.send
  - https://www.googleapis.com/auth/drive.file
Both are required here: gmail for OAuth, drive.file for state persistence.
"""
import io
import json
import logging
import socket
from datetime import datetime, timezone, timedelta

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from src.gmail_sender import get_credentials

logger = logging.getLogger(__name__)

TAIPEI = timezone(timedelta(hours=8))
STATE_FILENAME = "pharma_digest_state.json"


def _get_drive_service():
    return build("drive", "v3", credentials=get_credentials())


def _find_state_file(service) -> str | None:
    """Return file ID of pharma_digest_state.json if it exists in Drive."""
    result = service.files().list(
        q=f"name='{STATE_FILENAME}' and trashed=false",
        spaces="drive",
        fields="files(id)",
    ).execute()
    files = result.get("files", [])
    return files[0]["id"] if files else None


def _read_state(service, file_id: str) -> dict:
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return json.loads(fh.getvalue().decode("utf-8"))


def _write_state(service, file_id: str | None, data: dict) -> None:
    """Write state to Drive; creates the file if file_id is None."""
    content = json.dumps(data).encode("utf-8")
    fh = io.BytesIO(content)
    media = MediaIoBaseUpload(fh, mimetype="application/json")
    if file_id:
        service.files().update(fileId=file_id, media_body=media).execute()
    else:
        service.files().create(
            body={"name": STATE_FILENAME}, media_body=media
        ).execute()
        logger.info(f"Created new Drive state file: {STATE_FILENAME}")


_DRIVE_TIMEOUT = 30  # seconds for Drive API calls


def already_sent_today() -> bool:
    today = datetime.now(TAIPEI).strftime("%Y-%m-%d")
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(_DRIVE_TIMEOUT)
    try:
        service = _get_drive_service()
        file_id = _find_state_file(service)
        if not file_id:
            logger.info("No Drive state file found; proceeding with digest.")
            return False
        state = _read_state(service, file_id)
        if state.get("last_sent_date") == today:
            logger.info(f"Drive state: digest already sent on {today}, skipping.")
            return True
        return False
    except Exception as e:
        logger.warning(f"Drive state check failed (proceeding anyway): {e}")
        return False
    finally:
        socket.setdefaulttimeout(old_timeout)


def mark_sent_today() -> None:
    today = datetime.now(TAIPEI).strftime("%Y-%m-%d")
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(_DRIVE_TIMEOUT)
    try:
        service = _get_drive_service()
        file_id = _find_state_file(service)
        _write_state(service, file_id, {"last_sent_date": today})
        logger.info(f"Drive state updated: last_sent_date={today}")
    except Exception as e:
        logger.warning(f"Failed to update Drive state (email was still sent): {e}")
    finally:
        socket.setdefaulttimeout(old_timeout)
