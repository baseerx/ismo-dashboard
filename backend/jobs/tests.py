"""Tests for the internal recruitment applicant portal.

Run without touching the shared database:

    venv\\Scripts\\python.exe manage.py test jobs --settings=hris.test_settings

The employee lookup (`jobs.applicant.employee_record`) reads SQL Server through
SQLAlchemy, so it is stubbed here; everything else runs for real against a
throwaway SQLite database.
"""

import copy
import json
from datetime import date, timedelta
from unittest import mock

import jwt
from django.conf import settings
from django.test import TestCase

from notifications.models import Notification

from .form_text import SOFT_SKILLS
from .models import InternalJobApplication, JobRequisition
from .validators import validate_application

# The vacancy form's departments and locations come from SQL Server tables;
# every test sees this fixed list instead.
OPTIONS = {
    "grades": ["MG-07", "MG-08", "MG-09"],
    "departments": ["Market Operation & Development", "Planning", "System Operation"],
    "locations": ["ISMO-Head Office", "ISMO-Lahore"],
}
_options_patch = mock.patch(
    "jobs.requisition_views.department_and_location_options", return_value=OPTIONS
)


def setUpModule():
    _options_patch.start()


def tearDownModule():
    _options_patch.stop()


APPLICANT_ERP = 575
SUPERVISOR_ERP = 497

RECORD = {
    "emp_id": APPLICANT_ERP,
    "hris_id": 15549,
    "full_name": "Muhammad Adil",
    "cnic": "35202-1234567-1",
    "gender": "Male",
    "official_email": "muhammad.adil@ismo.gov.pk",
    "current_office_location": "Islamabad",
    "current_designation": "Assistant Manager",
    "current_grade": "G-07",
    "department_function": "System Operation",
    "current_supervisor_erp_id": SUPERVISOR_ERP,
    "current_supervisor_name": "Section Head",
}


def token(erp_id=APPLICANT_ERP, superuser=False, user_id=1102):
    payload = {"user_id": user_id, "erpid": erp_id, "is_superuser": superuser}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def auth(erp_id=APPLICANT_ERP, superuser=False):
    return {"HTTP_AUTHORIZATION": f"Bearer {token(erp_id, superuser)}"}


def valid_payload(requisition_ids):
    """A complete, correct submission covering all six sections."""
    return {
        "target_job_req_ids": list(requisition_ids),
        # 1 / 2
        "emp_id": APPLICANT_ERP,
        "full_name": "Muhammad Adil",
        "father_or_husband_name": "Muhammad Akram",
        "cnic": "35202-1234567-1",
        "date_of_birth": "1990-05-01",
        "gender": "Male",
        "official_email": "muhammad.adil@ismo.gov.pk",
        "personal_email": "adil.personal@gmail.com",
        "preferred_contact_method": "Teams",
        "mobile_no": "+92-300-1234567",
        "current_office_location": "Islamabad",
        "emergency_contact_no": "",
        "date_of_joining_ismo": "2015-03-01",
        "current_designation": "Assistant Manager",
        "current_grade": "G-07",
        "department_function": "System Operation",
        "current_supervisor_name": "Section Head",
        "date_of_appointment_to_current_grade": "2019-07-01",
        "total_service_ismo": "10 years",
        "total_relevant_experience": "12 years",
        "date_of_joining_current_position": "2019-07-01",
        # 3
        "education": [
            {"degree_qualification": "MSc Electrical Engineering",
             "major_field_of_study": "Power Systems", "institution_university": "UET Lahore",
             "country": "Pakistan", "year_of_completion": 2014, "cgpa_division": "3.6 / 4.0"},
            {"degree_qualification": "BSc Electrical Engineering",
             "major_field_of_study": "Electrical", "institution_university": "UET Lahore",
             "country": "Pakistan", "year_of_completion": 2011, "cgpa_division": "3.4 / 4.0"},
        ],
        # 4
        "experience": [
            {"organization_employer": "ISMO", "designation": "Assistant Manager",
             "grade": "G-07", "from_date": "2019-07-01", "to_date": None, "is_current": True,
             "duration": "", "key_responsibilities": "Real-time dispatch and grid operations.",
             "key_achievements": "Cut dispatch errors by 20%."},
        ],
        # 5
        "skills_technical_tags": ["Python", "SCADA", "python", "  Power   Flow "],
        "skills_soft_checkboxes": ["Teamwork & Collaboration", "Leadership"],
        "certifications": [],
        "trainings": [],
        # 6
        "application_rationale_sop": (
            "I have spent five years in grid operations and want to apply that "
            "experience to market operations planning."
        ),
        "ack_manager_notified_bool": True,
        "ack_data_accuracy_bool": True,
        "declaration_accepted": True,
        "applicant_signature": "Muhammad Adil",
    }


# ---------------------------------------------------------------------------
# Validation rules from the specification
# ---------------------------------------------------------------------------

class ValidatorTests(TestCase):
    def check(self, **changes):
        data = valid_payload([1])
        data.update(changes)
        return validate_application(data)

    def test_complete_submission_is_accepted(self):
        cleaned, errors = self.check()
        self.assertEqual(errors, {})
        self.assertEqual(cleaned["preferred_contact_method"], "Teams")

    def test_requisition_is_required(self):
        _, errors = self.check(target_job_req_ids=[])
        self.assertIn("target_job_req_ids", errors)

    # ---- section 2 ------------------------------------------------------
    def test_contact_phone_and_corporate_email_are_required(self):
        _, errors = self.check(mobile_no="", official_email="")
        self.assertIn("mobile_no", errors)
        self.assertIn("official_email", errors)

    def test_bad_phone_and_email_are_refused(self):
        _, errors = self.check(mobile_no="abc", official_email="not-an-email")
        self.assertIn("mobile_no", errors)
        self.assertIn("official_email", errors)

    def test_personal_email_is_optional(self):
        cleaned, errors = self.check(personal_email="")
        self.assertEqual(errors, {})
        self.assertIsNone(cleaned["personal_email"])

    def test_personal_email_must_be_valid(self):
        _, errors = self.check(personal_email="nope@")
        self.assertIn("personal_email", errors)

    def test_personal_email_cannot_repeat_the_corporate_one(self):
        _, errors = self.check(personal_email="Muhammad.Adil@ismo.gov.pk")
        self.assertIn("personal_email", errors)

    def test_contact_channel_is_required_and_limited(self):
        for method in ("Teams", "Email", "SMS"):
            _, errors = self.check(preferred_contact_method=method)
            self.assertNotIn("preferred_contact_method", errors, method)
        for bad in ("", "Fax", "teams"):
            _, errors = self.check(preferred_contact_method=bad)
            self.assertIn("preferred_contact_method", errors, bad)

    # ---- section 3 ------------------------------------------------------
    def test_at_least_one_qualification(self):
        _, errors = self.check(education=[])
        self.assertIn("education", errors)

    def test_education_row_fields_are_required(self):
        _, errors = self.check(education=[{"degree_qualification": "BSc"}])
        row = errors["education_rows"][0]
        for field in ("major_field_of_study", "institution_university",
                      "year_of_completion", "cgpa_division"):
            self.assertIn(field, row)

    def test_graduation_year_range(self):
        data = valid_payload([1])
        data["education"][0]["year_of_completion"] = 1900
        _, errors = validate_application(data)
        self.assertIn("year_of_completion", errors["education_rows"][0])

    def test_education_is_stored_chronologically(self):
        cleaned, errors = self.check()
        self.assertEqual(errors, {})
        self.assertEqual([row["year_of_completion"] for row in cleaned["education"]],
                         [2011, 2014])
        self.assertEqual([row["row_order"] for row in cleaned["education"]], [0, 1])

    # ---- section 4 ------------------------------------------------------
    def test_present_role_needs_no_end_date(self):
        cleaned, errors = self.check()
        self.assertEqual(errors, {})
        self.assertIsNone(cleaned["experience"][0]["to_date"])

    def test_past_role_needs_an_end_date_after_the_start(self):
        data = valid_payload([1])
        data["experience"][0].update(is_current=False, to_date=None)
        _, errors = validate_application(data)
        self.assertIn("to_date", errors["experience_rows"][0])

        data["experience"][0].update(to_date="2018-01-01")
        _, errors = validate_application(data)
        self.assertIn("to_date", errors["experience_rows"][0])

    def test_start_date_cannot_be_in_the_future(self):
        data = valid_payload([1])
        data["experience"][0]["from_date"] = (date.today() + timedelta(days=5)).isoformat()
        _, errors = validate_application(data)
        self.assertIn("from_date", errors["experience_rows"][0])

    def test_responsibilities_limit_is_1500(self):
        data = valid_payload([1])
        data["experience"][0]["key_responsibilities"] = "x" * 1500
        self.assertEqual(validate_application(data)[1], {})
        data["experience"][0]["key_responsibilities"] = "x" * 1501
        self.assertIn("key_responsibilities", validate_application(data)[1]["experience_rows"][0])

    def test_achievements_are_optional_and_limited_to_2000(self):
        data = valid_payload([1])
        data["experience"][0]["key_achievements"] = ""
        self.assertEqual(validate_application(data)[1], {})
        data["experience"][0]["key_achievements"] = "x" * 2000
        self.assertEqual(validate_application(data)[1], {})
        data["experience"][0]["key_achievements"] = "x" * 2001
        self.assertIn("key_achievements", validate_application(data)[1]["experience_rows"][0])

    # ---- section 5 ------------------------------------------------------
    def test_technical_tags_are_trimmed_and_deduplicated(self):
        cleaned, _ = self.check()
        self.assertEqual(cleaned["skills_technical_tags"], ["Python", "SCADA", "Power Flow"])

    def test_at_least_one_technical_skill(self):
        _, errors = self.check(skills_technical_tags=["  "])
        self.assertIn("skills_technical_tags", errors)

    def test_technical_skill_limits(self):
        _, errors = self.check(skills_technical_tags=["x" * 51])
        self.assertIn("skills_technical_tags", errors)
        _, errors = self.check(skills_technical_tags=[f"skill {n}" for n in range(31)])
        self.assertIn("skills_technical_tags", errors)
        _, errors = self.check(skills_technical_tags="Python")
        self.assertIn("skills_technical_tags", errors)

    def test_soft_skills_come_from_the_predefined_list(self):
        _, errors = self.check(skills_soft_checkboxes=["Juggling"])
        self.assertIn("skills_soft_checkboxes", errors)

    def test_soft_skills_are_optional_and_kept_in_list_order(self):
        cleaned, errors = self.check(skills_soft_checkboxes=[])
        self.assertEqual(errors, {})
        cleaned, _ = self.check()
        self.assertEqual(cleaned["skills_soft_checkboxes"],
                         ["Leadership", "Teamwork & Collaboration"])
        self.assertEqual(SOFT_SKILLS.index("Leadership"), 0)

    def test_certification_rows_are_complete_once_started(self):
        _, errors = self.check(certifications=[{"certification_membership": "PMP"}])
        self.assertIn("certifying_body", errors["certification_rows"][0])

    # ---- section 6 ------------------------------------------------------
    def test_statement_of_purpose_is_required_and_bounded(self):
        _, errors = self.check(application_rationale_sop="")
        self.assertIn("application_rationale_sop", errors)
        _, errors = self.check(application_rationale_sop="Too short.")
        self.assertIn("application_rationale_sop", errors)
        _, errors = self.check(application_rationale_sop="x" * 3000)
        self.assertNotIn("application_rationale_sop", errors)
        _, errors = self.check(application_rationale_sop="x" * 3001)
        self.assertIn("application_rationale_sop", errors)

    def test_both_acknowledgements_are_required(self):
        _, errors = self.check(ack_manager_notified_bool=False, ack_data_accuracy_bool=False)
        self.assertIn("ack_manager_notified_bool", errors)
        self.assertIn("ack_data_accuracy_bool", errors)

    def test_acknowledgements_must_be_real_booleans(self):
        _, errors = self.check(ack_manager_notified_bool="true", ack_data_accuracy_bool=1,
                               declaration_accepted="yes")
        self.assertIn("ack_manager_notified_bool", errors)
        self.assertIn("ack_data_accuracy_bool", errors)
        self.assertIn("declaration_accepted", errors)

    def test_signature_must_match_the_name(self):
        _, errors = self.check(applicant_signature="Someone Else")
        self.assertIn("applicant_signature", errors)

    def test_signature_ignores_the_title_on_record(self):
        for signature in ("Muhammad Adil", "mr. muhammad adil", "MUHAMMAD ADIL"):
            _, errors = self.check(full_name="Mr. MUHAMMAD ADIL",
                                   applicant_signature=signature)
            self.assertNotIn("applicant_signature", errors, signature)
        # A title is not a name: "Mr. Adil" alone does not sign for the full name.
        _, errors = self.check(full_name="Mr. MUHAMMAD ADIL", applicant_signature="Mr. Adil")
        self.assertIn("applicant_signature", errors)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@mock.patch("jobs.views.employee_record", side_effect=lambda erp: copy.deepcopy(RECORD)
            if int(erp) == APPLICANT_ERP else None)
class ApplicationEndpointTests(TestCase):
    def setUp(self):
        self.open_vacancy = JobRequisition.objects.create(
            title="Manager Market Operations", reference_no="ADV-01", grade="G-08",
            closing_date=date.today() + timedelta(days=10),
        )
        self.second_vacancy = JobRequisition.objects.create(title="Deputy Manager Planning")
        self.closed_vacancy = JobRequisition.objects.create(title="Closed Post", is_open=False)
        self.expired_vacancy = JobRequisition.objects.create(
            title="Expired Post", closing_date=date.today() - timedelta(days=1)
        )

    def post(self, data, headers=None):
        return self.client.post(
            "/api/jobs/applications/create/", data=json.dumps(data),
            content_type="application/json", **(auth() if headers is None else headers),
        )

    # ---- vacancy list -----------------------------------------------------
    def test_only_open_unexpired_vacancies_are_offered(self, _record):
        response = self.client.get("/api/jobs/requisitions/")
        titles = {row["title"] for row in response.json()}
        self.assertEqual(titles, {"Manager Market Operations", "Deputy Manager Planning"})

    # ---- profile ------------------------------------------------------------
    def test_profile_needs_a_session(self, _record):
        self.assertEqual(self.client.get("/api/jobs/application-profile/").status_code, 401)

    def test_profile_is_the_signed_in_employee(self, _record):
        response = self.client.get(
            "/api/jobs/application-profile/", {"erp_id": 999}, **auth()
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["emp_id"], APPLICANT_ERP)
        self.assertEqual(body["current_supervisor_name"], "Section Head")
        self.assertNotIn("locked_fields", body)
        self.assertEqual(
            set(body["record_fields"]),
            {"emp_id", "full_name", "department_function", "current_designation",
             "current_grade", "current_supervisor_name", "cnic", "gender",
             "official_email", "current_office_location"},
        )
        self.assertEqual(body["contact_methods"], ["Teams", "Email", "SMS"])
        self.assertEqual(body["soft_skill_options"], list(SOFT_SKILLS))

    def test_profile_for_an_unlinked_account(self, _record):
        response = self.client.get("/api/jobs/application-profile/", **auth(erp_id=0))
        self.assertEqual(response.status_code, 401)
        response = self.client.get("/api/jobs/application-profile/", **auth(erp_id=12345))
        self.assertEqual(response.status_code, 404)

    # ---- submitting -------------------------------------------------------
    def test_submission_needs_a_session(self, _record):
        response = self.post(valid_payload([self.open_vacancy.id]), headers={})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(InternalJobApplication.objects.count(), 0)

    def test_submission_is_stored_with_every_spec_field(self, _record):
        response = self.post(valid_payload([self.open_vacancy.id]))
        self.assertEqual(response.status_code, 201, response.content)

        application = InternalJobApplication.objects.get()
        self.assertEqual(application.applicant_erp_id, APPLICANT_ERP)
        self.assertTrue(application.application_reference_no.startswith("ISMO/IJA/"))
        self.assertEqual(application.current_supervisor_erp_id, SUPERVISOR_ERP)
        self.assertEqual(application.current_supervisor_name, "Section Head")
        self.assertEqual(application.personal_email, "adil.personal@gmail.com")
        self.assertEqual(application.preferred_contact_method, "Teams")
        self.assertEqual(application.technical_skills, ["Python", "SCADA", "Power Flow"])
        self.assertEqual(application.soft_skills, ["Leadership", "Teamwork & Collaboration"])
        self.assertTrue(application.application_rationale_sop.startswith("I have spent"))
        self.assertTrue(application.ack_manager_notified_bool)
        self.assertTrue(application.ack_data_accuracy_bool)
        self.assertEqual(
            list(application.education.values_list("year_of_completion", flat=True)),
            [2011, 2014],
        )
        experience = application.experience.get()
        self.assertEqual(experience.key_achievements, "Cut dispatch errors by 20%.")
        self.assertTrue(experience.is_current)
        self.assertIsNone(experience.to_date)

    def test_unchanged_prefill_records_no_changes(self, _record):
        response = self.post(valid_payload([self.open_vacancy.id]))
        self.assertEqual(response.json()["changed_from_record"], [])
        self.assertEqual(InternalJobApplication.objects.get().record_changes, {})

    def test_case_and_spacing_are_not_changes(self, _record):
        data = valid_payload([self.open_vacancy.id])
        data.update(current_grade="g-07 ", department_function="  system   operation")
        self.post(data)
        self.assertEqual(InternalJobApplication.objects.get().record_changes, {})

    def test_prefilled_fields_can_be_corrected(self, _record):
        data = valid_payload([self.open_vacancy.id])
        data.update(
            full_name="Muhammad Adil Khan", applicant_signature="Muhammad Adil Khan",
            department_function="Market Operations", current_designation="Deputy Manager",
            current_grade="G-08", cnic="35202-7654321-1",
        )
        response = self.post(data)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(
            response.json()["changed_from_record"],
            ["cnic", "current_designation", "current_grade", "department_function",
             "full_name"],
        )

        application = InternalJobApplication.objects.get()
        # What the applicant submitted is filed...
        self.assertEqual(application.full_name, "Muhammad Adil Khan")
        self.assertEqual(application.department_function, "Market Operations")
        self.assertEqual(application.current_designation, "Deputy Manager")
        self.assertEqual(application.current_grade, "G-08")
        # ...with what the record said kept alongside.
        self.assertEqual(application.record_changes["current_grade"],
                         {"record": "G-07", "submitted": "G-08"})
        self.assertEqual(application.record_changes["full_name"]["record"], "Muhammad Adil")

    def test_identity_still_comes_from_the_session(self, _record):
        data = valid_payload([self.open_vacancy.id])
        data.update(applicant_erp_id=1, emp_id=999)
        self.assertEqual(self.post(data).status_code, 201)
        application = InternalJobApplication.objects.get()
        # Filed under the signed-in employee; the typed ID is only recorded.
        self.assertEqual(application.applicant_erp_id, APPLICANT_ERP)
        self.assertEqual(application.emp_id, 999)
        self.assertEqual(application.record_changes["emp_id"],
                         {"record": str(APPLICANT_ERP), "submitted": "999"})
        self.assertEqual(len(self.client.get("/api/jobs/applications/", **auth()).json()), 1)

    def test_signature_follows_the_corrected_name(self, _record):
        data = valid_payload([self.open_vacancy.id])
        data.update(full_name="Muhammad Adil Khan", applicant_signature="Muhammad Adil")
        response = self.post(data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("applicant_signature", response.json()["errors"])

    def test_corrected_supervisor_is_filed_but_not_alerted(self, _record):
        data = valid_payload([self.open_vacancy.id])
        data.update(current_supervisor_name="Real Manager")
        response = self.post(data)
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["supervisor_notified"])
        application = InternalJobApplication.objects.get()
        self.assertEqual(application.current_supervisor_name, "Real Manager")
        self.assertIsNone(application.current_supervisor_erp_id)
        self.assertEqual(Notification.objects.count(), 0)

    def test_supervisor_name_is_validated(self, _record):
        data = valid_payload([self.open_vacancy.id])
        data.update(current_supervisor_name="X" * 151)
        self.assertIn("current_supervisor_name", self.post(data).json()["errors"])

    def test_hr_sees_what_was_changed(self, _record):
        data = valid_payload([self.open_vacancy.id])
        data.update(current_grade="G-08")
        self.post(data)
        application = InternalJobApplication.objects.get()
        hr = auth(erp_id=1, superuser=True)
        detail = self.client.get(f"/api/jobs/applications/{application.id}/detail/", **hr).json()
        self.assertEqual(detail["record_changes"], [{
            "field": "current_grade", "label": "Current Grade",
            "record": "G-07", "submitted": "G-08",
        }])
        listed = self.client.get("/api/jobs/applications/manage/", **hr).json()["results"][0]
        self.assertEqual(listed["record_change_count"], 1)
        pdf = self.client.get(f"/api/jobs/applications/{application.id}/pdf/", **hr)
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_supervisor_is_notified(self, _record):
        self.post(valid_payload([self.open_vacancy.id]))
        notification = Notification.objects.get()
        self.assertEqual(notification.recipient_erp_id, SUPERVISOR_ERP)
        self.assertEqual(notification.category, "job_application")
        self.assertIn("Manager Market Operations", notification.message)

    def test_no_notification_without_a_supervisor(self, record):
        without = copy.deepcopy(RECORD)
        without.update(current_supervisor_erp_id=None, current_supervisor_name="")
        record.side_effect = lambda erp: copy.deepcopy(without)

        response = self.post(valid_payload([self.open_vacancy.id]))
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["supervisor_notified"])
        self.assertEqual(Notification.objects.count(), 0)

    def test_one_application_per_vacancy_chosen(self, _record):
        response = self.post(valid_payload([self.open_vacancy.id, self.second_vacancy.id]))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(InternalJobApplication.objects.count(), 2)
        references = {a["reference_no"] for a in response.json()["applications"]}
        self.assertEqual(len(references), 2)

    def test_applying_twice_is_refused(self, _record):
        self.post(valid_payload([self.open_vacancy.id]))
        response = self.post(valid_payload([self.open_vacancy.id]))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(InternalJobApplication.objects.count(), 1)

    def test_closed_and_expired_vacancies_are_refused(self, _record):
        for vacancy in (self.closed_vacancy, self.expired_vacancy):
            response = self.post(valid_payload([vacancy.id]))
            self.assertEqual(response.status_code, 400)
            self.assertIn("target_job_req_ids", response.json()["errors"])
        self.assertEqual(InternalJobApplication.objects.count(), 0)

    def test_invalid_submission_stores_nothing(self, _record):
        data = valid_payload([self.open_vacancy.id])
        data.update(ack_manager_notified_bool=False, application_rationale_sop="",
                    skills_technical_tags=[], preferred_contact_method="")
        response = self.post(data)
        self.assertEqual(response.status_code, 400)
        errors = response.json()["errors"]
        for field in ("ack_manager_notified_bool", "application_rationale_sop",
                      "skills_technical_tags", "preferred_contact_method"):
            self.assertIn(field, errors)
        self.assertEqual(InternalJobApplication.objects.count(), 0)

    def test_my_applications_are_only_my_own(self, _record):
        self.post(valid_payload([self.open_vacancy.id]))
        mine = self.client.get("/api/jobs/applications/", {"erp_id": 1}, **auth())
        self.assertEqual(len(mine.json()), 1)
        other = self.client.get("/api/jobs/applications/", **auth(erp_id=12345))
        self.assertEqual(other.json(), [])
        self.assertEqual(self.client.get("/api/jobs/applications/").status_code, 401)

    # ---- the HR side --------------------------------------------------------
    def test_hr_detail_report_and_pdf_carry_the_new_fields(self, _record):
        self.post(valid_payload([self.open_vacancy.id]))
        application = InternalJobApplication.objects.get()
        hr = auth(erp_id=1, superuser=True)

        detail = self.client.get(f"/api/jobs/applications/{application.id}/detail/", **hr)
        self.assertEqual(detail.status_code, 200)
        body = detail.json()
        self.assertEqual(body["current_supervisor_name"], "Section Head")
        self.assertEqual(body["preferred_contact_method"], "Teams")
        self.assertEqual(body["technical_skills"], ["Python", "SCADA", "Power Flow"])
        self.assertEqual(body["soft_skills"], ["Leadership", "Teamwork & Collaboration"])
        self.assertTrue(body["ack_manager_notified_bool"])
        self.assertEqual(body["experience"][0]["key_achievements"],
                         "Cut dispatch errors by 20%.")

        pdf = self.client.get(f"/api/jobs/applications/{application.id}/pdf/", **hr)
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_hr_pages_need_rights(self, _record):
        self.post(valid_payload([self.open_vacancy.id]))
        application = InternalJobApplication.objects.get()
        with mock.patch("jobs.reports_permissions._has_menu_right", return_value=False):
            response = self.client.get(
                f"/api/jobs/applications/{application.id}/detail/", **auth()
            )
        self.assertEqual(response.status_code, 403)

    def test_report_filters_by_exact_skill(self, _record):
        self.post(valid_payload([self.open_vacancy.id]))
        hr = auth(erp_id=1, superuser=True)

        def count(**params):
            response = self.client.get("/api/jobs/applications/manage/", params, **hr)
            return response.json()["count"]

        self.assertEqual(count(skill="python"), 1)
        self.assertEqual(count(skill="Leadership"), 1)
        self.assertEqual(count(skill="Pyth"), 0)
        self.assertEqual(count(search="SCADA"), 1)


class ReportListStateTests(TestCase):
    """What the report list says when it has nothing to show, or cannot read."""

    def setUp(self):
        self.hr = auth(erp_id=1, superuser=True)

    def test_empty_report_reports_its_totals(self):
        JobRequisition.objects.create(title="Open Post")
        JobRequisition.objects.create(title="Closed Post", is_open=False)
        body = self.client.get("/api/jobs/applications/manage/", **self.hr).json()
        self.assertEqual(body["results"], [])
        self.assertEqual(body["count"], 0)
        self.assertEqual(body["total_applications"], 0)
        self.assertEqual(body["open_vacancies"], 1)

    def test_database_failure_is_a_clear_503(self):
        from django.db import DatabaseError

        with mock.patch("jobs.reports_views.Paginator",
                        side_effect=DatabaseError("Invalid column name")):
            response = self.client.get("/api/jobs/applications/manage/", **self.hr)
        self.assertEqual(response.status_code, 503)
        self.assertIn("database", response.json()["error"])
        self.assertNotIn("Invalid column name", response.json()["error"])


# ---------------------------------------------------------------------------
# Advertisement PDF, delete rules, how-to-apply instructions
# ---------------------------------------------------------------------------

import os
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
MEDIA = tempfile.mkdtemp(prefix="ismo-test-media-")


@override_settings(MEDIA_ROOT=MEDIA)
class AdvertisementTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.hr = auth(erp_id=1, superuser=True)
        self.vacancy = JobRequisition.objects.create(title="Manager Market Operations")

    def upload(self, content=PDF_BYTES, name="Advert 14.pdf", headers=None, vacancy=None):
        vacancy = vacancy or self.vacancy
        return self.client.post(
            f"/api/jobs/requisitions/{vacancy.id}/advertisement/",
            {"file": SimpleUploadedFile(name, content, content_type="application/pdf")},
            **(self.hr if headers is None else headers),
        )

    def test_upload_view_and_list(self):
        response = self.upload()
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["advertisement_name"], "Advert 14.pdf")
        self.assertTrue(body["advertisement_url"].endswith("/advertisement/view/"))

        view = self.client.get(f"/api/jobs/requisitions/{self.vacancy.id}/advertisement/view/")
        self.assertEqual(view.status_code, 200)
        self.assertEqual(view["Content-Type"], "application/pdf")
        self.assertIn("inline", view["Content-Disposition"])
        self.assertEqual(b"".join(view.streaming_content), PDF_BYTES)

        managed = self.client.get("/api/jobs/requisitions/manage/").json()[0]
        self.assertEqual(managed["advertisement_name"], "Advert 14.pdf")
        offered = self.client.get("/api/jobs/requisitions/").json()[0]
        self.assertTrue(offered["advertisement_url"])

    def test_only_real_pdfs_are_accepted(self):
        cases = {
            "word file": dict(name="advert.docx"),
            "renamed text": dict(content=b"hello, not a pdf", name="advert.pdf"),
            "empty": dict(content=b"", name="advert.pdf"),
            "too large": dict(content=b"%PDF-" + b"0" * (10 * 1024 * 1024), name="big.pdf"),
        }
        for label, kwargs in cases.items():
            response = self.upload(**kwargs)
            self.assertEqual(response.status_code, 400, label)
            self.assertIn("advertisement_pdf", response.json()["errors"], label)
        self.vacancy.refresh_from_db()
        self.assertFalse(self.vacancy.advertisement_pdf)

    def test_upload_needs_rights(self):
        with mock.patch("jobs.permissions._has_menu_right", return_value=False):
            response = self.upload(headers=auth())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.upload(headers={}).status_code, 403)

    def test_replacing_removes_the_old_file(self):
        self.upload()
        self.vacancy.refresh_from_db()
        first = self.vacancy.advertisement_pdf.path
        self.upload(content=PDF_BYTES + b"% v2\n", name="Advert v2.pdf")
        self.vacancy.refresh_from_db()
        self.assertEqual(self.vacancy.advertisement_pdf_name, "Advert v2.pdf")
        self.assertTrue(os.path.exists(self.vacancy.advertisement_pdf.path))
        if first != self.vacancy.advertisement_pdf.path:
            self.assertFalse(os.path.exists(first))

    def test_remove_advertisement(self):
        self.upload()
        self.vacancy.refresh_from_db()
        path = self.vacancy.advertisement_pdf.path
        response = self.client.post(
            f"/api/jobs/requisitions/{self.vacancy.id}/advertisement/remove/", **self.hr
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["advertisement_url"], "")
        self.assertFalse(os.path.exists(path))
        view = self.client.get(f"/api/jobs/requisitions/{self.vacancy.id}/advertisement/view/")
        self.assertEqual(view.status_code, 404)

    # ---- delete rules -------------------------------------------------------
    def delete(self, vacancy):
        return self.client.post(f"/api/jobs/requisitions/{vacancy.id}/delete/", **self.hr)

    def test_live_vacancy_cannot_be_deleted(self):
        listed = self.client.get("/api/jobs/requisitions/manage/").json()[0]
        self.assertTrue(listed["is_live"])
        self.assertFalse(listed["can_delete"])
        self.assertIn("live", listed["delete_blocked_reason"])

        response = self.delete(self.vacancy)
        self.assertEqual(response.status_code, 409)
        self.assertIn("live", response.json()["error"])
        self.assertTrue(JobRequisition.objects.filter(id=self.vacancy.id).exists())

    def test_vacancy_with_applications_cannot_be_deleted_even_when_closed(self):
        with mock.patch("jobs.views.employee_record", return_value=copy.deepcopy(RECORD)):
            self.client.post("/api/jobs/applications/create/",
                             data=json.dumps(valid_payload([self.vacancy.id])),
                             content_type="application/json", **auth())
        self.vacancy.is_open = False
        self.vacancy.save()

        response = self.delete(self.vacancy)
        self.assertEqual(response.status_code, 409)
        self.assertIn("1 application(s)", response.json()["error"])
        listed = self.client.get("/api/jobs/requisitions/manage/").json()[0]
        self.assertFalse(listed["can_delete"])

    def test_closed_or_expired_vacancy_without_applications_can_be_deleted(self):
        self.upload()
        self.vacancy.refresh_from_db()
        path = self.vacancy.advertisement_pdf.path
        self.vacancy.is_open = False
        self.vacancy.save()
        self.assertTrue(self.client.get("/api/jobs/requisitions/manage/").json()[0]["can_delete"])
        self.assertEqual(self.delete(self.vacancy).status_code, 200)
        self.assertFalse(os.path.exists(path))

        expired = JobRequisition.objects.create(
            title="Expired Post", closing_date=date.today() - timedelta(days=1)
        )
        self.assertFalse(expired.is_live)
        self.assertEqual(self.delete(expired).status_code, 200)

    def test_vacancy_closing_today_is_still_live(self):
        today = JobRequisition.objects.create(title="Closes Today", closing_date=date.today())
        self.assertTrue(today.is_live)
        self.assertEqual(self.delete(today).status_code, 409)


class InstructionsTests(TestCase):
    def test_instructions_are_public_and_structured(self):
        response = self.client.get("/api/jobs/application-instructions/")
        self.assertEqual(response.status_code, 200)
        sections = response.json()["sections"]
        self.assertEqual([s["heading"] for s in sections],
                         ["Before you start", "Filling in the form", "Submitting"])
        self.assertTrue(all(s["points"] for s in sections))


# ---------------------------------------------------------------------------
# Each job opening has its own job description
# ---------------------------------------------------------------------------

from django.db import IntegrityError, transaction

from .models import JobDescription


class OneDescriptionPerOpeningTests(TestCase):
    def setUp(self):
        self.hr = auth(erp_id=1, superuser=True)
        self.jd_a = JobDescription.objects.create(title="JD A", key_responsibilities="A duties")
        self.jd_b = JobDescription.objects.create(title="JD B", key_responsibilities="B duties")

    def create(self, title, jd):
        return self.client.post(
            "/api/jobs/requisitions/create/",
            data=json.dumps({"title": title, "job_description_id": jd}),
            content_type="application/json", **self.hr,
        )

    def update(self, vacancy, **changes):
        body = {"title": vacancy.title, "job_description_id": vacancy.job_description_id,
                "is_open": vacancy.is_open}
        body.update(changes)
        return self.client.post(
            f"/api/jobs/requisitions/{vacancy.id}/update/",
            data=json.dumps(body), content_type="application/json", **self.hr,
        )

    def test_new_opening_needs_a_job_description(self):
        response = self.create("Manager Planning", None)
        self.assertEqual(response.status_code, 400)
        self.assertIn("job_description_id", response.json()["errors"])

    def test_each_new_opening_gets_its_own_description(self):
        self.assertEqual(self.create("Manager Planning", self.jd_a.id).status_code, 201)
        response = self.create("Deputy Manager Planning", self.jd_a.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Manager Planning", response.json()["errors"]["job_description_id"])
        self.assertEqual(self.create("Deputy Manager Planning", self.jd_b.id).status_code, 201)

    def test_description_of_a_closed_opening_is_still_taken(self):
        self.create("Manager Planning", self.jd_a.id)
        JobRequisition.objects.filter(title="Manager Planning").update(is_open=False)
        self.assertEqual(self.create("Readvertised Post", self.jd_a.id).status_code, 400)

    def test_editing_keeps_or_swaps_but_never_shares(self):
        self.create("Manager Planning", self.jd_a.id)
        self.create("Deputy Manager Planning", self.jd_b.id)
        first = JobRequisition.objects.get(title="Manager Planning")

        self.assertEqual(self.update(first, location="ISMO-Lahore").status_code, 200)
        self.assertEqual(self.update(first, is_open=False).status_code, 200)
        response = self.update(first, job_description_id=self.jd_b.id)
        self.assertEqual(response.status_code, 400)
        response = self.update(first, job_description_id=None)
        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot be removed", response.json()["errors"]["job_description_id"])

        jd_c = JobDescription.objects.create(title="JD C", key_responsibilities="C duties")
        self.assertEqual(self.update(first, job_description_id=jd_c.id).status_code, 200)
        # JD A is free again once its opening moves to JD C.
        self.assertEqual(self.create("Another Post", self.jd_a.id).status_code, 201)

    def test_older_opening_without_a_description_can_still_be_edited(self):
        legacy = JobRequisition.objects.create(title="Test JOB")
        self.assertEqual(self.update(legacy, is_open=False).status_code, 200)
        self.assertEqual(self.update(legacy, job_description_id=self.jd_a.id).status_code, 200)

    def test_description_list_says_which_opening_holds_it(self):
        self.create("Manager Planning", self.jd_a.id)
        rows = {row["title"]: row for row in self.client.get("/api/jobs/descriptions/").json()}
        self.assertEqual(rows["JD A"]["requisition_title"], "Manager Planning")
        self.assertIsNone(rows["JD B"]["requisition_id"])

    def test_database_refuses_sharing_too(self):
        JobRequisition.objects.create(title="One", job_description=self.jd_a)
        JobRequisition.objects.create(title="Legacy 1")
        JobRequisition.objects.create(title="Legacy 2")  # two NULLs are fine
        with self.assertRaises(IntegrityError), transaction.atomic():
            JobRequisition.objects.create(title="Two", job_description=self.jd_a)


# ---------------------------------------------------------------------------
# Department and location come from the sections and locations tables
# ---------------------------------------------------------------------------

class DepartmentLocationTests(TestCase):
    def setUp(self):
        self.hr = auth(erp_id=1, superuser=True)
        self.jd = JobDescription.objects.create(title="JD", key_responsibilities="Duties")

    def create(self, **fields):
        body = {"title": "Manager Planning", "job_description_id": self.jd.id, **fields}
        return self.client.post("/api/jobs/requisitions/create/", data=json.dumps(body),
                                content_type="application/json", **self.hr)

    def test_options_endpoint_lists_both_tables(self):
        body = self.client.get("/api/jobs/requisitions/options/").json()
        self.assertEqual(body, OPTIONS)

    def test_listed_department_and_location_are_accepted(self):
        response = self.create(department="Planning", location="ISMO-Lahore", grade="MG-09")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["grade"], "MG-09")
        self.assertEqual(response.json()["department"], "Planning")
        self.assertEqual(response.json()["location"], "ISMO-Lahore")

    def test_both_stay_optional(self):
        self.assertEqual(self.create().status_code, 201)

    def test_values_outside_the_tables_are_refused(self):
        errors = self.create(department="Board of Directors", location="Karachi",
                             grade="G-99").json()["errors"]
        self.assertEqual(errors["grade"], "Choose a grade from the list")
        self.assertEqual(errors["department"], "Choose a department from the list")
        self.assertEqual(errors["location"], "Choose a location from the list")

    def test_older_vacancy_keeps_its_unlisted_values(self):
        legacy = JobRequisition.objects.create(
            title="Old Post", department="Old Department", location="Islamabad",
            grade="G-09", job_description=self.jd,
        )
        body = {"title": "Old Post", "department": "Old Department", "location": "Islamabad",
                "grade": "G-09",
                "job_description_id": self.jd.id, "is_open": False}
        response = self.client.post(f"/api/jobs/requisitions/{legacy.id}/update/",
                                    data=json.dumps(body), content_type="application/json",
                                    **self.hr)
        self.assertEqual(response.status_code, 200, response.content)
        body["department"] = "Another Unlisted"
        response = self.client.post(f"/api/jobs/requisitions/{legacy.id}/update/",
                                    data=json.dumps(body), content_type="application/json",
                                    **self.hr)
        self.assertIn("department", response.json()["errors"])

    def test_lookup_failure_does_not_block_saving(self):
        with mock.patch("jobs.requisition_views.department_and_location_options",
                        side_effect=RuntimeError("SQL Server down")):
            self.assertEqual(self.create(department="Planning").status_code, 201)
            self.assertEqual(self.client.get("/api/jobs/requisitions/options/").status_code, 503)


class DescriptionDepartmentTests(TestCase):
    """Job Descriptions take their department from the sections table too."""

    def setUp(self):
        self.hr = auth(erp_id=1, superuser=True)

    def create(self, **fields):
        body = {"title": "Manager Planning", "key_responsibilities": "Plans the grid for the year.",
                **fields}
        return self.client.post("/api/jobs/descriptions/create/", data=json.dumps(body),
                                content_type="application/json", **self.hr)

    def test_listed_department_is_accepted(self):
        response = self.create(department="Planning")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(JobDescription.objects.get().department, "Planning")

    def test_department_stays_optional(self):
        self.assertEqual(self.create().status_code, 201)

    def test_unlisted_department_is_refused(self):
        response = self.create(department="Board of Directors")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"]["department"], "Choose a department from the list")

    def test_older_description_keeps_its_department(self):
        old = JobDescription.objects.create(title="Old JD", department="Old Department",
                                            key_responsibilities="Duties of the old post.")
        body = {"title": "Old JD", "department": "Old Department",
                "key_responsibilities": "Duties of the old post, revised."}
        url = f"/api/jobs/descriptions/{old.id}/update/"
        ok = self.client.post(url, data=json.dumps(body), content_type="application/json", **self.hr)
        self.assertEqual(ok.status_code, 200, ok.content)
        body["department"] = "Another Unlisted"
        refused = self.client.post(url, data=json.dumps(body), content_type="application/json", **self.hr)
        self.assertIn("department", refused.json()["errors"])
