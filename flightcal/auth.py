"""Google OAuth2 인증. 토큰은 ~/.config/flightcal/token.json에 저장한다."""

from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

_CONFIG_DIR = Path.home() / ".config" / "flightcal"
TOKEN_PATH = _CONFIG_DIR / "token.json"
DEFAULT_CREDS_PATH = _CONFIG_DIR / "credentials.json"

_SETUP_GUIDE = """
Google API 인증 파일({path})이 없습니다.

설정 방법:
  1. https://console.cloud.google.com/ → 새 프로젝트 생성
  2. "API 및 서비스" → "사용 설정된 API" → Gmail API, Google Calendar API 사용 설정
  3. "OAuth 동의 화면" → 테스트 사용자에 본인 Gmail 추가
  4. "사용자 인증 정보" → "OAuth 2.0 클라이언트 ID" → 데스크톱 앱 → JSON 다운로드
  5. 다운로드한 파일을 {path} 에 저장
  6. flightcal auth  로 인증 완료
""".strip()


def get_credentials(credentials_path: Path | None = None) -> Credentials:
    creds_file = credentials_path or DEFAULT_CREDS_PATH
    creds: Credentials | None = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_file.exists():
                raise FileNotFoundError(_SETUP_GUIDE.format(path=creds_file))
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return creds
