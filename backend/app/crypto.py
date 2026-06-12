# vibepost - social media scheduling and posting tool
# Copyright (C) 2026  Travis West
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Application-level encryption at rest.

Everything sensitive in the database — platform credentials, user settings,
post text, email addresses — is encrypted with AES-256-GCM before it is
written, so a copied database file (volume snapshot, stray backup, future
file-read bug) yields ciphertext, not live tokens. The master key lives only
in the CREDENTIALS_KEY environment secret, never on the volume.

Design notes:
- Per-purpose subkeys are derived with HKDF, so ciphertext from one column
  can't be replayed into another.
- Values are tagged "enc1:"; key rotation works by setting a new
  CREDENTIALS_KEY, keeping the old one in CREDENTIALS_KEY_OLD for decryption,
  and running `python -m app.manage reencrypt`.
- Email lookups use a keyed blind index (HMAC-SHA256) rather than decrypting
  every row; see email_index().
- This protects the database *file*. An attacker with code execution on the
  live server also has the key — that boundary needs the Vault/KMS design in
  roadmap/security.md.
"""

import base64
import hashlib
import hmac as hmac_mod
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .config import CREDENTIALS_KEY, CREDENTIALS_KEY_OLD

_PREFIX = "enc1:"
_NONCE_LEN = 12


def _master(key_material: str) -> bytes:
    return hashlib.sha256(key_material.encode("utf-8")).digest()


def _derive(key_material: str, purpose: str) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"vibepost-at-rest-v1",
        info=purpose.encode("utf-8"),
    ).derive(_master(key_material))


# Subkeys are derived once per purpose and cached; purposes are static strings.
_key_cache: dict[tuple[str, str], bytes] = {}


def _subkey(key_material: str, purpose: str) -> bytes:
    cache_key = (hashlib.sha256(key_material.encode()).hexdigest()[:16], purpose)
    if cache_key not in _key_cache:
        _key_cache[cache_key] = _derive(key_material, purpose)
    return _key_cache[cache_key]


def encrypt(plaintext: str, purpose: str) -> str:
    nonce = os.urandom(_NONCE_LEN)
    ct = AESGCM(_subkey(CREDENTIALS_KEY, purpose)).encrypt(
        nonce, plaintext.encode("utf-8"), purpose.encode("utf-8")
    )
    return _PREFIX + base64.urlsafe_b64encode(nonce + ct).decode("ascii")


def decrypt(value: str, purpose: str) -> str:
    """Decrypt a tagged value; legacy plaintext (pre-encryption rows mid-
    migration) passes through unchanged."""
    if not value.startswith(_PREFIX):
        return value
    raw = base64.urlsafe_b64decode(value[len(_PREFIX):])
    nonce, ct = raw[:_NONCE_LEN], raw[_NONCE_LEN:]
    keys = [CREDENTIALS_KEY] + ([CREDENTIALS_KEY_OLD] if CREDENTIALS_KEY_OLD else [])
    last_error: Exception | None = None
    for key_material in keys:
        try:
            pt = AESGCM(_subkey(key_material, purpose)).decrypt(
                nonce, ct, purpose.encode("utf-8")
            )
            return pt.decode("utf-8")
        except Exception as exc:  # InvalidTag from any non-matching key
            last_error = exc
    raise ValueError(f"Cannot decrypt value for purpose {purpose!r}") from last_error


def is_encrypted(value: str) -> bool:
    return isinstance(value, str) and value.startswith(_PREFIX)


def email_index(email: str) -> str:
    """Deterministic keyed hash of an email for lookups and uniqueness.

    Keyed (unlike a bare SHA-256) so a database copy doesn't allow offline
    dictionary checks of who has an account."""
    key = _subkey(CREDENTIALS_KEY, "email-index")
    return hmac_mod.new(key, email.strip().lower().encode("utf-8"), hashlib.sha256).hexdigest()


def email_index_candidates(email: str) -> list[str]:
    """Index values under the current and (if set) previous key, so lookups
    keep working mid-rotation until `manage reencrypt` has run."""
    out = [email_index(email)]
    if CREDENTIALS_KEY_OLD:
        key = _subkey(CREDENTIALS_KEY_OLD, "email-index")
        out.append(
            hmac_mod.new(key, email.strip().lower().encode("utf-8"), hashlib.sha256).hexdigest()
        )
    return out
