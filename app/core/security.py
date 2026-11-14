import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import settings

# Key prefixes for clarity and security
PUBLIC_KEY_PREFIX = "pk_live_"
SECRET_KEY_PREFIX = "sk_live_"


def generate_public_key() -> str:
    """Generate a 32-character hex public key for platform script tag installation."""
    return f"{PUBLIC_KEY_PREFIX}{secrets.token_hex(16)}"


def generate_secret_key() -> str:
    """Generate a 48-character hex private integration key for server-to-server auth."""
    return f"{SECRET_KEY_PREFIX}{secrets.token_hex(24)}"


def hash_secret_key(secret_key: str) -> str:
    """Hash private integration key before storing in database for safe verification."""
    return hashlib.sha256(secret_key.encode("utf-8")).hexdigest()


def verify_secret_key(plain_secret_key: str, hashed_key: str) -> bool:
    """Verify integration key against hashed storage."""
    return secrets.compare_digest(hash_secret_key(plain_secret_key), hashed_key)


def hash_password(password: str) -> str:
    """Hash plain password using sha256 + salt (or bcrypt)."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against stored salt$hash."""
    try:
        salt, stored_hash = hashed_password.split("$")
        computed_key = hashlib.pbkdf2_hmac(
            "sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000
        )
        return secrets.compare_digest(computed_key.hex(), stored_hash)
    except Exception:
        return False


def create_access_token(
    subject: str | Any,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create signed JWT access token."""
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "sub": str(subject),
    }
    if extra_claims:
        to_encode.update(extra_claims)

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate signed JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError as e:
        raise ValueError(f"Invalid or expired token: {e!s}")
