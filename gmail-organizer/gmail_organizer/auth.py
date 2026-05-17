"""Gmail OAuth2 認證."""

from __future__ import annotations

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
]

DEFAULT_CREDENTIALS_PATH = Path("credentials.json")
DEFAULT_TOKEN_PATH = Path("token.json")


def get_service(
    credentials_path: Path = DEFAULT_CREDENTIALS_PATH,
    token_path: Path = DEFAULT_TOKEN_PATH,
) -> Resource:
    """取得已授權的 Gmail API client.

    第一次執行會打開瀏覽器要求授權，之後的 token 會存在 token.json。
    """
    creds: Credentials | None = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise FileNotFoundError(
                    f"找不到 {credentials_path}。請到 Google Cloud Console 建立 OAuth "
                    "client (Desktop app)，下載 JSON 後放到這個路徑。"
                    "詳細步驟見 README.md。"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())
        os.chmod(token_path, 0o600)

    return build("gmail", "v1", credentials=creds, cache_discovery=False)
