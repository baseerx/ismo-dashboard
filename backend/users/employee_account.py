"""Fields on the Add Employee form that are not plain `employees` columns.

Date of birth is stored on the employee row. The email address and the date
joined belong to the login account in `auth_user`, which is tied to an employee
through the `profiles` table (erpid to authid). An employee record can exist
before anyone creates a login for them, so those two are applied only when an
account is actually mapped, and the caller is told when it was not.
"""

import re
from datetime import date, datetime, time

from django.contrib.auth.models import User

from addtouser.models import CustomUser

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

# An employee is an adult, and nobody on the payroll was born before these.
MIN_AGE_YEARS = 18
MAX_AGE_YEARS = 75
# Nobody joined before they could work.
MIN_WORKING_AGE_YEARS = 16


def _as_date(value):
    """A date from what the form sends, or None if it is not one."""
    text = str(value or "").strip()
    if not text:
        return None
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text[:10], pattern).date()
        except ValueError:
            continue
    return None


def parse_dob(value):
    """Returns (dob, error). Both None means the field was left empty."""
    text = str(value or "").strip()
    if not text:
        return None, None

    parsed = _as_date(text)
    if parsed is None:
        return None, "Date of birth is not a valid date"
    if parsed > date.today():
        return None, "Date of birth cannot be in the future"

    years = (date.today() - parsed).days / 365.25
    if years < MIN_AGE_YEARS:
        return None, f"An employee must be at least {MIN_AGE_YEARS}"
    if years > MAX_AGE_YEARS:
        return None, f"Check the date of birth - that is over {MAX_AGE_YEARS} years ago"
    return parsed, None


def parse_email(value):
    """Returns (email, error). Both None means the field was left empty."""
    text = str(value or "").strip().lower()
    if not text:
        return None, None
    if not EMAIL.match(text):
        return None, "That does not look like an email address"
    if len(text) > 254:
        return None, "That email address is too long"
    return text, None


def parse_date_joined(value, dob=None):
    """Returns (date_joined, error). Both None means the field was left empty."""
    text = str(value or "").strip()
    if not text:
        return None, None

    parsed = _as_date(text)
    if parsed is None:
        return None, "Date joined is not a valid date"
    if parsed > date.today():
        return None, "Date joined cannot be in the future"
    if dob and (parsed - dob).days < MIN_WORKING_AGE_YEARS * 365:
        return None, (
            f"Date joined is before the employee turned {MIN_WORKING_AGE_YEARS}"
        )
    return parsed, None


def account_for(erp_id):
    """The login account mapped to an ERP id, or None when there is not one."""
    try:
        erp = int(erp_id)
    except (TypeError, ValueError):
        return None

    auth_id = (
        CustomUser.objects.filter(erpid=erp).values_list("authid", flat=True).first()
    )
    if not auth_id:
        return None
    return User.objects.filter(pk=auth_id).first()


def email_taken_by_another(email, account) -> bool:
    """True when a different account already uses this address."""
    if not email:
        return False
    others = User.objects.filter(email__iexact=email)
    if account is not None:
        others = others.exclude(pk=account.pk)
    return others.exists()


def apply_account_fields(erp_id, email, date_joined):
    """Writes the email and date joined onto the mapped login account.

    Returns a note when there was nothing to write them to, so the screen can
    say so rather than pretending they were saved.
    """
    if email is None and date_joined is None:
        return None

    account = account_for(erp_id)
    if account is None:
        return (
            "The employee was saved, but the email address and date joined were "
            "not: no login account is linked to this ERP ID yet. Create the "
            "account first from Create User."
        )

    changed = []
    if email is not None and account.email != email:
        account.email = email
        changed.append("email")
    if date_joined is not None:
        # Keep whatever time of day the account already carried; the form only
        # asks for a date, and rewriting it to midnight loses information.
        existing_time = (
            account.date_joined.timetz() if account.date_joined else time(0, 0)
        )
        replacement = datetime.combine(date_joined, existing_time)
        if account.date_joined != replacement:
            account.date_joined = replacement
            changed.append("date_joined")

    if changed:
        account.save(update_fields=changed)
    return None
