# Cloudinary Media Architecture

Enterprise-grade media delivery for Duo using **Cloudinary** as the primary storage backend (`MEDIA_STORAGE_BACKEND=cloudinary`).

## Overview

```
Client (Next.js / Flutter)
  → POST multipart → Django upload API
  → cloudinary_upload.upload_*_result()
  → Cloudinary API (optimized upload)
  → { image_url, media? } response
  → stored as URL in PostgreSQL (unchanged schema)

Display
  → Clients apply dynamic transforms via cloudinaryUrl() / cloudinaryDeliveryUrl()
  → f_auto, q_auto:good, progressive, responsive presets
  → No duplicate stored variants
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `CLOUDINARY_CLOUD_NAME` | Cloud name |
| `CLOUDINARY_API_KEY` | API key |
| `CLOUDINARY_API_SECRET` | API secret (server-only) |
| `CLOUDINARY_UPLOAD_PRESET` | Optional unsigned/signed preset |
| `CLOUDINARY_PROFILE_FOLDER` | Default: `duo/profile_photos` |
| `CLOUDINARY_CHAT_FOLDER` | Default: `duo/chat_media` |
| `CLOUDINARY_VERIFICATION_FOLDER` | Default: `duo/verification_selfies` |
| `MEDIA_STORAGE_BACKEND` | `cloudinary` (default) or `r2` |

Admin → Integration settings overrides env when set.

## Upload APIs (unchanged contracts)

| Endpoint | Field | Max size |
|----------|-------|----------|
| `POST /api/profiles/me/upload-photo/` | `image` | 10 MB |
| `POST /api/photos/upload/` | `image` | 10 MB |
| `POST /api/chat/upload/` | `image` | 25 MB |
| Verification selfie | `image` | 10 MB |

**Response (backward compatible):**
```json
{
  "image_url": "https://res.cloudinary.com/...",
  "media": {
    "public_id": "duo/profile_photos/user_1_photo_abc",
    "resource_type": "image",
    "secure_url": "https://...",
    "width": 1080,
    "height": 1350,
    "format": "jpg",
    "bytes": 245000,
    "version": 1710000000
  }
}
```

The `media` object is **additive** — existing clients that only read `image_url` continue to work.

## Upload Optimizations

Applied at upload time:
- `quality: auto:good`
- `fetch_format: auto` (WebP/AVIF where supported)
- `flags: progressive`
- Unique filenames (`overwrite: false`) + CDN `invalidate: true` on replace
- Video: async eager poster (`640×360` JPG)
- Profile replacement deletes previous Cloudinary asset

## Delivery Presets

| Preset | Size | Use case |
|--------|------|----------|
| `thumb` | 96×96 | Tiny previews |
| `avatar` | 128×128 | Avatars, chat list |
| `discover_card` | 480×600 | Discover swipe cards |
| `match_card` | 420×560 | Match cards |
| `chat_preview` | 480×480 | Chat images |
| `gallery` | 720×900 | Profile gallery |
| `verification` | 512×512 | Verification preview |

Transforms are applied **at delivery** via URL — not stored as separate files.

## Security

- MIME type + extension validation
- Blocked executable/script extensions
- Double-extension rejection
- Path traversal prevention in filenames
- Max file sizes enforced
- Image dimension validation (Pillow when available)
- Corrupted image rejection

## Cleanup

`duo_project/media/signals.py` deletes Cloudinary assets when:
- Profile photos are replaced or removed
- Chat messages are deleted
- Photo analysis records are deleted
- Verification selfies are replaced

Logs: `duo.cloudinary`, `duo.media`

## Client Integration

### Next.js
- `lib/cloudinary.ts` — URL builder
- `lib/mediaUrl.ts` — `resolveProfilePhotoUrl`, `resolveAvatarUrl`, `resolveChatMediaUrl`

### Flutter
- `lib/core/media/cloudinary_url.dart`
- `DuoProfile.optimizedDisplayPhoto`, `optimizedAvatarPhoto`, `optimizedProfilePhotos`
- `DuoNetworkImage` applies presets automatically

## R2 Fallback

Set `MEDIA_STORAGE_BACKEND=r2` to use Cloudflare R2. Cloudinary optimizations apply only on the `cloudinary` path.
