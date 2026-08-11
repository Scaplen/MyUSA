# MyUSA.us YouTube Publisher

Publishes MyUSA Weather Studio videos to the authorized YouTube channel using the official YouTube Data API v3.

## One-time Google setup

1. In Google Cloud Console, select/create the Google project used for MyUSA.us.
2. Enable **YouTube Data API v3**.
3. Configure the OAuth consent screen.
4. Create an OAuth 2.0 Client ID for a **Desktop app**.
5. Download the OAuth JSON and save it as:
   `tools/youtube_publisher/client_secret.json`

Do not commit this file. `.gitignore` already excludes it.

## Install

```bash
cd tools/youtube_publisher
python -m pip install -r requirements.txt
```

## First authorization

The first upload opens Google's authorization page. Sign in to the YouTube account that owns the MyUSA channel and approve the upload permission. A local `token.json` is then stored for later uploads and refreshes automatically when possible.

## Publish a video

```bash
python youtube_publish.py MyUSA-Weather-Studio-Ep1.mp4 \
  --title "MyUSA Weather Studio | Hurricane Season Progress" \
  --description "Weather Made Simple from MyUSA.us. Official weather data from NOAA/NWS. No ads. No clutter.\n\nhttps://myusa.us" \
  --tags MyUSA.us weather NOAA NWS hurricane \
  --thumbnail MyUSA-Weather-Ep1.jpg \
  --privacy private
```

Use `--privacy unlisted` for a shareable review copy or `--privacy public` when the Google API project is eligible for public uploads.

## Schedule a release

```bash
python youtube_publish.py episode.mp4 \
  --title "MyUSA Weather Studio" \
  --publish-at "2026-08-11T13:00:00Z"
```

The publisher automatically uses private status for scheduled releases as required by YouTube.

## Notes

- The helper requests only the `youtube.upload` OAuth scope.
- `client_secret.json` and `token.json` must remain private.
- YouTube API projects created after July 28, 2020 that have not passed Google's audit can have API uploads restricted to private viewing. Complete Google's API compliance audit before relying on automated public publishing.
- Custom thumbnail uploads must meet YouTube's thumbnail requirements.
