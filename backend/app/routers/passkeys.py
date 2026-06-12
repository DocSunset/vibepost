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

"""WebAuthn passkeys: registration and usernameless sign-in.

We store only credential public keys; private keys never leave the user's
authenticator. Challenges live in memory with a short TTL (single-process
deployment, same trade-off as the OAuth state store in auth.py).
"""

import json
import secrets
import threading
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from ..config import WEBAUTHN_ORIGINS, WEBAUTHN_RP_ID, WEBAUTHN_RP_NAME
from ..database import get_db
from ..models import User, WebAuthnCredential
from ..schemas import (
    PasskeyLoginVerifyRequest,
    PasskeyRead,
    PasskeyRegisterVerifyRequest,
    UserRead,
)
from ..security import (
    create_session_token,
    get_current_user,
    login_limiter,
    set_session_cookie,
)

router = APIRouter(prefix="/account/passkeys", tags=["passkeys"])

CHALLENGE_TTL_SECONDS = 300


class _ChallengeStore:
    """Short-lived, single-use challenges keyed by an opaque id."""

    def __init__(self):
        self._items: dict[str, tuple[bytes, float]] = {}
        self._lock = threading.Lock()

    def put(self, key: str, challenge: bytes) -> None:
        now = time.monotonic()
        with self._lock:
            self._items = {
                k: v for k, v in self._items.items()
                if v[1] > now - CHALLENGE_TTL_SECONDS
            }
            self._items[key] = (challenge, now)

    def pop(self, key: str) -> bytes | None:
        with self._lock:
            item = self._items.pop(key, None)
        if item is None or item[1] < time.monotonic() - CHALLENGE_TTL_SECONDS:
            return None
        return item[0]


_register_challenges = _ChallengeStore()
_login_challenges = _ChallengeStore()


def _options_response(options) -> Response:
    return Response(content=options_to_json(options), media_type="application/json")


@router.post("/register/options")
def register_options(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.query(WebAuthnCredential).filter(WebAuthnCredential.user_id == user.id).all()
    options = generate_registration_options(
        rp_id=WEBAUTHN_RP_ID,
        rp_name=WEBAUTHN_RP_NAME,
        user_id=str(user.id).encode("utf-8"),
        user_name=user.email,
        # Discoverable credential, so sign-in needs no email typed first
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id))
            for c in existing
        ],
    )
    _register_challenges.put(f"user:{user.id}", options.challenge)
    return _options_response(options)


@router.post("/register/verify", response_model=PasskeyRead)
def register_verify(
    body: PasskeyRegisterVerifyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    challenge = _register_challenges.pop(f"user:{user.id}")
    if challenge is None:
        raise HTTPException(400, "Registration session expired — try again")
    try:
        verification = verify_registration_response(
            credential=body.credential,
            expected_challenge=challenge,
            expected_rp_id=WEBAUTHN_RP_ID,
            expected_origin=WEBAUTHN_ORIGINS,
        )
    except InvalidRegistrationResponse:
        raise HTTPException(400, "Passkey registration could not be verified")
    credential_id = bytes_to_base64url(verification.credential_id)
    if db.query(WebAuthnCredential).filter(
        WebAuthnCredential.credential_id == credential_id
    ).first():
        raise HTTPException(400, "This passkey is already registered")
    transports = body.credential.get("response", {}).get("transports") or []
    passkey = WebAuthnCredential(
        user_id=user.id,
        credential_id=credential_id,
        public_key=bytes_to_base64url(verification.credential_public_key),
        sign_count=verification.sign_count,
        transports=",".join(t for t in transports if isinstance(t, str)),
        label=(body.label or "").strip()[:100] or "Passkey",
    )
    db.add(passkey)
    db.commit()
    db.refresh(passkey)
    return passkey


@router.get("", response_model=list[PasskeyRead])
def list_passkeys(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(WebAuthnCredential)
        .filter(WebAuthnCredential.user_id == user.id)
        .order_by(WebAuthnCredential.created_at)
        .all()
    )


@router.delete("/{passkey_id}")
def delete_passkey(
    passkey_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    passkey = (
        db.query(WebAuthnCredential)
        .filter(WebAuthnCredential.id == passkey_id, WebAuthnCredential.user_id == user.id)
        .first()
    )
    if not passkey:
        raise HTTPException(404, "Passkey not found")
    db.delete(passkey)
    db.commit()
    return {"ok": True}


@router.post("/login/options")
def login_options(request: Request):
    login_limiter.check(request)
    options = generate_authentication_options(
        rp_id=WEBAUTHN_RP_ID,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    challenge_id = secrets.token_urlsafe(16)
    _login_challenges.put(challenge_id, options.challenge)
    payload = json.loads(options_to_json(options))
    return {"challenge_id": challenge_id, "options": payload}


@router.post("/login/verify", response_model=UserRead)
def login_verify(
    body: PasskeyLoginVerifyRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    login_limiter.check(request)
    challenge = _login_challenges.pop(body.challenge_id)
    if challenge is None:
        raise HTTPException(400, "Sign-in session expired — try again")
    credential_id = body.credential.get("id")
    passkey = (
        db.query(WebAuthnCredential)
        .filter(WebAuthnCredential.credential_id == credential_id)
        .first()
    ) if isinstance(credential_id, str) else None
    if not passkey:
        raise HTTPException(403, "Passkey not recognized")
    try:
        verification = verify_authentication_response(
            credential=body.credential,
            expected_challenge=challenge,
            expected_rp_id=WEBAUTHN_RP_ID,
            expected_origin=WEBAUTHN_ORIGINS,
            credential_public_key=base64url_to_bytes(passkey.public_key),
            credential_current_sign_count=passkey.sign_count,
        )
    except InvalidAuthenticationResponse:
        raise HTTPException(403, "Passkey could not be verified")
    passkey.sign_count = verification.new_sign_count
    passkey.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    user = passkey.user
    set_session_cookie(response, create_session_token(user))
    return user
