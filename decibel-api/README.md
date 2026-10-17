# Decibel API

Optional server-side companion for the static GitHub Pages UI in `/decibel`.

It provides:
- `POST /api/info` — inspect supported public media links.
- `POST /api/convert` — retrieve and convert supported links to MP3, MP4, WAV or WebM with yt-dlp and FFmpeg.
- `POST /api/separate` — run the UVR MDX-Net model through `audio-separator` and return the resulting WAV stems in a ZIP.
- `GET /health` — health check.

## Deploy

This service cannot run on GitHub Pages; it needs a Python/Docker host with FFmpeg, outbound network access and sufficient RAM/disk. Deploy the `decibel-api` directory as a Docker web service using the repository's root `render.yaml`, or run it yourself:

```bash
cd decibel-api
docker build -t decibel-api .
docker run --rm -p 8000:8000 -e PORT=8000 -e DECIBEL_ALLOWED_ORIGINS=https://thereisfarq.github.io decibel-api
```

Then open `https://YOUR-API-HOST/health` and confirm it returns `{"ok":true,...}`.

## Connect the frontend

Edit `decibel/api-config.js` and set `window.DECIBEL_API_BASE` to the deployed HTTPS origin, with no trailing slash. Commit that file. The static UI will then route supported platform links to the server and use the AI separator for uploaded files. With the value left empty, the existing local file conversion and basic stereo split remain available.

## Limits and safety

- Only use links and files you are authorized to download or process; comply with the source platform's terms and applicable copyright law.
- The service limits media duration and file size via environment variables. Do not expose an unrestricted public instance to heavy traffic: add authentication, rate limits, quotas and monitoring before public production use.
- Media is processed in temporary directories; configure host-level disk cleanup and resource limits.
- AI separation requires downloading a model on first use and can be memory/CPU intensive. The service needs enough RAM and disk for the model and intermediate audio files.
- A free API provider is not assumed. Hosting, bandwidth and model inference may incur costs depending on the provider and traffic.
