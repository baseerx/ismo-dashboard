"""Who is applying, according to the employee record.

Section 1 of the specification makes the applicant's name, employee id,
department, position title and supervisor read-only, "auto-filled via SSO".
The supervisor is preselected and can be changed to another G-grade colleague
in the applicant's section.
This is that lookup. The form shows what it returns, and `create_application`
files what it returns rather than whatever the payload claims.
"""

from sqlalchemy import text

from db import SessionLocal

GENDER_NAMES = {"M": "Male", "F": "Female", "male": "Male", "female": "Female"}


def _g_rank(grade_name) -> int:
    """"G-11" -> 11. Anything that is not a G grade (Internee, none) is 0, so it
    can never outrank a G grade - its grade_id (Internee is 12) would."""
    name = str(grade_name or "").strip().upper()
    if not name.startswith("G-"):
        return 0
    digits = "".join(ch for ch in name if ch.isdigit())
    return int(digits) if digits else 0


def supervisor_options(session, employee) -> list:
    """Who the applicant can name as their current supervisor: the colleagues in
    their own section on a G grade, most senior first (ties by name). Internees
    and anyone without a G grade are left out, as is the applicant."""
    if not employee.section_id:
        return []
    rows = session.execute(
        text(
            """
            SELECT e.erp_id, e.name, g.name AS grade, d.title AS designation
            FROM employees e
            INNER JOIN grades g ON g.id = e.grade_id
            LEFT JOIN designations d ON d.id = e.designation_id
            WHERE e.flag = 1
              AND e.section_id = :section_id
              AND e.erp_id <> :erp_id
              AND g.name LIKE 'G-%'
            """
        ),
        {"section_id": employee.section_id, "erp_id": employee.erp_id},
    ).fetchall()
    options = [
        {
            "erp_id": row.erp_id,
            "name": (row.name or "").strip(),
            "grade": (row.grade or "").strip(),
            "designation": (row.designation or "").strip(),
        }
        for row in rows
    ]
    options.sort(key=lambda o: (-_g_rank(o["grade"]), o["name"].casefold()))
    return options


def _supervisor(options, employee):
    """The supervisor to preselect: the most senior G-grade colleague in the
    applicant's section, when they outrank the applicant. A peer at the
    applicant's own grade is not their supervisor, so the head of a section has
    none preselected and picks one. An internee is never chosen."""
    if not options:
        return None
    top = options[0]
    return top if _g_rank(top["grade"]) > _g_rank(employee.grade) else None


def employee_record(erp_id):
    """The active employee behind an ERP id, as the form needs it, or None."""
    session = SessionLocal()
    try:
        employee = session.execute(
            text(
                """
                SELECT
                    e.erp_id, e.hris_id, e.name, e.cnic, e.gender, e.position,
                    e.section_id, e.grade_id,
                    s.name AS section_name,
                    d.title AS designation,
                    g.name AS grade,
                    l.name AS office_location,
                    u.email AS official_email
                FROM employees e
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN grades g ON g.id = e.grade_id
                LEFT JOIN locations l ON l.id = e.location_id
                LEFT JOIN profiles p ON p.erpid = e.erp_id
                LEFT JOIN auth_user u ON u.id = p.authid
                WHERE e.erp_id = :erp_id AND e.flag = 1
                """
            ),
            {"erp_id": erp_id},
        ).first()

        if not employee:
            return None

        options = supervisor_options(session, employee)
        supervisor = _supervisor(options, employee)

        return {
            "emp_id": employee.erp_id,
            "hris_id": employee.hris_id,
            "full_name": (employee.name or "").strip(),
            "cnic": employee.cnic or "",
            "gender": GENDER_NAMES.get((employee.gender or "").strip(), ""),
            "official_email": employee.official_email or "",
            "current_office_location": employee.office_location or "",
            # Designation is the job title; `position` is a free-text note on
            # the row and is only used when there is no designation.
            "current_designation": employee.designation or employee.position or "",
            "current_grade": employee.grade or "",
            "department_function": employee.section_name or "",
            "current_supervisor_erp_id": supervisor["erp_id"] if supervisor else None,
            "current_supervisor_name": supervisor["name"] if supervisor else "",
            # The dropdown's choices: G-grade colleagues in the same section.
            "supervisor_options": options,
        }
    finally:
        session.close()
