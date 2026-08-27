"""Deprecated compatibility layer for scrypt-based key derivation.

This project does not use scrypt for authentication. Login and registration rely on
Werkzeug's password hashing helpers instead, so this module is intentionally disabled to
avoid import-time issues and any interference with auth flows.
"""
from __future__ import annotations

import os
from typing import Final

__all__ = ["scrypt_derive", "scrypt_verify", "generate_salt"]

_DISABLED_MESSAGE: Final[str] = (
    "scrypt-based key derivation is intentionally disabled for this app; "
    "use werkzeug.security for login and registration."
)


def scrypt_derive(password: bytes, *, salt: bytes, n: int, r: int, p: int, dklen: int = 64, maxmem: int = 0) -> bytes:
    """Raise a clear error instead of attempting any scrypt-backed fallback."""
    raise RuntimeError(_DISABLED_MESSAGE)


def scrypt_verify(password: bytes, *, salt: bytes, n: int, r: int, p: int, dk: bytes, maxmem: int = 0) -> bool:
    """Raise a clear error instead of attempting any scrypt-backed fallback."""
    raise RuntimeError(_DISABLED_MESSAGE)


def generate_salt(length: int = 16) -> bytes:
    """Return a cryptographically secure random salt for the app's non-scrypt routines."""
    return os.urandom(length)
