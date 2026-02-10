from __future__ import annotations
import base64
import json
import os
from dataclasses import dataclass
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# A stable, app-specific salt so the same passphrase works across restarts on the same machine.
# If you want per-installation salt, store it in /data once instead.
APP_SALT = b"ucm-site-provisioner::salt::v1"

def _derive_key(passphrase: str) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=APP_SALT,
        iterations=200_000,
    )
    return kdf.derive(passphrase.encode("utf-8"))

def encrypt_json(passphrase: str, payload: dict) -> bytes:
    key = _derive_key(passphrase)
    aes = AESGCM(key)
    nonce = os.urandom(12)
    pt = json.dumps(payload).encode("utf-8")
    ct = aes.encrypt(nonce, pt, associated_data=None)
    return nonce + ct

def decrypt_json(passphrase: str, blob: bytes) -> dict:
    key = _derive_key(passphrase)
    aes = AESGCM(key)
    nonce = blob[:12]
    ct = blob[12:]
    pt = aes.decrypt(nonce, ct, associated_data=None)
    return json.loads(pt.decode("utf-8"))