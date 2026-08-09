import base64
import hashlib
import hmac
import os
import time
from urllib.parse import urlencode

from flask import Flask, abort, redirect, request
from google.cloud import secretmanager
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "optimum-sound-505003-d3")
CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
SETUP_KEY = os.getenv("MYUSA_YOUTUBE_SETUP_KEY", "")
STATE_SECRET = os.getenv("MYUSA_YOUTUBE_STATE_SECRET", "")
REDIRECT_URI = os.getenv("YOUTUBE_OAUTH_REDIRECT_URI", "")
REFRESH_SECRET_ID = os.getenv("YOUTUBE_REFRESH_SECRET_ID", "myusa-youtube-refresh-token")
EXPECTED_HANDLE = os.getenv("MYUSA_YOUTUBE_HANDLE", "@MyUSAus")
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

app = Flask(__name__)
sm = secretmanager.SecretManagerServiceClient()


def _require_config():
    missing = [
        name
        for name, value in {
            "YOUTUBE_CLIENT_ID": CLIENT_ID,
            "YOUTUBE_CLIENT_SECRET": CLIENT_SECRET,
            "MYUSA_YOUTUBE_SETUP_KEY": SETUP_KEY,
            "MYUSA_YOUTUBE_STATE_SECRET": STATE_SECRET,
            "YOUTUBE_OAUTH_REDIRECT_URI": REDIRECT_URI,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError("Missing configuration: " + ", ".join(missing))


def _state_token() -> str:
    ts = str(int(time.time()))
    sig = hmac.new(STATE_SECRET.encode(), ts.encode(), hashlib.sha256).digest()
    return ts + "." + base64.urlsafe_b64encode(sig).decode().rstrip("=")


def _valid_state(value: str) -> bool:
    try:
        ts, given = value.split(".", 1)
        if abs(int(time.time()) - int(ts)) > 900:
            return False
        expected = base64.urlsafe_b64encode(
            hmac.new(STATE_SECRET.encode(), ts.encode(), hashlib.sha256).digest()
        ).decode().rstrip("=")
        return hmac.compare_digest(given, expected)
    except Exception:
        return False


def _flow(state=None):
    config = {
        "web": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }
    return Flow.from_client_config(config, scopes=SCOPES, state=state, redirect_uri=REDIRECT_URI)


def _verify_channel(creds: Credentials) -> dict:
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    result = youtube.channels().list(part="id,snippet", mine=True).execute()
    items = result.get("items", [])
    if len(items) != 1:
        raise RuntimeError("OAuth identity did not resolve to exactly one YouTube channel.")
    channel = items[0]
    custom = (channel.get("snippet", {}).get("customUrl") or "").strip()
    if custom.lower() != EXPECTED_HANDLE.lower():
        raise RuntimeError(
            f"Publishing blocked: authorized channel handle {custom!r} does not match {EXPECTED_HANDLE!r}."
        )
    return channel


def _store_refresh_token(token: str):
    parent = f"projects/{PROJECT_ID}/secrets/{REFRESH_SECRET_ID}"
    sm.add_secret_version(
        request={
            "parent": parent,
            "payload": {"data": token.encode("utf-8")},
        }
    )


@app.get("/")
def home():
    return "MyUSA YouTube authorization helper is running. Use /start with the private setup key.", 200


@app.get("/start")
def start():
    _require_config()
    supplied = request.args.get("key", "")
    if not supplied or not hmac.compare_digest(supplied, SETUP_KEY):
        abort(403)
    flow = _flow()
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
        state=_state_token(),
    )
    return redirect(authorization_url, code=302)


@app.get("/oauth2/callback")
def callback():
    _require_config()
    state = request.args.get("state", "")
    if not _valid_state(state):
        abort(403)
    flow = _flow(state=state)
    # Cloud Run terminates TLS before forwarding to Flask, so request.url may
    # appear as http:// internally. Rebuild the authorization response from
    # the configured public HTTPS callback URI plus Google's query string.
    query = request.query_string.decode("utf-8")
    authorization_response = REDIRECT_URI + (f"?{query}" if query else "")
    flow.fetch_token(authorization_response=authorization_response)
    creds = flow.credentials
    if not creds.refresh_token:
        raise RuntimeError("Google did not return a refresh token. Revoke prior grant and retry with consent.")
    channel = _verify_channel(creds)
    _store_refresh_token(creds.refresh_token)
    title = channel.get("snippet", {}).get("title", "MyUSA")
    channel_id = channel.get("id", "")
    return (
        "Authorization complete. "
        f"Verified {title} ({EXPECTED_HANDLE}), channel ID {channel_id}. "
        "The refresh token was stored directly in Google Secret Manager. You may close this page."
    ), 200


# Redeploy marker: refresh latest Web OAuth client secret from Secret Manager.

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
