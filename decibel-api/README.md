# Decibel API (optional, not deployed)

**Zero-cost product rule:** the public Decibel site must not depend on a paid server, paid API, usage-based inference, or a service that can generate surprise bills. The API in this folder is retained as optional experimental source only. It is not required by GitHub Pages and is not deployed.

The public site keeps `window.DECIBEL_API_BASE` empty in `decibel/api-config.js`, so no API host is called. Local file conversion and the basic stereo-based split are the no-server paths.

## Optional endpoints

If you choose to self-host this yourself later, this service provides:
- `POST /api/info` — inspect supported public media links.
- `POST /api/convert` — retrieve and convert supported links to MP3, MP4, WAV or WebM with yt-dlp and FFmpeg.
- `POST /api/separate` — run UVR MDX-Net through `audio-separator` and return WAV stems in a ZIP.
- `GET /health` — health check.

## Run locally for development

Requires Docker, FFmpeg in the image, outbound network access, and enough RAM/disk for the AI model:

```bash
cd decibel-api
docker build -t decibel-api .
docker run --rm -p 8000:8000 -e PORT=8000 -e DECIBEL_ALLOWED_ORIGINS=https://thereisfarq.github.io decibel-api
```

To connect a privately managed API for testing, set `window.DECIBEL_API_BASE` in `decibel/api-config.js` to its HTTPS origin. Do not do this for the public site unless you have independently verified that hosting and inference will remain free and have explicit budget protections. This repository intentionally contains no one-click paid-host deployment manifest.

## Limits and safety

- Platform-link conversion cannot be guaranteed for every site; platforms may block retrieval or restrict downloads.
- Only use links and files you are authorized to download or process; comply with source-platform terms and copyright law.
- AI separation can require substantial RAM, CPU, disk, and model downloads.
- Browser-only processing is slower than native FFmpeg and depends on device/browser capabilities.
- No paid hosting or inference is assumed to be free. This API is not a production public endpoint.
