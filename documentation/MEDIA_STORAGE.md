# Duo Media Storage (Cloudflare R2)

Production media pipeline for profile photos, chat media, and verification selfies.

## Current Upload Flow (unchanged API)

| Endpoint | Field | Response |
|----------|-------|----------|
| `POST /api/profiles/me/upload-photo/` | `image` | `{ "image_url": "..." }` |
| `POST /api/photos/upload/` | `image` | `{ "success", "image_url", "analysis" }` |
| `POST /api/chat/upload/` | `image` | `{ "image_url": "..." }` |
| `POST /api/verification/selfie/` | `image` | selfie URL stored on session |

Clients (Flutter, Next.js) continue using `image_url` / `photo_url` string fields — **no API changes**.

## Storage Backends

Set in `.env`:

```env
MEDIA_STORAGE_BACKEND=r2   # or cloudinary (default)
```

### Cloudinary (default)

Existing behavior when `MEDIA_STORAGE_BACKEND=cloudinary` or R2 is not fully configured.

### Cloudflare R2 (production)

```env
MEDIA_STORAGE_BACKEND=r2
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=duo-media
R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
R2_PUBLIC_URL=https://media.yourdomain.com
```

Bind `R2_PUBLIC_URL` to your R2 bucket via Cloudflare CDN custom domain for global edge delivery.

## Image Processing (R2)

On upload, images are automatically:

- EXIF-orientation corrected
- Metadata stripped (re-encoded)
- Converted to **WebP** (except animated GIF)
- Generated in sizes: `thumb` (150px), `small` (400), `medium` (800), `large` (1600), `original` (max 2048)

**Primary `image_url`** returns the **medium** WebP variant (best balance for mobile + web).

### Variant paths

```
duo/profile_photos/{user_id}/{asset_id}/thumb.webp
duo/profile_photos/{user_id}/{asset_id}/medium.webp
...
```

## Chat Media (R2)

| Type | Processing |
|------|------------|
| Images | WebP variants (same as profile) |
| Audio | Stored as-is (webm, ogg, mp3, wav) |
| Video | Stored as-is + optional `thumb.webp` preview |
| GIF | Preserved as animated GIF |

## CDN Cache Headers

| Asset | Cache-Control |
|-------|---------------|
| Image variants (versioned UUID paths) | `public, max-age=31536000, immutable` |
| Audio/video | `public, max-age=86400` |

## Security

- MIME type + extension validation
- Blocked executable extensions (`.exe`, `.php`, `.js`, etc.)
- Max size: 10 MB profile, 25 MB chat
- Path traversal prevention on filenames
- Virus scan hook point: extend `duo_project/media/validation.py`

## Cleanup

When `MEDIA_STORAGE_BACKEND=r2`, orphaned objects are deleted when:

- Profile `photo_url` / `photo_urls` change
- Chat `Message` deleted
- `PhotoAnalysis` deleted
- Verification selfie URL replaced

## Frontend CDN Setup

Add your R2 public domain to:

- **Next.js** `next.config.mjs` → `images.remotePatterns`
- **Flutter** — URLs work directly via `CachedNetworkImage`

## Development

```env
MEDIA_STORAGE_BACKEND=cloudinary   # no R2 credentials needed
# or
MEDIA_STORAGE_BACKEND=r2
R2_AUTO_CREATE_BUCKET=true         # creates bucket on first upload (DEBUG default)
```
