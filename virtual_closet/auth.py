"""Local-demo password hashing. No plaintext passwords are persisted."""
import hashlib
import hmac
import re
import secrets

ITERATIONS = 600_000

def normalize_username(username):
    username = username.strip().lower()
    if not re.fullmatch(r"[a-z0-9_]{3,32}", username):
        raise ValueError("Use 3–32 letters, numbers or underscores for your username.")
    return username

def hash_password(password):
    if not 10 <= len(password) <= 128:
        raise ValueError("Use a password containing 10–128 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"

def verify_password(password, encoded):
    try:
        algorithm, rounds, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or len(password) > 128:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False
