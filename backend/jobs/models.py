from django.db import models


class JobRequisition(models.Model):
    """An advertised internal vacancy, the thing an application targets.

    Maintained by HR — registered in the Django admin so openings can be added
    without a screen of their own. Closing one hides it from the application
    form without touching applications already submitted against it.
    """

    title = models.CharField(max_length=200)
    # Free text rather than a foreign key to `sections`: a requisition is often
    # advertised for a business unit that is not one section exactly.
    department = models.CharField(max_length=200, null=True, blank=True)
    location = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    closing_date = models.DateField(null=True, blank=True)
    is_open = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'job_requisitions'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class InternalJobApplication(models.Model):
    """One employee's application against one requisition.

    The auto-filled fields are stored as submitted rather than looked up on
    read: `employees` changes over time, and an application should still show
    the department and job title the applicant actually held when they applied.
    """

    TEAMS = "Teams"
    EMAIL = "Email"
    SMS = "SMS"
    CONTACT_METHODS = (TEAMS, EMAIL, SMS)

    # Who applied, taken from the session rather than the form, so the record
    # cannot be filed under somebody else by editing the page.
    applicant_erp_id = models.IntegerField(db_index=True)

    target_job_req = models.ForeignKey(
        JobRequisition, on_delete=models.PROTECT, related_name="applications"
    )

    # --- section 1: target position and internal validation ---------------
    emp_full_name = models.CharField(max_length=150)
    emp_id = models.IntegerField()
    current_dept_code = models.CharField(max_length=200)
    current_job_title = models.CharField(max_length=200)
    # The label asks for a name; the ERP id is kept alongside it when the
    # supervisor was the one the system proposed, so the record can be traced
    # back to a person rather than a spelling.
    current_supervisor_id = models.CharField(max_length=150)
    current_supervisor_erp_id = models.IntegerField(null=True, blank=True)

    # --- section 2: personal and contact information ----------------------
    cnic = models.CharField(max_length=15)
    contact_phone_no = models.CharField(max_length=25)
    corporate_email = models.EmailField(max_length=150)
    personal_email = models.EmailField(max_length=150, null=True, blank=True)
    preferred_contact_method = models.CharField(max_length=10)

    status = models.CharField(max_length=20, default="submitted")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'internal_job_applications'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.emp_full_name} -> {self.target_job_req_id}"


class InternalJobApplicationEducation(models.Model):
    """One degree or certificate on an application.

    A separate table rather than repeated columns: the form is a repeater and
    the number of degrees is not knowable in advance.
    """

    application = models.ForeignKey(
        InternalJobApplication, on_delete=models.CASCADE, related_name="education"
    )

    edu_degree_title = models.CharField(max_length=200)
    edu_institution_name = models.CharField(max_length=200)
    edu_major_specialization = models.CharField(max_length=200)
    edu_graduation_year = models.IntegerField()
    edu_grade_score = models.CharField(max_length=40)

    # The order the applicant listed them in, so a chronological list comes
    # back the way it was entered.
    row_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'internal_job_application_education'
        ordering = ['row_order', 'id']

    def __str__(self):
        return f"{self.edu_degree_title} ({self.edu_graduation_year})"
