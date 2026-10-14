"""The password policy, enforced on the server.

The same rules as frontend/src/utils/passwordPolicy.ts, which only guides the
user as they type. This is what actually decides: every place that sets a
password - creating a user, signing up, changing a password, an administrator
resetting one - calls `password_problems` and refuses the password if it
returns anything.

On top of the browser's short list of common passwords, Django's own list of
20,000 is checked too.
"""

import re
import secrets
import string

from django.contrib.auth.password_validation import CommonPasswordValidator
from django.core.exceptions import ValidationError

MIN_LENGTH = 12
MAX_LENGTH = 128

# The browser's list, kept identical so the checklist and the server agree.
COMMON_PASSWORDS = {
    "password", "password1", "password123", "passw0rd", "p@ssword", "p@ssw0rd",
    "123456", "1234567", "12345678", "123456789", "1234567890", "12345",
    "qwerty", "qwerty123", "qwertyuiop", "asdfghjkl", "zxcvbnm",
    "111111", "000000", "654321", "abc123", "abcd1234", "a1b2c3d4",
    "iloveyou", "admin", "admin123", "administrator", "root", "toor",
    "welcome", "welcome1", "welcome123", "letmein", "monkey", "dragon",
    "sunshine", "princess", "football", "baseball", "master", "shadow",
    "superman", "trustno1", "changeme", "secret", "default", "test123",
    "pakistan", "pakistan123", "islamabad", "karachi", "lahore",
    "ismo", "ismo123", "ismo@123", "hris", "hris123", "leave123",
}

SEQUENCE_SOURCES = (
    "abcdefghijklmnopqrstuvwxyz",
    "0123456789",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
)
SEQUENCE_RUN = 4

_django_common = CommonPasswordValidator()


def _has_sequence(lowered: str) -> bool:
    for source in SEQUENCE_SOURCES:
        for haystack in (source, source[::-1]):
            for start in range(len(haystack) - SEQUENCE_RUN + 1):
                if haystack[start:start + SEQUENCE_RUN] in lowered:
                    return True
    return False


def _personal_tokens(username="", email="", first_name="", last_name="", erp_id="") -> list:
    """Details an attacker can look up. The email's domain is left out, or
    everyone at the same organisation would trip on it."""
    raw = [username, first_name, last_name, erp_id, (email or "").split("@")[0]]
    return [
        value for value in (str(item or "").strip().lower() for item in raw)
        if len(value) >= 3
    ]


def password_problems(password, *, username="", email="", first_name="", last_name="",
                      erp_id="", current_password=None) -> list:
    """Every rule the password breaks, as sentences. Empty means acceptable."""
    password = password if isinstance(password, str) else ""
    lowered = password.lower()
    problems = []

    if len(password) < MIN_LENGTH:
        problems.append(f"Use at least {MIN_LENGTH} characters")
    if len(password) > MAX_LENGTH:
        problems.append(f"Use no more than {MAX_LENGTH} characters")
    if not re.search(r"[A-Z]", password):
        problems.append("Include an uppercase letter (A-Z)")
    if not re.search(r"[a-z]", password):
        problems.append("Include a lowercase letter (a-z)")
    if not re.search(r"[0-9]", password):
        problems.append("Include a number (0-9)")
    if not re.search(r"[^A-Za-z0-9]", password):
        problems.append("Include a special character (e.g. ! @ # $ % & *)")
    if re.search(r"\s", password):
        problems.append("Do not use spaces or tabs")
    if re.search(r"(.)\1{2,}", password):
        problems.append("Do not repeat a character 3 or more times in a row")
    if password and _has_sequence(lowered):
        problems.append("Avoid obvious sequences such as abcd, 1234 or qwerty")

    common = lowered in COMMON_PASSWORDS
    if password and not common:
        try:
            _django_common.validate(password)
        except ValidationError:
            common = True
    if common:
        problems.append("That password is too common - choose another")

    tokens = _personal_tokens(username, email, first_name, last_name, erp_id)
    if password and any(token in lowered for token in tokens):
        problems.append("Do not include your name, username, email or ERP ID")

    if current_password is not None and password and password == current_password:
        problems.append("Choose a password different from the current one")

    return problems


def generate_password(length: int = 16, **details) -> str:
    """A random password that satisfies the policy, for administrator resets."""
    # No look-alikes (I l 1, O 0), so a password read out or copied by hand
    # survives the trip.
    alphabet = "".join(
        ch for ch in string.ascii_letters + string.digits if ch not in "Il1O0"
    ) + "!@#$%&*?-_+="
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if not password_problems(candidate, **details):
            return candidate
