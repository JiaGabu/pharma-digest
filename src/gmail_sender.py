import base64
import logging
import os
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config.settings import CREDENTIALS_FILE, TOKEN_FILE

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.file",
]


def _restore_credential_files() -> None:
    """Decode Base64 env vars to credential files when running in CI.

    In GitHub Actions the files don't exist on disk; instead the secrets
    GMAIL_CREDENTIALS and GMAIL_TOKEN are injected as Base64 env vars.
    This function writes them to the paths expected by the OAuth library
    so the rest of the code works identically in both local and CI runs.

    Local runs are unaffected: if the files already exist, this is a no-op.
    """
    for filepath, env_var in (
        (CREDENTIALS_FILE, "GMAIL_CREDENTIALS"),
        (TOKEN_FILE, "GMAIL_TOKEN"),
    ):
        if not os.path.exists(filepath):
            encoded = os.environ.get(env_var, "")
            if encoded:
                with open(filepath, "wb") as fh:
                    fh.write(base64.b64decode(encoded))
                logger.info(f"Restored {filepath} from ${env_var} env var")


def get_credentials() -> Credentials:
    # Write files from env vars if we're running in CI without local files.
    _restore_credential_files()

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(30)
            try:
                creds.refresh(Request())
            finally:
                socket.setdefaulttimeout(old_timeout)
            logger.info("OAuth token refreshed successfully.")
        else:
            # Interactive browser flow — only works in a local environment.
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as fh:
            fh.write(creds.to_json())
        logger.info("OAuth token written to token.json")

    return creds


def _get_service():
    return build("gmail", "v1", credentials=get_credentials())


def send_email(subject: str, html_body: str, recipient: str) -> None:
    service = _get_service()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["To"] = recipient
    msg["From"] = "me"
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(30)
    try:
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
    finally:
        socket.setdefaulttimeout(old_timeout)
    logger.info(f"Email sent to {recipient}: {subject}")
