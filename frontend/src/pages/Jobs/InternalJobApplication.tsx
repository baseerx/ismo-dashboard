import { useEffect, useMemo, useState } from "react";
import { ToastContainer, toast } from "react-toastify";
import PageMeta from "../../components/common/PageMeta";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import Label from "../../components/form/Label";
import Input from "../../components/form/input/InputField";
import Select from "../../components/form/Select";
import Checkbox from "../../components/form/input/Checkbox";
import Radio from "../../components/form/input/Radio";
import TextArea from "../../components/form/input/TextArea";
import DateField from "../../components/form/DateField";
import MultiSelect from "../../components/form/MultiSelect";
import Button from "../../components/ui/button/Button";
import Badge from "../../components/ui/badge/Badge";
import { Modal } from "../../components/ui/modal";
import axios from "../../api/axios";
import moment from "moment";

/**
 * ISMO internal recruitment - online application form.
 *
 * Laid out in the six sections of the "Internal Recruitment Applicant Portal"
 * specification: target position & internal validation, personal & contact
 * information, educational background, professional experience, skills &
 * certifications, and statement of purpose & acknowledgement. The fields of
 * the official printed form (CNIC, service dates, trainings, the declaration
 * and signature) sit in the section they belong to, so nothing HR files is
 * lost.
 *
 * Everything the employee record knows is prefilled, and every prefilled field
 * can be corrected - the record is not always right. A corrected field shows
 * what the record says, and the server notes the change for HR.
 *
 * One submission may target several vacancies. Each becomes an application of
 * its own with its own reference number, because each is reviewed separately.
 *
 * Every limit and rule here is enforced again in jobs/validators.py, which is
 * what actually decides - a payload can be sent without going near this page.
 */

// Kept in step with jobs/validators.py. The server also sends the text limits
// with the profile, which override these defaults.
const MAX_EDUCATION_ROWS = 15;
const MAX_EXPERIENCE_ROWS = 20;
const MAX_CERTIFICATION_ROWS = 15;
const MAX_TRAINING_ROWS = 20;
const MAX_VACANCIES = 10;
const MAX_SKILL_LENGTH = 50;

const DEFAULT_LIMITS = {
  responsibilities: 1500,
  achievements: 2000,
  sop_min: 50,
  sop_max: 3000,
  technical_skills: 30,
};

const GENDERS = ["Male", "Female", "Other"];

// Common degrees for the dropdown; "Other" lets the applicant type their own.
const DEGREE_OPTIONS = [
  "Matriculation / O-Levels",
  "Intermediate / A-Levels",
  "Diploma of Associate Engineer (DAE)",
  "Bachelor of Science (BSc)",
  "Bachelor of Engineering (BE)",
  "Bachelor of Business Administration (BBA)",
  "Bachelor of Arts (BA)",
  "Bachelor of Commerce (BCom)",
  "Master of Science (MSc)",
  "Master of Engineering (ME)",
  "Master of Business Administration (MBA)",
  "Master of Arts (MA)",
  "Master of Philosophy (MPhil)",
  "Doctor of Philosophy (PhD)",
  "Chartered Accountant (CA)",
  "ACCA",
  "PMP",
];
const OTHER_DEGREE = "__other__";

const CNIC = /^\d{5}-\d{7}-\d$/;
const PHONE = /^\+?[\d][\d\s\-()]{6,20}$/;
const EMAIL = /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/;

const EARLIEST_QUALIFICATION_YEAR = 1950;
const FUTURE_QUALIFICATION_YEARS = 6;

const today = () => moment().format("YYYY-MM-DD");

const graduationYears = () => {
  const latest = moment().year() + FUTURE_QUALIFICATION_YEARS;
  const years: string[] = [];
  for (let year = latest; year >= EARLIEST_QUALIFICATION_YEAR; year -= 1) {
    years.push(String(year));
  }
  return years;
};

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
  /** The advertisement PDF, relative to the API root; empty when none. */
  advertisement_url: string;
  advertisement_name: string;
};

type InstructionSection = { heading: string; points: string[] };

type EducationRow = {
  degree_qualification: string;
  /** True once "Other" is picked, so the degree is typed rather than chosen. */
  degree_custom: boolean;
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
  key_achievements: string;
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

  // 1. internal validation (read-only once the record supplies them)
  emp_id: string;
  full_name: string;
  department_function: string;
  current_designation: string;
  current_grade: string;
  current_supervisor_name: string;
  // 1. current employment details
  date_of_joining_ismo: string;
  date_of_appointment_to_current_grade: string;
  date_of_joining_current_position: string;
  total_service_ismo: string;
  total_relevant_experience: string;

  // 2. personal & contact information
  mobile_no: string;
  official_email: string;
  personal_email: string;
  preferred_contact_method: string;
  father_or_husband_name: string;
  cnic: string;
  date_of_birth: string;
  gender: string;
  current_office_location: string;
  emergency_contact_no: string;

  // 6. statement of purpose & acknowledgement
  application_rationale_sop: string;
  ack_manager_notified_bool: boolean;
  ack_data_accuracy_bool: boolean;
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

type RowErrors = Record<number, Record<string, string>>;

/** How each application status reads in "My Applications". */
const APPLICATION_STATUS: Record<
  string,
  { label: string; color: "success" | "warning" | "error" | "info" | "light" }
> = {
  submitted: { label: "Submitted", color: "success" },
  under_review: { label: "Under review", color: "warning" },
  verified: { label: "Verified", color: "info" },
  shortlisted: { label: "Shortlisted", color: "success" },
  rejected: { label: "Rejected", color: "error" },
  hired: { label: "Selected", color: "success" },
};

const blankEducationRow = (): EducationRow => ({
  degree_qualification: "",
  degree_custom: false,
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
  key_achievements: "",
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
  department_function: "",
  current_designation: "",
  current_grade: "",
  current_supervisor_name: "",
  date_of_joining_ismo: "",
  date_of_appointment_to_current_grade: "",
  date_of_joining_current_position: "",
  total_service_ismo: "",
  total_relevant_experience: "",
  mobile_no: "",
  official_email: "",
  personal_email: "",
  preferred_contact_method: "",
  father_or_husband_name: "",
  cnic: "",
  date_of_birth: "",
  gender: "",
  current_office_location: "",
  emergency_contact_no: "",
  application_rationale_sop: "",
  ack_manager_notified_bool: false,
  ack_data_accuracy_bool: false,
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

// Titles the employee record puts before names ("Mr. MUHAMMAD ADIL"); the
// signature check ignores them, as jobs/validators.py does.
const NAME_TITLES = /^(?:(?:mr|mrs|ms|miss|dr|engr|prof)\.?\s+)+/i;
const nameKey = (value: string) =>
  value.trim().replace(NAME_TITLES, "").toLowerCase().replace(/[^a-z]/g, "");

const authHeaders = () => {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : undefined;
};

// ---------------------------------------------------------------------------
// Small presentational helpers
// ---------------------------------------------------------------------------

/** The numbered blue section bar. */
const SectionBar = ({
  number,
  title,
  note,
}: {
  number: number;
  title: string;
  note?: string;
}) => (
  <div className="mb-4">
    <div className="rounded-md bg-[#1f4e79] px-3 py-2 text-sm font-semibold uppercase tracking-wide text-white">
      Section {number}: {title}
    </div>
    {note && <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">{note}</p>}
  </div>
);

const SubHeading = ({ children }: { children: React.ReactNode }) => (
  <h4 className="mb-3 mt-6 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
    {children}
  </h4>
);

const FieldNote = ({ children }: { children: React.ReactNode }) => (
  <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">{children}</p>
);

const ErrorText = ({ message }: { message?: string }) =>
  message ? <p className="mt-1 text-xs text-error-500">{message}</p> : null;

const Required = () => <span className="text-error-500">*</span>;

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
  <p
    className={`mt-1 text-right text-xs ${
      value >= limit ? "text-warning-600" : "text-gray-400 dark:text-gray-500"
    }`}
  >
    {value} / {limit}
  </p>
);

/** Type a skill and press Enter (or comma) to add it as a tag. */
const TagInput = ({
  id,
  tags,
  limit,
  onChange,
  error,
}: {
  id: string;
  tags: string[];
  limit: number;
  onChange: (tags: string[]) => void;
  error?: string;
}) => {
  const [draft, setDraft] = useState("");
  const [note, setNote] = useState("");

  const add = (raw: string) => {
    const tag = raw.replace(/\s+/g, " ").trim().replace(/,$/, "").trim();
    if (!tag) return;
    if (tag.length > MAX_SKILL_LENGTH) {
      setNote(`Keep each skill within ${MAX_SKILL_LENGTH} characters`);
      return;
    }
    if (tags.some((existing) => existing.toLowerCase() === tag.toLowerCase())) {
      setNote(`"${tag}" is already listed`);
      setDraft("");
      return;
    }
    if (tags.length >= limit) {
      setNote(`At most ${limit} skills`);
      return;
    }
    onChange([...tags, tag]);
    setDraft("");
    setNote("");
  };

  return (
    <div>
      <div
        className={`flex min-h-11 flex-wrap items-center gap-2 rounded-lg border px-3 py-1.5 shadow-theme-xs dark:bg-gray-900 ${
          error ? "border-error-500" : "border-gray-300 dark:border-gray-700"
        }`}
      >
        {tags.map((tag) => (
          <span
            key={tag}
            data-skill-tag={tag}
            className="flex items-center gap-1 rounded-full bg-brand-50 py-1 pl-2.5 pr-2 text-sm text-brand-700 dark:bg-brand-500/15 dark:text-brand-300"
          >
            {tag}
            <button
              type="button"
              aria-label={`Remove ${tag}`}
              onClick={() => onChange(tags.filter((item) => item !== tag))}
              className="ml-1 text-brand-500 hover:text-error-500"
            >
              ×
            </button>
          </span>
        ))}
        <input
          id={id}
          value={draft}
          onChange={(e) => {
            const value = e.target.value;
            if (value.endsWith(",")) add(value);
            else setDraft(value);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add(draft);
            } else if (e.key === "Backspace" && !draft && tags.length) {
              onChange(tags.slice(0, -1));
            }
          }}
          onBlur={() => add(draft)}
          placeholder={tags.length ? "" : "Type and press enter (e.g., Python, SAP, Agile)"}
          className="min-w-40 flex-1 border-0 bg-transparent p-1 text-sm text-gray-800 outline-hidden focus:ring-0 dark:text-white/90"
        />
      </div>
      <div className="mt-1 flex justify-between text-xs">
        <span className={error ? "text-error-500" : "text-warning-600"}>{error || note}</span>
        <span className="text-gray-400">
          {tags.length} / {limit}
        </span>
      </div>
    </div>
  );
};

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
  const [technicalSkills, setTechnicalSkills] = useState<string[]>([]);
  const [softSkills, setSoftSkills] = useState<string[]>([]);

  // Wording and lists served by the server, so page and server agree.
  const [declaration, setDeclaration] = useState<string[]>([]);
  const [submissionNote, setSubmissionNote] = useState("");
  const [softSkillOptions, setSoftSkillOptions] = useState<string[]>([]);
  const [contactMethods, setContactMethods] = useState<string[]>(["Teams", "Email", "SMS"]);
  const [ackManagerText, setAckManagerText] = useState(
    "I certify that my current manager is aware of this transfer request"
  );
  const [ackAccuracyText, setAckAccuracyText] = useState(
    "I confirm all provided data details match official corporate record"
  );
  const [limits, setLimits] = useState(DEFAULT_LIMITS);
  const [supervisorName, setSupervisorName] = useState("");

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [eduErrors, setEduErrors] = useState<RowErrors>({});
  const [expErrors, setExpErrors] = useState<RowErrors>({});
  const [certErrors, setCertErrors] = useState<RowErrors>({});
  const [trainErrors, setTrainErrors] = useState<RowErrors>({});

  const [loadingProfile, setLoadingProfile] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [profileNote, setProfileNote] = useState<string | null>(null);
  // What the employee record said for each prefilled field, so a corrected
  // field can show it and be put back.
  const [recordValues, setRecordValues] = useState<Record<string, string>>({});
  const [submissions, setSubmissions] = useState<Submitted[]>([]);
  // Bumped after a submission so the vacancy picker remounts with nothing chosen.
  const [vacancyPickerKey, setVacancyPickerKey] = useState(0);
  // Which chosen positions have their description expanded. Everything picked
  // starts open - the point of choosing a position is to read what it involves -
  // and each panel can be folded away.
  const [openDescriptions, setOpenDescriptions] = useState<number[]>([]);
  // "How to apply / general instructions" popup.
  const [instructionsOpen, setInstructionsOpen] = useState(false);
  const [instructions, setInstructions] = useState<InstructionSection[] | null>(null);
  const [instructionsError, setInstructionsError] = useState(false);

  const years = useMemo(graduationYears, []);

  useEffect(() => {
    loadRequisitions();
    loadProfile();
    loadSubmissions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Fetched when the popup is first opened, then kept. */
  const openInstructions = async () => {
    setInstructionsOpen(true);
    if (instructions) return;
    setInstructionsError(false);
    try {
      const response = await axios.get("/jobs/application-instructions/");
      setInstructions(Array.isArray(response.data?.sections) ? response.data.sections : []);
    } catch {
      setInstructionsError(true);
    }
  };

  const loadRequisitions = async () => {
    try {
      const response = await axios.get("/jobs/requisitions/");
      setRequisitions(Array.isArray(response.data) ? response.data : []);
    } catch {
      setRequisitions([]);
    }
  };

  const loadSubmissions = async () => {
    try {
      const response = await axios.get("/jobs/applications/", { headers: authHeaders() });
      setSubmissions(Array.isArray(response.data) ? response.data : []);
    } catch {
      setSubmissions([]);
    }
  };

  /** Fills in what the employee record already knows about the signed-in user. */
  const loadProfile = async () => {
    try {
      const response = await axios.get("/jobs/application-profile/", {
        headers: authHeaders(),
      });
      const profile = response.data || {};

      setDeclaration(profile.declaration_paragraphs || []);
      setSubmissionNote(profile.submission_note || "");
      setSoftSkillOptions(profile.soft_skill_options || []);
      if (profile.contact_methods?.length) setContactMethods(profile.contact_methods);
      if (profile.ack_manager_notified_text) setAckManagerText(profile.ack_manager_notified_text);
      if (profile.ack_data_accuracy_text) setAckAccuracyText(profile.ack_data_accuracy_text);
      if (profile.limits) setLimits({ ...DEFAULT_LIMITS, ...profile.limits });
      setSupervisorName(profile.current_supervisor_name || "");

      const fromRecord: Record<string, string> = {};
      const take = (field: keyof FormState, value: unknown) => {
        const text = value == null ? "" : String(value);
        if (text) fromRecord[field as string] = text;
        return text;
      };

      setForm((previous) => ({
        ...previous,
        emp_id: take("emp_id", profile.emp_id),
        full_name: take("full_name", profile.full_name),
        department_function: take("department_function", profile.department_function),
        current_designation: take("current_designation", profile.current_designation),
        current_grade: take("current_grade", profile.current_grade),
        current_supervisor_name: take(
          "current_supervisor_name",
          profile.current_supervisor_name
        ),
        cnic: take("cnic", profile.cnic),
        gender: take("gender", profile.gender),
        official_email: take("official_email", profile.official_email),
        current_office_location: take(
          "current_office_location",
          profile.current_office_location
        ),
      }));
      setRecordValues(fromRecord);

      // The applicant's current post starts the experience section off, since
      // everyone has one and it is the row reviewers look at first.
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
      const status = error?.response?.status;
      if (status === 401) {
        setProfileNote(
          error?.response?.data?.error || "Sign in again - your session has expired."
        );
      } else if (status === 404) {
        setProfileNote(
          "No active employee record was found for your account, so nothing could be filled in for you."
        );
      } else if (!error?.response) {
        setProfileNote("Your details could not be loaded from the server, so the form starts empty.");
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
    setOpenDescriptions(selected.map(Number));
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

  const toggleSoftSkill = (skill: string, checked: boolean) => {
    setSoftSkills((current) =>
      checked ? [...current, skill] : current.filter((item) => item !== skill)
    );
    clearError("skills_soft_checkboxes");
  };

  // ---- repeaters ---------------------------------------------------------
  const dropRowError = (
    setRowErrors: React.Dispatch<React.SetStateAction<RowErrors>>,
    index: number,
    field: string
  ) =>
    setRowErrors((previous) => {
      if (!previous[index]?.[field]) return previous;
      const next = { ...previous, [index]: { ...previous[index] } };
      delete next[index][field];
      return next;
    });

  const editEducation = (index: number, changes: Partial<EducationRow>) => {
    setEducation((rows) => rows.map((row, i) => (i === index ? { ...row, ...changes } : row)));
    Object.keys(changes).forEach((field) => dropRowError(setEduErrors, index, field));
  };

  const chooseDegree = (index: number, choice: string) => {
    if (choice === OTHER_DEGREE) {
      editEducation(index, { degree_custom: true, degree_qualification: "" });
    } else {
      editEducation(index, { degree_custom: false, degree_qualification: choice });
    }
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
    dropRowError(setExpErrors, index, field as string);
  };

  const editCertification = (index: number, field: keyof CertificationRow, value: string) => {
    setCertifications((rows) =>
      rows.map((row, i) => (i === index ? { ...row, [field]: value } : row))
    );
    dropRowError(setCertErrors, index, field);
  };

  const editTraining = (
    index: number,
    field: keyof TrainingRow,
    value: string | boolean
  ) => {
    setTrainings((rows) =>
      rows.map((row, i) => (i === index ? { ...row, [field]: value } : row))
    );
    dropRowError(setTrainErrors, index, field as string);
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
    const digits = (value: string) => (value.match(/\d/g) || []).length;

    // 1. target position & internal validation
    if (form.target_job_req_ids.length === 0) {
      problems.target_job_req_ids = "Select at least one vacancy to apply for";
    } else if (form.target_job_req_ids.length > MAX_VACANCIES) {
      problems.target_job_req_ids = `Apply for at most ${MAX_VACANCIES} vacancies at a time`;
    }
    if (!form.emp_id.trim() || Number(form.emp_id) <= 0) {
      problems.emp_id = "Employee ID must be a number";
    }
    if (!form.full_name.trim()) problems.full_name = "Full name is required";
    else if (form.full_name.trim().length < 3) problems.full_name = "That looks too short";
    if (!form.department_function.trim()) {
      problems.department_function = "Current department is required";
    }
    if (!form.current_designation.trim()) {
      problems.current_designation = "Current position title is required";
    }
    if (!form.current_grade.trim()) problems.current_grade = "Current grade is required";
    const supervisor = form.current_supervisor_name.trim();
    if (supervisor.length > 150) {
      problems.current_supervisor_name = "Keep the supervisor's name within 150 characters";
    } else if (supervisor && supervisor.length < 3) {
      problems.current_supervisor_name = "That name looks too short";
    }

    if (!form.date_of_joining_ismo) {
      problems.date_of_joining_ismo = "Date of joining ISMO is required";
    } else if (form.date_of_joining_ismo > today()) {
      problems.date_of_joining_ismo = "That date cannot be in the future";
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

    // 2. personal & contact information
    if (!form.mobile_no.trim()) problems.mobile_no = "Contact phone number is required";
    else if (!PHONE.test(form.mobile_no.trim()) || digits(form.mobile_no) < 7) {
      problems.mobile_no = "Enter a number like +92-300-1234567";
    }
    if (!form.official_email.trim()) {
      problems.official_email = "Corporate email address is required";
    } else if (!EMAIL.test(form.official_email.trim())) {
      problems.official_email = "That does not look like an email address";
    }
    if (form.personal_email.trim()) {
      if (!EMAIL.test(form.personal_email.trim())) {
        problems.personal_email = "That does not look like an email address";
      } else if (
        form.personal_email.trim().toLowerCase() === form.official_email.trim().toLowerCase()
      ) {
        problems.personal_email =
          "Give a different address from your corporate email, or leave this blank";
      }
    }
    if (!form.preferred_contact_method) {
      problems.preferred_contact_method = "Choose how you would like to be contacted";
    }
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
      const age = moment().diff(moment(form.date_of_birth, "YYYY-MM-DD"), "years", true);
      if (age < 18) problems.date_of_birth = "An applicant must be at least 18";
      else if (age > 70) {
        problems.date_of_birth = "Check the date of birth - that is over 70 years ago";
      }
    }
    if (!form.gender) problems.gender = "Gender is required";
    if (!form.current_office_location.trim()) {
      problems.current_office_location = "Current office / location is required";
    }
    if (
      form.emergency_contact_no.trim() &&
      (!PHONE.test(form.emergency_contact_no.trim()) || digits(form.emergency_contact_no) < 7)
    ) {
      problems.emergency_contact_no = "Enter a number like +92-300-1234567";
    }

    // 3. educational background
    const educationProblems: RowErrors = {};
    const thisYear = moment().year();
    education.forEach((row, index) => {
      const rowProblems: Record<string, string> = {};
      if (!row.degree_qualification.trim()) {
        rowProblems.degree_qualification = row.degree_custom
          ? "Type the degree or certificate"
          : "Degree / certificate is required";
      } else if (row.degree_qualification.trim().length < 2) {
        rowProblems.degree_qualification = "That looks too short";
      }
      if (!row.major_field_of_study.trim()) {
        rowProblems.major_field_of_study = "Major / field of study is required";
      }
      if (!row.institution_university.trim()) {
        rowProblems.institution_university = "Institution / university is required";
      }
      if (!row.country.trim()) rowProblems.country = "Country is required";
      const year = Number(row.year_of_completion);
      if (!row.year_of_completion) {
        rowProblems.year_of_completion = "Graduation year is required";
      } else if (year < EARLIEST_QUALIFICATION_YEAR || year > thisYear + FUTURE_QUALIFICATION_YEARS) {
        rowProblems.year_of_completion = "Choose a year from the list";
      }
      if (!row.cgpa_division.trim()) {
        rowProblems.cgpa_division = "CGPA / percentage / grade is required";
      }
      if (Object.keys(rowProblems).length) educationProblems[index] = rowProblems;
    });
    if (education.length === 0) problems.education = "Add at least one qualification";

    // 4. professional experience
    const experienceProblems: RowErrors = {};
    experience.forEach((row, index) => {
      const rowProblems: Record<string, string> = {};
      if (!row.designation.trim()) rowProblems.designation = "Job position title is required";
      if (!row.organization_employer.trim()) {
        rowProblems.organization_employer = "Organization / company name is required";
      }
      if (!row.from_date) rowProblems.from_date = "Start date is required";
      else if (row.from_date > today()) rowProblems.from_date = "That date cannot be in the future";

      if (!row.is_current) {
        if (!row.to_date) rowProblems.to_date = "Select an end date or tick 'Present role'";
        else if (row.to_date > today()) rowProblems.to_date = "That date cannot be in the future";
        else if (row.from_date && row.to_date < row.from_date) {
          rowProblems.to_date = "The end date cannot be before the start date";
        }
      }

      if (!row.key_responsibilities.trim()) {
        rowProblems.key_responsibilities = "Key responsibilities are required";
      } else if (row.key_responsibilities.trim().length < 10) {
        rowProblems.key_responsibilities = "Add a little more detail";
      } else if (row.key_responsibilities.length > limits.responsibilities) {
        rowProblems.key_responsibilities = `Keep this within ${limits.responsibilities} characters`;
      }
      if (row.key_achievements.length > limits.achievements) {
        rowProblems.key_achievements = `Keep this within ${limits.achievements} characters`;
      }
      if (Object.keys(rowProblems).length) experienceProblems[index] = rowProblems;
    });
    if (experience.length === 0) {
      problems.experience = "Add at least one post, including your current one";
    }

    // 5. skills, certifications, trainings
    if (technicalSkills.length === 0) {
      problems.skills_technical_tags = "Add at least one core technical skill";
    } else if (technicalSkills.length > limits.technical_skills) {
      problems.skills_technical_tags = `List at most ${limits.technical_skills} technical skills`;
    }

    const certificationProblems: RowErrors = {};
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

    const trainingProblems: RowErrors = {};
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

    // 6. statement of purpose & acknowledgement
    const sop = form.application_rationale_sop.trim();
    if (!sop) {
      problems.application_rationale_sop = "Explain why you are applying for this position";
    } else if (sop.length < limits.sop_min) {
      problems.application_rationale_sop = `Give a little more detail - at least ${limits.sop_min} characters`;
    } else if (sop.length > limits.sop_max) {
      problems.application_rationale_sop = `Keep this within ${limits.sop_max} characters`;
    }
    if (!form.ack_manager_notified_bool) {
      problems.ack_manager_notified_bool =
        "Confirm that your current manager is aware of this application";
    }
    if (!form.ack_data_accuracy_bool) {
      problems.ack_data_accuracy_bool =
        "Confirm that your details match the official corporate record";
    }
    if (!form.declaration_accepted) {
      problems.declaration_accepted =
        "Read and accept the declaration and undertaking before submitting";
    }
    if (!form.applicant_signature.trim()) {
      problems.applicant_signature = "Type your full name to sign the application";
    } else if (
      form.full_name.trim() &&
      nameKey(form.applicant_signature) !== nameKey(form.full_name)
    ) {
      problems.applicant_signature = "The signature must be your full name as shown in section 1";
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

    if (!clean) {
      toast.error("Please correct the highlighted fields");
      // Bring the first problem into view.
      window.setTimeout(() => {
        document
          .querySelector(".text-error-500, .border-error-500, .text-red-600")
          ?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 50);
    }
    return clean;
  };

  // ---- submitting --------------------------------------------------------
  const submit = async () => {
    if (!validate()) return;

    setSubmitting(true);
    const hasContent = (values: string[]) => values.some((value) => value.trim());

    try {
      const response = await axios.post(
        "/jobs/applications/create/",
        {
          target_job_req_ids: form.target_job_req_ids.map(Number),

          emp_id: Number(form.emp_id),
          full_name: form.full_name.trim(),
          department_function: form.department_function.trim(),
          current_designation: form.current_designation.trim(),
          current_grade: form.current_grade.trim(),
          current_supervisor_name: form.current_supervisor_name.trim(),
          date_of_joining_ismo: form.date_of_joining_ismo,
          date_of_appointment_to_current_grade: form.date_of_appointment_to_current_grade,
          date_of_joining_current_position: form.date_of_joining_current_position,
          total_service_ismo: form.total_service_ismo.trim(),
          total_relevant_experience: form.total_relevant_experience.trim(),

          mobile_no: form.mobile_no.trim(),
          official_email: form.official_email.trim(),
          personal_email: form.personal_email.trim(),
          preferred_contact_method: form.preferred_contact_method,
          father_or_husband_name: form.father_or_husband_name.trim(),
          cnic: form.cnic.trim(),
          date_of_birth: form.date_of_birth,
          gender: form.gender,
          current_office_location: form.current_office_location.trim(),
          emergency_contact_no: form.emergency_contact_no.trim(),

          education: education.map((row) => ({
            degree_qualification: row.degree_qualification.trim(),
            major_field_of_study: row.major_field_of_study,
            institution_university: row.institution_university,
            country: row.country,
            year_of_completion: Number(row.year_of_completion),
            cgpa_division: row.cgpa_division,
          })),
          experience: experience.map((row) => ({
            ...row,
            to_date: row.is_current ? null : row.to_date || null,
          })),

          skills_technical_tags: technicalSkills,
          skills_soft_checkboxes: softSkills,
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
            hasContent([row.training_title, row.training_provider, row.duration, row.date_or_year])
          ),

          application_rationale_sop: form.application_rationale_sop.trim(),
          ack_manager_notified_bool: form.ack_manager_notified_bool,
          ack_data_accuracy_bool: form.ack_data_accuracy_bool,
          declaration_accepted: form.declaration_accepted,
          applicant_signature: form.applicant_signature.trim(),
        },
        { headers: authHeaders() }
      );

      toast.success(response.data?.message ?? "Your application has been submitted");
      if (response.data?.supervisor_notified && supervisorName) {
        toast.info(`${supervisorName} has been notified of your application.`);
      }

      // What the applicant typed for these vacancies is cleared; their own
      // details stay, so applying again later needs little retyping.
      setForm((previous) => ({
        ...previous,
        target_job_req_ids: [],
        application_rationale_sop: "",
        ack_manager_notified_bool: false,
        ack_data_accuracy_bool: false,
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
          const mapped: RowErrors = {};
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

  /** True when the field still holds what the employee record said. */
  const sameAsRecord = (field: string) =>
    (form[field as keyof FormState] as string).trim().replace(/\s+/g, " ").toLowerCase() ===
    (recordValues[field] ?? "").trim().replace(/\s+/g, " ").toLowerCase();

  const autoFilled = (field: string) =>
    !(field in recordValues) ? null : sameAsRecord(field) ? (
      <span className="ml-2 align-middle text-[10px] font-medium uppercase tracking-wide text-brand-500">
        auto-filled
      </span>
    ) : (
      <span
        className="ml-2 align-middle text-[10px] font-medium uppercase tracking-wide text-warning-600"
        data-edited={field}
      >
        edited
      </span>
    );

  /** Under a corrected field: what the record says, and a way back to it. */
  const recordHint = (field: keyof FormState) =>
    field in recordValues && !sameAsRecord(field) ? (
      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400" data-record-hint={field}>
        Employee record says: <span className="font-medium">{recordValues[field]}</span>
        {" · "}
        <button
          type="button"
          onClick={() => set(field, recordValues[field])}
          className="font-medium text-brand-500 hover:text-brand-600"
        >
          Use this
        </button>
      </p>
    ) : null;

  /** A text field prefilled from the employee record, open to correction. */
  const recordField = (field: keyof FormState, label: string, placeholder?: string) => (
    <div>
      <Label htmlFor={field}>
        {label} <Required />
        {autoFilled(field)}
      </Label>
      <Input
        id={field}
        placeholder={placeholder}
        value={form[field] as string}
        onChange={(e) =>
          set(field, field === "emp_id" ? e.target.value.replace(/\D/g, "") : e.target.value)
        }
        error={!!errors[field]}
        hint={errors[field]}
      />
      {recordHint(field)}
    </div>
  );

  const vacancyOptions = requisitions.map((item) => ({
    text: [item.title, item.reference_no || null, item.grade || null, item.department || null]
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
            INTERNAL RECRUITMENT APPLICANT PORTAL
          </p>
          <p className="mt-1 text-xs italic text-gray-500 dark:text-gray-400">
            For applications against internally advertised positions. Fields marked{" "}
            <span className="text-error-500">*</span> are required.
          </p>
          <button
            type="button"
            id="how-to-apply"
            onClick={openInstructions}
            className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-brand-200 bg-brand-50 px-3.5 py-1.5 text-xs font-medium text-brand-600 hover:bg-brand-100 dark:border-brand-500/30 dark:bg-brand-500/10 dark:text-brand-400"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <circle cx="12" cy="12" r="9" />
              <path d="M12 16v-4M12 8h.01" />
            </svg>
            General instructions
          </button>
          {loadingProfile && (
            <p className="mt-3 text-xs text-gray-400">Filling in your details...</p>
          )}
          {profileNote && (
            <p className="mt-3 text-xs text-warning-600 dark:text-warning-400">{profileNote}</p>
          )}
        </div>

        {/* ------------- 1. target position & internal validation ----------- */}
        <ComponentCard title="" desc="">
          <SectionBar
            number={1}
            title="Target Position & Internal Validation"
            note="Choose the advertised vacancy. Your details below come from your corporate record."
          />

          <div>
            <Label htmlFor="requisition-dropdown">
              Job Requisition / Opening <Required />
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
                  searchable
                  placeholder="Select advertised vacancy..."
                />
                <FieldNote>
                  Search by title, reference number, grade or department. Pick as many as
                  you want to apply for: each one gets its own reference number and is
                  reviewed separately.
                </FieldNote>
                <ErrorText message={errors.target_job_req_ids} />
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
                    {(
                      [
                        ["Position Title", vacancy.title],
                        ["Advertisement / Reference No.", vacancy.reference_no || "—"],
                        ["Grade", vacancy.grade || "—"],
                        ["Department / Function", vacancy.department || "—"],
                        ["Date of Advertisement", showDate(vacancy.advertisement_date)],
                        ["Closing Date", showDate(vacancy.closing_date)],
                      ] as [string, string][]
                    ).map(([label, value]) => (
                      <div key={label}>
                        <p className="text-xs text-gray-400">{label}</p>
                        <p className="text-sm text-gray-800 dark:text-white/90">{value}</p>
                      </div>
                    ))}
                  </div>

                  {vacancy.notes ? (
                    <p className="mt-3 whitespace-pre-wrap text-sm text-gray-600 dark:text-gray-400">
                      {vacancy.notes}
                    </p>
                  ) : null}

                  {vacancy.advertisement_url ? (
                    <a
                      href={`${axios.defaults.baseURL}${vacancy.advertisement_url}`}
                      target="_blank"
                      rel="noreferrer"
                      data-advertisement-link={vacancy.id}
                      className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-brand-500 hover:text-brand-600"
                    >
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" strokeWidth="2" aria-hidden="true">
                        <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
                        <path d="M14 3v5h5" />
                      </svg>
                      View advertisement (PDF)
                    </a>
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

          <SubHeading>Internal validation</SubHeading>
          <p className="-mt-1 mb-3 text-xs text-gray-500 dark:text-gray-400">
            Filled in from your employee record. Check each one and correct anything
            that is wrong - HR is shown what you changed.
          </p>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {recordField("full_name", "Employee Full Name")}
            {recordField("emp_id", "Employee ID")}
            {recordField("department_function", "Current Department")}
            {recordField("current_designation", "Current Position Title")}
            {recordField("current_grade", "Current Grade", "e.g., G-07")}
            <div>
              <Label htmlFor="current_supervisor_name">
                Current Supervisor Name
                {autoFilled("current_supervisor_name")}
              </Label>
              <Input
                id="current_supervisor_name"
                placeholder={
                  loadingProfile ? "" : "None on record - type your supervisor's name"
                }
                value={form.current_supervisor_name}
                onChange={(e) => set("current_supervisor_name", e.target.value)}
                error={!!errors.current_supervisor_name}
                hint={errors.current_supervisor_name}
              />
              {recordHint("current_supervisor_name")}
            </div>
          </div>

          <SubHeading>Current employment details</SubHeading>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            <div>
              <Label htmlFor="date_of_joining_ismo">
                Date of Joining ISMO <Required />
              </Label>
              <DateField
                id="date_of_joining_ismo"
                placeholder="Select joining date"
                maxDate={today()}
                value={form.date_of_joining_ismo}
                onChange={(value) => set("date_of_joining_ismo", value)}
                error={!!errors.date_of_joining_ismo}
                hint={errors.date_of_joining_ismo}
              />
            </div>
            <div>
              <Label htmlFor="date_of_joining_current_position">
                Date of Joining Current Position <Required />
              </Label>
              <DateField
                id="date_of_joining_current_position"
                placeholder="Select date"
                maxDate={today()}
                value={form.date_of_joining_current_position}
                onChange={(value) => set("date_of_joining_current_position", value)}
                error={!!errors.date_of_joining_current_position}
                hint={errors.date_of_joining_current_position}
              />
            </div>
            <div>
              <Label htmlFor="date_of_appointment_to_current_grade">
                Date of Appointment to Current Grade <Required />
              </Label>
              <DateField
                id="date_of_appointment_to_current_grade"
                placeholder="Select date"
                maxDate={today()}
                value={form.date_of_appointment_to_current_grade}
                onChange={(value) => set("date_of_appointment_to_current_grade", value)}
                error={!!errors.date_of_appointment_to_current_grade}
                hint={errors.date_of_appointment_to_current_grade}
              />
            </div>
            <div>
              <Label htmlFor="total_service_ismo">
                Total Service in ISMO <Required />
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
                Total Relevant Experience <Required />
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
          </div>
        </ComponentCard>

        {/* --------------- 2. personal & contact information ---------------- */}
        <ComponentCard title="" desc="">
          <SectionBar
            number={2}
            title="Personal & Contact Information"
            note="How we reach you about this application outside the usual internal channels."
          />

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="mobile_no">
                Contact Phone Number <Required />
              </Label>
              <Input
                id="mobile_no"
                type="tel"
                placeholder="+92-3XX-XXXXXXX"
                value={form.mobile_no}
                onChange={(e) => set("mobile_no", e.target.value)}
                error={!!errors.mobile_no}
                hint={errors.mobile_no}
              />
            </div>
            <div>
              <Label htmlFor="official_email">
                Corporate Email Address <Required />
                {autoFilled("official_email")}
              </Label>
              <Input
                id="official_email"
                type="email"
                placeholder="username@ismo.gov.pk"
                value={form.official_email}
                onChange={(e) => set("official_email", e.target.value)}
                error={!!errors.official_email}
                hint={errors.official_email}
              />
              {recordHint("official_email")}
            </div>
            <div>
              <Label htmlFor="personal_email">Personal Email Address (optional)</Label>
              <Input
                id="personal_email"
                type="email"
                placeholder="alternative.email@domain.com"
                value={form.personal_email}
                onChange={(e) => set("personal_email", e.target.value)}
                error={!!errors.personal_email}
                hint={errors.personal_email}
              />
            </div>
            <div>
              <Label>
                Internal Communication Channel <Required />
              </Label>
              <div className="flex h-11 flex-wrap items-center gap-6" id="preferred_contact_method">
                {contactMethods.map((method) => (
                  <Radio
                    key={method}
                    id={`contact-${method}`}
                    name="preferred_contact_method"
                    value={method}
                    label={method}
                    checked={form.preferred_contact_method === method}
                    onChange={(value) => set("preferred_contact_method", value)}
                  />
                ))}
              </div>
              <ErrorText message={errors.preferred_contact_method} />
            </div>
            <div>
              <Label htmlFor="father_or_husband_name">
                Father&apos;s / Husband&apos;s Name <Required />
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
                CNIC No. <Required />
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
              {recordHint("cnic")}
            </div>
            <div>
              <Label htmlFor="date_of_birth">
                Date of Birth <Required />
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
                Gender <Required />
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
              {recordHint("gender")}
            </div>
            <div>
              <Label htmlFor="current_office_location">
                Current Office / Location <Required />
                {autoFilled("current_office_location")}
              </Label>
              <Input
                id="current_office_location"
                value={form.current_office_location}
                onChange={(e) => set("current_office_location", e.target.value)}
                error={!!errors.current_office_location}
                hint={errors.current_office_location}
              />
              {recordHint("current_office_location")}
            </div>
            <div>
              <Label htmlFor="emergency_contact_no">Emergency Contact No. (optional)</Label>
              <Input
                id="emergency_contact_no"
                type="tel"
                placeholder="+92-3XX-XXXXXXX"
                value={form.emergency_contact_no}
                onChange={(e) => set("emergency_contact_no", e.target.value)}
                error={!!errors.emergency_contact_no}
                hint={errors.emergency_contact_no}
              />
            </div>
          </div>
        </ComponentCard>

        {/* ------------------- 3. educational background -------------------- */}
        <ComponentCard title="" desc="">
          <SectionBar
            number={3}
            title="Educational Background"
            note="Add each degree or certificate. They are filed in chronological order of graduation year."
          />

          <div className="space-y-4">
            {education.map((row, index) => {
              const rowProblems = eduErrors[index] || {};
              const listed = DEGREE_OPTIONS.includes(row.degree_qualification);
              const degreeChoice = row.degree_custom
                ? OTHER_DEGREE
                : listed
                  ? row.degree_qualification
                  : "";
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
                      <Label>
                        Degree / Certificate Earned <Required />
                      </Label>
                      <Select
                        options={[
                          ...DEGREE_OPTIONS.map((value) => ({ label: value, value })),
                          { label: "Other (type it in)", value: OTHER_DEGREE },
                        ]}
                        placeholder="e.g., Bachelor of Science, MBA, PMP"
                        value={degreeChoice}
                        onChange={(value) => chooseDegree(index, value)}
                        error={!!rowProblems.degree_qualification && !row.degree_custom}
                        hint={row.degree_custom ? "" : rowProblems.degree_qualification}
                      />
                      {row.degree_custom && (
                        <div className="mt-2">
                          <Input
                            id={`edu-${index}-degree`}
                            placeholder="Type your degree or certificate"
                            value={row.degree_qualification}
                            onChange={(e) =>
                              editEducation(index, { degree_qualification: e.target.value })
                            }
                            error={!!rowProblems.degree_qualification}
                            hint={rowProblems.degree_qualification}
                          />
                        </div>
                      )}
                    </div>
                    <div>
                      <Label htmlFor={`edu-${index}-institution`}>
                        Institution / University Name <Required />
                      </Label>
                      <Input
                        id={`edu-${index}-institution`}
                        placeholder="Enter name of school/university"
                        value={row.institution_university}
                        onChange={(e) =>
                          editEducation(index, { institution_university: e.target.value })
                        }
                        error={!!rowProblems.institution_university}
                        hint={rowProblems.institution_university}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`edu-${index}-major`}>
                        Major / Field of Study <Required />
                      </Label>
                      <Input
                        id={`edu-${index}-major`}
                        placeholder="e.g., Computer Science, Finance, HR Management"
                        value={row.major_field_of_study}
                        onChange={(e) =>
                          editEducation(index, { major_field_of_study: e.target.value })
                        }
                        error={!!rowProblems.major_field_of_study}
                        hint={rowProblems.major_field_of_study}
                      />
                    </div>
                    <div>
                      <Label>
                        Graduation Year <Required />
                      </Label>
                      <Select
                        options={years.map((value) => ({ label: value, value }))}
                        placeholder="Select Year of Completion"
                        value={row.year_of_completion}
                        onChange={(value) => editEducation(index, { year_of_completion: value })}
                        error={!!rowProblems.year_of_completion}
                        hint={rowProblems.year_of_completion}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`edu-${index}-grade`}>
                        CGPA / Percentage / Grade <Required />
                      </Label>
                      <Input
                        id={`edu-${index}-grade`}
                        placeholder="e.g., 3.8 / 4.0 or Grade A"
                        value={row.cgpa_division}
                        onChange={(e) =>
                          editEducation(index, { cgpa_division: e.target.value.slice(0, 40) })
                        }
                        error={!!rowProblems.cgpa_division}
                        hint={rowProblems.cgpa_division}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`edu-${index}-country`}>
                        Country <Required />
                      </Label>
                      <Input
                        id={`edu-${index}-country`}
                        value={row.country}
                        onChange={(e) => editEducation(index, { country: e.target.value })}
                        error={!!rowProblems.country}
                        hint={rowProblems.country}
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
          <ErrorText message={errors.education} />
        </ComponentCard>

        {/* -------------------- 4. professional experience ------------------ */}
        <ComponentCard title="" desc="">
          <SectionBar
            number={4}
            title="Professional Experience"
            note="Add your past employment and your internal promotions, one row each."
          />

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
                      <Label htmlFor={`exp-${index}-designation`}>
                        Job Position Title <Required />
                      </Label>
                      <Input
                        id={`exp-${index}-designation`}
                        placeholder="e.g., Senior Software Engineer, Assistant Manager"
                        value={row.designation}
                        onChange={(e) => editExperience(index, "designation", e.target.value)}
                        error={!!rowProblems.designation}
                        hint={rowProblems.designation}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`exp-${index}-employer`}>
                        Organization / Company Name <Required />
                      </Label>
                      <Input
                        id={`exp-${index}-employer`}
                        placeholder="Enter employer name or internal subsidiary"
                        value={row.organization_employer}
                        onChange={(e) =>
                          editExperience(index, "organization_employer", e.target.value)
                        }
                        error={!!rowProblems.organization_employer}
                        hint={rowProblems.organization_employer}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`exp-${index}-grade`}>Grade (if applicable)</Label>
                      <Input
                        id={`exp-${index}-grade`}
                        placeholder="e.g., G-08"
                        value={row.grade}
                        onChange={(e) => editExperience(index, "grade", e.target.value)}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`exp-${index}-from`}>
                        Employment Start Date <Required />
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
                        Employment End Date {!row.is_current && <Required />}
                      </Label>
                      <Input
                        id={`exp-${index}-to`}
                        type="date"
                        max={today()}
                        min={row.from_date || undefined}
                        value={row.to_date}
                        disabled={row.is_current}
                        onChange={(e) => editExperience(index, "to_date", e.target.value)}
                        error={!!rowProblems.to_date}
                        hint={rowProblems.to_date}
                      />
                      <div className="mt-2">
                        <Checkbox
                          id={`exp-${index}-current`}
                          label="Present Role (currently in this role)"
                          checked={row.is_current}
                          onChange={(checked) => editExperience(index, "is_current", checked)}
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
                      <FieldNote>Worked out from the dates.</FieldNote>
                    </div>
                    <div className="md:col-span-3">
                      <Label htmlFor={`exp-${index}-responsibilities`}>
                        Key Responsibilities &amp; Roles <Required />
                      </Label>
                      <TextArea
                        id={`exp-${index}-responsibilities`}
                        rows={3}
                        placeholder="Summarize core day-to-day functional mandates..."
                        value={row.key_responsibilities}
                        onChange={(value) =>
                          editExperience(
                            index,
                            "key_responsibilities",
                            value.slice(0, limits.responsibilities)
                          )
                        }
                        error={!!rowProblems.key_responsibilities}
                        hint={rowProblems.key_responsibilities}
                      />
                      <Counter
                        value={row.key_responsibilities.length}
                        limit={limits.responsibilities}
                      />
                    </div>
                    <div className="md:col-span-3">
                      <Label htmlFor={`exp-${index}-achievements`}>
                        Key Achievements &amp; Projects (optional)
                      </Label>
                      <TextArea
                        id={`exp-${index}-achievements`}
                        rows={3}
                        placeholder="List quantifiable achievements (e.g., 'Boosted efficiency by 20%')"
                        value={row.key_achievements}
                        onChange={(value) =>
                          editExperience(
                            index,
                            "key_achievements",
                            value.slice(0, limits.achievements)
                          )
                        }
                        error={!!rowProblems.key_achievements}
                        hint={rowProblems.key_achievements}
                      />
                      <Counter value={row.key_achievements.length} limit={limits.achievements} />
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
          <ErrorText message={errors.experience} />
        </ComponentCard>

        {/* ------------ 5. skills matrix & professional certifications ------- */}
        <ComponentCard title="" desc="">
          <SectionBar
            number={5}
            title="Skills Matrix & Professional Certifications"
            note="Your skills are used to match you to positions, so name them plainly."
          />

          <div>
            <Label htmlFor="technical-skills">
              Core Technical Skills <Required />
            </Label>
            <TagInput
              id="technical-skills"
              tags={technicalSkills}
              limit={limits.technical_skills}
              onChange={(tags) => {
                setTechnicalSkills(tags);
                clearError("skills_technical_tags");
              }}
              error={errors.skills_technical_tags}
            />
          </div>

          <div className="mt-5">
            <Label>Soft Skills / Leadership Capabilities</Label>
            <p className="mb-3 text-xs text-gray-400">Check relevant matching items.</p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3" id="soft-skills">
              {softSkillOptions.map((skill) => (
                <Checkbox
                  key={skill}
                  id={`soft-${skill}`}
                  label={skill}
                  checked={softSkills.includes(skill)}
                  onChange={(checked) => toggleSoftSkill(skill, checked)}
                />
              ))}
            </div>
            <ErrorText message={errors.skills_soft_checkboxes} />
          </div>

          <SubHeading>Active professional certifications</SubHeading>
          <p className="-mt-2 mb-4 text-xs text-gray-500 dark:text-gray-400">
            List any credentials (e.g., AWS Architect, ACCA, Six Sigma). Leave blank if you
            have none; once a row is started, the certification and its issuing body are
            both needed.
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
                      <Label htmlFor={`cert-${index}-body`}>Certifying / Professional Body</Label>
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
                      <Label htmlFor={`cert-${index}-expiry`}>Expiry Date (if applicable)</Label>
                      <Input
                        id={`cert-${index}-expiry`}
                        type="date"
                        value={row.expiry_date}
                        onChange={(e) => editCertification(index, "expiry_date", e.target.value)}
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
              onClick={() => setCertifications((rows) => [...rows, blankCertificationRow()])}
              disabled={certifications.length >= MAX_CERTIFICATION_ROWS}
            >
              + Add another certification
            </Button>
            <span className="text-xs text-gray-400">
              {certifications.length} of {MAX_CERTIFICATION_ROWS}
            </span>
          </div>

          <SubHeading>Trainings &amp; professional development</SubHeading>
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
                        onChange={(e) => editTraining(index, "training_provider", e.target.value)}
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

        {/* ------ 6. statement of purpose & workflow acknowledgement --------- */}
        <ComponentCard title="" desc="">
          <SectionBar
            number={6}
            title="Statement of Purpose & Workflow Acknowledgement"
            note="A final check before your application goes to HR and your manager is alerted."
          />

          <div>
            <Label htmlFor="application_rationale_sop">
              Why are you applying for this position? <Required />
            </Label>
            <TextArea
              id="application_rationale_sop"
              rows={6}
              placeholder="Provide detailed reasoning and business alignment rationale..."
              value={form.application_rationale_sop}
              onChange={(value) =>
                set("application_rationale_sop", value.slice(0, limits.sop_max))
              }
              error={!!errors.application_rationale_sop}
              hint={errors.application_rationale_sop}
            />
            <Counter value={form.application_rationale_sop.length} limit={limits.sop_max} />
          </div>

          <div className="mt-4 space-y-3 rounded-lg border border-gray-200 p-4 dark:border-gray-800">
            <div>
              <Checkbox
                id="ack_manager_notified_bool"
                label={`${ackManagerText} *`}
                checked={form.ack_manager_notified_bool}
                onChange={(checked) => set("ack_manager_notified_bool", checked)}
              />
              {supervisorName && sameAsRecord("current_supervisor_name") ? (
                <FieldNote>{supervisorName} will be notified when you submit.</FieldNote>
              ) : form.current_supervisor_name.trim() ? (
                <FieldNote>
                  You changed your supervisor&apos;s name, so they are not notified
                  automatically - please let them know yourself.
                </FieldNote>
              ) : null}
              <ErrorText message={errors.ack_manager_notified_bool} />
            </div>
            <div>
              <Checkbox
                id="ack_data_accuracy_bool"
                label={`${ackAccuracyText} *`}
                checked={form.ack_data_accuracy_bool}
                onChange={(checked) => set("ack_data_accuracy_bool", checked)}
              />
              <ErrorText message={errors.ack_data_accuracy_bool} />
            </div>
          </div>

          <SubHeading>Declaration &amp; undertaking</SubHeading>
          <div className="space-y-3 text-sm leading-relaxed text-gray-700 dark:text-gray-300">
            {declaration.length > 0 ? (
              declaration.map((paragraph, index) => <p key={index}>{paragraph}</p>)
            ) : (
              <p className="text-xs text-gray-400">
                The declaration could not be loaded from the server. Reload the page before
                submitting.
              </p>
            )}
          </div>
          <div className="mt-4 rounded-lg border border-gray-200 p-4 dark:border-gray-800">
            <Checkbox
              id="declaration_accepted"
              label="I have read, understood and accept the declaration and undertaking above *"
              checked={form.declaration_accepted}
              onChange={(checked) => set("declaration_accepted", checked)}
            />
            <ErrorText message={errors.declaration_accepted} />
          </div>

          <SubHeading>Submission record</SubHeading>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <Label>Applicant Name</Label>
              <Input value={form.full_name} disabled />
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
            </div>
            <div>
              <Label htmlFor="applicant_signature">
                Applicant&apos;s Electronic Signature / Confirmation <Required />
              </Label>
              <Input
                id="applicant_signature"
                placeholder="Type your full name as shown in section 1"
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
          <ComponentCard title="My Applications" desc="Everything you have submitted, newest first.">
            <div className="max-w-full overflow-x-auto custom-scrollbar">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-xs uppercase text-gray-500 dark:border-gray-800 dark:text-gray-400">
                    <th className="py-2 pr-4 font-medium">Reference No.</th>
                    <th className="py-2 pr-4 font-medium">Position</th>
                    <th className="py-2 pr-4 font-medium">Submitted On</th>
                    <th className="py-2 pr-4 font-medium">Sections</th>
                    <th className="py-2 pr-4 font-medium">Status</th>
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
                        {(() => {
                          const shown = APPLICATION_STATUS[row.status] ?? {
                            label: row.hr_verification_status,
                            color: "light" as const,
                          };
                          return (
                            <span data-application-status={row.status}>
                              <Badge size="sm" color={shown.color}>
                                {shown.label}
                              </Badge>
                            </span>
                          );
                        })()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </ComponentCard>
        )}
      </div>

      <Modal
        isOpen={instructionsOpen}
        onClose={() => setInstructionsOpen(false)}
        className="m-4 max-w-2xl"
      >
        <div className="max-h-[85vh] overflow-y-auto p-6 sm:p-8" data-instructions-modal>
          <h3 className="pr-12 text-lg font-semibold text-gray-800 dark:text-white/90">
            How to apply
          </h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            General instructions for applying against an internally advertised position.
          </p>

          {instructionsError ? (
            <p className="mt-6 text-sm text-error-500">
              The instructions could not be loaded. Check your connection and try again.
            </p>
          ) : !instructions ? (
            <p className="mt-6 text-sm text-gray-400">Loading instructions...</p>
          ) : (
            <div className="mt-5 space-y-5">
              {instructions.map((section, sectionIndex) => (
                <div key={section.heading}>
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-brand-500">
                    {sectionIndex + 1}. {section.heading}
                  </h4>
                  <ul className="mt-2 space-y-2">
                    {section.points.map((point) => (
                      <li
                        key={point}
                        className="flex gap-2.5 text-sm leading-relaxed text-gray-700 dark:text-gray-300"
                      >
                        <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-400" />
                        <span>{point}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}

          <div className="mt-6 flex justify-end">
            <Button size="sm" variant="primary" onClick={() => setInstructionsOpen(false)}>
              Got it
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
