"""Fixed wording from the printed application form.

Kept in one place so the page the applicant accepts, the PDF that is filed, and
the popup HR reviews all show exactly the same words.
"""

# Section 8 of the form, word for word.
DECLARATION_PARAGRAPHS = (
    "I hereby declare that all information and particulars provided by me in this application "
    "are true, complete and correct to the best of my knowledge and belief. I understand that "
    "any false, incorrect, misleading or concealed information may result in cancellation of my "
    "candidature or, in case of selection/appointment, cancellation of my appointment, in "
    "addition to any disciplinary action that may be taken against me under the applicable "
    "rules, policies and procedures of ISMO.",
    "I further confirm that, based on the eligibility criteria prescribed in the advertisement, "
    "I meet the requirements for the position applied for and am eligible to apply.",
    "I understand that submission of this application does not confer any right to appointment "
    "and that selection shall be made in accordance with the applicable recruitment process and "
    "criteria approved by ISMO.",
    "If selected, I undertake to accept the offer of appointment/promotion to the position for "
    "which I have applied and to comply with the terms and conditions of the offer as prescribed "
    "by ISMO.",
)

# The note printed under the submission record.
SUBMISSION_NOTE = (
    "Fields marked as mandatory in the online system should be completed before submission. "
    "Supporting documents may be required where specified in the advertisement."
)

# Spec section 2: how the applicant would like to be contacted.
CONTACT_METHODS = ("Teams", "Email", "SMS")

# Spec section 5: the predefined soft skills / leadership capabilities list.
# The applicant ticks any that apply; anything else is refused, so the report
# can filter on these exact words.
SOFT_SKILLS = (
    "Leadership",
    "Team Management",
    "Communication",
    "Problem Solving",
    "Decision Making",
    "Teamwork & Collaboration",
    "Time Management",
    "Adaptability",
    "Critical Thinking",
    "Conflict Resolution",
    "Stakeholder Management",
    "Mentoring & Coaching",
    "Negotiation",
    "Strategic Planning",
)

# Spec section 6: the two acknowledgements, word for word.
ACK_MANAGER_NOTIFIED = (
    "I certify that my current manager is aware of this transfer request"
)
ACK_DATA_ACCURACY = (
    "I confirm all provided data details match official corporate record"
)

# "How to apply / general instructions", shown in a popup on the application
# form. Each entry is (heading, [points]).
HOW_TO_APPLY = (
    ("Before you start", (
        "Open the vacancy and read its advertisement (the PDF attached to it) and its "
        "job description in full.",
        "Check that you meet the eligibility criteria the advertisement sets out - "
        "grade, qualifications and experience - before applying.",
        "Discuss the move with your current line manager. Section 6 asks you to confirm "
        "that they know, and they are notified automatically when you submit.",
    )),
    ("Filling in the form", (
        "Choose one or more advertised vacancies in section 1. The rest of the form is "
        "submitted once for each, and each is reviewed separately.",
        "Your name, employee ID, department, position title, grade, supervisor and "
        "contact details are filled in from your corporate record. Check them, and "
        "correct anything that is wrong - HR is shown what you changed.",
        "Complete every field marked with a red asterisk (*). Optional fields can be "
        "left blank.",
        "List your qualifications and your professional experience, including internal "
        "promotions, one row each. Use 'Present Role' for the post you hold now.",
        "Name your technical skills plainly (for example Python, SCADA, SAP) - HR "
        "searches applications by skill.",
        "Explain in section 6 why you are applying and how your experience fits the "
        "position.",
    )),
    ("Submitting", (
        "Accept the acknowledgements and the declaration, then type your full name as "
        "your electronic signature.",
        "Applications must be submitted before the vacancy's closing date. A vacancy "
        "disappears from the form once it closes.",
        "You can apply only once for each vacancy, and a submitted application cannot be "
        "edited. Check everything before you submit.",
        "Each application gets a reference number. You can follow its progress under "
        "'My Applications' at the bottom of the form.",
        "Supporting documents may be required where the advertisement says so. HR will "
        "contact you through the channel you choose in section 2.",
    )),
)
