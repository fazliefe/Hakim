from __future__ import annotations

import hashlib
import hmac
import secrets

ITERATIONS = 210_000
MIN_PASSWORD_LENGTH = 6


def password_too_short(password: str) -> bool:
    return len(password or "") < MIN_PASSWORD_LENGTH


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), ITERATIONS)
    return f"pbkdf2${ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iter_s, salt, digest = stored.split("$", 3)
    except ValueError:
        return False
    if scheme != "pbkdf2":
        return False
    try:
        rounds = int(iter_s)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), rounds)
    return hmac.compare_digest(candidate.hex(), digest)
