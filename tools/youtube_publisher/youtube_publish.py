#!/usr/bin/env python3
"""MyUSA.us YouTube publisher.

Uploads a video to the authorized YouTube channel, sets metadata, and optionally
sets a custom thumbnail. OAuth credentials stay local and are never committed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
HERE = Path(__file__).resolve().parent
DEFAULT_CLIENT_SECRET = HERE / "client_secret.json"
DEFAULT_TOKEN = HERE / "token.json"


def get_credentials(client_secret: Path, token_path: Path) -> Credentials:
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds or not creds.valid:
        if not client_secret.exists():
            raise FileNotFoundError(
                f"Missing OAuth client file: {client_secret}. "
                "Create a Desktop app OAuth client in Google Cloud, enable the "
                "YouTube Data API v3, and save its JSON here as client_secret.json."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)

    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def upload_video(youtube, args) -> str:
    status = {
        "privacyStatus": args.privacy,
        "selfDeclaredMadeForKids": args.made_for_kids,
    }
    if args.contains_synthetic_media:
        status["containsSyntheticMedia"] = True
    if args.publish_at:
        status["publishAt"] = args.publish_at
        status["privacyStatus"] = "private"

    body = {
        "snippet": {
            "title": args.title,
            "description": args.description,
            "tags": args.tags,
            "categoryId": args.category,
            "defaultLanguage": args.language,
        },
        "status": status,
    }

    media = MediaFileUpload(
        args.video,
        mimetype="video/*",
        chunksize=8 * 1024 * 1024,
        resumable=True,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
        notifySubscribers=args.notify_subscribers,
    )

    response = None
    while response is None:
        upload_status, response = request.next_chunk()
        if upload_status:
            pct = int(upload_status.progress() * 100)
            print(f"Upload progress: {pct}%", flush=True)

    video_id = response["id"]
    print(f"Uploaded video ID: {video_id}")
    print(f"YouTube URL: https://youtu.be/{video_id}")
    return video_id


def set_thumbnail(youtube, video_id: str, thumbnail: str) -> None:
    media = MediaFileUpload(thumbnail, mimetype="image/*", resumable=False)
    youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
    print("Custom thumbnail set.")


def parse_args():
    p = argparse.ArgumentParser(description="Upload a MyUSA.us video to YouTube")
    p.add_argument("video", help="Path to MP4 or other YouTube-supported video")
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="MyUSA.us — Official weather. No ads. No clutter.\nhttps://myusa.us")
    p.add_argument("--tags", nargs="*", default=["MyUSA.us", "weather", "NOAA", "NWS"])
    p.add_argument("--category", default="28", help="YouTube category ID; 28 = Science & Technology")
    p.add_argument("--language", default="en")
    p.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    p.add_argument("--publish-at", help="RFC3339 scheduled publish time; YouTube requires private status when scheduling")
    p.add_argument("--thumbnail", help="Path to JPG/PNG custom thumbnail")
    p.add_argument("--made-for-kids", action="store_true")
    p.add_argument("--contains-synthetic-media", action="store_true")
    p.add_argument("--notify-subscribers", action="store_true")
    p.add_argument("--client-secret", default=str(DEFAULT_CLIENT_SECRET))
    p.add_argument("--token", default=str(DEFAULT_TOKEN))
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not Path(args.video).exists():
        print(f"Video not found: {args.video}", file=sys.stderr)
        return 2
    if args.thumbnail and not Path(args.thumbnail).exists():
        print(f"Thumbnail not found: {args.thumbnail}", file=sys.stderr)
        return 2

    try:
        creds = get_credentials(Path(args.client_secret), Path(args.token))
        youtube = build("youtube", "v3", credentials=creds)
        video_id = upload_video(youtube, args)
        if args.thumbnail:
            set_thumbnail(youtube, video_id, args.thumbnail)
        return 0
    except (HttpError, OSError, ValueError) as exc:
        print(f"YouTube publishing failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
