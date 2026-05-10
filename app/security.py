import base64
import hashlib
import hmac
import secrets
import string


PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 260_000
PASSWORD_HASH_SALT_BYTES = 16
PASSWORD_HASH_BYTES = 32


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def _passlib_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(f"{value.replace('.', '+')}{padding}")


def _pbkdf2(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
        dklen=PASSWORD_HASH_BYTES,
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(PASSWORD_HASH_SALT_BYTES)
    digest = _pbkdf2(password, salt, PASSWORD_HASH_ITERATIONS)
    return (
        f"{PASSWORD_HASH_ALGORITHM}"
        f"${PASSWORD_HASH_ITERATIONS}"
        f"${_b64encode(salt)}"
        f"${_b64encode(digest)}"
    )


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith(f"{PASSWORD_HASH_ALGORITHM}$"):
        return _verify_minipbx_password(password, password_hash)
    if password_hash.startswith("$pbkdf2-sha256$"):
        return _verify_passlib_pbkdf2_sha256(password, password_hash)
    return False


def _verify_minipbx_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, digest = password_hash.split("$", 3)
        if algorithm != PASSWORD_HASH_ALGORITHM:
            return False
        expected = _pbkdf2(password, _b64decode(salt), int(iterations))
        return hmac.compare_digest(expected, _b64decode(digest))
    except (TypeError, ValueError):
        return False


def _verify_passlib_pbkdf2_sha256(password: str, password_hash: str) -> bool:
    try:
        empty, algorithm, iterations, salt, digest = password_hash.split("$", 4)
        if empty or algorithm != "pbkdf2-sha256":
            return False
        expected = _pbkdf2(password, _passlib_b64decode(salt), int(iterations))
        return hmac.compare_digest(expected, _passlib_b64decode(digest))
    except (TypeError, ValueError):
        return False


def generate_secret(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def generate_sip_secret(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
