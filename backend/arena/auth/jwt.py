from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from arena.auth import JWT_ALGORITHM, JWT_EXPIRY_DAYS, JWT_SECRET


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS)
    claims = {"sub": user_id, "exp": expire}
    return jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
