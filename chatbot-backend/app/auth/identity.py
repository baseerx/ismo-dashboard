"""Who is asking — established from the dashboard's own login token.

The Django login view (`users.views.UsersView.login_user`) signs a JWT with
Django's SECRET_KEY and hands it to the browser, which keeps it in
localStorage. The browser sends it back here as `Authorization: Bearer <jwt>`.

Verifying that signature is the whole basis of privacy in this service: the
ERP id used for every leave / attendance lookup comes out of the *verified*
token, never out of the request body and never out of anything the language
model produced. A user who edits their cached profile in devtools changes
nothing, because an altered payload no longer matches the signature.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, Header, HTTPException, status

from app.config.settings import settings

logger = logging.getLogger(__name__)


class InvalidIdentity(Exception):
    """Token missing, malformed, expired, or not signed by the dashboard."""


@dataclass(frozen=True)
class Identity:
    erp_id: int
    name: str
    username: Optional[str] = None
    email: Optional[str] = None
    section_id: Optional[int] = None
    section_name: Optional[str] = None
    grade_id: Optional[int] = None
    # Admin is `is_superuser`, deliberately the same test the dashboard UI
    # uses to decide whether to show admin features (see Home.tsx and the
    # chat widget's upload button). One definition, one behaviour.
    is_admin: bool = False

    def describe(self) -> str:
        role = "Administrator" if self.is_admin else "Employee"
        parts = [f"- Name: {self.name}", f"- ERP ID: {self.erp_id}", f"- Role: {role}"]
        if self.section_name:
            parts.append(f"- Section: {self.section_name}")
        return "\n".join(parts)


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _check_expiry(payload: Dict[str, Any]) -> None:
    """The dashboard stamps its own `expires` field instead of a JWT `exp`.

    PyJWT therefore cannot enforce it, so it is enforced here — otherwise a
    token would be valid forever.
    """
    raw = payload.get("expires")
    if not raw:
        raise InvalidIdentity("token carries no expiry")

    try:
        expires = datetime.fromisoformat(str(raw))
    except ValueError as exc:
        raise InvalidIdentity(f"unreadable expiry {raw!r}") from exc

    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)

    leeway = timedelta(seconds=settings.JWT_LEEWAY_SECONDS)
    if datetime.now(timezone.utc) - leeway > expires:
        raise InvalidIdentity("session expired — sign in again")


def decode_token(token: str) -> Identity:
    token = (token or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    if not token:
        raise InvalidIdentity("no token supplied")

    try:
        payload = jwt.decode(
            token,
            settings.DJANGO_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            # The dashboard's payload has no aud/iss/exp claims to verify.
            options={"verify_exp": False, "verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise InvalidIdentity(f"token rejected: {exc}") from exc

    _check_expiry(payload)

    erp_id = _as_int(payload.get("erpid"))
    if not erp_id or erp_id <= 0:
        raise InvalidIdentity("token carries no usable ERP id")

    if not payload.get("is_active", True):
        raise InvalidIdentity("this account is inactive")

    name = (
        payload.get("employee_name")
        or " ".join(filter(None, [payload.get("first_name"), payload.get("last_name")])).strip()
        or payload.get("username")
        or f"ERP {erp_id}"
    )

    return Identity(
        erp_id=erp_id,
        name=name,
        username=payload.get("username"),
        email=payload.get("email"),
        section_id=_as_int(payload.get("section_id")),
        section_name=payload.get("section_name"),
        grade_id=_as_int(payload.get("grade_id")),
        is_admin=bool(payload.get("is_superuser")),
    )


def current_identity(authorization: Optional[str] = Header(default=None)) -> Identity:
    """FastAPI dependency: the signed-in employee, or 401."""
    try:
        identity = decode_token(authorization or "")
    except InvalidIdentity as exc:
        logger.info("rejected request: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    return identity


def require_admin(identity: Identity = Depends(current_identity)) -> Identity:
    """FastAPI dependency for admin-only routes (document training, etc)."""
    if not identity.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an administrator can do this.",
        )
    return identity
