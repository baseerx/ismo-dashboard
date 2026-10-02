

import re

from sqlalchemy import text
from db import SessionLocal

from .models import LeaveModel

FORCE_CEO_FINAL = True



def _grade_rank_from_name(grade_name):
    if not grade_name:
        return None
    digits = re.sub(r"\D", "", grade_name)
    return int(digits) if digits else None


def get_employee_grade(erp_id):
    """ASSUMPTION: a `grades` table with `id`/`name` columns, matching
    the Grade type from /users/details/. Fix here if names differ."""
    session = SessionLocal()
    try:
        row = session.execute(text("""
            SELECT g.name AS grade_name, e.grade_id
            FROM employees e
            LEFT JOIN grades g ON e.grade_id = g.id
            WHERE e.erp_id = :erp_id AND e.flag = 1
        """), {"erp_id": erp_id}).fetchone()
        if not row:
            return None
        parsed = _grade_rank_from_name(row.grade_name)
        return parsed if parsed is not None else row.grade_id
    finally:
        session.close()

def get_reporting_officer(leave):
    return leave.head_erpid or None



def get_functional_head(erp_id):
    session = SessionLocal()
    try:
        self_row = session.execute(text("""
            SELECT erp_id, location_id FROM employees
            WHERE erp_id = :erp_id AND flag = 1
        """), {"erp_id": erp_id}).fetchone()
        if not self_row or not self_row.location_id:
            return None

        candidates = session.execute(text("""
            SELECT e.erp_id, e.grade_id, g.name AS grade_name
            FROM employees e
            LEFT JOIN grades g ON e.grade_id = g.id
            WHERE e.location_id = :location_id AND e.flag = 1
        """), {"location_id": self_row.location_id}).fetchall()

        if not candidates:
            return None

        def rank(row):
            parsed = _grade_rank_from_name(row.grade_name)
            return parsed if parsed is not None else (row.grade_id or -1)

        best = sorted(candidates, key=lambda r: (-rank(r), r.erp_id))[0]
        return best.erp_id
    finally:
        session.close()


ORG_ROLE_DESIGNATION_KEYWORDS = {
    "ceo": "CEO",
    "ed_hr": "ED (HR)",
    "finance": "Finance",
    "hr_admin_dept": "HR", 
    "hr_committee": None,    
}


def resolve_erp_id_by_designation(keyword):
    if not keyword:
        return None
    session = SessionLocal()
    try:
        row = session.execute(text("""
            SELECT TOP 1 e.erp_id
            FROM employees e
            JOIN designations d ON e.designation_id = d.id
            WHERE LOWER(d.title) LIKE LOWER(:pattern) AND e.flag = 1
            ORDER BY e.erp_id
        """), {"pattern": f"%{keyword}%"}).fetchone()
        return row.erp_id if row else None
    finally:
        session.close()


ORG_ROLE_ERP_ID_OVERRIDES = {
    "ceo": 111,
    "ed_hr": 183,
    "finance": 1062,
    "hr_admin_dept": None,
    "hr_committee": None,
}


def resolve_org_role_erp_id(role_key):
    override = ORG_ROLE_ERP_ID_OVERRIDES.get(role_key)
    if override:
        return override
    keyword = ORG_ROLE_DESIGNATION_KEYWORDS.get(role_key)
    return resolve_erp_id_by_designation(keyword) if keyword else None


LOCATION_TO_ED_KEYWORD = {
    "ISMO-Head Office": None,
    "ISMO-Jamshoro": None,
    "ISMO-Lahore": None,
    "ISMO-Shaheen Plaza": None,
}


def _resolve_location_name(erp_id):
    session = SessionLocal()
    try:
        row = session.execute(text("""
            SELECT l.name AS location_name
            FROM employees e
            LEFT JOIN locations l ON e.location_id = l.id
            WHERE e.erp_id = :erp_id AND e.flag = 1
        """), {"erp_id": erp_id}).fetchone()
        return row.location_name if row else None
    finally:
        session.close()


def get_concerned_executive_director(erp_id):
    location_name = _resolve_location_name(erp_id)
    if not location_name:
        return None
    ed_keyword = LOCATION_TO_ED_KEYWORD.get(location_name)
    return resolve_erp_id_by_designation(ed_keyword) if ed_keyword else None



LOCATION_TO_DIRECTOR_KEYWORD = {
    "ISMO-Head Office": None,
    "ISMO-Jamshoro": None,
    "ISMO-Lahore": None,
    "ISMO-Shaheen Plaza": None,
}


def get_concerned_director(erp_id):
    location_name = _resolve_location_name(erp_id)
    if not location_name:
        return None
    director_keyword = LOCATION_TO_DIRECTOR_KEYWORD.get(location_name)
    return resolve_erp_id_by_designation(director_keyword) if director_keyword else None



LEAVE_WORKFLOW_STAGES = {
    "casual leave": [
        ("Recommended By", "reporting_officer", None),
    ],
    "earned leave": [
        ("Recommended By", "reporting_officer", None),
        ("Concurrence (if >10 days)", "functional_head",
         lambda leave: leave.total_days > 10),
    ],
    "earned leave encashment": [
        ("Recommended By", "hr_admin_dept", None),
        ("Concurrence (Finance)", "finance", None),
    ],
    "on the job study": [
        ("Recommended By", "functional_head", None),
        ("Concurrence/Verification", "hr_admin_dept", None),
    ],
    "extraordinary leave": [
        ("Recommended By", "reporting_officer", None),
        ("Concurrence", "functional_head", None),
        ("Concurrence", "hr_admin_dept", None),
    ],
    "disability leave": [
        ("Recommended By (medical verification)", "hr_admin_dept", None),
        ("Concurrence", "functional_head", None),
    ],
    "maternity leave": [
        ("Recommended By", "hr_admin_dept", None),
    ],
    "paternity leave": [
        ("Recommended By", "hr_admin_dept", None),
    ],
    "medical leave": [
        ("Recommended By (medical verification)", "hr_admin_dept", None),
        ("Concurrence", "functional_head", None),
    ],
    "iddat leave": [
        ("Recommended By", "hr_admin_dept", None),
    ],
    "leave ex-pakistan": [
        ("Recommended By", "reporting_officer", None),
        ("Concurrence", "functional_head", None),
    ],
    "hajj leave": [
        ("Recommended By (service-record verification)", "hr_admin_dept", None),
    ],
    "rest & recreational leave": [
        ("Recommended By", "reporting_officer", None),
        ("Concurrence", "functional_head", None),
    ],
    "bereavement leave": [
        ("Recommended By", "reporting_officer", None),
    ],
}

for _sub_type in ("maternity leave first", "maternity leave second", "maternity leave third"):
    LEAVE_WORKFLOW_STAGES[_sub_type] = LEAVE_WORKFLOW_STAGES["maternity leave"]


def build_review_stages(leave):
    lt_lower = (leave.leave_type or "").strip().lower()
    stages = LEAVE_WORKFLOW_STAGES.get(lt_lower, [])
    resolved = []
    for label, role_key, condition in stages:
        if condition is None or condition(leave):
            resolved.append((label, role_key))
    return resolved


GRADE_TABLE_1_TYPES = {
    "earned leave", "earned leave encashment", "on the job study",
    "extraordinary leave", "disability leave", "medical leave",
    "iddat leave", "leave ex-pakistan", "hajj leave",
}

def resolve_final_authority_table_1(grade, requested_days):
    """Table 1: EL, Leave Encashment, On-the-Job Study, Extraordinary
    Leave, Disability, Medical, Iddat, Ex-Pakistan, Hajj.

    Grades 10-11: CEO regardless of duration.
    Grades 07-09: ED(HR) up to 1 month; beyond 1 month, CEO.
    Grades 01-06: ED(HR) for anything up to 1 YEAR; only beyond 1 YEAR
    escalates to CEO.
    """
    if grade in (10, 11):
        return "ceo"
    if 7 <= grade <= 9:
        return "ed_hr" if requested_days <= 30 else "ceo"
    if 1 <= grade <= 6:
        return "ceo" if requested_days > 365 else "ed_hr"
    return None


GRADE_TABLE_2_TYPES = {
    "maternity leave", "maternity leave first", "maternity leave second",
    "maternity leave third", "paternity leave", "rest & recreational leave",
    "bereavement leave", "casual leave",
}

def resolve_final_authority_table_2(grade, leave_type_lower):
    """Table 2: Maternity, Paternity, R&R, Bereavement, Casual Leave.

    Grades 10-11: CEO for everything.
    Grades 07-09: ED(HR) for Maternity/Paternity/R&R; "Concerned E.D.
    with copy to ED(HR)" for Bereavement/Casual.
    Grades 01-06: ED(HR) for Maternity/Paternity/R&R; "Concerned
    DIRECTOR with copy to HR" for Bereavement/Casual.
    """
    if grade in (10, 11):
        return "ceo"
    if 7 <= grade <= 9:
        if leave_type_lower in ("bereavement leave", "casual leave"):
            return "concerned_ed"
        return "ed_hr"
    if 1 <= grade <= 6:
        if leave_type_lower in ("bereavement leave", "casual leave"):
            return "concerned_director"
        return "ed_hr"
    return None


def resolve_final_authority(leave):
    grade = get_employee_grade(leave.erp_id)
    if grade is None:
        return None

    lt_lower = (leave.leave_type or "").strip().lower()
    if lt_lower in GRADE_TABLE_1_TYPES:
        return resolve_final_authority_table_1(grade, leave.total_days or 0)
    if lt_lower in GRADE_TABLE_2_TYPES:
        return resolve_final_authority_table_2(grade, lt_lower)
    return None



def resolve_role_erp_id(role_key, leave):
    if role_key in ORG_ROLE_DESIGNATION_KEYWORDS:
        return resolve_org_role_erp_id(role_key)

    if role_key == "reporting_officer":
        return get_reporting_officer(leave)
    if role_key == "functional_head":
        return get_functional_head(leave.erp_id)
    if role_key == "concerned_ed":
        return get_concerned_executive_director(leave.erp_id)
    if role_key == "concerned_director":
        return get_concerned_director(leave.erp_id)

    raise ValueError(f"Unknown role_key: {role_key}")


def build_full_approval_chain(leave):
    """Complete chain: review stages (Anex-B Section 2) + final
    sanctioning stage. Each entry is (label, role_key, erp_id_or_None).
    Any None means resolution genuinely failed -- callers fall back to
    legacy single-stage routing rather than guess.

    With FORCE_CEO_FINAL on, the final stage is always the CEO.
    """
    chain = []
    for label, role_key in build_review_stages(leave):
        try:
            erp_id = resolve_role_erp_id(role_key, leave)
        except ValueError:
            erp_id = None
        chain.append((label, role_key, erp_id))

    
    if FORCE_CEO_FINAL and not chain:
        chain.append(
            ("Recommended By", "reporting_officer", get_reporting_officer(leave))
        )

    final_role = "ceo" if FORCE_CEO_FINAL else resolve_final_authority(leave)
    if final_role:
        try:
            final_erp_id = resolve_role_erp_id(final_role, leave)
        except ValueError:
            final_erp_id = None

        
        if final_erp_id is not None:
            chain = [c for c in chain if c[2] != final_erp_id]

        chain.append(("Final Sanctioning Authority", final_role, final_erp_id))

    return chain