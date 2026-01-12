"""
Encryption utilities for AI provider secrets.

Uses Fernet symmetric encryption for API keys and OAuth tokens.
The encryption key is derived from SESSION_SECRET or a dedicated AI_ENCRYPTION_KEY.
"""

import base64
import hashlib
import os
from functools import lru_cache

from cryptography.fernet import Fernet


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Get Fernet instance with encryption key.

    Key is derived from AI_ENCRYPTION_KEY or SESSION_SECRET environment variable.
    """
    # Try dedicated AI encryption key first
    key_source = os.environ.get("AI_ENCRYPTION_KEY")

    if not key_source:
        # Fall back to session secret
        key_source = os.environ.get("SESSION_SECRET")

    if not key_source:
        # Generate a warning-level key for development
        # In production, this should be set properly
        import structlog
        logger = structlog.get_logger()
        logger.warning(
            "ai_encryption_no_key",
            msg="No AI_ENCRYPTION_KEY or SESSION_SECRET set. Using fallback key. "
                "This is insecure for production!"
        )
        key_source = "dno-crawler-development-fallback-key-do-not-use-in-production"

    # Derive a 32-byte key using SHA256
    key_bytes = hashlib.sha256(key_source.encode()).digest()
    # Fernet requires URL-safe base64 encoded 32-byte key
    fernet_key = base64.urlsafe_b64encode(key_bytes)

    return Fernet(fernet_key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret (API key, OAuth token, etc.).

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
