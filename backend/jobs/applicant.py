"""Who is applying, according to the employee record.

Section 1 of the specification makes the applicant's name, employee id,
department, position title and supervisor read-only, "auto-filled via SSO".
This is that lookup. The form shows what it returns, and `create_application`
files what it returns rather than whatever the payload claims.
"""

from sqlalchemy import text

from db import SessionLocal

GENDER_NAMES = {"M": "Male", "F": "Female", "male": "Male", "female": "Female"}


def _supervisor(session, employee):
    """The applicant's current supervisor, or None.

    The same rule the rest of this app uses for a section head: the most
    senior person in the section (highest grade_id, ties broken by name). A
    peer at the applicant's own grade is not their supervisor, so when the
    applicant is themselves at the top grade of their section there is none on
    record.
    """
    if not employee.section_id:
        return None

    return session.execute(
        text(
            """
            SELECT TOP 1 e.erp_id, e.name
            FROM employees e
            WHERE e.flag = 1
              AND e.section_id = :section_id
              AND e.erp_id <> :erp_id
              AND e.grade_id > :grade_id
              AND e.grade_id = (
                  SELECT MAX(e2.grade_id) FROM employees e2
                  WHERE e2.flag = 1 AND e2.section_id = :section_id
              )
            ORDER BY e.name
            """
        ),
        {
            "section_id": employee.section_id,
            "erp_id": employee.erp_id,
            "grade_id": employee.grade_id or 0,
        },
    ).first()


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

        supervisor = _supervisor(session, employee)

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
            "current_supervisor_erp_id": supervisor.erp_id if supervisor else None,
            "current_supervisor_name": (supervisor.name or "").strip() if supervisor else "",
        }
    finally:
        session.close()
