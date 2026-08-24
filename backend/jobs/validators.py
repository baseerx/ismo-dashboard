"""Validation for an internal job application.

The form checks the same things in the browser for immediate feedback, but this
is the copy that decides: a POST can be made without the page, so anything the
browser refuses has to be refused here too.

Errors come back keyed by field, and education errors keyed by row index, so
the form can put each message next to the input that caused it rather than
showing one banner for the whole submission.
"""

import re
from datetime import date
from typing import Any, Dict, List, Tuple

from .models import InternalJobApplication

# Grid rows a person can add. Generous for a career, small enough that a script
# cannot post ten thousand of them.
MAX_EDUCATION_ROWS = 15

# The oldest graduation year worth accepting, and how far ahead an in-progress
# degree may be expected to finish.
EARLIEST_GRADUATION_YEAR = 1950
GRADUATION_YEARS_AHEAD = 7

EMAIL = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")

# 13 digits, conventionally written 12345-1234567-1.
CNIC_DIGITS = 13

# Pakistani numbers reach 12 digits with the country code (923001234567); the
# range also accepts a landline with an area code, and any of the usual
# separators, because people type these however they please.
PHONE_MIN_DIGITS = 10
PHONE_MAX_DIGITS = 15


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalise_cnic(value: Any) -> str:
    """Digits only, then written back as 12345-1234567-1."""
    digits = re.sub(r"\D", "", _text(value))
    if len(digits) != CNIC_DIGITS:
        return _text(value)
    return f"{digits[:5]}-{digits[5:12]}-{digits[12]}"


def normalise_phone(value: Any) -> str:
    """Keeps a leading +, drops everything that is not a digit."""
    raw = _text(value)
    digits = re.sub(r"\D", "", raw)
    return f"+{digits}" if raw.startswith("+") else digits


def _require(errors: Dict[str, str], field: str, value: str, label: str, maximum: int) -> str:
    if not value:
        errors[field] = f"{label} is required"
    elif len(value) > maximum:
        errors[field] = f"{label} must be {maximum} characters or fewer"
    return value


def validate_application(data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Returns (cleaned, errors). `errors` is empty when the payload is usable."""
    errors: Dict[str, Any] = {}
    cleaned: Dict[str, Any] = {}

    # --- section 1 --------------------------------------------------------
    try:
        cleaned["target_job_req_id"] = int(data.get("target_job_req_id") or 0)
    except (TypeError, ValueError):
        cleaned["target_job_req_id"] = 0
    if not cleaned["target_job_req_id"]:
        errors["target_job_req_id"] = "Select the vacancy you are applying for"

    cleaned["emp_full_name"] = _require(
        errors, "emp_full_name", _text(data.get("emp_full_name")), "Employee full name", 150
    )
    if cleaned["emp_full_name"] and len(cleaned["emp_full_name"]) < 3:
        errors["emp_full_name"] = "Employee full name looks too short"

    try:
        cleaned["emp_id"] = int(data.get("emp_id") or 0)
    except (TypeError, ValueError):
        cleaned["emp_id"] = 0
    if cleaned["emp_id"] <= 0:
        errors["emp_id"] = "Employee ID must be a number"

    cleaned["current_dept_code"] = _require(
        errors, "current_dept_code", _text(data.get("current_dept_code")), "Current department", 200
    )
    cleaned["current_job_title"] = _require(
        errors, "current_job_title", _text(data.get("current_job_title")), "Current position title", 200
    )
    cleaned["current_supervisor_id"] = _require(
        errors, "current_supervisor_id", _text(data.get("current_supervisor_id")), "Current supervisor name", 150
    )

    supervisor_erp = data.get("current_supervisor_erp_id")
    try:
        cleaned["current_supervisor_erp_id"] = int(supervisor_erp) if supervisor_erp else None
    except (TypeError, ValueError):
        cleaned["current_supervisor_erp_id"] = None

    # --- section 2 --------------------------------------------------------
    cnic = normalise_cnic(data.get("cnic"))
    cleaned["cnic"] = cnic
    if not cnic:
        errors["cnic"] = "CNIC is required"
    elif len(re.sub(r"\D", "", cnic)) != CNIC_DIGITS:
        errors["cnic"] = "CNIC must be 13 digits, like 12345-1234567-1"

    raw_phone = _text(data.get("contact_phone_no"))
    phone = normalise_phone(raw_phone)
    cleaned["contact_phone_no"] = phone
    digits = re.sub(r"\D", "", phone)
    if not raw_phone:
        errors["contact_phone_no"] = "Contact phone number is required"
    elif not (PHONE_MIN_DIGITS <= len(digits) <= PHONE_MAX_DIGITS):
        # Covers both "too short" and text with no digits in it at all, which
        # would otherwise be reported as a missing field.
        errors["contact_phone_no"] = "Enter a phone number like +92-300-1234567"

    corporate = _text(data.get("corporate_email")).lower()
    cleaned["corporate_email"] = corporate
    if not corporate:
        errors["corporate_email"] = "Corporate email address is required"
    elif not EMAIL.match(corporate):
        errors["corporate_email"] = "That does not look like an email address"

    personal = _text(data.get("personal_email")).lower()
    cleaned["personal_email"] = personal or None
    if personal and not EMAIL.match(personal):
        errors["personal_email"] = "That does not look like an email address"
    if personal and personal == corporate:
        errors["personal_email"] = "Personal email should differ from the corporate one"

    method = _text(data.get("preferred_contact_method"))
    cleaned["preferred_contact_method"] = method
    if not method:
        errors["preferred_contact_method"] = "Choose how you would like to be contacted"
    elif method not in InternalJobApplication.CONTACT_METHODS:
        errors["preferred_contact_method"] = (
            f"Choose one of {', '.join(InternalJobApplication.CONTACT_METHODS)}"
        )

    # --- section 3: the education repeater --------------------------------
    rows = data.get("education")
    if not isinstance(rows, list):
        rows = []

    if not rows:
        errors["education"] = "Add at least one degree or certificate"
    elif len(rows) > MAX_EDUCATION_ROWS:
        errors["education"] = f"At most {MAX_EDUCATION_ROWS} entries can be listed"

    latest_year = date.today().year + GRADUATION_YEARS_AHEAD
    cleaned_rows: List[Dict[str, Any]] = []
    row_errors: Dict[str, Dict[str, str]] = {}

    for index, row in enumerate(rows[:MAX_EDUCATION_ROWS]):
        if not isinstance(row, dict):
            row_errors[str(index)] = {"edu_degree_title": "Unreadable entry"}
            continue

        problems: Dict[str, str] = {}
        entry = {
            "edu_degree_title": _text(row.get("edu_degree_title")),
            "edu_institution_name": _text(row.get("edu_institution_name")),
            "edu_major_specialization": _text(row.get("edu_major_specialization")),
            "edu_grade_score": _text(row.get("edu_grade_score")),
        }

        for field, label, maximum in (
            ("edu_degree_title", "Degree / certificate", 200),
            ("edu_institution_name", "Institution", 200),
            ("edu_major_specialization", "Major / field of study", 200),
            ("edu_grade_score", "CGPA / grade", 40),
        ):
            if not entry[field]:
                problems[field] = f"{label} is required"
            elif len(entry[field]) > maximum:
                problems[field] = f"{label} must be {maximum} characters or fewer"

        try:
            year = int(row.get("edu_graduation_year") or 0)
        except (TypeError, ValueError):
            year = 0
        entry["edu_graduation_year"] = year

        if not year:
            problems["edu_graduation_year"] = "Select the year of completion"
        elif not (EARLIEST_GRADUATION_YEAR <= year <= latest_year):
            problems["edu_graduation_year"] = (
                f"Year must be between {EARLIEST_GRADUATION_YEAR} and {latest_year}"
            )

        entry["row_order"] = index
        if problems:
            row_errors[str(index)] = problems
        else:
            cleaned_rows.append(entry)

    if row_errors:
        errors["education_rows"] = row_errors

    cleaned["education"] = cleaned_rows
    return cleaned, errors
