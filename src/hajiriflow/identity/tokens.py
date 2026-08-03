import hashlib
import hmac
import secrets


def generate_session_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str, secret: str) -> str:
    return hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def generate_csrf_token(secret: str) -> str:
    nonce = secrets.token_urlsafe(24)
    signature = hash_token(nonce, secret)
    return f"{nonce}.{signature}"


def verify_csrf_token(token: str, secret: str) -> bool:
    try:
        nonce, signature = token.rsplit(".", 1)
    except ValueError:
        return False
    expected = hash_token(nonce, secret)
    return hmac.compare_digest(signature, expected)
