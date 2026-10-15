"""Locking an account after repeated wrong passwords.

Three wrong passwords in a row lock the account. It stays locked - however many
more attempts are made, and however long ago - until an administrator unlocks
it from Create User. A correct password before the third strike clears the
count. Administrators can also lock an account by hand.

The user is told: the sign-in page says how many tries are left and when the
account has been locked, and an in-app notification records each lock and
unlock.

Superusers are exempt: their wrong passwords are not counted, they are never
locked (automatically or by hand), and a lock recorded against an account
before it became a superuser does not stop it. Someone always has to be able
to sign in and unlock everyone else.
"""

from django.db import transaction
from django.utils import timezone

from addtouser.models import CustomUser
from notifications.service import employee_label, notify

from .models import AccountLockout

MAX_FAILED_ATTEMPTS = 3

AUTO_LOCK_REASON = f"{MAX_FAILED_ATTEMPTS} failed sign-in attempts"

LOCKED_MESSAGE = (
    "Your account is locked after too many failed sign-in attempts. "
    "Contact the system administrator to unlock it."
)
ADMIN_LOCKED_MESSAGE = (
    "Your account has been locked by the system administrator. "
    "Contact them to unlock it."
)


def _local(moment):
    """For display. This project runs without time zones (USE_TZ off), so
    timestamps are already local; convert only one that carries a zone."""
    return timezone.localtime(moment) if timezone.is_aware(moment) else moment


def applies_to(user) -> bool:
    """Whether the lockout policy covers this account. Superusers are exempt."""
    return not user.is_superuser


def lockout_for(user) -> AccountLockout:
    record, _ = AccountLockout.objects.get_or_create(user=user)
    return record


def locked_message(record: AccountLockout) -> str:
    return ADMIN_LOCKED_MESSAGE if record.locked_by else LOCKED_MESSAGE


def _erp_id(user):
    return CustomUser.objects.filter(authid=user.pk).values_list("erpid", flat=True).first()


def _notify_user(user, event, title, message, actor_user_id=None):
    """In-app notification for the account's owner. Never raises."""
    actor_erp = (
        CustomUser.objects.filter(authid=actor_user_id).values_list("erpid", flat=True).first()
        if actor_user_id else None
    )
    notify(
        recipient_erp_id=_erp_id(user),
        category="account",
        event=event,
        title=title,
        message=message,
        link="/change-password",
        related_id=user.pk,
        actor_erp_id=actor_erp,
    )


def record_failure(user):
    """One more wrong password. Locks the account on the last allowed one.

    Returns None for an exempt (superuser) account: nothing is counted.
    """
    if not applies_to(user):
        return None
    with transaction.atomic():
        record = AccountLockout.objects.select_for_update().get_or_create(user=user)[0]
        if record.is_locked:
            return record
        record.failed_attempts += 1
        record.last_failed_at = timezone.now()
        just_locked = record.failed_attempts >= MAX_FAILED_ATTEMPTS
        if just_locked:
            record.is_locked = True
            record.locked_at = record.last_failed_at
            record.locked_reason = AUTO_LOCK_REASON
            record.locked_by = None
        record.save()

    if just_locked:
        _notify_user(
            user, "locked", "Your account was locked",
            f"Your account was locked at {_local(record.locked_at):%d %b %Y %H:%M} "
            f"after {MAX_FAILED_ATTEMPTS} failed sign-in attempts. If this was not you, "
            "tell the system administrator and change your password once it is unlocked.",
        )
    return record


def attempts_left(record: AccountLockout) -> int:
    return max(MAX_FAILED_ATTEMPTS - record.failed_attempts, 0)


def record_success(user) -> None:
    """A correct password clears the count."""
    AccountLockout.objects.filter(user=user, is_locked=False).exclude(
        failed_attempts=0
    ).update(failed_attempts=0)


def lock(user, by_user_id, reason="") -> AccountLockout:
    if not applies_to(user):
        raise ValueError("Superuser accounts cannot be locked")
    record = lockout_for(user)
    record.is_locked = True
    record.locked_at = timezone.now()
    record.locked_reason = (reason or "Locked by the system administrator")[:200]
    record.locked_by = by_user_id
    record.save()
    _notify_user(
        user, "locked", "Your account was locked",
        f"Your account was locked by {employee_label(_erp_id_of(by_user_id), with_erp=False) or 'the system administrator'}"
        f": {record.locked_reason}.",
        actor_user_id=by_user_id,
    )
    return record


def unlock(user, by_user_id) -> AccountLockout:
    record = lockout_for(user)
    record.is_locked = False
    record.failed_attempts = 0
    record.unlocked_at = timezone.now()
    record.unlocked_by = by_user_id
    record.save()
    _notify_user(
        user, "unlocked", "Your account was unlocked",
        "Your account has been unlocked and you can sign in again. If you did not make "
        "the failed attempts that locked it, change your password now.",
        actor_user_id=by_user_id,
    )
    return record


def require_password_change(user) -> None:
    """After an administrator reset: the user must choose their own password."""
    record = lockout_for(user)
    if not record.must_change_password:
        record.must_change_password = True
        record.save(update_fields=["must_change_password"])


def password_change_required(user) -> bool:
    return AccountLockout.objects.filter(user=user, must_change_password=True).exists()


def clear_password_change(user) -> None:
    AccountLockout.objects.filter(user=user, must_change_password=True).update(
        must_change_password=False
    )


def _erp_id_of(auth_user_id):
    return CustomUser.objects.filter(authid=auth_user_id).values_list("erpid", flat=True).first()


def is_locked(user_id) -> bool:
    return AccountLockout.objects.filter(
        user_id=user_id, is_locked=True, user__is_superuser=False
    ).exists()
