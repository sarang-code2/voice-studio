"""Upload a finished video to YouTube.

Requires a Google Cloud OAuth client (see README: "YouTube upload setup").
Uploads are always private or unlisted from this pipeline -- flip a video to
public yourself in YouTube Studio when you've reviewed it. This is enforced
in code, not just by convention: upload_video() refuses privacy_status="public".
"""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .config import ROOT

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_PATH = ROOT / "client_secret.json"
TOKEN_PATH = ROOT / "token.json"

ALLOWED_PRIVACY_STATUSES = {"private", "unlisted"}


def _get_credentials() -> Credentials:
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_PATH.exists():
                raise FileNotFoundError(
                    f"No OAuth client secret at {CLIENT_SECRET_PATH}. "
                    "See README: 'YouTube upload setup'."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    return creds


def upload_video(video_path: Path, script: dict, privacy_status: str = "private") -> str:
    if privacy_status not in ALLOWED_PRIVACY_STATUSES:
        raise ValueError(
            f"privacy_status must be one of {ALLOWED_PRIVACY_STATUSES}. "
            "This pipeline never auto-publishes as public -- review the "
            "upload in YouTube Studio and flip visibility yourself when ready."
        )

    creds = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": script["title"],
            "description": script["description"],
            "tags": script.get("tags", []),
        },
        "status": {"privacyStatus": privacy_status},
    }
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _, response = request.next_chunk()

    return response["id"]
