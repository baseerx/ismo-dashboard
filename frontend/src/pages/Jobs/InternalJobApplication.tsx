import { useEffect, useMemo, useState } from "react";
import { ToastContainer, toast } from "react-toastify";
import PageMeta from "../../components/common/PageMeta";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import Label from "../../components/form/Label";
import Input from "../../components/form/input/InputField";
import Select from "../../components/form/Select";
import Checkbox from "../../components/form/input/Checkbox";
import TextArea from "../../components/form/input/TextArea";
import MultiSelect from "../../components/form/MultiSelect";
import Button from "../../components/ui/button/Button";
import Badge from "../../components/ui/badge/Badge";
import axios from "../../api/axios";
import moment from "moment";

/**
 * ISMO internal recruitment - online application form.
 *
 * Follows the printed form section by section, top to bottom: vacancy
 * information, personal and contact information, current employment details,
 * educational background, employment history, certifications, trainings, the
 * declaration, and the submission record.
 *
 * One submission may target several vacancies. Each becomes an application of
 * its own with its own reference number, because each is reviewed separately.
 *
 * Every limit and rule here is enforced again in jobs/validators.py, which is
 * what actually decides - a payload can be sent without going near this page.
 */

// Kept in step with jobs/validators.py.
const MAX_EDUCATION_ROWS = 15;
const MAX_EXPERIENCE_ROWS = 20;
const MAX_CERTIFICATION_ROWS = 15;
const MAX_TRAINING_ROWS = 20;
const MAX_VACANCIES = 10;
const MAX_RESPONSIBILITIES = 1500;

const GENDERS = ["Male", "Female", "Other"];

const CNIC = /^\d{5}-\d{7}-\d$/;
const PHONE = /^\+?[\d][\d\s\-()]{6,20}$/;
const EMAIL = /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/;

const EARLIEST_QUALIFICATION_YEAR = 1950;
const FUTURE_QUALIFICATION_YEARS = 6;

const today = () => moment().format("YYYY-MM-DD");

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type JobDescriptionBody = {
  id: number;
  title: string;
  code: string;
  department: string;
  grade: string;
  reports_to: string;
  job_purpose: string;
  key_responsibilities: string;
  qualifications: string;
  experience_required: string;
  skills_competencies: string;
};

type Requisition = {
  id: number;
  title: string;
  reference_no: string;
  grade: string;
  department: string;
  location: string;
  advertisement_date: string | null;
  closing_date: string | null;
  /** A note about this advertisement, as opposed to the description below. */
  notes: string;
  /** The description of the post, written once in the Job Descriptions library. */
  job_description: JobDescriptionBody | null;
};

type EducationRow = {
  degree_qualification: string;
  major_field_of_study: string;
  institution_university: string;
  country: string;
  year_of_completion: string;
  cgpa_division: string;
};

type ExperienceRow = {
  organization_employer: string;
  designation: string;
  grade: string;
  from_date: string;
  to_date: string;
  is_current: boolean;
  duration: string;
  key_responsibilities: string;
};

type CertificationRow = {
  certification_membership: string;
  certifying_body: string;
  date_obtained: string;
  expiry_date: string;
  registration_no: string;
};

type TrainingRow = {
  training_title: string;
  training_provider: string;
  duration: string;
  date_or_year: string;
  relevant_to_position: boolean;
};

type FormState = {
  /** Section 1: one submission can target several vacancies. */
  target_job_req_ids: string[];

  // 2. personal & contact information
  emp_id: string;
  full_name: string;
  father_or_husband_name: string;
  cnic: string;
  date_of_birth: string;
  gender: string;
  official_email: string;
  mobile_no: string;
  current_office_location: string;
  emergency_contact_no: string;

  // 3. current employment details (current designation and grade also head
  // section 1 of the printed form, and are shown in both places)
  date_of_joining_ismo: string;
  current_designation: string;
  current_grade: string;
  department_function: string;
  date_of_appointment_to_current_grade: string;
  total_service_ismo: string;
  total_relevant_experience: string;
  date_of_joining_current_position: string;

  // 8 & 9
  declaration_accepted: boolean;
  applicant_signature: string;
};

type Submitted = {
  id: number;
  reference_no: string;
  vacancy: string;
  status: string;
  hr_verification_status: string;
  created_at: string;
  education_count: number;
  experience_count: number;
  certification_count: number;
  training_count: number;
};

const blankEducationRow = (): EducationRow => ({
  degree_qualification: "",
  major_field_of_study: "",
  institution_university: "",
  country: "Pakistan",
  year_of_completion: "",
  cgpa_division: "",
});

const blankExperienceRow = (): ExperienceRow => ({
  organization_employer: "",
  designation: "",
  grade: "",
  from_date: "",
  to_date: "",
  is_current: false,
  duration: "",
  key_responsibilities: "",
});

const blankCertificationRow = (): CertificationRow => ({
  certification_membership: "",
  certifying_body: "",
  date_obtained: "",
  expiry_date: "",
  registration_no: "",
});

const blankTrainingRow = (): TrainingRow => ({
  training_title: "",
  training_provider: "",
  duration: "",
  date_or_year: "",
  relevant_to_position: false,
});

const blankForm = (): FormState => ({
  target_job_req_ids: [],
  emp_id: "",
  full_name: "",
  father_or_husband_name: "",
  cnic: "",
  date_of_birth: "",
  gender: "",
  official_email: "",
  mobile_no: "",
  current_office_location: "",
  emergency_contact_no: "",
  date_of_joining_ismo: "",
  current_designation: "",
  current_grade: "",
  department_function: "",
  date_of_appointment_to_current_grade: "",
  total_service_ismo: "",
  total_relevant_experience: "",
  date_of_joining_current_position: "",
  declaration_accepted: false,
  applicant_signature: "",
});

/** "3 years 4 months", the way the form's Duration column reads. */
const describeSpan = (from: string, to: string): string => {
  if (!from) return "";
  const start = moment(from, "YYYY-MM-DD");
  const finish = to ? moment(to, "YYYY-MM-DD") : moment();
  if (!start.isValid() || !finish.isValid() || finish.isBefore(start)) return "";

  const months = finish.diff(start, "months");
  const years = Math.floor(months / 12);
  const remainder = months % 12;
  const parts: string[] = [];
  if (years) parts.push(`${years} year${years === 1 ? "" : "s"}`);
  if (remainder) parts.push(`${remainder} month${remainder === 1 ? "" : "s"}`);
  return parts.join(" ") || "less than a month";
};

const nameKey = (value: string) => value.toLowerCase().replace(/[^a-z]/g, "");

// ---------------------------------------------------------------------------
// Small presentational helpers
// ---------------------------------------------------------------------------

/** The printed form's numbered blue section bar. */
const SectionBar = ({ number, title }: { number: number; title: string }) => (
  <div className="mb-4 rounded-md bg-[#1f4e79] px-3 py-2 text-sm font-semibold uppercase tracking-wide text-white">
    {number}. {title}
  </div>
);

const FieldNote = ({ children }: { children: React.ReactNode }) => (
  <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">{children}</p>
);

const RowHeader = ({
  label,
  onRemove,
  removable,
}: {
  label: string;
  onRemove: () => void;
  removable: boolean;
}) => (
  <div className="mb-3 flex items-center justify-between">
    <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-300">
      {label}
    </span>
    {removable && (
      <button
        type="button"
        onClick={onRemove}
        className="text-xs font-medium text-error-500 hover:text-error-600"
      >
        Remove
      </button>
    )}
  </div>
);

/** The description of the post, shown under the position it belongs to. */
const JobDescriptionPanel = ({
  description,
  open,
  onToggle,
}: {
  description: JobDescriptionBody;
  open: boolean;
  onToggle: () => void;
}) => {
  const sections = (
    [
      ["Job Purpose", description.job_purpose],
      ["Key Responsibilities", description.key_responsibilities],
      ["Qualifications", description.qualifications],
      ["Experience Required", description.experience_required],
      ["Skills & Competencies", description.skills_competencies],
    ] as [string, string][]
  ).filter(([, value]) => value);

  return (
    <div className="mt-3 rounded-lg border border-brand-200 bg-brand-50/40 dark:border-brand-500/30 dark:bg-brand-500/5">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between px-4 py-2.5 text-left"
      >
        <span className="text-sm font-medium text-brand-600 dark:text-brand-400">
          Job Description
          {description.code ? (
            <span className="ml-2 text-xs font-normal text-gray-500">{description.code}</span>
          ) : null}
        </span>
        <span className="text-xs text-gray-500">{open ? "Hide" : "Show"}</span>
      </button>

      {open && (
        <div className="space-y-3 border-t border-brand-200 px-4 py-3 dark:border-brand-500/30">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div>
              <p className="text-xs text-gray-400">Description Title</p>
              <p className="text-sm text-gray-700 dark:text-gray-300">{description.title}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Grade</p>
              <p className="text-sm text-gray-700 dark:text-gray-300">
                {description.grade || "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Reports To</p>
              <p className="text-sm text-gray-700 dark:text-gray-300">
                {description.reports_to || "—"}
              </p>
            </div>
          </div>

          {sections.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No further detail has been written for this post yet.
            </p>
          ) : (
            sections.map(([label, value]) => (
              <div key={label}>
                <p className="text-xs font-medium uppercase tracking-wide text-brand-500">
                  {label}
                </p>
                <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-gray-700 dark:text-gray-300">
                  {value}
                </p>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};

const Counter = ({ value, limit }: { value: number; limit: number }) => (
  <p className="mt-1 text-right text-xs text-gray-400 dark:text-gray-500">
    {value} / {limit}
  </p>
);

// ---------------------------------------------------------------------------

export default function InternalJobApplication() {
  const [requisitions, setRequisitions] = useState<Requisition[]>([]);
  const [form, setForm] = useState<FormState>(blankForm);
  const [education, setEducation] = useState<EducationRow[]>([blankEducationRow()]);
  const [experience, setExperience] = useState<ExperienceRow[]>([blankExperienceRow()]);
  const [certifications, setCertifications] = useState<CertificationRow[]>([
    blankCertificationRow(),
  ]);
  const [trainings, setTrainings] = useState<TrainingRow[]>([blankTrainingRow()]);

  const [declaration, setDeclaration] = useState<string[]>([]);
  const [submissionNote, setSubmissionNote] = useState("");

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [eduErrors, setEduErrors] = useState<Record<number, Record<string, string>>>({});
  const [expErrors, setExpErrors] = useState<Record<number, Record<string, string>>>({});
  const [certErrors, setCertErrors] = useState<Record<number, Record<string, string>>>({});
  const [trainErrors, setTrainErrors] = useState<Record<number, Record<string, string>>>({});

  const [loadingProfile, setLoadingProfile] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [profileNote, setProfileNote] = useState<string | null>(null);
  const [prefilled, setPrefilled] = useState<Set<string>>(new Set());
  const [submissions, setSubmissions] = useState<Submitted[]>([]);
  // Bumped after a submission so the vacancy picker remounts with nothing chosen.
  const [vacancyPickerKey, setVacancyPickerKey] = useState(0);
  // Which chosen positions have their description expanded. The first one opens
  // by default; with several selected the rest start folded so the form stays
  // navigable.
  const [openDescriptions, setOpenDescriptions] = useState<number[]>([]);

  const user = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem("user") || "{}");
    } catch {
      return {};
    }
  }, []);

  useEffect(() => {
    loadRequisitions();
    loadProfile();
    loadSubmissions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadRequisitions = async () => {
    try {
      const response = await axios.get("/jobs/requisitions/");
      setRequisitions(Array.isArray(response.data) ? response.data : []);
    } catch {
      setRequisitions([]);
    }
  };

  const loadSubmissions = async () => {
    if (!user?.erpid) return;
    try {
      const response = await axios.get("/jobs/applications/", {
        params: { erp_id: user.erpid },
      });
      setSubmissions(Array.isArray(response.data) ? response.data : []);
    } catch {
      setSubmissions([]);
    }
  };

  /**
   * Fills in what the employee record already knows. Every field stays
   * editable: the record is a starting point, not the last word.
   */
  const loadProfile = async () => {
    if (!user?.erpid) {
      setLoadingProfile(false);
      setProfileNote("Sign in again - your employee id is missing from this session.");
      return;
    }

    try {
      const response = await axios.get("/jobs/application-profile/", {
        params: { erp_id: user.erpid },
      });
      const profile = response.data || {};

      setDeclaration(profile.declaration_paragraphs || []);
      setSubmissionNote(profile.submission_note || "");

      const filled = new Set<string>();
      const take = (field: keyof FormState, value: unknown) => {
        const text = value == null ? "" : String(value);
        if (text) filled.add(field as string);
        return text;
      };

      setForm((previous) => ({
        ...previous,
        emp_id: take("emp_id", profile.emp_id),
        full_name: take("full_name", profile.full_name),
        cnic: take("cnic", profile.cnic),
        gender: take("gender", profile.gender),
        official_email: take("official_email", profile.official_email),
        current_office_location: take(
          "current_office_location",
          profile.current_office_location
        ),
        current_designation: take("current_designation", profile.current_designation),
        current_grade: take("current_grade", profile.current_grade),
        department_function: take("department_function", profile.department_function),
        father_or_husband_name: take(
          "father_or_husband_name",
          profile.father_or_husband_name
        ),
        mobile_no: take("mobile_no", profile.mobile_no),
      }));
      setPrefilled(filled);

      // The applicant's current post starts section 5 off, since everyone has
      // one and it is the row reviewers look at first.
      setExperience((previous) => {
        if (previous.length !== 1 || previous[0].organization_employer) return previous;
        return [
          {
            ...previous[0],
            organization_employer: "Independent System & Market Operator (ISMO)",
            designation: profile.current_designation || "",
            grade: profile.current_grade || "",
            is_current: true,
          },
        ];
      });

      setProfileNote(null);
    } catch (error: any) {
      if (error?.response?.status === 404) {
        setProfileNote(
          "No active employee record was found for your ID, so nothing could be filled in for you."
        );
      } else if (!error?.response) {
        setProfileNote(
          "Your details could not be loaded from the server, so the form starts empty."
        );
      } else {
        setProfileNote("Your details could not be filled in automatically.");
      }
    } finally {
      setLoadingProfile(false);
    }
  };

  // ---- editing -----------------------------------------------------------
  const clearError = (field: string) =>
    setErrors((previous) => {
      if (!previous[field]) return previous;
      const next = { ...previous };
      delete next[field];
      return next;
    });

  const set = (field: keyof FormState, value: string | boolean) => {
    setForm((previous) => {
      const next = { ...previous, [field]: value } as FormState;
      // Total service follows the joining date until the applicant edits it.
      if (field === "date_of_joining_ismo" && typeof value === "string") {
        const span = describeSpan(value, "");
        if (span) next.total_service_ismo = span;
      }
      return next;
    });
    clearError(field as string);
  };

  const setVacancies = (selected: string[]) => {
    setForm((previous) => ({ ...previous, target_job_req_ids: selected }));
    clearError("target_job_req_ids");
    // The first position picked shows its description straight away; anything
    // added after that is left folded.
    setOpenDescriptions(selected.length === 1 ? [Number(selected[0])] : []);
  };

  const toggleDescription = (requisitionId: number) =>
    setOpenDescriptions((open) =>
      open.includes(requisitionId)
        ? open.filter((id) => id !== requisitionId)
        : [...open, requisitionId]
    );

  const chosenVacancies = useMemo(
    () =>
      form.target_job_req_ids
        .map((id) => requisitions.find((item) => String(item.id) === id))
        .filter((item): item is Requisition => Boolean(item)),
    [form.target_job_req_ids, requisitions]
  );

  // ---- repeaters ---------------------------------------------------------
  const editEducation = (index: number, field: keyof EducationRow, value: string) => {
    setEducation((rows) =>
      rows.map((row, i) => (i === index ? { ...row, [field]: value } : row))
    );
    setEduErrors((previous) => {
      if (!previous[index]?.[field]) return previous;
      const next = { ...previous, [index]: { ...previous[index] } };
      delete next[index][field];
      return next;
    });
  };

  const editExperience = (
    index: number,
    field: keyof ExperienceRow,
    value: string | boolean
  ) => {
    setExperience((rows) =>
      rows.map((row, i) => {
        if (i !== index) return row;
        const updated = { ...row, [field]: value } as ExperienceRow;
        if (field === "is_current" && value === true) updated.to_date = "";
        // Duration follows the dates unless the applicant types their own.
        if (["from_date", "to_date", "is_current"].includes(field as string)) {
          const span = describeSpan(
            updated.from_date,
            updated.is_current ? "" : updated.to_date
          );
          if (span) updated.duration = span;
        }
        return updated;
      })
    );
    setExpErrors((previous) => {
      if (!previous[index]?.[field as string]) return previous;
      const next = { ...previous, [index]: { ...previous[index] } };
      delete next[index][field as string];
      return next;
    });
  };

  const editCertification = (
    index: number,
    field: keyof CertificationRow,
    value: string
  ) => {
    setCertifications((rows) =>
      rows.map((row, i) => (i === index ? { ...row, [field]: value } : row))
    );
    setCertErrors((previous) => {
      if (!previous[index]?.[field]) return previous;
      const next = { ...previous, [index]: { ...previous[index] } };
      delete next[index][field];
      return next;
    });
  };

  const editTraining = (
    index: number,
    field: keyof TrainingRow,
    value: string | boolean
  ) => {
    setTrainings((rows) =>
      rows.map((row, i) => (i === index ? { ...row, [field]: value } : row))
    );
    setTrainErrors((previous) => {
      if (!previous[index]?.[field as string]) return previous;
      const next = { ...previous, [index]: { ...previous[index] } };
      delete next[index][field as string];
      return next;
    });
  };

  const removeAt = <T,>(
    rows: T[],
    index: number,
    setRows: (rows: T[]) => void,
    resetErrors: () => void
  ) => {
    setRows(rows.filter((_, i) => i !== index));
    resetErrors();
  };

  // ---- validation --------------------------------------------------------
  const validate = (): boolean => {
    const problems: Record<string, string> = {};

    // 1. vacancy information
    if (form.target_job_req_ids.length === 0) {
      problems.target_job_req_ids = "Select at least one vacancy to apply for";
    } else if (form.target_job_req_ids.length > MAX_VACANCIES) {
      problems.target_job_req_ids = `Apply for at most ${MAX_VACANCIES} vacancies at a time`;
    }

    // 2. personal & contact information
    if (!form.emp_id.trim() || Number(form.emp_id) <= 0) {
      problems.emp_id = "Employee ID must be a number";
    }
    if (!form.full_name.trim()) problems.full_name = "Full name is required";
    else if (form.full_name.trim().length < 3) problems.full_name = "That looks too short";

    if (!form.father_or_husband_name.trim()) {
      problems.father_or_husband_name = "Father's / husband's name is required";
    } else if (form.father_or_husband_name.trim().length < 3) {
      problems.father_or_husband_name = "That looks too short";
    }

    if (!form.cnic.trim()) problems.cnic = "CNIC number is required";
    else if (!CNIC.test(form.cnic.trim())) {
      problems.cnic = "CNIC must be 13 digits, like 12345-1234567-1";
    }

    if (!form.date_of_birth) problems.date_of_birth = "Date of birth is required";
    else {
      const years = moment().diff(moment(form.date_of_birth, "YYYY-MM-DD"), "years", true);
      if (years < 18) problems.date_of_birth = "An applicant must be at least 18";
      else if (years > 70) {
        problems.date_of_birth = "Check the date of birth - that is over 70 years ago";
      }
    }

    if (!form.gender) problems.gender = "Gender is required";

    if (!form.official_email.trim()) {
      problems.official_email = "Official email address is required";
    } else if (!EMAIL.test(form.official_email.trim())) {
      problems.official_email = "That does not look like an email address";
    }

    const digits = (value: string) => (value.match(/\d/g) || []).length;
    if (!form.mobile_no.trim()) problems.mobile_no = "Mobile / contact number is required";
    else if (!PHONE.test(form.mobile_no.trim()) || digits(form.mobile_no) < 7) {
      problems.mobile_no = "Enter a number like +92-300-1234567";
    }

    if (!form.current_office_location.trim()) {
      problems.current_office_location = "Current office / location is required";
    }

    if (
      form.emergency_contact_no.trim() &&
      (!PHONE.test(form.emergency_contact_no.trim()) || digits(form.emergency_contact_no) < 7)
    ) {
      problems.emergency_contact_no = "Enter a number like +92-300-1234567";
    }

    // 3. current employment details
    if (!form.date_of_joining_ismo) {
      problems.date_of_joining_ismo = "Date of joining ISMO is required";
    } else if (form.date_of_joining_ismo > today()) {
      problems.date_of_joining_ismo = "That date cannot be in the future";
    }

    if (!form.current_designation.trim()) {
      problems.current_designation = "Current designation is required";
    }
    if (!form.current_grade.trim()) problems.current_grade = "Current grade is required";
    if (!form.department_function.trim()) {
      problems.department_function = "Department / function is required";
    }

    if (!form.date_of_appointment_to_current_grade) {
      problems.date_of_appointment_to_current_grade =
        "Date of appointment to current grade is required";
    } else if (form.date_of_appointment_to_current_grade > today()) {
      problems.date_of_appointment_to_current_grade = "That date cannot be in the future";
    } else if (
      form.date_of_joining_ismo &&
      form.date_of_appointment_to_current_grade < form.date_of_joining_ismo
    ) {
      problems.date_of_appointment_to_current_grade =
        "This cannot be before the date of joining ISMO";
    }

    if (!form.date_of_joining_current_position) {
      problems.date_of_joining_current_position =
        "Date of joining current position is required";
    } else if (form.date_of_joining_current_position > today()) {
      problems.date_of_joining_current_position = "That date cannot be in the future";
    } else if (
      form.date_of_joining_ismo &&
      form.date_of_joining_current_position < form.date_of_joining_ismo
    ) {
      problems.date_of_joining_current_position =
        "This cannot be before the date of joining ISMO";
    }

    if (!form.total_service_ismo.trim()) {
      problems.total_service_ismo = "Total service in ISMO is required";
    }
    if (!form.total_relevant_experience.trim()) {
      problems.total_relevant_experience = "Total relevant experience is required";
    }

    // 4. educational background
    const educationProblems: Record<number, Record<string, string>> = {};
    const thisYear = moment().year();
    education.forEach((row, index) => {
      const rowProblems: Record<string, string> = {};
      if (!row.degree_qualification.trim()) {
        rowProblems.degree_qualification = "Degree / qualification is required";
      }
      if (!row.major_field_of_study.trim()) {
        rowProblems.major_field_of_study = "Major / field of study is required";
      }
      if (!row.institution_university.trim()) {
        rowProblems.institution_university = "Institution / university is required";
      }
      if (!row.country.trim()) rowProblems.country = "Country is required";
      if (!row.year_of_completion.trim()) {
        rowProblems.year_of_completion = "Year of completion is required";
      } else {
        const year = Number(row.year_of_completion);
        if (
          !Number.isInteger(year) ||
          year < EARLIEST_QUALIFICATION_YEAR ||
          year > thisYear + FUTURE_QUALIFICATION_YEARS
        ) {
          rowProblems.year_of_completion = `Year must be between ${EARLIEST_QUALIFICATION_YEAR} and ${
            thisYear + FUTURE_QUALIFICATION_YEARS
          }`;
        }
      }
      if (!row.cgpa_division.trim()) rowProblems.cgpa_division = "CGPA / division is required";
      if (Object.keys(rowProblems).length) educationProblems[index] = rowProblems;
    });
    if (education.length === 0) problems.education = "Add at least one qualification";

    // 5. employment history
    const experienceProblems: Record<number, Record<string, string>> = {};
    experience.forEach((row, index) => {
      const rowProblems: Record<string, string> = {};
      if (!row.organization_employer.trim()) {
        rowProblems.organization_employer = "Organization / employer is required";
      }
      if (!row.designation.trim()) rowProblems.designation = "Designation is required";
      if (!row.from_date) rowProblems.from_date = "From date is required";
      else if (row.from_date > today()) rowProblems.from_date = "That date cannot be in the future";

      if (!row.is_current) {
        if (!row.to_date) rowProblems.to_date = "To date is required";
        else if (row.to_date > today()) rowProblems.to_date = "That date cannot be in the future";
        else if (row.from_date && row.to_date < row.from_date) {
          rowProblems.to_date = "The To date cannot be before the From date";
        }
      }

      if (!row.key_responsibilities.trim()) {
        rowProblems.key_responsibilities = "Key responsibilities are required";
      } else if (row.key_responsibilities.trim().length < 10) {
        rowProblems.key_responsibilities = "Add a little more detail";
      }
      if (Object.keys(rowProblems).length) experienceProblems[index] = rowProblems;
    });
    if (experience.length === 0) {
      problems.experience = "Add at least one post, including your current one";
    }

    // 6. certifications - optional, but complete once a row is started
    const certificationProblems: Record<number, Record<string, string>> = {};
    certifications.forEach((row, index) => {
      const started =
        row.certification_membership.trim() ||
        row.certifying_body.trim() ||
        row.date_obtained ||
        row.expiry_date ||
        row.registration_no.trim();
      if (!started) return;

      const rowProblems: Record<string, string> = {};
      if (!row.certification_membership.trim()) {
        rowProblems.certification_membership = "Certification / membership is required";
      }
      if (!row.certifying_body.trim()) {
        rowProblems.certifying_body = "Certifying body is required";
      }
      if (row.date_obtained && row.date_obtained > today()) {
        rowProblems.date_obtained = "That date cannot be in the future";
      }
      if (row.date_obtained && row.expiry_date && row.expiry_date < row.date_obtained) {
        rowProblems.expiry_date = "Expiry cannot be before the date obtained";
      }
      if (Object.keys(rowProblems).length) certificationProblems[index] = rowProblems;
    });

    // 7. trainings - same rule
    const trainingProblems: Record<number, Record<string, string>> = {};
    trainings.forEach((row, index) => {
      const started =
        row.training_title.trim() ||
        row.training_provider.trim() ||
        row.duration.trim() ||
        row.date_or_year.trim();
      if (!started) return;

      const rowProblems: Record<string, string> = {};
      if (!row.training_title.trim()) {
        rowProblems.training_title = "Training / course title is required";
      }
      if (!row.training_provider.trim()) {
        rowProblems.training_provider = "Training provider is required";
      }
      if (/^\d{4}$/.test(row.date_or_year.trim())) {
        const year = Number(row.date_or_year);
        if (year < EARLIEST_QUALIFICATION_YEAR || year > thisYear) {
          rowProblems.date_or_year = `Year must be between ${EARLIEST_QUALIFICATION_YEAR} and ${thisYear}`;
        }
      }
      if (Object.keys(rowProblems).length) trainingProblems[index] = rowProblems;
    });

    // 8. declaration
    if (!form.declaration_accepted) {
      problems.declaration_accepted =
        "Read and accept the declaration and undertaking before submitting";
    }

    // 9. submission record
    if (!form.applicant_signature.trim()) {
      problems.applicant_signature = "Type your full name to sign the application";
    } else if (
      form.full_name.trim() &&
      nameKey(form.applicant_signature) !== nameKey(form.full_name)
    ) {
      problems.applicant_signature = "The signature must be your full name as entered above";
    }

    setErrors(problems);
    setEduErrors(educationProblems);
    setExpErrors(experienceProblems);
    setCertErrors(certificationProblems);
    setTrainErrors(trainingProblems);

    const clean =
      Object.keys(problems).length === 0 &&
      Object.keys(educationProblems).length === 0 &&
      Object.keys(experienceProblems).length === 0 &&
      Object.keys(certificationProblems).length === 0 &&
      Object.keys(trainingProblems).length === 0;

    if (!clean) toast.error("Please correct the highlighted fields");
    return clean;
  };

  // ---- submitting --------------------------------------------------------
  const submit = async () => {
    if (!validate()) return;

    setSubmitting(true);
    const hasContent = (values: string[]) => values.some((value) => value.trim());

    try {
      const response = await axios.post("/jobs/applications/create/", {
        applicant_erp_id: user.erpid,
        target_job_req_ids: form.target_job_req_ids.map(Number),

        emp_id: Number(form.emp_id),
        full_name: form.full_name.trim(),
        father_or_husband_name: form.father_or_husband_name.trim(),
        cnic: form.cnic.trim(),
        date_of_birth: form.date_of_birth,
        gender: form.gender,
        official_email: form.official_email.trim(),
        mobile_no: form.mobile_no.trim(),
        current_office_location: form.current_office_location.trim(),
        emergency_contact_no: form.emergency_contact_no.trim(),

        date_of_joining_ismo: form.date_of_joining_ismo,
        current_designation: form.current_designation.trim(),
        current_grade: form.current_grade.trim(),
        department_function: form.department_function.trim(),
        date_of_appointment_to_current_grade: form.date_of_appointment_to_current_grade,
        total_service_ismo: form.total_service_ismo.trim(),
        total_relevant_experience: form.total_relevant_experience.trim(),
        date_of_joining_current_position: form.date_of_joining_current_position,

        education: education.map((row) => ({
          ...row,
          year_of_completion: Number(row.year_of_completion),
        })),
        experience: experience.map((row) => ({
          ...row,
          to_date: row.is_current ? null : row.to_date || null,
        })),
        certifications: certifications
          .filter((row) =>
            hasContent([
              row.certification_membership,
              row.certifying_body,
              row.date_obtained,
              row.expiry_date,
              row.registration_no,
            ])
          )
          .map((row) => ({
            ...row,
            date_obtained: row.date_obtained || null,
            expiry_date: row.expiry_date || null,
          })),
        trainings: trainings.filter((row) =>
          hasContent([
            row.training_title,
            row.training_provider,
            row.duration,
            row.date_or_year,
          ])
        ),

        declaration_accepted: form.declaration_accepted,
        applicant_signature: form.applicant_signature.trim(),
      });

      toast.success(response.data?.message ?? "Your application has been submitted");

      // What the applicant typed for these vacancies is cleared; their own
      // details stay, so applying again later needs little retyping.
      setForm((previous) => ({
        ...previous,
        target_job_req_ids: [],
        declaration_accepted: false,
        applicant_signature: "",
      }));
      setVacancyPickerKey((key) => key + 1);
      setErrors({});
      loadSubmissions();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error: any) {
      const returned = error?.response?.data;
      const fields = returned?.errors;
      if (fields) {
        const flat: Record<string, string> = {};
        Object.entries(fields).forEach(([key, value]) => {
          if (typeof value === "string") flat[key] = value;
        });
        setErrors(flat);

        const byIndex = (rows: any) => {
          const mapped: Record<number, Record<string, string>> = {};
          Object.entries(rows || {}).forEach(([index, value]) => {
            mapped[Number(index)] = value as Record<string, string>;
          });
          return mapped;
        };
        if (fields.education_rows) setEduErrors(byIndex(fields.education_rows));
        if (fields.experience_rows) setExpErrors(byIndex(fields.experience_rows));
        if (fields.certification_rows) setCertErrors(byIndex(fields.certification_rows));
        if (fields.training_rows) setTrainErrors(byIndex(fields.training_rows));

        const conflict = error?.response?.status === 409;
        toast.error(
          conflict && typeof fields.target_job_req_ids === "string"
            ? fields.target_job_req_ids
            : "Please correct the highlighted fields"
        );
      } else if (!error?.response) {
        toast.error("Could not reach the server. Please try again.");
      } else {
        toast.error(returned?.error ?? "The application could not be submitted");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const autoFilled = (field: string) =>
    prefilled.has(field) ? (
      <span className="ml-2 align-middle text-[10px] font-medium uppercase tracking-wide text-brand-500">
        auto-filled
      </span>
    ) : null;

  const vacancyOptions = requisitions.map((item) => ({
    text: [item.title, item.reference_no || null, item.grade || null]
      .filter(Boolean)
      .join(" · "),
    value: String(item.id),
  }));

  const showDate = (value: string | null) =>
    value ? moment(value).format("DD MMM YYYY") : "—";

  return (
    <>
      <PageMeta
        title="ISMO - Internal Recruitment Application"
        description="Internal recruitment online application form"
      />
      <PageBreadcrumb pageTitle="Internal Recruitment - Online Application Form" />
      <ToastContainer position="bottom-right" />

      <div className="space-y-6">
        <div className="rounded-2xl border border-gray-200 bg-white px-6 py-5 text-center dark:border-gray-800 dark:bg-white/[0.03]">
          <h2 className="text-base font-semibold text-gray-800 dark:text-white/90">
            INDEPENDENT SYSTEM AND MARKET OPERATOR (ISMO)
          </h2>
          <p className="mt-1 text-sm font-medium text-gray-700 dark:text-gray-300">
            INTERNAL RECRUITMENT – ONLINE APPLICATION FORM
          </p>
          <p className="mt-1 text-xs italic text-gray-500 dark:text-gray-400">
            For applications against internally advertised positions
          </p>
          {loadingProfile && (
            <p className="mt-3 text-xs text-gray-400">Filling in your details...</p>
          )}
          {profileNote && (
            <p className="mt-3 text-xs text-warning-600 dark:text-warning-400">{profileNote}</p>
          )}
        </div>

        {/* ------------------------- 1. vacancy information ------------------ */}
        <ComponentCard title="" desc="">
          <SectionBar number={1} title="Vacancy Information" />

          <div>
            <Label htmlFor="requisition-dropdown">
              Position Title <span className="text-error-500">*</span>
            </Label>
            {requisitions.length === 0 ? (
              <p className="rounded-lg border border-dashed border-gray-300 px-4 py-3 text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
                No vacancies are advertised at the moment. They are added from Job
                Openings under Internal Recruitment Portal.
              </p>
            ) : (
              <div id="requisition-dropdown">
                <MultiSelect
                  key={`vacancies-${requisitions.length}-${vacancyPickerKey}`}
                  label=""
                  options={vacancyOptions}
                  defaultSelected={form.target_job_req_ids}
                  onChange={setVacancies}
                />
                <FieldNote>
                  Pick as many advertised positions as you want to apply for. The rest
                  of this form is submitted once for each, and each one gets its own
                  reference number and is reviewed separately.
                </FieldNote>
                {errors.target_job_req_ids && (
                  <p className="mt-1 text-xs text-error-500">{errors.target_job_req_ids}</p>
                )}
              </div>
            )}
          </div>

          {chosenVacancies.length > 0 && (
            <div className="mt-4 space-y-3">
              {chosenVacancies.map((vacancy) => (
                <div
                  key={vacancy.id}
                  className="rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-white/[0.02]"
                  data-vacancy-card={vacancy.id}
                >
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    <div>
                      <p className="text-xs text-gray-400">Position Title</p>
                      <p className="text-sm font-medium text-gray-800 dark:text-white/90">
                        {vacancy.title}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Advertisement / Reference No.</p>
                      <p className="text-sm text-gray-700 dark:text-gray-300">
                        {vacancy.reference_no || "—"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Grade</p>
                      <p className="text-sm text-gray-700 dark:text-gray-300">
                        {vacancy.grade || "—"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Department / Function</p>
                      <p className="text-sm text-gray-700 dark:text-gray-300">
                        {vacancy.department || "—"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Date of Advertisement</p>
                      <p className="text-sm text-gray-700 dark:text-gray-300">
                        {showDate(vacancy.advertisement_date)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Closing Date</p>
                      <p className="text-sm text-gray-700 dark:text-gray-300">
                        {showDate(vacancy.closing_date)}
                      </p>
                    </div>
                  </div>

                  {vacancy.notes ? (
                    <p className="mt-3 whitespace-pre-wrap text-sm text-gray-600 dark:text-gray-400">
                      {vacancy.notes}
                    </p>
                  ) : null}

                  {vacancy.job_description ? (
                    <JobDescriptionPanel
                      description={vacancy.job_description}
                      open={openDescriptions.includes(vacancy.id)}
                      onToggle={() => toggleDescription(vacancy.id)}
                    />
                  ) : (
                    <p className="mt-3 text-xs text-gray-400 dark:text-gray-500">
                      No job description has been attached to this position yet.
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="current_designation_top">
                Current Designation <span className="text-error-500">*</span>
                {autoFilled("current_designation")}
              </Label>
              <Input
                id="current_designation_top"
                value={form.current_designation}
                onChange={(e) => set("current_designation", e.target.value)}
                error={!!errors.current_designation}
                hint={errors.current_designation}
              />
            </div>
            <div>
              <Label htmlFor="current_grade_top">
                Current Grade <span className="text-error-500">*</span>
                {autoFilled("current_grade")}
              </Label>
              <Input
                id="current_grade_top"
                placeholder="e.g., G-09"
                value={form.current_grade}
                onChange={(e) => set("current_grade", e.target.value)}
                error={!!errors.current_grade}
                hint={errors.current_grade}
              />
            </div>
          </div>
        </ComponentCard>

        {/* --------------- 2. personal & contact information ---------------- */}
        <ComponentCard title="" desc="">
          <SectionBar number={2} title="Personal &amp; Contact Information" />

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="emp_id">
                Employee ID <span className="text-error-500">*</span>
                {autoFilled("emp_id")}
              </Label>
              <Input
                id="emp_id"
                value={form.emp_id}
                onChange={(e) => set("emp_id", e.target.value.replace(/\D/g, ""))}
                error={!!errors.emp_id}
                hint={errors.emp_id}
              />
            </div>
            <div>
              <Label htmlFor="full_name">
                Full Name <span className="text-error-500">*</span>
                {autoFilled("full_name")}
              </Label>
              <Input
                id="full_name"
                value={form.full_name}
                onChange={(e) => set("full_name", e.target.value)}
                error={!!errors.full_name}
                hint={errors.full_name}
              />
            </div>
            <div>
              <Label htmlFor="father_or_husband_name">
                Father&apos;s / Husband&apos;s Name <span className="text-error-500">*</span>
              </Label>
              <Input
                id="father_or_husband_name"
                value={form.father_or_husband_name}
                onChange={(e) => set("father_or_husband_name", e.target.value)}
                error={!!errors.father_or_husband_name}
                hint={errors.father_or_husband_name}
              />
            </div>
            <div>
              <Label htmlFor="cnic">
                CNIC No. <span className="text-error-500">*</span>
                {autoFilled("cnic")}
              </Label>
              <Input
                id="cnic"
                placeholder="12345-1234567-1"
                value={form.cnic}
                onChange={(e) => set("cnic", e.target.value)}
                error={!!errors.cnic}
                hint={errors.cnic}
              />
            </div>
            <div>
              <Label htmlFor="date_of_birth">
                Date of Birth <span className="text-error-500">*</span>
              </Label>
              <Input
                id="date_of_birth"
                type="date"
                max={today()}
                value={form.date_of_birth}
                onChange={(e) => set("date_of_birth", e.target.value)}
                error={!!errors.date_of_birth}
                hint={errors.date_of_birth}
              />
            </div>
            <div>
              <Label>
                Gender <span className="text-error-500">*</span>
                {autoFilled("gender")}
              </Label>
              <Select
                options={GENDERS.map((value) => ({ label: value, value }))}
                placeholder="Select gender"
                value={form.gender}
                onChange={(value) => set("gender", value)}
                error={!!errors.gender}
                hint={errors.gender}
              />
            </div>
            <div>
              <Label htmlFor="official_email">
                Official Email Address <span className="text-error-500">*</span>
                {autoFilled("official_email")}
              </Label>
              <Input
                id="official_email"
                type="email"
                value={form.official_email}
                onChange={(e) => set("official_email", e.target.value)}
                error={!!errors.official_email}
                hint={errors.official_email}
              />
            </div>
            <div>
              <Label htmlFor="mobile_no">
                Mobile / Contact No. <span className="text-error-500">*</span>
              </Label>
              <Input
                id="mobile_no"
                placeholder="+92-300-1234567"
                value={form.mobile_no}
                onChange={(e) => set("mobile_no", e.target.value)}
                error={!!errors.mobile_no}
                hint={errors.mobile_no}
              />
            </div>
            <div>
              <Label htmlFor="current_office_location">
                Current Office / Location <span className="text-error-500">*</span>
                {autoFilled("current_office_location")}
              </Label>
              <Input
                id="current_office_location"
                value={form.current_office_location}
                onChange={(e) => set("current_office_location", e.target.value)}
                error={!!errors.current_office_location}
                hint={errors.current_office_location}
              />
            </div>
            <div>
              <Label htmlFor="emergency_contact_no">Emergency Contact No. (optional)</Label>
              <Input
                id="emergency_contact_no"
                placeholder="+92-300-1234567"
                value={form.emergency_contact_no}
                onChange={(e) => set("emergency_contact_no", e.target.value)}
                error={!!errors.emergency_contact_no}
                hint={errors.emergency_contact_no}
              />
            </div>
          </div>
        </ComponentCard>

        {/* ------------------ 3. current employment details ----------------- */}
        <ComponentCard title="" desc="">
          <SectionBar number={3} title="Current Employment Details" />

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="date_of_joining_ismo">
                Date of Joining ISMO <span className="text-error-500">*</span>
              </Label>
              <Input
                id="date_of_joining_ismo"
                type="date"
                max={today()}
                value={form.date_of_joining_ismo}
                onChange={(e) => set("date_of_joining_ismo", e.target.value)}
                error={!!errors.date_of_joining_ismo}
                hint={errors.date_of_joining_ismo}
              />
            </div>
            <div>
              <Label htmlFor="current_designation">
                Current Designation <span className="text-error-500">*</span>
                {autoFilled("current_designation")}
              </Label>
              <Input
                id="current_designation"
                value={form.current_designation}
                onChange={(e) => set("current_designation", e.target.value)}
                error={!!errors.current_designation}
                hint={errors.current_designation}
              />
            </div>
            <div>
              <Label htmlFor="current_grade">
                Current Grade <span className="text-error-500">*</span>
                {autoFilled("current_grade")}
              </Label>
              <Input
                id="current_grade"
                value={form.current_grade}
                onChange={(e) => set("current_grade", e.target.value)}
                error={!!errors.current_grade}
                hint={errors.current_grade}
              />
            </div>
            <div>
              <Label htmlFor="department_function">
                Department / Function <span className="text-error-500">*</span>
                {autoFilled("department_function")}
              </Label>
              <Input
                id="department_function"
                value={form.department_function}
                onChange={(e) => set("department_function", e.target.value)}
                error={!!errors.department_function}
                hint={errors.department_function}
              />
            </div>
            <div>
              <Label htmlFor="date_of_appointment_to_current_grade">
                Date of Appointment to Current Grade{" "}
                <span className="text-error-500">*</span>
              </Label>
              <Input
                id="date_of_appointment_to_current_grade"
                type="date"
                max={today()}
                value={form.date_of_appointment_to_current_grade}
                onChange={(e) =>
                  set("date_of_appointment_to_current_grade", e.target.value)
                }
                error={!!errors.date_of_appointment_to_current_grade}
                hint={errors.date_of_appointment_to_current_grade}
              />
            </div>
            <div>
              <Label htmlFor="total_service_ismo">
                Total Service in ISMO <span className="text-error-500">*</span>
              </Label>
              <Input
                id="total_service_ismo"
                placeholder="e.g., 8 years 4 months"
                value={form.total_service_ismo}
                onChange={(e) => set("total_service_ismo", e.target.value)}
                error={!!errors.total_service_ismo}
                hint={errors.total_service_ismo}
              />
              <FieldNote>Worked out from your joining date - correct it if needed.</FieldNote>
            </div>
            <div>
              <Label htmlFor="total_relevant_experience">
                Total Relevant Experience <span className="text-error-500">*</span>
              </Label>
              <Input
                id="total_relevant_experience"
                placeholder="e.g., 12 years"
                value={form.total_relevant_experience}
                onChange={(e) => set("total_relevant_experience", e.target.value)}
                error={!!errors.total_relevant_experience}
                hint={errors.total_relevant_experience}
              />
            </div>
            <div>
              <Label htmlFor="date_of_joining_current_position">
                Date of Joining Current Position <span className="text-error-500">*</span>
              </Label>
              <Input
                id="date_of_joining_current_position"
                type="date"
                max={today()}
                value={form.date_of_joining_current_position}
                onChange={(e) => set("date_of_joining_current_position", e.target.value)}
                error={!!errors.date_of_joining_current_position}
                hint={errors.date_of_joining_current_position}
              />
            </div>
          </div>
        </ComponentCard>

        {/* ------------------- 4. educational background -------------------- */}
        <ComponentCard title="" desc="">
          <SectionBar number={4} title="Educational Background" />

          <div className="space-y-4">
            {education.map((row, index) => {
              const rowProblems = eduErrors[index] || {};
              return (
                <div
                  key={index}
                  className="rounded-lg border border-gray-200 p-4 dark:border-gray-800"
                  data-education-row={index}
                >
                  <RowHeader
                    label={`Qualification ${index + 1}`}
                    removable={education.length > 1}
                    onRemove={() =>
                      removeAt(education, index, setEducation, () => setEduErrors({}))
                    }
                  />
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <div>
                      <Label htmlFor={`edu-${index}-degree`}>
                        Degree / Qualification <span className="text-error-500">*</span>
                      </Label>
                      <Input
                        id={`edu-${index}-degree`}
                        placeholder="e.g., BSc Electrical Engineering"
                        value={row.degree_qualification}
                        onChange={(e) =>
                          editEducation(index, "degree_qualification", e.target.value)
                        }
                        error={!!rowProblems.degree_qualification}
                        hint={rowProblems.degree_qualification}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`edu-${index}-major`}>
                        Major / Field of Study <span className="text-error-500">*</span>
                      </Label>
                      <Input
                        id={`edu-${index}-major`}
                        placeholder="e.g., Power Systems"
                        value={row.major_field_of_study}
                        onChange={(e) =>
                          editEducation(index, "major_field_of_study", e.target.value)
                        }
                        error={!!rowProblems.major_field_of_study}
                        hint={rowProblems.major_field_of_study}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`edu-${index}-institution`}>
                        Institution / University <span className="text-error-500">*</span>
                      </Label>
                      <Input
                        id={`edu-${index}-institution`}
                        placeholder="e.g., UET Lahore"
                        value={row.institution_university}
                        onChange={(e) =>
                          editEducation(index, "institution_university", e.target.value)
                        }
                        error={!!rowProblems.institution_university}
                        hint={rowProblems.institution_university}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`edu-${index}-country`}>
                        Country <span className="text-error-500">*</span>
                      </Label>
                      <Input
                        id={`edu-${index}-country`}
                        value={row.country}
                        onChange={(e) => editEducation(index, "country", e.target.value)}
                        error={!!rowProblems.country}
                        hint={rowProblems.country}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`edu-${index}-year`}>
                        Year of Completion <span className="text-error-500">*</span>
                      </Label>
                      <Input
                        id={`edu-${index}-year`}
                        placeholder="e.g., 2014"
                        value={row.year_of_completion}
                        onChange={(e) =>
                          editEducation(
                            index,
                            "year_of_completion",
                            e.target.value.replace(/\D/g, "").slice(0, 4)
                          )
                        }
                        error={!!rowProblems.year_of_completion}
                        hint={rowProblems.year_of_completion}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`edu-${index}-grade`}>
                        CGPA / Division <span className="text-error-500">*</span>
                      </Label>
                      <Input
                        id={`edu-${index}-grade`}
                        placeholder="e.g., 3.6 or First Division"
                        value={row.cgpa_division}
                        onChange={(e) =>
                          editEducation(index, "cgpa_division", e.target.value)
                        }
                        error={!!rowProblems.cgpa_division}
                        hint={rowProblems.cgpa_division}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-4 flex items-center justify-between">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setEducation((rows) => [...rows, blankEducationRow()])}
              disabled={education.length >= MAX_EDUCATION_ROWS}
            >
              + Add another qualification
            </Button>
            <span className="text-xs text-gray-400">
              {education.length} of {MAX_EDUCATION_ROWS}
            </span>
          </div>
          {errors.education && (
            <p className="mt-2 text-xs text-error-500">{errors.education}</p>
          )}
        </ComponentCard>

        {/* ----------- 5. employment history / professional experience ------ */}
        <ComponentCard title="" desc="">
          <SectionBar number={5} title="Employment History / Professional Experience" />

          <div className="space-y-4">
            {experience.map((row, index) => {
              const rowProblems = expErrors[index] || {};
              return (
                <div
                  key={index}
                  className="rounded-lg border border-gray-200 p-4 dark:border-gray-800"
                  data-experience-row={index}
                >
                  <RowHeader
                    label={`Position ${index + 1}`}
                    removable={experience.length > 1}
                    onRemove={() =>
                      removeAt(experience, index, setExperience, () => setExpErrors({}))
                    }
                  />
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <div>
                      <Label htmlFor={`exp-${index}-employer`}>
                        Organization / Employer <span className="text-error-500">*</span>
                      </Label>
                      <Input
                        id={`exp-${index}-employer`}
                        value={row.organization_employer}
                        onChange={(e) =>
                          editExperience(index, "organization_employer", e.target.value)
                        }
                        error={!!rowProblems.organization_employer}
                        hint={rowProblems.organization_employer}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`exp-${index}-designation`}>
                        Designation <span className="text-error-500">*</span>
                      </Label>
                      <Input
                        id={`exp-${index}-designation`}
                        value={row.designation}
                        onChange={(e) => editExperience(index, "designation", e.target.value)}
                        error={!!rowProblems.designation}
                        hint={rowProblems.designation}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`exp-${index}-grade`}>Grade (if applicable)</Label>
                      <Input
                        id={`exp-${index}-grade`}
                        placeholder="e.g., G-08"
                        value={row.grade}
                        onChange={(e) => editExperience(index, "grade", e.target.value)}
                        error={!!rowProblems.grade}
                        hint={rowProblems.grade}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`exp-${index}-from`}>
                        From <span className="text-error-500">*</span>
                      </Label>
                      <Input
                        id={`exp-${index}-from`}
                        type="date"
                        max={today()}
                        value={row.from_date}
                        onChange={(e) => editExperience(index, "from_date", e.target.value)}
                        error={!!rowProblems.from_date}
                        hint={rowProblems.from_date}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`exp-${index}-to`}>
                        To{" "}
                        {!row.is_current && <span className="text-error-500">*</span>}
                      </Label>
                      <Input
                        id={`exp-${index}-to`}
                        type="date"
                        max={today()}
                        value={row.to_date}
                        disabled={row.is_current}
                        onChange={(e) => editExperience(index, "to_date", e.target.value)}
                        error={!!rowProblems.to_date}
                        hint={rowProblems.to_date}
                      />
                      <div className="mt-2">
                        <Checkbox
                          id={`exp-${index}-current`}
                          label="Currently in this position"
                          checked={row.is_current}
                          onChange={(checked) =>
                            editExperience(index, "is_current", checked)
                          }
                        />
                      </div>
                    </div>
                    <div>
                      <Label htmlFor={`exp-${index}-duration`}>Duration</Label>
                      <Input
                        id={`exp-${index}-duration`}
                        placeholder="e.g., 5 years 2 months"
                        value={row.duration}
                        onChange={(e) => editExperience(index, "duration", e.target.value)}
                      />
                      <FieldNote>Worked out from the dates above.</FieldNote>
                    </div>
                    <div className="md:col-span-3">
                      <Label htmlFor={`exp-${index}-responsibilities`}>
                        Key Responsibilities / Relevant Experience{" "}
                        <span className="text-error-500">*</span>
                      </Label>
                      <TextArea
                        id={`exp-${index}-responsibilities`}
                        rows={3}
                        placeholder="What the post covered, and the parts relevant to the position applied for..."
                        value={row.key_responsibilities}
                        onChange={(value) =>
                          editExperience(
                            index,
                            "key_responsibilities",
                            value.slice(0, MAX_RESPONSIBILITIES)
                          )
                        }
                        error={!!rowProblems.key_responsibilities}
                        hint={rowProblems.key_responsibilities}
                      />
                      <Counter
                        value={row.key_responsibilities.length}
                        limit={MAX_RESPONSIBILITIES}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-4 flex items-center justify-between">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setExperience((rows) => [...rows, blankExperienceRow()])}
              disabled={experience.length >= MAX_EXPERIENCE_ROWS}
            >
              + Add another position
            </Button>
            <span className="text-xs text-gray-400">
              {experience.length} of {MAX_EXPERIENCE_ROWS}
            </span>
          </div>
          {errors.experience && (
            <p className="mt-2 text-xs text-error-500">{errors.experience}</p>
          )}
        </ComponentCard>

        {/* ------- 6. professional certifications / memberships ------------- */}
        <ComponentCard title="" desc="">
          <SectionBar number={6} title="Professional Certifications / Memberships" />
          <p className="-mt-2 mb-4 text-xs text-gray-500 dark:text-gray-400">
            Leave blank if you have none. Once a row is started, the certification and
            the body that issued it are both needed.
          </p>

          <div className="space-y-4">
            {certifications.map((row, index) => {
              const rowProblems = certErrors[index] || {};
              return (
                <div
                  key={index}
                  className="rounded-lg border border-gray-200 p-4 dark:border-gray-800"
                  data-certification-row={index}
                >
                  <RowHeader
                    label={`Certification ${index + 1}`}
                    removable={certifications.length > 1}
                    onRemove={() =>
                      removeAt(certifications, index, setCertifications, () =>
                        setCertErrors({})
                      )
                    }
                  />
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <div>
                      <Label htmlFor={`cert-${index}-name`}>Certification / Membership</Label>
                      <Input
                        id={`cert-${index}-name`}
                        placeholder="e.g., PMP"
                        value={row.certification_membership}
                        onChange={(e) =>
                          editCertification(index, "certification_membership", e.target.value)
                        }
                        error={!!rowProblems.certification_membership}
                        hint={rowProblems.certification_membership}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`cert-${index}-body`}>
                        Certifying / Professional Body
                      </Label>
                      <Input
                        id={`cert-${index}-body`}
                        placeholder="e.g., Pakistan Engineering Council"
                        value={row.certifying_body}
                        onChange={(e) =>
                          editCertification(index, "certifying_body", e.target.value)
                        }
                        error={!!rowProblems.certifying_body}
                        hint={rowProblems.certifying_body}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`cert-${index}-registration`}>
                        Registration / Membership No.
                      </Label>
                      <Input
                        id={`cert-${index}-registration`}
                        value={row.registration_no}
                        onChange={(e) =>
                          editCertification(index, "registration_no", e.target.value)
                        }
                      />
                    </div>
                    <div>
                      <Label htmlFor={`cert-${index}-obtained`}>Date Obtained</Label>
                      <Input
                        id={`cert-${index}-obtained`}
                        type="date"
                        max={today()}
                        value={row.date_obtained}
                        onChange={(e) =>
                          editCertification(index, "date_obtained", e.target.value)
                        }
                        error={!!rowProblems.date_obtained}
                        hint={rowProblems.date_obtained}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`cert-${index}-expiry`}>
                        Expiry Date (if applicable)
                      </Label>
                      <Input
                        id={`cert-${index}-expiry`}
                        type="date"
                        value={row.expiry_date}
                        onChange={(e) =>
                          editCertification(index, "expiry_date", e.target.value)
                        }
                        error={!!rowProblems.expiry_date}
                        hint={rowProblems.expiry_date}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-4 flex items-center justify-between">
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                setCertifications((rows) => [...rows, blankCertificationRow()])
              }
              disabled={certifications.length >= MAX_CERTIFICATION_ROWS}
            >
              + Add another certification
            </Button>
            <span className="text-xs text-gray-400">
              {certifications.length} of {MAX_CERTIFICATION_ROWS}
            </span>
          </div>
        </ComponentCard>

        {/* --------- 7. trainings & professional development ---------------- */}
        <ComponentCard title="" desc="">
          <SectionBar number={7} title="Trainings &amp; Professional Development" />
          <p className="-mt-2 mb-4 text-xs text-gray-500 dark:text-gray-400">
            Leave blank if you have none to declare.
          </p>

          <div className="space-y-4">
            {trainings.map((row, index) => {
              const rowProblems = trainErrors[index] || {};
              return (
                <div
                  key={index}
                  className="rounded-lg border border-gray-200 p-4 dark:border-gray-800"
                  data-training-row={index}
                >
                  <RowHeader
                    label={`Training ${index + 1}`}
                    removable={trainings.length > 1}
                    onRemove={() =>
                      removeAt(trainings, index, setTrainings, () => setTrainErrors({}))
                    }
                  />
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
                    <div>
                      <Label htmlFor={`train-${index}-title`}>Training / Course Title</Label>
                      <Input
                        id={`train-${index}-title`}
                        placeholder="e.g., Grid Code Compliance"
                        value={row.training_title}
                        onChange={(e) => editTraining(index, "training_title", e.target.value)}
                        error={!!rowProblems.training_title}
                        hint={rowProblems.training_title}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`train-${index}-provider`}>
                        Training Provider / Institute
                      </Label>
                      <Input
                        id={`train-${index}-provider`}
                        placeholder="e.g., NPCC"
                        value={row.training_provider}
                        onChange={(e) =>
                          editTraining(index, "training_provider", e.target.value)
                        }
                        error={!!rowProblems.training_provider}
                        hint={rowProblems.training_provider}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`train-${index}-duration`}>Duration</Label>
                      <Input
                        id={`train-${index}-duration`}
                        placeholder="e.g., 2 weeks"
                        value={row.duration}
                        onChange={(e) => editTraining(index, "duration", e.target.value)}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`train-${index}-when`}>Date / Year</Label>
                      <Input
                        id={`train-${index}-when`}
                        placeholder="e.g., 2023"
                        value={row.date_or_year}
                        onChange={(e) => editTraining(index, "date_or_year", e.target.value)}
                        error={!!rowProblems.date_or_year}
                        hint={rowProblems.date_or_year}
                      />
                    </div>
                    <div className="md:col-span-4">
                      <Checkbox
                        id={`train-${index}-relevant`}
                        label="Relevant to the position applied for"
                        checked={row.relevant_to_position}
                        onChange={(checked) =>
                          editTraining(index, "relevant_to_position", checked)
                        }
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-4 flex items-center justify-between">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setTrainings((rows) => [...rows, blankTrainingRow()])}
              disabled={trainings.length >= MAX_TRAINING_ROWS}
            >
              + Add another training
            </Button>
            <span className="text-xs text-gray-400">
              {trainings.length} of {MAX_TRAINING_ROWS}
            </span>
          </div>
        </ComponentCard>

        {/* ------------------ 8. declaration & undertaking ------------------ */}
        <ComponentCard title="" desc="">
          <SectionBar number={8} title="Declaration &amp; Undertaking" />

          <div className="space-y-3 text-sm leading-relaxed text-gray-700 dark:text-gray-300">
            {declaration.length > 0 ? (
              declaration.map((paragraph, index) => <p key={index}>{paragraph}</p>)
            ) : (
              <p className="text-xs text-gray-400">
                The declaration could not be loaded from the server. Reload the page
                before submitting.
              </p>
            )}
          </div>

          <div className="mt-4 rounded-lg border border-gray-200 p-4 dark:border-gray-800">
            <Checkbox
              id="declaration_accepted"
              label="I have read, understood and accept the declaration and undertaking above"
              checked={form.declaration_accepted}
              onChange={(checked) => set("declaration_accepted", checked)}
            />
            {errors.declaration_accepted && (
              <p className="mt-2 text-xs text-error-500">{errors.declaration_accepted}</p>
            )}
          </div>
        </ComponentCard>

        {/* ---------------------- 9. submission record ---------------------- */}
        <ComponentCard title="" desc="">
          <SectionBar number={9} title="Submission Record" />

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <Label>Applicant Name</Label>
              <Input value={form.full_name} disabled />
              <FieldNote>Taken from section 2.</FieldNote>
            </div>
            <div>
              <Label>Employee ID</Label>
              <Input value={form.emp_id} disabled />
            </div>
            <div>
              <Label>Date of Submission</Label>
              <Input value={moment().format("DD MMM YYYY")} disabled />
            </div>
            <div>
              <Label>Application Reference No.</Label>
              <Input value="Issued when you submit" disabled />
              <FieldNote>
                One reference number per position applied for, shown after submitting.
              </FieldNote>
            </div>
            <div>
              <Label htmlFor="applicant_signature">
                Applicant&apos;s Electronic Signature / Confirmation{" "}
                <span className="text-error-500">*</span>
              </Label>
              <Input
                id="applicant_signature"
                placeholder="Type your full name exactly as in section 2"
                value={form.applicant_signature}
                onChange={(e) => set("applicant_signature", e.target.value)}
                error={!!errors.applicant_signature}
                hint={errors.applicant_signature}
              />
            </div>
            <div>
              <Label>HR Verification Status</Label>
              <Input value="Pending verification" disabled />
            </div>
          </div>

          {submissionNote && (
            <p className="mt-4 text-center text-xs italic text-gray-500 dark:text-gray-400">
              Note: {submissionNote}
            </p>
          )}

          <div className="mt-6 flex justify-center">
            <Button
              size="md"
              variant="primary"
              onClick={submit}
              disabled={submitting || requisitions.length === 0}
              className="min-w-60"
            >
              {submitting ? "Submitting..." : "Submit Application"}
            </Button>
          </div>
        </ComponentCard>

        {/* ------------------------- what has been filed -------------------- */}
        {submissions.length > 0 && (
          <ComponentCard
            title="My Applications"
            desc="Everything you have submitted, newest first."
          >
            <div className="max-w-full overflow-x-auto custom-scrollbar">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-xs uppercase text-gray-500 dark:border-gray-800 dark:text-gray-400">
                    <th className="py-2 pr-4 font-medium">Reference No.</th>
                    <th className="py-2 pr-4 font-medium">Position</th>
                    <th className="py-2 pr-4 font-medium">Submitted</th>
                    <th className="py-2 pr-4 font-medium">Sections</th>
                    <th className="py-2 pr-4 font-medium">HR Verification</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {submissions.map((row) => (
                    <tr key={row.id} className="text-gray-700 dark:text-gray-300">
                      <td className="py-2.5 pr-4 font-medium text-gray-800 dark:text-white/90">
                        {row.reference_no || `#${row.id}`}
                      </td>
                      <td className="py-2.5 pr-4">{row.vacancy}</td>
                      <td className="py-2.5 pr-4">
                        {moment(row.created_at).format("DD MMM YYYY, HH:mm")}
                      </td>
                      <td className="py-2.5 pr-4 text-xs text-gray-500 dark:text-gray-400">
                        {row.education_count} qualification(s) · {row.experience_count} post(s)
                        · {row.certification_count} certification(s) · {row.training_count}{" "}
                        training(s)
                      </td>
                      <td className="py-2.5 pr-4">
                        <Badge size="sm" color="light">
                          {row.hr_verification_status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </ComponentCard>
        )}
      </div>
    </>
  );
}
