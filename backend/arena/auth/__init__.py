import os

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
# SESSION_KEY_SECRET signs game session keys (nks_...). Falls back to JWT_SECRET
# so existing deployments work without config changes. Set it independently to
# allow rotating one secret without invalidating the other.
SESSION_KEY_SECRET = os.environ.get("SESSION_KEY_SECRET", JWT_SECRET)
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 7
