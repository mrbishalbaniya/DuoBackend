# Security hardening documentation

See deployment checklist in `.env.example` for production security variables.

## Key controls

- `REQUIRE_EMAIL_OTP_FOR_REGISTRATION` — enforce email OTP before register (default: on when `DEBUG=False`)
- `TRUSTED_MEDIA_HOSTS` — extra comma-separated hosts allowed in chat `image_url`
- JWT refresh token blacklist after rotation (`rest_framework_simplejwt.token_blacklist`)
- Rate limits: `auth` 10/min, `upload` 30/hour, `swipe` 120/hour
- Profile PII stripped for non-owners (email, phone, location privacy)
- Chat media URLs restricted to Cloudinary/R2/trusted CDN hosts
- Wallet top-up activation is atomic with amount verification on eSewa callback
- WebSocket throttle/registry fail closed when Redis unavailable (production)
- Security audit logging via `duo.security` logger

## Migrations

After deploy, run:

```bash
python manage.py migrate
```

This applies `token_blacklist` tables required for refresh token rotation blacklist.
