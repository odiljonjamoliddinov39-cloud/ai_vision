# Enterprise streaming transport

This layer changes video transport only. Detection, tracking, recognition,
warehouse counting, databases, analytics, and dashboard business logic retain
their existing interfaces.

## Data path

1. MediaMTX pulls each camera/NVR RTSP URL once.
2. One FFmpeg process per camera reads the internal MediaMTX source and decodes
   it once.
3. That process publishes:
   - `camera-<id>-ai`: configurable 960 px / 6 FPS H.264 stream.
   - `camera-<id>-dashboard`: configurable 1080p / 20 FPS H.264 stream.
   - JPEG preview/snapshot frames through the existing shared-frame adapter.
4. MediaMTX exposes the dashboard rendition over WebRTC/WHEP and low-latency
   HLS. Multiple browser viewers never open additional camera connections.
5. MediaMTX records the original source without passing recording through the
   AI decode path. Files are organized as camera/year/month/day/time.

## Start

Set public browser endpoints in `.env`:

```dotenv
MEDIAMTX_PUBLIC_WEBRTC_URL=https://video.example.com
MEDIAMTX_PUBLIC_HLS_URL=https://video.example.com/hls
```

Then start the stack:

```shell
docker compose up -d --build
```

The compose deployment enables enterprise streaming by default. Set
`AI_VISION_ENTERPRISE_STREAMING=false` to roll back to the previous transport
without changing any camera, AI, tracking, or warehouse configuration.
Until the MediaMTX health check is confirmed, routing fails open to the existing
transport. Set `MEDIAMTX_STRICT_STARTUP=true` only after the sidecar and its
internal DNS name are verified.

## Control API

- `POST /api/v2/channels/{id}/stream/start`
- `POST /api/v2/channels/{id}/stream/stop`
- `POST /api/v2/channels/{id}/stream/restart`
- `GET /api/v2/channels/{id}/stream/health`
- `GET /api/v2/channels/{id}/stream/routes`
- `GET /api/v2/channels/{id}/stream/snapshot`
- `GET /api/v2/channels/{id}/recording/status`
- `GET /api/v2/streams/health`

The route response contains internal AI RTSP, dashboard RTSP, WebRTC/WHEP, and
HLS URLs. Existing dashboard JPEG/WebSocket endpoints remain available during
the staged migration.

## Health and isolation

The stream status reports FPS, resolution, bitrate, frame age/latency,
reconnects, decode errors, and frozen streams. MediaMTX reconnects upstream
sources independently. FFmpeg has an I/O timeout and restarts with exponential
backoff. A failed camera cannot terminate the detector or another camera.
