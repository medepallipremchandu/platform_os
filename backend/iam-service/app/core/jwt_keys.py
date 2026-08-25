"""Loads the RS256 signing keypair from disk (paths from Settings) and builds the JWKS
document. The private key never leaves iam-service; only the public key is published."""
import base64
from functools import lru_cache

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from app.config import get_settings


def _b64url_uint(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    data = value.to_bytes(length, "big")
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@lru_cache
def load_private_key() -> RSAPrivateKey:
    settings = get_settings()
    with open(settings.JWT_PRIVATE_KEY_PATH, "rb") as f:
        key = serialization.load_pem_private_key(f.read(), password=None)
    if not isinstance(key, RSAPrivateKey):
        raise ValueError("JWT_PRIVATE_KEY_PATH does not contain an RSA private key")
    return key


@lru_cache
def load_public_key() -> RSAPublicKey:
    settings = get_settings()
    with open(settings.JWT_PUBLIC_KEY_PATH, "rb") as f:
        key = serialization.load_pem_public_key(f.read())
    if not isinstance(key, RSAPublicKey):
        raise ValueError("JWT_PUBLIC_KEY_PATH does not contain an RSA public key")
    return key


def build_jwks() -> dict:
    settings = get_settings()
    public_key = load_public_key()
    numbers = public_key.public_numbers()
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": settings.JWT_KEY_ID,
        "n": _b64url_uint(numbers.n),
        "e": _b64url_uint(numbers.e),
    }
    return {"keys": [jwk]}
