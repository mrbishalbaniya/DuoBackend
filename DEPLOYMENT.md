# Duo — production environment variables
# Copy values into Render (backend) and Vercel (frontend) dashboards.

## Backend (Render)

| Variable | Example | Required |
|----------|---------|----------|
| `DEBUG` | `False` | Yes |
| `SECRET_KEY` | `<50+ char random string>` | Yes |
| `DATABASE_URL` | (auto from Render Postgres) | Yes |
| `ALLOWED_HOSTS` | (auto from Render service host) | Yes |
| `FRONTEND_URL` | `https://duonepal.vercel.app` | Yes |
| `CORS_ALLOWED_ORIGINS` | `https://duonepal.vercel.app` | Yes |
| `REDIS_URL` | (auto from Render Redis) | Recommended |
| `GOOGLE_OAUTH_CLIENT_ID` | `*.apps.googleusercontent.com` | Yes |
| `GOOGLE_OAUTH_CLIENT_SECRET` | `GOCSPX-...` | Yes |
| `GOOGLE_OAUTH_REDIRECT_URI` | `https://duonepal.vercel.app/api/auth/google/callback` | Yes |
| `GOOGLE_OAUTH_ALLOWED_REDIRECT_URIS` | `https://duonepal.vercel.app/api/auth/google/callback,https://<backend>.onrender.com/api/auth/google/callback/` | Yes |
| `CLOUDINARY_CLOUD_NAME` | | Yes |
| `CLOUDINARY_API_KEY` | | Yes |
| `CLOUDINARY_API_SECRET` | | Yes |
| `CLOUDINARY_UPLOAD_PRESET` | | Yes |
| `ESEWA_PRODUCT_CODE` | | Yes (prod) |
| `ESEWA_SECRET_KEY` | | Yes (prod) |
| `ESEWA_SUCCESS_URL` | `https://<backend>/api/subscriptions/esewa/success/` | Yes |
| `ESEWA_FAILURE_URL` | `https://<backend>/api/subscriptions/esewa/failure/` | Yes |
| `EMAIL_HOST_USER` | Gmail address | Yes |
| `EMAIL_HOST_PASSWORD` | Gmail app password | Yes |
| `SENTRY_DSN` | `https://...@sentry.io/...` | Optional |

**Health check:** `GET https://<backend>/health/` → `{"status":"ok"}`

---

## Frontend (Vercel)

| Variable | Example | Required |
|----------|---------|----------|
| `NEXT_PUBLIC_API_URL` | `https://duo-backend.onrender.com/api` | Yes |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Same as backend client ID | Yes |
| `NEXT_PUBLIC_GOOGLE_REDIRECT_URI` | `https://duonepal.vercel.app/api/auth/google/callback` | Yes |
| `NEXT_PUBLIC_SENTRY_DSN` | | Optional |
| `SENTRY_AUTH_TOKEN` | For source maps upload | Optional |

---

## Mobile (Expo / EAS)

| Variable | Example | Required |
|----------|---------|----------|
| `EXPO_PUBLIC_API_URL` | `https://duo-backend.onrender.com/api` | Yes (prod builds) |
| `EXPO_PUBLIC_GOOGLE_CLIENT_ID` | Web client ID from Google Console | Yes |

Add redirect URI in Google Console: `duomobile://` (Expo scheme from `app.json`).

---

## Google Cloud Console

1. **APIs & Services → Credentials → OAuth 2.0 Client**
2. **Authorized redirect URIs:**
   - `https://<vercel-app>/api/auth/google/callback`
   - `https://<backend>.onrender.com/api/auth/google/callback/`
   - `https://auth.expo.io/@<expo-username>/duomobile` (Expo Go dev)
   - `duomobile://` (standalone builds)

---

## Post-deploy smoke test

1. `GET /health/` on backend
2. Register + login on web
3. Discover → swipe → match
4. Chat: send message, confirm real-time delivery
5. Upload profile photo
6. Google sign-in (web + mobile)
7. Logout clears session

---

## Local development

```bash
# Backend (port 8001 for frontend, 8000 for mobile default)
cd DuoBackend && python manage.py runserver 8001

# Frontend
cd DuoFrontend && npm run dev

# Mobile
cd DuoMobile && npm start
```

Fill `DuoBackend/.env` from `.env.example` with real Cloudinary, Gmail, and Google credentials.
