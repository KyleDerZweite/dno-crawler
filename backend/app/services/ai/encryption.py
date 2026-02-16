"""
Encryption utilities for AI provider secrets.

Uses Fernet symmetric encryption for API keys.
The encryption key is derived from SESSION_SECRET or a dedicated AI_ENCRYPTION_KEY
using HKDF for proper key derivation.
"""

import base64
import os
from functools import lru_cache

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Get Fernet instance with encryption key.

    Key is derived from AI_ENCRYPTION_KEY or SESSION_SECRET environment variable
    using HKDF for proper cryptographic key derivation.

    In production/staging, refuses to start without a configured key.
    """
    # Try dedicated AI encryption key first
    key_source = os.environ.get("AI_ENCRYPTION_KEY")

    if not key_source:
        # Fall back to session secret
        key_source = os.environ.get("SESSION_SECRET")

    if not key_source:
        import structlog

        logger = structlog.get_logger()

        environment = os.environ.get("ENVIRONMENT", "development").lower()
        if environment in ("production", "staging"):
            logger.critical(
                "ai_encryption_no_key",
                msg="AI_ENCRYPTION_KEY or SESSION_SECRET must be set in production/staging. "
                "Refusing to use fallback key.",
            )
            raise RuntimeError(
                "AI_ENCRYPTION_KEY or SESSION_SECRET must be set in production/staging environments."
            )

        logger.warning(
            "ai_encryption_no_key",
            msg="No AI_ENCRYPTION_KEY or SESSION_SECRET set. Using fallback key. "
            "This is insecure for production!",
        )
        key_source = "dno-crawler-development-fallback-key-do-not-use-in-production"

    # Derive a 32-byte key using HKDF (proper cryptographic KDF)
    hkdf = HKDF(
        algorithm=SHA256(),
        length=32,
        salt=None,
        info=b"dno-crawler-ai-encryption",
    )
    key_bytes = hkdf.derive(key_source.encode())
    # Fernet requires URL-safe base64 encoded 32-byte key
    fernet_key = base64.urlsafe_b64encode(key_bytes)

    return Fernet(fernet_key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret (API key, etc.).

    Args:
        plaintext: The secret to encrypt

    Returns:
        Encrypted string (base64 encoded)
    """
    if not plaintext:
        return ""

    fernet = _get_fernet()
    encrypted = fernet.encrypt(plaintext.encode())
    return encrypted.decode()


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a secret.

    Args:
        ciphertext: The encrypted secret (base64 encoded)

    Returns:
        Decrypted plaintext

    Raises:
        cryptography.fernet.InvalidToken: If decryption fails
    """
    if not ciphertext:
        return ""

    fernet = _get_fernet()
    decrypted = fernet.decrypt(ciphertext.encode())
    return decrypted.decode()
