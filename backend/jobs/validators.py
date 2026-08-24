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

from .models import InternalJobApplication, InternalJobApplicationSkill

# Grid rows a person can add. Generous for a career, small enough that a script
# cannot post ten thousand of them.
MAX_EDUCATION_ROWS = 15
MAX_EXPERIENCE_ROWS = 20

# Character ceilings from the specification, enforced here as well as in each
# textarea's own maxlength — which a POST can ignore.
MAX_RESPONSIBILITIES = 1500
MAX_ACHIEVEMENTS = 2000
MAX_CERTIFICATIONS = 1500
MAX_SOP = 3000

# A statement of purpose has to say something; this only rules out "n/a".
MIN_SOP = 30

# Tags exist to be filtered on, so they are capped and de-duplicated.
MAX_TECHNICAL_SKILLS = 30
MAX_SKILL_LENGTH = 80

# Nobody here was employed before this, and no post starts in the future.
EARLIEST_EMPLOYMENT_YEAR = 1950

# The list the form offers. Anything else is a typo rather than a soft skill,
# and is refused instead of becoming a category nothing will match again.
SOFT_SKILL_OPTIONS = (
    "Leadership",
    "Team Management",
    "Communication",
    "Stakeholder Management",
    "Problem Solving",
    "Analytical Thinking",
    "Decision Making",
    "Negotiation",
    "Conflict Resolution",
    "Mentoring & Coaching",
    "Time Management",
    "Adaptability",
    "Presentation Skills",
    "Report Writing",
    "Cross-functional Collaboration",
)

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

    _validate_experience(data, cleaned, errors)
    _validate_skills(data, cleaned, errors)
    _validate_statement(data, cleaned, errors)

    return cleaned, errors


def _parse_date(value: Any):
    """A date from YYYY-MM-DD, or None when it is not one."""
    text = _text(value)[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _validate_experience(
    data: Dict[str, Any], cleaned: Dict[str, Any], errors: Dict[str, Any]
) -> None:
    """Section 4: one row per post held, internal or external."""
    rows = data.get("experience")
    if not isinstance(rows, list):
        rows = []

    if not rows:
        errors["experience"] = "Add at least one position, including your current role"
    elif len(rows) > MAX_EXPERIENCE_ROWS:
        errors["experience"] = f"At most {MAX_EXPERIENCE_ROWS} positions can be listed"

    today = date.today()
    cleaned_rows: List[Dict[str, Any]] = []
    row_errors: Dict[str, Dict[str, str]] = {}

    for index, row in enumerate(rows[:MAX_EXPERIENCE_ROWS]):
        if not isinstance(row, dict):
            row_errors[str(index)] = {"exp_job_title": "Unreadable entry"}
            continue

        problems: Dict[str, str] = {}
        entry: Dict[str, Any] = {
            "exp_job_title": _text(row.get("exp_job_title")),
            "exp_company_name": _text(row.get("exp_company_name")),
            "exp_key_responsibilities": _text(row.get("exp_key_responsibilities")),
            "exp_key_achievements": _text(row.get("exp_key_achievements")),
            "exp_is_current": bool(row.get("exp_is_current")),
        }

        for field, label, maximum in (
            ("exp_job_title", "Job position title", 200),
            ("exp_company_name", "Organization / company name", 200),
        ):
            if not entry[field]:
                problems[field] = f"{label} is required"
            elif len(entry[field]) > maximum:
                problems[field] = f"{label} must be {maximum} characters or fewer"

        if not entry["exp_key_responsibilities"]:
            problems["exp_key_responsibilities"] = "Key responsibilities are required"
        elif len(entry["exp_key_responsibilities"]) > MAX_RESPONSIBILITIES:
            problems["exp_key_responsibilities"] = (
                f"Keep responsibilities within {MAX_RESPONSIBILITIES} characters"
            )

        # Achievements are optional: a long-ago junior post may have none worth
        # quantifying, and demanding one invites invention.
        if len(entry["exp_key_achievements"]) > MAX_ACHIEVEMENTS:
            problems["exp_key_achievements"] = (
                f"Keep achievements within {MAX_ACHIEVEMENTS} characters"
            )
        entry["exp_key_achievements"] = entry["exp_key_achievements"] or None

        start = _parse_date(row.get("exp_start_date"))
        entry["exp_start_date"] = start
        if start is None:
            problems["exp_start_date"] = "Select the employment start date"
        elif start.year < EARLIEST_EMPLOYMENT_YEAR:
            problems["exp_start_date"] = f"Start date cannot be before {EARLIEST_EMPLOYMENT_YEAR}"
        elif start > today:
            problems["exp_start_date"] = "Start date cannot be in the future"

        end = _parse_date(row.get("exp_end_date"))
        if entry["exp_is_current"]:
            # "Currently in this role" and an end date contradict each other;
            # the toggle wins and the date is dropped.
            entry["exp_end_date"] = None
        else:
            entry["exp_end_date"] = end
            if end is None:
                problems["exp_end_date"] = (
                    "Select the end date, or tick 'Currently in this role'"
                )
            elif end > today:
                problems["exp_end_date"] = "End date cannot be in the future"
            elif start and end < start:
                problems["exp_end_date"] = "End date cannot be before the start date"

        entry["row_order"] = index
        if problems:
            row_errors[str(index)] = problems
        else:
            cleaned_rows.append(entry)

    if row_errors:
        errors["experience_rows"] = row_errors

    cleaned["experience"] = cleaned_rows


def _validate_skills(
    data: Dict[str, Any], cleaned: Dict[str, Any], errors: Dict[str, Any]
) -> None:
    """Section 5: the skills matrix and certifications."""
    technical_in = data.get("skills_technical_tags")
    if isinstance(technical_in, str):
        # A comma-separated string is accepted as well as a list of tags.
        technical_in = technical_in.split(",")
    if not isinstance(technical_in, list):
        technical_in = []

    technical: List[str] = []
    seen = set()
    for value in technical_in:
        tag = _text(value)
        if not tag:
            continue
        if len(tag) > MAX_SKILL_LENGTH:
            errors["skills_technical_tags"] = (
                f"Each skill must be {MAX_SKILL_LENGTH} characters or fewer"
            )
            break
        # Case-insensitive de-duplication: "python" and "Python" are one skill.
        if tag.casefold() in seen:
            continue
        seen.add(tag.casefold())
        technical.append(tag)

    if "skills_technical_tags" not in errors:
        if not technical:
            errors["skills_technical_tags"] = "Add at least one technical skill"
        elif len(technical) > MAX_TECHNICAL_SKILLS:
            errors["skills_technical_tags"] = (
                f"At most {MAX_TECHNICAL_SKILLS} skills can be listed"
            )

    soft_in = data.get("skills_soft_checkboxes")
    if not isinstance(soft_in, list):
        soft_in = []

    soft: List[str] = []
    for value in soft_in:
        name = _text(value)
        if not name:
            continue
        # Only the offered options are stored, so a typo cannot become a new
        # category that nothing else will ever match.
        if name not in SOFT_SKILL_OPTIONS:
            errors["skills_soft_checkboxes"] = f"Unknown soft skill: {name}"
            break
        if name not in soft:
            soft.append(name)

    certifications = _text(data.get("certifications_list"))
    if len(certifications) > MAX_CERTIFICATIONS:
        errors["certifications_list"] = (
            f"Keep certifications within {MAX_CERTIFICATIONS} characters"
        )
    cleaned["certifications_list"] = certifications or None

    cleaned["skills"] = [
        {"skill_type": InternalJobApplicationSkill.TECHNICAL, "skill_name": name}
        for name in technical
    ] + [
        {"skill_type": InternalJobApplicationSkill.SOFT, "skill_name": name}
        for name in soft
    ]


def _validate_statement(
    data: Dict[str, Any], cleaned: Dict[str, Any], errors: Dict[str, Any]
) -> None:
    """Section 6: the statement of purpose and the two acknowledgements."""
    statement = _text(data.get("application_rationale_sop"))
    cleaned["application_rationale_sop"] = statement

    if not statement:
        errors["application_rationale_sop"] = "Tell us why you are applying"
    elif len(statement) < MIN_SOP:
        errors["application_rationale_sop"] = (
            f"Please give a little more detail — at least {MIN_SOP} characters"
        )
    elif len(statement) > MAX_SOP:
        errors["application_rationale_sop"] = f"Keep this within {MAX_SOP} characters"

    manager = bool(data.get("ack_manager_notified_bool"))
    accuracy = bool(data.get("ack_data_accuracy_bool"))
    cleaned["ack_manager_notified_bool"] = manager
    cleaned["ack_data_accuracy_bool"] = accuracy

    if not manager:
        errors["ack_manager_notified_bool"] = (
            "Confirm your current manager is aware of this request"
        )
    if not accuracy:
        errors["ack_data_accuracy_bool"] = "Confirm the details match the corporate record"
