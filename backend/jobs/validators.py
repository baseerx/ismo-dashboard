"""Validation for the internal recruitment online application form.

One function, `validate_application`, returns (cleaned, errors) so a submission
is either stored whole or refused with a message against every field that is
wrong. The rules mirror the printed form: the fields it marks mandatory are
required here, the one field it marks optional stays optional, and the four
repeating tables are checked row by row.

The browser checks the same things first; this is what actually decides, since
a payload can be sent without going near the page.
"""

import re
from datetime import date, datetime
from typing import List

# Repeater ceilings. Generous enough for a long career, low enough that a
# runaway payload cannot fill the database.
MAX_EDUCATION_ROWS = 15
MAX_EXPERIENCE_ROWS = 20
MAX_CERTIFICATION_ROWS = 15
MAX_TRAINING_ROWS = 20

# Vacancies one submission may target. Applying for everything advertised is
# not a career move, and each one becomes its own application to review.
MAX_VACANCIES_PER_SUBMISSION = 10

MAX_RESPONSIBILITIES = 1500

GENDERS = ("Male", "Female", "Other")

# 12345-1234567-1, the way a CNIC is written on the card.
CNIC = re.compile(r"^\d{5}-\d{7}-\d$")
# Local or international, with or without separators: +92-300-1234567, 03001234567.
PHONE = re.compile(r"^\+?[\d][\d\s\-()]{6,20}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

EARLIEST_QUALIFICATION_YEAR = 1950
# A degree can be awarded shortly after the form is filled in, and nobody is
# still at school in 1949.
FUTURE_QUALIFICATION_YEARS = 6


def _text(value, limit: int | None = None) -> str:
    cleaned = str(value or "").strip()
    return cleaned[:limit] if limit else cleaned


def _require(errors: dict, field: str, value, message: str, minimum: int = 0) -> str:
    """Records `message` when the value is missing or too short."""
    cleaned = _text(value)
    if not cleaned:
        errors[field] = message
    elif minimum and len(cleaned) < minimum:
        errors[field] = f"{message.rstrip('.')} - that looks too short"
    return cleaned


def _as_date(value):
    """A date from an ISO string, or None when absent or unparseable."""
    cleaned = _text(value)
    if not cleaned:
        return None
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(cleaned[:10], pattern).date()
        except ValueError:
            continue
    return None


def _required_date(errors: dict, field: str, value, label: str, *, allow_future=False):
    """A date that has to be there, and has to make sense."""
    cleaned = _text(value)
    if not cleaned:
        errors[field] = f"{label} is required"
        return None

    parsed = _as_date(cleaned)
    if parsed is None:
        errors[field] = f"{label} is not a valid date"
        return None
    if not allow_future and parsed > date.today():
        errors[field] = f"{label} cannot be in the future"
        return None
    return parsed


def _optional_date(errors: dict, field: str, value, label: str, *, allow_future=True):
    cleaned = _text(value)
    if not cleaned:
        return None
    parsed = _as_date(cleaned)
    if parsed is None:
        errors[field] = f"{label} is not a valid date"
        return None
    if not allow_future and parsed > date.today():
        errors[field] = f"{label} cannot be in the future"
        return None
    return parsed


def describe_span(start: date, end: date | None) -> str:
    """"3 years 4 months", the way the form's Duration column reads."""
    finish = end or date.today()
    if finish < start:
        return ""

    months = (finish.year - start.year) * 12 + (finish.month - start.month)
    if finish.day < start.day:
        months -= 1
    months = max(months, 0)

    years, remainder = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if remainder:
        parts.append(f"{remainder} month{'s' if remainder != 1 else ''}")
    return " ".join(parts) or "less than a month"


def _rows(data, key) -> list:
    rows = data.get(key)
    return rows if isinstance(rows, list) else []


def _row_is_empty(row: dict, fields) -> bool:
    """True when the applicant added a row and typed nothing in it."""
    return all(not _text(row.get(field)) for field in fields)


# ---------------------------------------------------------------------------
# 4. Educational background
# ---------------------------------------------------------------------------

def _validate_education(data, errors) -> list:
    rows = _rows(data, "education")
    if not rows:
        errors["education"] = "Add at least one qualification"
        return []
    if len(rows) > MAX_EDUCATION_ROWS:
        errors["education"] = f"At most {MAX_EDUCATION_ROWS} qualifications can be listed"
        return []

    cleaned_rows, row_errors = [], {}
    this_year = date.today().year

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            row_errors[index] = {"degree_qualification": "This row is not filled in"}
            continue

        problems = {}
        degree = _require(problems, "degree_qualification", row.get("degree_qualification"),
                          "Degree / qualification is required", minimum=2)
        major = _require(problems, "major_field_of_study", row.get("major_field_of_study"),
                         "Major / field of study is required", minimum=2)
        institution = _require(problems, "institution_university", row.get("institution_university"),
                               "Institution / university is required", minimum=2)
        country = _require(problems, "country", row.get("country"), "Country is required", minimum=2)

        year_raw = _text(row.get("year_of_completion"))
        year = None
        if not year_raw:
            problems["year_of_completion"] = "Year of completion is required"
        else:
            try:
                year = int(year_raw)
            except (TypeError, ValueError):
                problems["year_of_completion"] = "Year of completion must be a year"
            else:
                if not EARLIEST_QUALIFICATION_YEAR <= year <= this_year + FUTURE_QUALIFICATION_YEARS:
                    problems["year_of_completion"] = (
                        f"Year must be between {EARLIEST_QUALIFICATION_YEAR} and "
                        f"{this_year + FUTURE_QUALIFICATION_YEARS}"
                    )

        grade = _require(problems, "cgpa_division", row.get("cgpa_division"),
                         "CGPA / division is required")

        if problems:
            row_errors[index] = problems
            continue

        cleaned_rows.append({
            "degree_qualification": degree[:200],
            "major_field_of_study": major[:200],
            "institution_university": institution[:200],
            "country": country[:100],
            "year_of_completion": year,
            "cgpa_division": grade[:40],
            "row_order": index,
        })

    if row_errors:
        errors["education_rows"] = row_errors
    return cleaned_rows


# ---------------------------------------------------------------------------
# 5. Employment history / professional experience
# ---------------------------------------------------------------------------

def _validate_experience(data, errors) -> list:
    rows = _rows(data, "experience")
    if not rows:
        errors["experience"] = "Add at least one post, including your current one"
        return []
    if len(rows) > MAX_EXPERIENCE_ROWS:
        errors["experience"] = f"At most {MAX_EXPERIENCE_ROWS} posts can be listed"
        return []

    cleaned_rows, row_errors = [], {}

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            row_errors[index] = {"organization_employer": "This row is not filled in"}
            continue

        problems = {}
        employer = _require(problems, "organization_employer", row.get("organization_employer"),
                            "Organization / employer is required", minimum=2)
        designation = _require(problems, "designation", row.get("designation"),
                               "Designation is required", minimum=2)
        grade = _text(row.get("grade"), 40)

        is_current = bool(row.get("is_current"))
        from_date = _required_date(problems, "from_date", row.get("from_date"), "From date")
        to_date = None
        if is_current:
            # "To" is meaningless for a post still held, and the form's Duration
            # runs to today in that case.
            to_date = None
        else:
            to_date = _required_date(problems, "to_date", row.get("to_date"), "To date")
            if from_date and to_date and to_date < from_date:
                problems["to_date"] = "The To date cannot be before the From date"

        responsibilities = _require(
            problems, "key_responsibilities", row.get("key_responsibilities"),
            "Key responsibilities / relevant experience is required", minimum=10,
        )
        if len(responsibilities) > MAX_RESPONSIBILITIES:
            problems["key_responsibilities"] = (
                f"Keep this within {MAX_RESPONSIBILITIES} characters"
            )

        if problems:
            row_errors[index] = problems
            continue

        duration = _text(row.get("duration"), 60) or describe_span(from_date, to_date)

        cleaned_rows.append({
            "organization_employer": employer[:200],
            "designation": designation[:200],
            "grade": grade or None,
            "from_date": from_date,
            "to_date": to_date,
            "is_current": is_current,
            "duration": duration,
            "key_responsibilities": responsibilities,
            "row_order": index,
        })

    if row_errors:
        errors["experience_rows"] = row_errors
    return cleaned_rows


# ---------------------------------------------------------------------------
# 6. Professional certifications / memberships
# ---------------------------------------------------------------------------

CERTIFICATION_FIELDS = (
    "certification_membership", "certifying_body", "date_obtained",
    "expiry_date", "registration_no",
)


def _validate_certifications(data, errors) -> list:
    """Optional as a section; complete once a row has anything in it."""
    rows = _rows(data, "certifications")
    if len(rows) > MAX_CERTIFICATION_ROWS:
        errors["certifications"] = f"At most {MAX_CERTIFICATION_ROWS} entries can be listed"
        return []

    cleaned_rows, row_errors = [], {}

    for index, row in enumerate(rows):
        if not isinstance(row, dict) or _row_is_empty(row, CERTIFICATION_FIELDS):
            continue

        problems = {}
        name = _require(problems, "certification_membership", row.get("certification_membership"),
                        "Certification / membership is required", minimum=2)
        body = _require(problems, "certifying_body", row.get("certifying_body"),
                        "Certifying / professional body is required", minimum=2)
        obtained = _optional_date(problems, "date_obtained", row.get("date_obtained"),
                                  "Date obtained", allow_future=False)
        expiry = _optional_date(problems, "expiry_date", row.get("expiry_date"), "Expiry date")
        if obtained and expiry and expiry < obtained:
            problems["expiry_date"] = "The expiry date cannot be before the date obtained"

        if problems:
            row_errors[index] = problems
            continue

        cleaned_rows.append({
            "certification_membership": name[:200],
            "certifying_body": body[:200],
            "date_obtained": obtained,
            "expiry_date": expiry,
            "registration_no": _text(row.get("registration_no"), 100) or None,
            "row_order": index,
        })

    if row_errors:
        errors["certification_rows"] = row_errors
    return cleaned_rows


# ---------------------------------------------------------------------------
# 7. Trainings & professional development
# ---------------------------------------------------------------------------

TRAINING_FIELDS = ("training_title", "training_provider", "duration", "date_or_year")


def _validate_trainings(data, errors) -> list:
    """Also optional as a section, also complete once started."""
    rows = _rows(data, "trainings")
    if len(rows) > MAX_TRAINING_ROWS:
        errors["trainings"] = f"At most {MAX_TRAINING_ROWS} entries can be listed"
        return []

    cleaned_rows, row_errors = [], {}
    this_year = date.today().year

    for index, row in enumerate(rows):
        if not isinstance(row, dict) or _row_is_empty(row, TRAINING_FIELDS):
            continue

        problems = {}
        title = _require(problems, "training_title", row.get("training_title"),
                         "Training / course title is required", minimum=2)
        provider = _require(problems, "training_provider", row.get("training_provider"),
                            "Training provider / institute is required", minimum=2)

        # "Date / Year": a bare year is a fine answer, so only a year that could
        # not be one is refused.
        when = _text(row.get("date_or_year"), 40)
        if when and re.fullmatch(r"\d{4}", when):
            year = int(when)
            if not EARLIEST_QUALIFICATION_YEAR <= year <= this_year:
                problems["date_or_year"] = (
                    f"Year must be between {EARLIEST_QUALIFICATION_YEAR} and {this_year}"
                )

        if problems:
            row_errors[index] = problems
            continue

        cleaned_rows.append({
            "training_title": title[:200],
            "training_provider": provider[:200],
            "duration": _text(row.get("duration"), 60) or None,
            "date_or_year": when or None,
            "relevant_to_position": bool(row.get("relevant_to_position")),
            "row_order": index,
        })

    if row_errors:
        errors["training_rows"] = row_errors
    return cleaned_rows


# ---------------------------------------------------------------------------
# The whole submission
# ---------------------------------------------------------------------------

def _signature_matches(signature: str, full_name: str) -> bool:
    """A signature is the applicant's own name, however it is punctuated."""
    strip = lambda value: re.sub(r"[^a-z]", "", value.lower())
    return strip(signature) == strip(full_name)


def validate_application(data):
    """Returns (cleaned, errors). `errors` empty means the payload is storable."""
    errors: dict = {}
    cleaned: dict = {}

    if not isinstance(data, dict):
        return {}, {"__all__": "The submission was not readable"}

    # ---- which vacancies -------------------------------------------------
    raw_ids = data.get("target_job_req_ids")
    if raw_ids is None:
        # An older client sent a single vacancy.
        single = data.get("target_job_req_id")
        raw_ids = [single] if single else []
    if not isinstance(raw_ids, list):
        raw_ids = [raw_ids]

    requisition_ids: List[int] = []
    for value in raw_ids:
        try:
            requisition_id = int(value)
        except (TypeError, ValueError):
            errors["target_job_req_ids"] = f"Not a vacancy: {value!r}"
            break
        if requisition_id > 0 and requisition_id not in requisition_ids:
            requisition_ids.append(requisition_id)

    cleaned["target_job_req_ids"] = requisition_ids
    if "target_job_req_ids" not in errors:
        if not requisition_ids:
            errors["target_job_req_ids"] = "Select at least one vacancy to apply for"
        elif len(requisition_ids) > MAX_VACANCIES_PER_SUBMISSION:
            errors["target_job_req_ids"] = (
                f"Apply for at most {MAX_VACANCIES_PER_SUBMISSION} vacancies at a time"
            )

    # ---- 2. personal & contact information -------------------------------
    try:
        cleaned["emp_id"] = int(data.get("emp_id") or 0)
    except (TypeError, ValueError):
        cleaned["emp_id"] = 0
    if cleaned["emp_id"] <= 0:
        errors["emp_id"] = "Employee ID must be a number"

    cleaned["full_name"] = _require(errors, "full_name", data.get("full_name"),
                                    "Full name is required", minimum=3)[:150]
    cleaned["father_or_husband_name"] = _require(
        errors, "father_or_husband_name", data.get("father_or_husband_name"),
        "Father's / husband's name is required", minimum=3,
    )[:150]

    cnic = _text(data.get("cnic"), 15)
    cleaned["cnic"] = cnic
    if not cnic:
        errors["cnic"] = "CNIC number is required"
    elif not CNIC.match(cnic):
        errors["cnic"] = "CNIC must be 13 digits, like 12345-1234567-1"

    date_of_birth = _required_date(errors, "date_of_birth", data.get("date_of_birth"),
                                   "Date of birth")
    cleaned["date_of_birth"] = date_of_birth
    if date_of_birth:
        age = (date.today() - date_of_birth).days / 365.25
        if age < 18:
            errors["date_of_birth"] = "An applicant must be at least 18"
        elif age > 70:
            errors["date_of_birth"] = "Check the date of birth - that is over 70 years ago"

    gender = _text(data.get("gender"), 10)
    cleaned["gender"] = gender
    if not gender:
        errors["gender"] = "Gender is required"
    elif gender not in GENDERS:
        errors["gender"] = f"Gender should be one of: {', '.join(GENDERS)}"

    email = _text(data.get("official_email"), 150).lower()
    cleaned["official_email"] = email
    if not email:
        errors["official_email"] = "Official email address is required"
    elif not EMAIL.match(email):
        errors["official_email"] = "That does not look like an email address"

    mobile = _text(data.get("mobile_no"), 25)
    cleaned["mobile_no"] = mobile
    if not mobile:
        errors["mobile_no"] = "Mobile / contact number is required"
    elif not PHONE.match(mobile) or sum(character.isdigit() for character in mobile) < 7:
        errors["mobile_no"] = "Enter a number like +92-300-1234567"

    cleaned["current_office_location"] = _require(
        errors, "current_office_location", data.get("current_office_location"),
        "Current office / location is required", minimum=2,
    )[:200]

    emergency = _text(data.get("emergency_contact_no"), 25)
    cleaned["emergency_contact_no"] = emergency or None
    if emergency and (not PHONE.match(emergency)
                      or sum(character.isdigit() for character in emergency) < 7):
        errors["emergency_contact_no"] = "Enter a number like +92-300-1234567"

    # ---- 3. current employment details -----------------------------------
    joined = _required_date(errors, "date_of_joining_ismo", data.get("date_of_joining_ismo"),
                            "Date of joining ISMO")
    cleaned["date_of_joining_ismo"] = joined
    if joined and date_of_birth and (joined - date_of_birth).days < 16 * 365:
        errors["date_of_joining_ismo"] = "That is before the applicant turned 16"

    cleaned["current_designation"] = _require(
        errors, "current_designation", data.get("current_designation"),
        "Current designation is required", minimum=2,
    )[:200]
    cleaned["current_grade"] = _require(
        errors, "current_grade", data.get("current_grade"), "Current grade is required",
    )[:40]
    cleaned["department_function"] = _require(
        errors, "department_function", data.get("department_function"),
        "Department / function is required", minimum=2,
    )[:200]

    appointed = _required_date(
        errors, "date_of_appointment_to_current_grade",
        data.get("date_of_appointment_to_current_grade"), "Date of appointment to current grade",
    )
    cleaned["date_of_appointment_to_current_grade"] = appointed
    if appointed and joined and appointed < joined:
        errors["date_of_appointment_to_current_grade"] = (
            "This cannot be before the date of joining ISMO"
        )

    current_position_since = _required_date(
        errors, "date_of_joining_current_position",
        data.get("date_of_joining_current_position"), "Date of joining current position",
    )
    cleaned["date_of_joining_current_position"] = current_position_since
    if current_position_since and joined and current_position_since < joined:
        errors["date_of_joining_current_position"] = (
            "This cannot be before the date of joining ISMO"
        )

    cleaned["total_service_ismo"] = _require(
        errors, "total_service_ismo", data.get("total_service_ismo"),
        "Total service in ISMO is required",
    )[:60]
    cleaned["total_relevant_experience"] = _require(
        errors, "total_relevant_experience", data.get("total_relevant_experience"),
        "Total relevant experience is required",
    )[:60]

    # ---- 4 to 7: the repeating tables ------------------------------------
    cleaned["education"] = _validate_education(data, errors)
    cleaned["experience"] = _validate_experience(data, errors)
    cleaned["certifications"] = _validate_certifications(data, errors)
    cleaned["trainings"] = _validate_trainings(data, errors)

    # ---- 8. declaration & undertaking ------------------------------------
    cleaned["declaration_accepted"] = bool(data.get("declaration_accepted"))
    if not cleaned["declaration_accepted"]:
        errors["declaration_accepted"] = (
            "Read and accept the declaration and undertaking before submitting"
        )

    # ---- 9. submission record --------------------------------------------
    signature = _text(data.get("applicant_signature"), 150)
    cleaned["applicant_signature"] = signature
    if not signature:
        errors["applicant_signature"] = "Type your full name to sign the application"
    elif cleaned["full_name"] and not _signature_matches(signature, cleaned["full_name"]):
        errors["applicant_signature"] = (
            "The signature must be your full name as entered above"
        )

    return cleaned, errors
