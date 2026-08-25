"""Generates the RS256 signing keypair used to sign/verify access tokens, writing PEM files
to the paths configured in .env (JWT_PRIVATE_KEY_PATH / JWT_PUBLIC_KEY_PATH). The private key
never leaves this service; only the public key is ever published (via /.well-known/jwks.json).

Usage (from iam-service/):
    .venv/Scripts/python.exe scripts/generate_signing_key.py [--force]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402

from app.config import get_settings  # noqa: E402


def main() -> None:
    force = "--force" in sys.argv
    settings = get_settings()
    private_path = Path(settings.JWT_PRIVATE_KEY_PATH)
    public_path = Path(settings.JWT_PUBLIC_KEY_PATH)

    if private_path.exists() and public_path.exists() and not force:
        print(f"Keypair already exists at {private_path} / {public_path} - pass --force to regenerate.")
        return

    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)

    print(f"Wrote private key to {private_path}")
    print(f"Wrote public key to  {public_path}")
    print(f"kid (JWT_KEY_ID)     {settings.JWT_KEY_ID}")


if __name__ == "__main__":
    main()
