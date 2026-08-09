import os
import tempfile
from pathlib import Path
from typing import Any

from google.cloud import storage
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from mcp.server.fastmcp import FastMCP

PORT = int(os.getenv("PORT", "8080"))
CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
EXPECTED_CHANNEL_ID = os.getenv("MYUSA_YOUTUBE_CHANNEL_ID", "")
DEFAULT_CATEGORY_ID = os.getenv("MYUSA_YOUTUBE_CATEGORY_ID", "28")
ALLOW_PUBLIC = os.getenv("MYUSA_YOUTUBE_ALLOW_PUBLIC", "false").lower() == "true"
ALLOWED_BUCKET = os.getenv("MYUSA_YOUTUBE_BUCKET", "")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

mcp = FastMCP(
    "MyUSA YouTube Publisher",
    host="0.0.0.0",
    port=PORT,
    streamable_http_path="/mcp",
)


def _credentials() -> Credentials:
    missing = [
        name
        for name, value in {
            "YOUTUBE_CLIENT_ID": CLIENT_ID,
            "YOUTUBE_CLIENT_SECRET": CLIENT_SECRET,
            "YOUTUBE_REFRESH_TOKEN": REFRESH_TOKEN,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing YouTube OAuth secret(s): {', '.join(missing)}")
    return Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=SCOPES,
    )


def _youtube():
    return build("youtube", "v3", credentials=_credentials(), cache_discovery=False)


def _channel(youtube) -> dict[str, Any]:
    result = youtube.channels().list(
        part="id,snippet,contentDetails,statistics,status",
        mine=True,
    ).execute()
    items = result.get("items", [])
    if len(items) != 1:
        raise RuntimeError("OAuth identity must resolve to exactly one YouTube channel.")
    channel = items[0]
    if EXPECTED_CHANNEL_ID and channel.get("id") != EXPECTED_CHANNEL_ID:
        raise RuntimeError(
            "Authorized YouTube channel does not match MYUSA_YOUTUBE_CHANNEL_ID. "
            "Publishing is blocked."
        )
    return channel


def _privacy(value: str) -> str:
    value = value.strip().lower()
    if value not in {"private", "unlisted", "public"}:
        raise ValueError("privacy_status must be private, unlisted, or public")
    if value == "public" and not ALLOW_PUBLIC:
        raise PermissionError(
            "Public publishing is disabled. Set MYUSA_YOUTUBE_ALLOW_PUBLIC=true only after "
            "the channel, OAuth grant, and API compliance status are verified."
        )
    return value


def _parse_gcs_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError("video_gcs_uri must start with gs://")
    body = uri[5:]
    if "/" not in body:
        raise ValueError("video_gcs_uri must include a bucket and object path")
    bucket, blob = body.split("/", 1)
    if not bucket or not blob:
        raise ValueError("video_gcs_uri must include a bucket and object path")
    if ALLOWED_BUCKET and bucket != ALLOWED_BUCKET:
        raise PermissionError(f"Only gs://{ALLOWED_BUCKET}/ objects may be published.")
    return bucket, blob


def _download_from_gcs(uri: str) -> tuple[str, str]:
    bucket_name, blob_name = _parse_gcs_uri(uri)
    suffix = Path(blob_name).suffix or ".mp4"
    fd, path = tempfile.mkstemp(prefix="myusa-youtube-", suffix=suffix)
    os.close(fd)
    storage.Client().bucket(bucket_name).blob(blob_name).download_to_filename(path)
    return path, blob_name


@mcp.tool()
def authorization_status() -> dict[str, Any]:
    """Verify the OAuth grant and return the authorized channel without changing YouTube."""
    channel = _channel(_youtube())
    return {
        "authorized": True,
        "channel_id": channel.get("id"),
        "channel_title": channel.get("snippet", {}).get("title"),
        "public_publishing_enabled": ALLOW_PUBLIC,
        "allowed_bucket": ALLOWED_BUCKET or None,
    }


@mcp.tool()
def get_channel_summary() -> dict[str, Any]:
    """Return the authorized MyUSA YouTube channel summary."""
    channel = _channel(_youtube())
    snippet = channel.get("snippet", {})
    statistics = channel.get("statistics", {})
    status = channel.get("status", {})
    return {
        "id": channel.get("id"),
        "title": snippet.get("title"),
        "custom_url": snippet.get("customUrl"),
        "published_at": snippet.get("publishedAt"),
        "subscribers": statistics.get("subscriberCount"),
        "videos": statistics.get("videoCount"),
        "views": statistics.get("viewCount"),
        "privacy_status": status.get("privacyStatus"),
    }


@mcp.tool()
def list_recent_videos(max_results: int = 10) -> list[dict[str, Any]]:
    """List recent uploads from the authorized channel."""
    max_results = max(1, min(int(max_results), 25))
    youtube = _youtube()
    channel = _channel(youtube)
    uploads = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    if not uploads:
        return []
    response = youtube.playlistItems().list(
        part="snippet,contentDetails,status",
        playlistId=uploads,
        maxResults=max_results,
    ).execute()
    rows: list[dict[str, Any]] = []
    for item in response.get("items", []):
        snippet = item.get("snippet", {})
        rows.append(
            {
                "video_id": item.get("contentDetails", {}).get("videoId"),
                "title": snippet.get("title"),
                "published_at": snippet.get("publishedAt"),
                "privacy_status": item.get("status", {}).get("privacyStatus"),
            }
        )
    return rows


@mcp.tool()
def upload_video_from_gcs(
    video_gcs_uri: str,
    title: str,
    description: str,
    tags: list[str] | None = None,
    privacy_status: str = "private",
    category_id: str = "",
    made_for_kids: bool = False,
) -> dict[str, Any]:
    """Upload one video from the private MyUSA GCS staging bucket. Defaults to private."""
    title = title.strip()
    if not title or len(title) > 100:
        raise ValueError("title must be 1-100 characters")
    if len(description) > 5000:
        raise ValueError("description must be 5000 characters or fewer")
    privacy_status = _privacy(privacy_status)
    tags = [str(tag).strip() for tag in (tags or []) if str(tag).strip()][:30]
    youtube = _youtube()
    _channel(youtube)
    local_path, source_object = _download_from_gcs(video_gcs_uri)
    try:
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id or DEFAULT_CATEGORY_ID,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": bool(made_for_kids),
            },
        }
        media = MediaFileUpload(
            local_path,
            mimetype="video/*",
            chunksize=8 * 1024 * 1024,
            resumable=True,
        )
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
            notifySubscribers=False,
        )
        response = None
        while response is None:
            _, response = request.next_chunk()
        video_id = response.get("id")
        return {
            "uploaded": True,
            "video_id": video_id,
            "youtube_url": f"https://www.youtube.com/watch?v={video_id}" if video_id else None,
            "privacy_status": response.get("status", {}).get("privacyStatus"),
            "source_object": source_object,
            "public_publishing_enabled": ALLOW_PUBLIC,
        }
    except HttpError as exc:
        raise RuntimeError(f"YouTube upload failed: {exc}") from exc
    finally:
        try:
            os.remove(local_path)
        except OSError:
            pass


@mcp.tool()
def set_video_privacy(video_id: str, privacy_status: str) -> dict[str, Any]:
    """Change privacy on an existing channel video. Public is blocked unless explicitly enabled."""
    privacy_status = _privacy(privacy_status)
    youtube = _youtube()
    _channel(youtube)
    existing = youtube.videos().list(part="status", id=video_id).execute().get("items", [])
    if not existing:
        raise ValueError("Video not found")
    status = existing[0].get("status", {})
    status["privacyStatus"] = privacy_status
    response = youtube.videos().update(
        part="status",
        body={"id": video_id, "status": status},
    ).execute()
    return {
        "video_id": response.get("id"),
        "privacy_status": response.get("status", {}).get("privacyStatus"),
    }


@mcp.tool()
def update_video_metadata(
    video_id: str,
    title: str,
    description: str,
    tags: list[str] | None = None,
    category_id: str = "",
) -> dict[str, Any]:
    """Update title, description, tags, and category for an existing channel video."""
    title = title.strip()
    if not title or len(title) > 100:
        raise ValueError("title must be 1-100 characters")
    if len(description) > 5000:
        raise ValueError("description must be 5000 characters or fewer")
    youtube = _youtube()
    _channel(youtube)
    existing = youtube.videos().list(part="snippet", id=video_id).execute().get("items", [])
    if not existing:
        raise ValueError("Video not found")
    old = existing[0].get("snippet", {})
    snippet = {
        "title": title,
        "description": description,
        "tags": [str(tag).strip() for tag in (tags or []) if str(tag).strip()][:30],
        "categoryId": category_id or old.get("categoryId") or DEFAULT_CATEGORY_ID,
    }
    for optional in ("defaultLanguage", "defaultAudioLanguage"):
        if old.get(optional):
            snippet[optional] = old[optional]
    response = youtube.videos().update(
        part="snippet",
        body={"id": video_id, "snippet": snippet},
    ).execute()
    return {
        "video_id": response.get("id"),
        "title": response.get("snippet", {}).get("title"),
        "description": response.get("snippet", {}).get("description"),
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
