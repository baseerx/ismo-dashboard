"""Tables behind the ISMO internal recruitment online application form.

The shape follows the printed form section by section - vacancy information,
personal and contact information, current employment details, then the four
repeating tables (education, employment history, certifications, trainings),
the declaration, and the submission record. Anything the form prints in more
than one place is stored once and rendered twice.
"""

from django.db import models


class JobRequisition(models.Model):
    """An advertised internal vacancy - what section 1 of the form describes.

    Maintained from Job Openings under Internal Recruitment Portal. Closing one
    hides it from the application form without touching applications already
    submitted against it.
    """

    # "Position Title" on the form.
    title = models.CharField(max_length=200)
    # "Advertisement / Reference No." - the number the advertisement carries, so
    # an application can be traced back to the notice it answered.
    reference_no = models.CharField(max_length=100, null=True, blank=True)
    # The grade the post is advertised at, as text ("G-09"): grades come and go
    # and a closed vacancy should still print what it said at the time.
    grade = models.CharField(max_length=40, null=True, blank=True)
    # "Department / Function" - free text rather than a foreign key to
    # `sections`, because a post is often advertised for a business unit that is
    # not one section exactly.
    department = models.CharField(max_length=200, null=True, blank=True)
    advertisement_date = models.DateField(null=True, blank=True)
    closing_date = models.DateField(null=True, blank=True)

    # Not printed in section 1, but needed to advertise the post at all.
    location = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    is_open = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'job_requisitions'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class InternalJobApplication(models.Model):
    """One employee's application against one vacancy.

    An applicant may apply for several vacancies at once; each becomes a row of
    its own, because each is reviewed and progresses separately.

    The vacancy and employment details are stored as submitted rather than
    looked up on read: both `employees` and the advertisement change over time,
    and a submitted application should still print what it said on the day.
    """

    PENDING = "submitted"
    HR_STATUS_LABELS = {
        "submitted": "Pending verification",
        "under_review": "Under review",
        "verified": "Verified",
        "shortlisted": "Shortlisted",
        "rejected": "Rejected",
        "hired": "Selected",
    }

    # Who applied, taken from the session rather than the form, so the record
    # cannot be filed under somebody else by editing the page.
    applicant_erp_id = models.IntegerField(db_index=True)

    target_job_req = models.ForeignKey(
        JobRequisition, on_delete=models.PROTECT, related_name="applications"
    )

    # --- 1. vacancy information (copied from the advertisement) -----------
    vacancy_position_title = models.CharField(max_length=200, default="")
    vacancy_reference_no = models.CharField(max_length=100, null=True, blank=True)
    vacancy_grade = models.CharField(max_length=40, null=True, blank=True)
    vacancy_department = models.CharField(max_length=200, null=True, blank=True)
    vacancy_advertisement_date = models.DateField(null=True, blank=True)
    vacancy_closing_date = models.DateField(null=True, blank=True)

    # --- 2. personal & contact information --------------------------------
    emp_id = models.IntegerField()
    full_name = models.CharField(max_length=150)
    father_or_husband_name = models.CharField(max_length=150, default="")
    cnic = models.CharField(max_length=15)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, default="")
    official_email = models.EmailField(max_length=150)
    mobile_no = models.CharField(max_length=25)
    current_office_location = models.CharField(max_length=200, default="")
    # The one field the form itself marks optional.
    emergency_contact_no = models.CharField(max_length=25, null=True, blank=True)

    # --- 3. current employment details ------------------------------------
    # Current designation and grade also head section 1 of the printed form;
    # they are held once here and rendered in both places.
    date_of_joining_ismo = models.DateField(null=True, blank=True)
    current_designation = models.CharField(max_length=200, default="")
    current_grade = models.CharField(max_length=40, default="")
    department_function = models.CharField(max_length=200, default="")
    date_of_appointment_to_current_grade = models.DateField(null=True, blank=True)
    # Free text ("8 years 3 months"): the form asks for a span, and the figure
    # the applicant claims is what should be on the record, not a computed one.
    total_service_ismo = models.CharField(max_length=60, default="")
    total_relevant_experience = models.CharField(max_length=60, default="")
    date_of_joining_current_position = models.DateField(null=True, blank=True)

    # --- 8. declaration & undertaking -------------------------------------
    # Required to submit - see jobs/validators.py. Kept as a record of what the
    # applicant accepted at the time.
    declaration_accepted = models.BooleanField(default=False)

    # --- 9. submission record ---------------------------------------------
    # Typed confirmation standing in for a signature, which is what the form
    # calls an electronic signature.
    applicant_signature = models.CharField(max_length=150, default="")
    # Issued on submission, unique, and printed on the application.
    application_reference_no = models.CharField(
        max_length=40, null=True, blank=True, db_index=True
    )

    # Drives both the report filters and the form's "HR Verification Status".
    status = models.CharField(max_length=20, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'internal_job_applications'
        ordering = ['-created_at']
        constraints = [
            # One application per person per vacancy: two against the same post
            # would leave reviewers guessing which one counts.
            models.UniqueConstraint(
                fields=["applicant_erp_id", "target_job_req"],
                name="one_application_per_vacancy",
            )
        ]

    def __str__(self):
        return f"{self.full_name} -> {self.target_job_req_id}"

    @property
    def hr_verification_status(self) -> str:
        """What section 9 prints for the current status."""
        return self.HR_STATUS_LABELS.get(self.status, self.status)


class InternalJobApplicationEducation(models.Model):
    """4. Educational background - one row per qualification."""

    application = models.ForeignKey(
        InternalJobApplication, on_delete=models.CASCADE, related_name="education"
    )

    degree_qualification = models.CharField(max_length=200)
    major_field_of_study = models.CharField(max_length=200)
    institution_university = models.CharField(max_length=200)
    country = models.CharField(max_length=100)
    year_of_completion = models.IntegerField()
    cgpa_division = models.CharField(max_length=40)

    # The order the applicant listed them in, so the list comes back the way it
    # was entered.
    row_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'internal_job_application_education'
        ordering = ['row_order', 'id']

    def __str__(self):
        return f"{self.degree_qualification} ({self.year_of_completion})"


class InternalJobApplicationExperience(models.Model):
    """5. Employment history / professional experience - one row per post.

    Internal promotions belong here alongside outside employment, which is why
    the employer is free text: an applicant names the organisation or the
    department they held the post in, in their own words.
    """

    application = models.ForeignKey(
        InternalJobApplication, on_delete=models.CASCADE, related_name="experience"
    )

    organization_employer = models.CharField(max_length=200)
    designation = models.CharField(max_length=200)
    # "Grade (if applicable)" - blank for posts held outside ISMO.
    grade = models.CharField(max_length=40, null=True, blank=True)
    from_date = models.DateField()
    # Null while the applicant still holds the post.
    to_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    # Worked out from the dates when the applicant leaves it alone, but stored
    # rather than computed on read so the printed form matches what was filed.
    duration = models.CharField(max_length=60, default="")
    key_responsibilities = models.TextField()

    row_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'internal_job_application_experience'
        ordering = ['row_order', 'id']

    def __str__(self):
        return f"{self.designation} at {self.organization_employer}"


class InternalJobApplicationCertification(models.Model):
    """6. Professional certifications / memberships - one row each."""

    application = models.ForeignKey(
        InternalJobApplication, on_delete=models.CASCADE, related_name="certifications"
    )

    certification_membership = models.CharField(max_length=200)
    certifying_body = models.CharField(max_length=200)
    date_obtained = models.DateField(null=True, blank=True)
    # Blank for credentials that do not lapse.
    expiry_date = models.DateField(null=True, blank=True)
    registration_no = models.CharField(max_length=100, null=True, blank=True)

    row_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'internal_job_application_certifications'
        ordering = ['row_order', 'id']

    def __str__(self):
        return self.certification_membership


class InternalJobApplicationTraining(models.Model):
    """7. Trainings & professional development - one row each."""

    application = models.ForeignKey(
        InternalJobApplication, on_delete=models.CASCADE, related_name="trainings"
    )

    training_title = models.CharField(max_length=200)
    training_provider = models.CharField(max_length=200)
    duration = models.CharField(max_length=60, null=True, blank=True)
    # "Date / Year" on the form: a year alone is a perfectly good answer, so it
    # is text rather than a date.
    date_or_year = models.CharField(max_length=40, null=True, blank=True)
    relevant_to_position = models.BooleanField(default=False)

    row_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'internal_job_application_trainings'
        ordering = ['row_order', 'id']

    def __str__(self):
        return self.training_title
