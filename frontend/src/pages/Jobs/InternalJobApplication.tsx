import { useEffect, useMemo, useRef, useState } from "react";
import { ToastContainer, toast } from "react-toastify";
import PageMeta from "../../components/common/PageMeta";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import Label from "../../components/form/Label";
import Input from "../../components/form/input/InputField";
import Select from "../../components/form/Select";
import Radio from "../../components/form/input/Radio";
import Checkbox from "../../components/form/input/Checkbox";
import TextArea from "../../components/form/input/TextArea";
import SearchableDropdown from "../../components/form/input/SearchableDropDown";
import Button from "../../components/ui/button/Button";
import Badge from "../../components/ui/badge/Badge";
import axios from "../../api/axios";
import moment from "moment";

/**
 * Kept in step with jobs/validators.py, which enforces the same rules. These
 * checks exist for immediate feedback while typing; the server decides.
 */
const MAX_EDUCATION_ROWS = 15;
const MAX_EXPERIENCE_ROWS = 20;
const EARLIEST_GRADUATION_YEAR = 1950;
const GRADUATION_YEARS_AHEAD = 7;

const MAX_RESPONSIBILITIES = 1500;
const MAX_ACHIEVEMENTS = 2000;
const MAX_CERTIFICATIONS = 1500;
const MAX_SOP = 3000;
const MIN_SOP = 30;
const MAX_TECHNICAL_SKILLS = 30;
const MAX_SKILL_LENGTH = 80;

/** Kept identical to SOFT_SKILL_OPTIONS in jobs/validators.py, which only
 *  accepts these; a typo would otherwise become a category nothing matches. */
const SOFT_SKILL_OPTIONS = [
  "Leadership",
  "Team Management",
  "Communication",
  "Stakeholder Management",
  "Problem Solving",
  "Analytical Thinking",
  "Decision Making",
  "Negotiation",
  "Conflict Resolution",
  "Mentoring & Coaching",
  "Time Management",
  "Adaptability",
  "Presentation Skills",
  "Report Writing",
  "Cross-functional Collaboration",
];

/** Used to seed the first experience row with the applicant's current post. */
const ORGANISATION_NAME = "Independent System & Market Operator (ISMO)";

const CONTACT_METHODS = ["Teams", "Email", "SMS"] as const;
type ContactMethod = (typeof CONTACT_METHODS)[number];

/** Common qualifications, plus an escape hatch for anything not listed. */
const DEGREE_OPTIONS = [
  "Matriculation",
  "Intermediate / A-Level",
  "Diploma",
  "Bachelor of Science",
  "Bachelor of Engineering",
  "Bachelor of Arts",
  "Bachelor of Commerce",
  "Bachelor of Business Administration",
  "Master of Science",
  "Master of Engineering",
  "Master of Arts",
  "MBA",
  "MPhil",
  "PhD",
  "CA / ACCA / CMA",
  "PMP",
  "Other certification",
];
const DEGREE_OTHER = "__other__";

type Requisition = {
  id: number;
  title: string;
  department: string | null;
  location: string | null;
  closing_date: string | null;
};

type EducationRow = {
  edu_degree_title: string;
  /** Set when the degree dropdown is on "Other", holding the typed value. */
  degree_is_custom: boolean;
  edu_institution_name: string;
  edu_major_specialization: string;
  edu_graduation_year: string;
  edu_grade_score: string;
};

type ExperienceRow = {
  exp_job_title: string;
  exp_company_name: string;
  exp_start_date: string;
  exp_end_date: string;
  exp_is_current: boolean;
  exp_key_responsibilities: string;
  exp_key_achievements: string;
};

type FormState = {
  target_job_req_id: string;
  emp_full_name: string;
  emp_id: string;
  current_dept_code: string;
  current_job_title: string;
  current_supervisor_id: string;
  current_supervisor_erp_id: number | null;
  cnic: string;
  contact_phone_no: string;
  corporate_email: string;
  personal_email: string;
  preferred_contact_method: ContactMethod | "";
  certifications_list: string;
  application_rationale_sop: string;
  ack_manager_notified_bool: boolean;
  ack_data_accuracy_bool: boolean;
};

type SubmittedApplication = {
  id: number;
  vacancy: string;
  status: string;
  created_at: string;
  education_count: number;
  experience_count?: number;
  skill_count?: number;
};

const blankEducationRow = (): EducationRow => ({
  edu_degree_title: "",
  degree_is_custom: false,
  edu_institution_name: "",
  edu_major_specialization: "",
  edu_graduation_year: "",
  edu_grade_score: "",
});

const blankExperienceRow = (): ExperienceRow => ({
  exp_job_title: "",
  exp_company_name: "",
  exp_start_date: "",
  exp_end_date: "",
  exp_is_current: false,
  exp_key_responsibilities: "",
  exp_key_achievements: "",
});

const blankForm = (): FormState => ({
  target_job_req_id: "",
  emp_full_name: "",
  emp_id: "",
  current_dept_code: "",
  current_job_title: "",
  current_supervisor_id: "",
  current_supervisor_erp_id: null,
  cnic: "",
  contact_phone_no: "",
  corporate_email: "",
  personal_email: "",
  preferred_contact_method: "",
  certifications_list: "",
  application_rationale_sop: "",
  ack_manager_notified_bool: false,
  ack_data_accuracy_bool: false,
});

const EMAIL = /^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$/;
const digitsOf = (value: string) => value.replace(/\D/g, "");

/** 13 digits shown as 12345-1234567-1, formatted while the person types. */
function formatCnic(value: string): string {
  const digits = digitsOf(value).slice(0, 13);
  if (digits.length <= 5) return digits;
  if (digits.length <= 12) return `${digits.slice(0, 5)}-${digits.slice(5)}`;
  return `${digits.slice(0, 5)}-${digits.slice(5, 12)}-${digits.slice(12)}`;
}

/** How much of a character limit is used, and a warning as it runs out. */
function Counter({ used, limit }: { used: number; limit: number }) {
  const nearlyFull = used > limit * 0.9;
  return (
    <p
      className={`mt-1 text-right text-xs ${
        nearlyFull ? "text-warning-500" : "text-gray-400 dark:text-gray-500"
      }`}
    >
      {used} / {limit}
    </p>
  );
}

export default function InternalJobApplication() {
  const user = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem("user") || "{}");
    } catch {
      return {};
    }
  }, []);

  const [form, setForm] = useState<FormState>(blankForm);
  const [education, setEducation] = useState<EducationRow[]>([blankEducationRow()]);
  const [experience, setExperience] = useState<ExperienceRow[]>([blankExperienceRow()]);
  const [technicalSkills, setTechnicalSkills] = useState<string[]>([]);
  const [skillDraft, setSkillDraft] = useState("");
  const [softSkills, setSoftSkills] = useState<string[]>([]);
  const [requisitions, setRequisitions] = useState<Requisition[]>([]);
  const [applications, setApplications] = useState<SubmittedApplication[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [rowErrors, setRowErrors] = useState<Record<number, Record<string, string>>>({});
  const [expErrors, setExpErrors] = useState<Record<number, Record<string, string>>>({});
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [profileNote, setProfileNote] = useState<string | null>(null);

  // Which fields arrived pre-filled, so the form can say so without claiming
  // it for something the employee typed themselves.
  const prefilled = useRef<Set<keyof FormState>>(new Set());
  // Whether the first experience row came from the employee record.
  const prefilledExperience = useRef(false);

  const years = useMemo(() => {
    const latest = new Date().getFullYear() + GRADUATION_YEARS_AHEAD;
    const list: string[] = [];
    for (let year = latest; year >= EARLIEST_GRADUATION_YEAR; year -= 1) {
      list.push(String(year));
    }
    return list;
  }, []);

  // ---- loading ---------------------------------------------------------
  useEffect(() => {
    loadRequisitions();
    loadProfile();
    loadApplications();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadRequisitions = async () => {
    try {
      const response = await axios.get("/jobs/requisitions/");
      setRequisitions(Array.isArray(response.data) ? response.data : []);
    } catch {
      setRequisitions([]);
      toast.error("Could not load the list of vacancies");
    }
  };

  const loadProfile = async () => {
    if (!user?.erpid) {
      setLoadingProfile(false);
      setProfileNote("Sign in again — your employee id is missing from this session.");
      return;
    }

    try {
      const response = await axios.get("/jobs/application-profile/", {
        params: { erp_id: user.erpid },
      });
      const profile = response.data ?? {};

      // Only fields the employee record actually holds are filled; the rest
      // stay empty rather than being invented.
      const filled = new Set<keyof FormState>();
      const take = (key: keyof FormState, value: unknown): string => {
        const text = value === null || value === undefined ? "" : String(value);
        if (text) filled.add(key);
        return text;
      };

      setForm((previous) => ({
        ...previous,
        emp_full_name: take("emp_full_name", profile.emp_full_name),
        emp_id: take("emp_id", profile.emp_id),
        current_dept_code: take("current_dept_code", profile.current_dept_code),
        current_job_title: take("current_job_title", profile.current_job_title),
        current_supervisor_id: take("current_supervisor_id", profile.current_supervisor_id),
        current_supervisor_erp_id: profile.current_supervisor_erp_id ?? null,
        cnic: formatCnic(take("cnic", profile.cnic)),
        corporate_email: take("corporate_email", profile.corporate_email),
        contact_phone_no: take("contact_phone_no", profile.contact_phone_no),
      }));

      prefilled.current = filled;

      // The applicant's current post is the one thing the employee record can
      // contribute to work history, so the first row starts filled in and
      // marked as still current. Start date is not held anywhere, so it stays
      // empty; everything here can be edited or the row removed outright.
      const currentTitle = String(profile.current_job_title ?? "");
      if (currentTitle) {
        setExperience((previous) => {
          const [first, ...rest] = previous;
          const untouched =
            !first ||
            (!first.exp_job_title &&
              !first.exp_company_name &&
              !first.exp_key_responsibilities);
          if (!untouched) return previous;
          return [
            {
              ...blankExperienceRow(),
              exp_job_title: currentTitle,
              exp_company_name: ORGANISATION_NAME,
              exp_is_current: true,
            },
            ...rest,
          ];
        });
        prefilledExperience.current = true;
      }

      setProfileNote(null);
    } catch (error: any) {
      setProfileNote(
        error?.response?.status === 404
          ? "No active employee record was found for your ERP id, so nothing could be pre-filled."
          : "Your employee record could not be loaded, so please fill the form in by hand."
      );
    } finally {
      setLoadingProfile(false);
    }
  };

  const loadApplications = async () => {
    if (!user?.erpid) return;
    try {
      const response = await axios.get("/jobs/applications/", {
        params: { erp_id: user.erpid },
      });
      setApplications(Array.isArray(response.data) ? response.data : []);
    } catch {
      setApplications([]);
    }
  };

  // ---- editing ---------------------------------------------------------
  const set = (field: keyof FormState, value: string) => {
    setForm((previous) => ({ ...previous, [field]: value }));
    setErrors((previous) => {
      if (!previous[field]) return previous;
      const next = { ...previous };
      delete next[field];
      return next;
    });
  };

  const setRow = (index: number, field: keyof EducationRow, value: string | boolean) => {
    setEducation((previous) =>
      previous.map((row, position) =>
        position === index ? { ...row, [field]: value } : row
      )
    );
    setRowErrors((previous) => {
      const forRow = previous[index];
      if (!forRow || !forRow[field as string]) return previous;
      const next = { ...previous, [index]: { ...forRow } };
      delete next[index][field as string];
      return next;
    });
  };

  const addRow = () => {
    if (education.length >= MAX_EDUCATION_ROWS) {
      toast.info(`Up to ${MAX_EDUCATION_ROWS} qualifications can be listed`);
      return;
    }
    setEducation((previous) => [...previous, blankEducationRow()]);
  };

  const removeRow = (index: number) => {
    // One row always remains: the section is required, and an empty grid gives
    // nothing to type into.
    if (education.length === 1) {
      setEducation([blankEducationRow()]);
      setRowErrors({});
      return;
    }
    setEducation((previous) => previous.filter((_, position) => position !== index));
    setRowErrors({});
  };

  const setExpRow = (index: number, field: keyof ExperienceRow, value: string | boolean) => {
    setExperience((previous) =>
      previous.map((row, position) =>
        position === index ? { ...row, [field]: value } : row
      )
    );
    setExpErrors((previous) => {
      const forRow = previous[index];
      if (!forRow || !forRow[field as string]) return previous;
      const next = { ...previous, [index]: { ...forRow } };
      delete next[index][field as string];
      return next;
    });
  };

  const addExpRow = () => {
    if (experience.length >= MAX_EXPERIENCE_ROWS) {
      toast.info(`Up to ${MAX_EXPERIENCE_ROWS} positions can be listed`);
      return;
    }
    setExperience((previous) => [...previous, blankExperienceRow()]);
  };

  const removeExpRow = (index: number) => {
    if (experience.length === 1) {
      setExperience([blankExperienceRow()]);
      setExpErrors({});
      prefilledExperience.current = false;
      return;
    }
    setExperience((previous) => previous.filter((_, position) => position !== index));
    setExpErrors({});
    if (index === 0) prefilledExperience.current = false;
  };

  /** Adds whatever is in the tag box, if it is new. */
  const commitSkill = () => {
    const tag = skillDraft.trim();
    if (!tag) return;

    if (tag.length > MAX_SKILL_LENGTH) {
      toast.error(`Keep each skill within ${MAX_SKILL_LENGTH} characters`);
      return;
    }
    if (technicalSkills.length >= MAX_TECHNICAL_SKILLS) {
      toast.info(`Up to ${MAX_TECHNICAL_SKILLS} skills can be listed`);
      return;
    }
    // Case-insensitive, so "python" does not join "Python" in the list.
    if (technicalSkills.some((skill) => skill.toLowerCase() === tag.toLowerCase())) {
      setSkillDraft("");
      return;
    }

    setTechnicalSkills((previous) => [...previous, tag]);
    setSkillDraft("");
    setErrors((previous) => {
      if (!previous.skills_technical_tags) return previous;
      const next = { ...previous };
      delete next.skills_technical_tags;
      return next;
    });
  };

  const toggleSoftSkill = (skill: string) => {
    setSoftSkills((previous) =>
      previous.includes(skill)
        ? previous.filter((item) => item !== skill)
        : [...previous, skill]
    );
  };

  // ---- validation ------------------------------------------------------
  const validate = (): boolean => {
    const problems: Record<string, string> = {};

    if (!form.target_job_req_id) {
      problems.target_job_req_id = "Select the vacancy you are applying for";
    }
    if (!form.emp_full_name.trim()) {
      problems.emp_full_name = "Employee full name is required";
    } else if (form.emp_full_name.trim().length < 3) {
      problems.emp_full_name = "Employee full name looks too short";
    }
    if (!form.emp_id.trim()) {
      problems.emp_id = "Employee ID is required";
    } else if (!/^\d+$/.test(form.emp_id.trim())) {
      problems.emp_id = "Employee ID must be a number";
    }
    if (!form.current_dept_code.trim()) problems.current_dept_code = "Current department is required";
    if (!form.current_job_title.trim()) problems.current_job_title = "Current position title is required";
    if (!form.current_supervisor_id.trim()) {
      problems.current_supervisor_id = "Current supervisor name is required";
    }

    const cnicDigits = digitsOf(form.cnic);
    if (!cnicDigits) problems.cnic = "CNIC is required";
    else if (cnicDigits.length !== 13) problems.cnic = "CNIC must be 13 digits, like 12345-1234567-1";

    const phoneDigits = digitsOf(form.contact_phone_no);
    if (!form.contact_phone_no.trim()) {
      problems.contact_phone_no = "Contact phone number is required";
    } else if (phoneDigits.length < 10 || phoneDigits.length > 15) {
      problems.contact_phone_no = "Enter a phone number like +92-300-1234567";
    }

    if (!form.corporate_email.trim()) {
      problems.corporate_email = "Corporate email address is required";
    } else if (!EMAIL.test(form.corporate_email.trim())) {
      problems.corporate_email = "That does not look like an email address";
    }

    if (form.personal_email.trim()) {
      if (!EMAIL.test(form.personal_email.trim())) {
        problems.personal_email = "That does not look like an email address";
      } else if (
        form.personal_email.trim().toLowerCase() === form.corporate_email.trim().toLowerCase()
      ) {
        problems.personal_email = "Personal email should differ from the corporate one";
      }
    }

    if (!form.preferred_contact_method) {
      problems.preferred_contact_method = "Choose how you would like to be contacted";
    }

    const rows: Record<number, Record<string, string>> = {};
    education.forEach((row, index) => {
      const rowProblems: Record<string, string> = {};
      if (!row.edu_degree_title.trim()) rowProblems.edu_degree_title = "Degree / certificate is required";
      if (!row.edu_institution_name.trim()) rowProblems.edu_institution_name = "Institution is required";
      if (!row.edu_major_specialization.trim()) {
        rowProblems.edu_major_specialization = "Major / field of study is required";
      }
      if (!row.edu_graduation_year) rowProblems.edu_graduation_year = "Select the year of completion";
      if (!row.edu_grade_score.trim()) rowProblems.edu_grade_score = "CGPA / grade is required";
      if (Object.keys(rowProblems).length) rows[index] = rowProblems;
    });

    // --- section 4 ------------------------------------------------------
    const today = moment().format("YYYY-MM-DD");
    const expRows: Record<number, Record<string, string>> = {};

    if (experience.length === 0) {
      problems.experience = "Add at least one position, including your current role";
    }

    experience.forEach((row, index) => {
      const rowProblems: Record<string, string> = {};

      if (!row.exp_job_title.trim()) rowProblems.exp_job_title = "Job position title is required";
      if (!row.exp_company_name.trim()) {
        rowProblems.exp_company_name = "Organization / company name is required";
      }

      if (!row.exp_start_date) {
        rowProblems.exp_start_date = "Select the employment start date";
      } else if (row.exp_start_date > today) {
        rowProblems.exp_start_date = "Start date cannot be in the future";
      }

      if (!row.exp_is_current) {
        if (!row.exp_end_date) {
          rowProblems.exp_end_date = "Select the end date, or tick 'Currently in this role'";
        } else if (row.exp_end_date > today) {
          rowProblems.exp_end_date = "End date cannot be in the future";
        } else if (row.exp_start_date && row.exp_end_date < row.exp_start_date) {
          rowProblems.exp_end_date = "End date cannot be before the start date";
        }
      }

      if (!row.exp_key_responsibilities.trim()) {
        rowProblems.exp_key_responsibilities = "Key responsibilities are required";
      } else if (row.exp_key_responsibilities.length > MAX_RESPONSIBILITIES) {
        rowProblems.exp_key_responsibilities = `Keep this within ${MAX_RESPONSIBILITIES} characters`;
      }

      if (row.exp_key_achievements.length > MAX_ACHIEVEMENTS) {
        rowProblems.exp_key_achievements = `Keep this within ${MAX_ACHIEVEMENTS} characters`;
      }

      if (Object.keys(rowProblems).length) expRows[index] = rowProblems;
    });

    // --- section 5 ------------------------------------------------------
    if (technicalSkills.length === 0) {
      problems.skills_technical_tags = "Add at least one technical skill";
    }
    if (form.certifications_list.length > MAX_CERTIFICATIONS) {
      problems.certifications_list = `Keep this within ${MAX_CERTIFICATIONS} characters`;
    }

    // --- section 6 ------------------------------------------------------
    const statement = form.application_rationale_sop.trim();
    if (!statement) {
      problems.application_rationale_sop = "Tell us why you are applying";
    } else if (statement.length < MIN_SOP) {
      problems.application_rationale_sop = `Please give a little more detail — at least ${MIN_SOP} characters`;
    } else if (statement.length > MAX_SOP) {
      problems.application_rationale_sop = `Keep this within ${MAX_SOP} characters`;
    }
    if (!form.ack_manager_notified_bool) {
      problems.ack_manager_notified_bool = "Confirm your current manager is aware of this request";
    }
    if (!form.ack_data_accuracy_bool) {
      problems.ack_data_accuracy_bool = "Confirm the details match the corporate record";
    }

    setErrors(problems);
    setRowErrors(rows);
    setExpErrors(expRows);

    const total =
      Object.keys(problems).length + Object.keys(rows).length + Object.keys(expRows).length;
    if (total > 0) {
      toast.error("Please correct the highlighted fields");
    }
    return total === 0;
  };

  // ---- submitting ------------------------------------------------------
  const submit = async () => {
    if (!validate()) return;

    setSubmitting(true);
    try {
      const response = await axios.post("/jobs/applications/create/", {
        applicant_erp_id: user.erpid,
        target_job_req_id: Number(form.target_job_req_id),
        emp_full_name: form.emp_full_name.trim(),
        emp_id: Number(form.emp_id),
        current_dept_code: form.current_dept_code.trim(),
        current_job_title: form.current_job_title.trim(),
        current_supervisor_id: form.current_supervisor_id.trim(),
        current_supervisor_erp_id: form.current_supervisor_erp_id,
        cnic: form.cnic,
        contact_phone_no: form.contact_phone_no.trim(),
        corporate_email: form.corporate_email.trim(),
        personal_email: form.personal_email.trim() || null,
        preferred_contact_method: form.preferred_contact_method,
        certifications_list: form.certifications_list.trim() || null,
        application_rationale_sop: form.application_rationale_sop.trim(),
        ack_manager_notified_bool: form.ack_manager_notified_bool,
        ack_data_accuracy_bool: form.ack_data_accuracy_bool,
        skills_technical_tags: technicalSkills,
        skills_soft_checkboxes: softSkills,
        experience: experience.map((row, index) => ({
          exp_job_title: row.exp_job_title.trim(),
          exp_company_name: row.exp_company_name.trim(),
          exp_start_date: row.exp_start_date,
          // The toggle wins: an end date left behind by unticking and
          // reticking it would contradict "currently in this role".
          exp_end_date: row.exp_is_current ? null : row.exp_end_date,
          exp_is_current: row.exp_is_current,
          exp_key_responsibilities: row.exp_key_responsibilities.trim(),
          exp_key_achievements: row.exp_key_achievements.trim() || null,
          row_order: index,
        })),
        education: education.map((row, index) => ({
          edu_degree_title: row.edu_degree_title.trim(),
          edu_institution_name: row.edu_institution_name.trim(),
          edu_major_specialization: row.edu_major_specialization.trim(),
          edu_graduation_year: Number(row.edu_graduation_year),
          edu_grade_score: row.edu_grade_score.trim(),
          row_order: index,
        })),
      });

      toast.success(response.data?.message ?? "Your application has been submitted");
      // The identity and employment fields are pre-filled again by the reload;
      // only what the applicant typed for this vacancy is cleared.
      setForm((previous) => ({
        ...previous,
        target_job_req_id: "",
        personal_email: "",
        preferred_contact_method: "",
      }));
      setEducation([blankEducationRow()]);
      setExperience([blankExperienceRow()]);
      setTechnicalSkills([]);
      setSoftSkills([]);
      setSkillDraft("");
      setForm((previous) => ({
        ...previous,
        certifications_list: "",
        application_rationale_sop: "",
        ack_manager_notified_bool: false,
        ack_data_accuracy_bool: false,
      }));
      setErrors({});
      setRowErrors({});
      setExpErrors({});
      loadApplications();
    } catch (error: any) {
      const returned = error?.response?.data?.errors;
      if (returned) {
        // The server keys its complaints the same way, so they land next to the
        // same inputs the browser would have flagged.
        const {
          education_rows: returnedRows,
          experience_rows: returnedExpRows,
          ...fields
        } = returned;
        setErrors(fields as Record<string, string>);

        const byIndex = (rows: unknown) => {
          const mapped: Record<number, Record<string, string>> = {};
          Object.entries((rows ?? {}) as Record<string, Record<string, string>>).forEach(
            ([index, problems]) => {
              mapped[Number(index)] = problems;
            }
          );
          return mapped;
        };
        if (returnedRows) setRowErrors(byIndex(returnedRows));
        if (returnedExpRows) setExpErrors(byIndex(returnedExpRows));
        toast.error(
          typeof fields.target_job_req_id === "string" && error?.response?.status === 409
            ? fields.target_job_req_id
            : "Please correct the highlighted fields"
        );
      } else if (!error?.response) {
        toast.error("Could not reach the server. Please try again.");
      } else {
        toast.error("Your application could not be submitted");
      }
    } finally {
      setSubmitting(false);
    }
  };

  // ---- rendering -------------------------------------------------------
  const autoFilled = (field: keyof FormState) =>
    prefilled.current.has(field) ? (
      <span className="ml-2 text-[10px] font-normal uppercase tracking-wide text-gray-400 dark:text-gray-500">
        auto-filled
      </span>
    ) : null;

  const requisitionOptions = requisitions.map((item) => ({
    label: [item.title, item.department, item.location].filter(Boolean).join(" · "),
    value: String(item.id),
  }));

  return (
    <>
      <PageMeta
        title="ISMO - Internal Job Application"
        description="Apply for an advertised internal vacancy"
      />
      <PageBreadcrumb pageTitle="Internal Job Application" />
      <ToastContainer position="bottom-right" />

      <div className="space-y-6">
        {profileNote && (
          <div className="rounded-2xl border border-warning-200 bg-warning-50 px-5 py-3 text-sm text-warning-700 dark:border-warning-500/30 dark:bg-warning-500/15 dark:text-orange-400">
            {profileNote}
          </div>
        )}

        {/* ---------------- Section 1 ---------------- */}
        <ComponentCard
          title="1. Target Position & Internal Validation"
          desc="Your details are filled in from your employee record. Correct anything that is out of date before submitting."
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="md:col-span-2">
              <Label htmlFor="requisition-dropdown">
                Job Requisition / Opening <span className="text-error-500">*</span>
              </Label>
              {requisitions.length === 0 ? (
                <p className="rounded-lg border border-dashed border-gray-300 px-4 py-3 text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
                  No vacancies are advertised at the moment. HR can add one from the admin panel.
                </p>
              ) : (
                <SearchableDropdown
                  options={requisitionOptions}
                  placeholder="Select advertised vacancy..."
                  id="requisition-dropdown"
                  value={form.target_job_req_id}
                  onChange={(value) => set("target_job_req_id", value ? String(value) : "")}
                  error={!!errors.target_job_req_id}
                  hint={errors.target_job_req_id}
                />
              )}
            </div>

            <div>
              <Label htmlFor="emp_full_name">
                Employee Full Name <span className="text-error-500">*</span>
                {autoFilled("emp_full_name")}
              </Label>
              <Input
                id="emp_full_name"
                placeholder="Auto-filled from your employee record"
                value={form.emp_full_name}
                onChange={(e) => set("emp_full_name", e.target.value)}
                error={!!errors.emp_full_name}
                hint={errors.emp_full_name}
              />
            </div>

            <div>
              <Label htmlFor="emp_id">
                Employee ID <span className="text-error-500">*</span>
                {autoFilled("emp_id")}
              </Label>
              <Input
                id="emp_id"
                placeholder="Auto-filled numeric ID"
                value={form.emp_id}
                onChange={(e) => set("emp_id", e.target.value.replace(/\D/g, ""))}
                error={!!errors.emp_id}
                hint={errors.emp_id}
              />
            </div>

            <div>
              <Label htmlFor="current_dept_code">
                Current Department <span className="text-error-500">*</span>
                {autoFilled("current_dept_code")}
              </Label>
              <Input
                id="current_dept_code"
                placeholder="Auto-filled current business unit"
                value={form.current_dept_code}
                onChange={(e) => set("current_dept_code", e.target.value)}
                error={!!errors.current_dept_code}
                hint={errors.current_dept_code}
              />
            </div>

            <div>
              <Label htmlFor="current_job_title">
                Current Position Title <span className="text-error-500">*</span>
                {autoFilled("current_job_title")}
              </Label>
              <Input
                id="current_job_title"
                placeholder="Auto-filled current designation"
                value={form.current_job_title}
                onChange={(e) => set("current_job_title", e.target.value)}
                error={!!errors.current_job_title}
                hint={errors.current_job_title}
              />
            </div>

            <div className="md:col-span-2">
              <Label htmlFor="current_supervisor_id">
                Current Supervisor Name <span className="text-error-500">*</span>
                {autoFilled("current_supervisor_id")}
              </Label>
              <Input
                id="current_supervisor_id"
                placeholder="Auto-filled reporting manager"
                value={form.current_supervisor_id}
                onChange={(e) => {
                  set("current_supervisor_id", e.target.value);
                  // Typing a different name detaches the stored ERP id: it no
                  // longer refers to whoever is named here.
                  setForm((previous) => ({ ...previous, current_supervisor_erp_id: null }));
                }}
                error={!!errors.current_supervisor_id}
                hint={errors.current_supervisor_id}
              />
            </div>
          </div>
        </ComponentCard>

        {/* ---------------- Section 2 ---------------- */}
        <ComponentCard
          title="2. Personal & Contact Information"
          desc="How HR should reach you about this application, including outside internal channels."
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="cnic">
                CNIC <span className="text-error-500">*</span>
                {autoFilled("cnic")}
              </Label>
              <Input
                id="cnic"
                placeholder="12345-1234567-1"
                value={form.cnic}
                onChange={(e) => set("cnic", formatCnic(e.target.value))}
                error={!!errors.cnic}
                hint={errors.cnic}
              />
            </div>

            <div>
              <Label htmlFor="contact_phone_no">
                Contact Phone Number <span className="text-error-500">*</span>
                {autoFilled("contact_phone_no")}
              </Label>
              <Input
                id="contact_phone_no"
                type="tel"
                placeholder="+92-3XX-XXXXXXX or equivalent"
                value={form.contact_phone_no}
                onChange={(e) => set("contact_phone_no", e.target.value)}
                error={!!errors.contact_phone_no}
                hint={errors.contact_phone_no}
              />
            </div>

            <div>
              <Label htmlFor="corporate_email">
                Corporate Email Address <span className="text-error-500">*</span>
                {autoFilled("corporate_email")}
              </Label>
              <Input
                id="corporate_email"
                type="email"
                placeholder="username@company.com"
                value={form.corporate_email}
                onChange={(e) => set("corporate_email", e.target.value)}
                error={!!errors.corporate_email}
                hint={errors.corporate_email}
              />
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

            <div className="md:col-span-2">
              <Label>
                Internal Communication Channel <span className="text-error-500">*</span>
              </Label>
              <div className="mt-2 flex flex-wrap items-center gap-6">
                {CONTACT_METHODS.map((method) => (
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
              {errors.preferred_contact_method && (
                <p className="mt-1.5 text-xs text-error-500">
                  {errors.preferred_contact_method}
                </p>
              )}
            </div>
          </div>
        </ComponentCard>

        {/* ---------------- Section 3 ---------------- */}
        <ComponentCard
          title="3. Educational Background"
          desc="List every degree or certificate, oldest first. Add a row for each one."
        >
          {errors.education && (
            <p className="mb-3 text-sm text-error-500">{errors.education}</p>
          )}

          <div className="space-y-4">
            {education.map((row, index) => {
              const rowProblems = rowErrors[index] ?? {};
              const usingCustomDegree =
                row.degree_is_custom ||
                (!!row.edu_degree_title && !DEGREE_OPTIONS.includes(row.edu_degree_title));

              return (
                <div
                  key={index}
                  className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800"
                >
                  <div className="mb-3 flex items-center justify-between">
                    <Badge color="light" size="sm">
                      Qualification {index + 1}
                    </Badge>
                    <button
                      type="button"
                      onClick={() => removeRow(index)}
                      className="text-xs font-medium text-error-500 hover:text-error-600"
                    >
                      Remove
                    </button>
                  </div>

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                    <div>
                      <Label>
                        Degree / Certificate Earned <span className="text-error-500">*</span>
                      </Label>
                      <Select
                        options={[
                          ...DEGREE_OPTIONS.map((degree) => ({ label: degree, value: degree })),
                          { label: "Other (type it in)", value: DEGREE_OTHER },
                        ]}
                        placeholder="e.g., Bachelor of Science, MBA, PMP"
                        value={usingCustomDegree ? DEGREE_OTHER : row.edu_degree_title}
                        onChange={(value) => {
                          if (value === DEGREE_OTHER) {
                            setRow(index, "degree_is_custom", true);
                            setRow(index, "edu_degree_title", "");
                          } else {
                            setRow(index, "degree_is_custom", false);
                            setRow(index, "edu_degree_title", value);
                          }
                        }}
                        error={!!rowProblems.edu_degree_title}
                        hint={usingCustomDegree ? undefined : rowProblems.edu_degree_title}
                      />
                      {usingCustomDegree && (
                        <div className="mt-2">
                          <Input
                            placeholder="Type the degree or certificate"
                            value={row.edu_degree_title}
                            onChange={(e) => setRow(index, "edu_degree_title", e.target.value)}
                            error={!!rowProblems.edu_degree_title}
                            hint={rowProblems.edu_degree_title}
                          />
                        </div>
                      )}
                    </div>

                    <div>
                      <Label>
                        Institution / University Name <span className="text-error-500">*</span>
                      </Label>
                      <Input
                        placeholder="Enter name of school/university"
                        value={row.edu_institution_name}
                        onChange={(e) => setRow(index, "edu_institution_name", e.target.value)}
                        error={!!rowProblems.edu_institution_name}
                        hint={rowProblems.edu_institution_name}
                      />
                    </div>

                    <div>
                      <Label>
                        Major / Field of Study <span className="text-error-500">*</span>
                      </Label>
                      <Input
                        placeholder="e.g., Computer Science, Finance, HR Management"
                        value={row.edu_major_specialization}
                        onChange={(e) => setRow(index, "edu_major_specialization", e.target.value)}
                        error={!!rowProblems.edu_major_specialization}
                        hint={rowProblems.edu_major_specialization}
                      />
                    </div>

                    <div>
                      <Label>
                        Graduation Year <span className="text-error-500">*</span>
                      </Label>
                      <Select
                        options={years.map((year) => ({ label: year, value: year }))}
                        placeholder="Select Year of Completion"
                        value={row.edu_graduation_year}
                        onChange={(value) => setRow(index, "edu_graduation_year", value)}
                        error={!!rowProblems.edu_graduation_year}
                        hint={rowProblems.edu_graduation_year}
                      />
                    </div>

                    <div>
                      <Label>
                        CGPA / Percentage / Grade <span className="text-error-500">*</span>
                      </Label>
                      <Input
                        placeholder="e.g., 3.8 / 4.0 or Grade A"
                        value={row.edu_grade_score}
                        onChange={(e) => setRow(index, "edu_grade_score", e.target.value)}
                        error={!!rowProblems.edu_grade_score}
                        hint={rowProblems.edu_grade_score}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-4 flex items-center justify-between">
            <Button size="sm" variant="outline" onClick={addRow}>
              + Add another qualification
            </Button>
            <span className="text-xs text-gray-400 dark:text-gray-500">
              {education.length} of {MAX_EDUCATION_ROWS}
            </span>
          </div>
        </ComponentCard>

        {/* ---------------- Section 4 ---------------- */}
        <ComponentCard
          title="4. Professional Experience"
          desc="Every post you have held — outside the organisation and internal promotions alike. Your current role starts filled in."
        >
          {errors.experience && (
            <p className="mb-3 text-sm text-error-500">{errors.experience}</p>
          )}

          <div className="space-y-4">
            {experience.map((row, index) => {
              const problems = expErrors[index] ?? {};
              return (
                <div
                  key={index}
                  className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800"
                >
                  <div className="mb-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge color="light" size="sm">
                        Position {index + 1}
                      </Badge>
                      {index === 0 && prefilledExperience.current && (
                        <span className="text-[10px] font-normal uppercase tracking-wide text-gray-400 dark:text-gray-500">
                          auto-filled — your current role
                        </span>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => removeExpRow(index)}
                      className="text-xs font-medium text-error-500 hover:text-error-600"
                    >
                      Remove
                    </button>
                  </div>

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div>
                      <Label>
                        Job Position Title <span className="text-error-500">*</span>
                      </Label>
                      <Input
                        placeholder="e.g., Senior Software Engineer, Assistant Manager"
                        value={row.exp_job_title}
                        onChange={(e) => setExpRow(index, "exp_job_title", e.target.value)}
                        error={!!problems.exp_job_title}
                        hint={problems.exp_job_title}
                      />
                    </div>

                    <div>
                      <Label>
                        Organization / Company Name <span className="text-error-500">*</span>
                      </Label>
                      <Input
                        placeholder="Enter employer name or internal subsidiary"
                        value={row.exp_company_name}
                        onChange={(e) => setExpRow(index, "exp_company_name", e.target.value)}
                        error={!!problems.exp_company_name}
                        hint={problems.exp_company_name}
                      />
                    </div>

                    <div>
                      <Label>
                        Employment Start Date <span className="text-error-500">*</span>
                      </Label>
                      <Input
                        type="date"
                        max={moment().format("YYYY-MM-DD")}
                        value={row.exp_start_date}
                        onChange={(e) => setExpRow(index, "exp_start_date", e.target.value)}
                        error={!!problems.exp_start_date}
                        hint={problems.exp_start_date}
                      />
                    </div>

                    <div>
                      <Label>
                        Employment End Date{" "}
                        {!row.exp_is_current && <span className="text-error-500">*</span>}
                      </Label>
                      <Input
                        type="date"
                        max={moment().format("YYYY-MM-DD")}
                        min={row.exp_start_date || undefined}
                        value={row.exp_is_current ? "" : row.exp_end_date}
                        disabled={row.exp_is_current}
                        onChange={(e) => setExpRow(index, "exp_end_date", e.target.value)}
                        error={!!problems.exp_end_date}
                        hint={problems.exp_end_date}
                      />
                      <div className="mt-2">
                        <Checkbox
                          id={`exp-current-${index}`}
                          label="Currently in this role"
                          checked={row.exp_is_current}
                          onChange={(checked) => {
                            setExpRow(index, "exp_is_current", checked);
                            // Clearing the date keeps the two from disagreeing.
                            if (checked) setExpRow(index, "exp_end_date", "");
                          }}
                        />
                      </div>
                    </div>

                    <div className="md:col-span-2">
                      <Label>
                        Key Responsibilities & Roles <span className="text-error-500">*</span>
                      </Label>
                      <TextArea
                        rows={3}
                        placeholder="Summarize core day-to-day functional mandates..."
                        value={row.exp_key_responsibilities}
                        onChange={(value) =>
                          setExpRow(
                            index,
                            "exp_key_responsibilities",
                            value.slice(0, MAX_RESPONSIBILITIES)
                          )
                        }
                        error={!!problems.exp_key_responsibilities}
                        hint={problems.exp_key_responsibilities}
                      />
                      <Counter
                        used={row.exp_key_responsibilities.length}
                        limit={MAX_RESPONSIBILITIES}
                      />
                    </div>

                    <div className="md:col-span-2">
                      <Label>Key Achievements & Projects (optional)</Label>
                      <TextArea
                        rows={3}
                        placeholder="List quantifiable achievements (e.g., 'Boosted efficiency by 20%')"
                        value={row.exp_key_achievements}
                        onChange={(value) =>
                          setExpRow(index, "exp_key_achievements", value.slice(0, MAX_ACHIEVEMENTS))
                        }
                        error={!!problems.exp_key_achievements}
                        hint={problems.exp_key_achievements}
                      />
                      <Counter
                        used={row.exp_key_achievements.length}
                        limit={MAX_ACHIEVEMENTS}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-4 flex items-center justify-between">
            <Button size="sm" variant="outline" onClick={addExpRow}>
              + Add another position
            </Button>
            <span className="text-xs text-gray-400 dark:text-gray-500">
              {experience.length} of {MAX_EXPERIENCE_ROWS}
            </span>
          </div>
        </ComponentCard>

        {/* ---------------- Section 5 ---------------- */}
        <ComponentCard
          title="5. Skills Matrix & Professional Certifications"
          desc="Keywords here are what reviewers filter on, so be specific."
        >
          <div className="space-y-5">
            <div>
              <Label htmlFor="skill-input">
                Core Technical Skills <span className="text-error-500">*</span>
              </Label>
              <div
                className={`rounded-lg border px-3 py-2.5 ${
                  errors.skills_technical_tags
                    ? "border-error-500"
                    : "border-gray-300 dark:border-gray-700"
                }`}
              >
                {technicalSkills.length > 0 && (
                  <div className="mb-2 flex flex-wrap gap-2">
                    {technicalSkills.map((skill) => (
                      <span
                        key={skill}
                        className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-600 dark:bg-brand-500/15 dark:text-brand-300"
                      >
                        {skill}
                        <button
                          type="button"
                          aria-label={`Remove ${skill}`}
                          onClick={() =>
                            setTechnicalSkills((previous) =>
                              previous.filter((item) => item !== skill)
                            )
                          }
                          className="text-brand-400 hover:text-error-500"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                )}
                <input
                  id="skill-input"
                  type="text"
                  value={skillDraft}
                  placeholder="Type and press Enter (e.g., Python, SAP, Agile)"
                  className="w-full bg-transparent text-sm text-gray-800 outline-none placeholder:text-gray-400 dark:text-white/90"
                  onChange={(e) => setSkillDraft(e.target.value)}
                  onKeyDown={(e) => {
                    // Enter or comma commits a tag; backspace on an empty box
                    // removes the last one, as tag inputs usually behave.
                    if (e.key === "Enter" || e.key === ",") {
                      e.preventDefault();
                      commitSkill();
                    } else if (e.key === "Backspace" && !skillDraft && technicalSkills.length) {
                      setTechnicalSkills((previous) => previous.slice(0, -1));
                    }
                  }}
                  onBlur={commitSkill}
                />
              </div>
              <div className="mt-1.5 flex items-center justify-between">
                <span className="text-xs text-error-500">
                  {errors.skills_technical_tags ?? ""}
                </span>
                <span className="text-xs text-gray-400 dark:text-gray-500">
                  {technicalSkills.length} of {MAX_TECHNICAL_SKILLS}
                </span>
              </div>
            </div>

            <div>
              <Label>Soft Skills / Leadership Capabilities</Label>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {SOFT_SKILL_OPTIONS.map((skill) => (
                  <Checkbox
                    key={skill}
                    id={`soft-${skill}`}
                    label={skill}
                    checked={softSkills.includes(skill)}
                    onChange={() => toggleSoftSkill(skill)}
                  />
                ))}
              </div>
            </div>

            <div>
              <Label htmlFor="certifications_list">Active Professional Certifications</Label>
              <TextArea
                rows={3}
                placeholder="List dynamic credentials (e.g., AWS Architect, ACCA, Six Sigma)"
                value={form.certifications_list}
                onChange={(value) =>
                  set("certifications_list", value.slice(0, MAX_CERTIFICATIONS))
                }
                error={!!errors.certifications_list}
                hint={errors.certifications_list}
              />
              <Counter used={form.certifications_list.length} limit={MAX_CERTIFICATIONS} />
            </div>
          </div>
        </ComponentCard>

        {/* ---------------- Section 6 ---------------- */}
        <ComponentCard
          title="6. Statement of Purpose & Acknowledgement"
          desc="The last step before your application reaches the HR queue."
        >
          <div className="space-y-5">
            <div>
              <Label htmlFor="application_rationale_sop">
                Why are you applying for this position?{" "}
                <span className="text-error-500">*</span>
              </Label>
              <TextArea
                rows={6}
                placeholder="Provide detailed reasoning and business alignment rationale..."
                value={form.application_rationale_sop}
                onChange={(value) =>
                  set("application_rationale_sop", value.slice(0, MAX_SOP))
                }
                error={!!errors.application_rationale_sop}
                hint={errors.application_rationale_sop}
              />
              <Counter used={form.application_rationale_sop.length} limit={MAX_SOP} />
            </div>

            <div className="space-y-3 rounded-2xl bg-gray-50 p-4 dark:bg-white/[0.03]">
              <div>
                <Checkbox
                  id="ack_manager_notified_bool"
                  label="I certify that my current manager is aware of this transfer request"
                  checked={form.ack_manager_notified_bool}
                  onChange={(checked) => {
                    setForm((previous) => ({
                      ...previous,
                      ack_manager_notified_bool: checked,
                    }));
                    setErrors((previous) => {
                      if (!previous.ack_manager_notified_bool) return previous;
                      const next = { ...previous };
                      delete next.ack_manager_notified_bool;
                      return next;
                    });
                  }}
                />
                {errors.ack_manager_notified_bool && (
                  <p className="mt-1 text-xs text-error-500">
                    {errors.ack_manager_notified_bool}
                  </p>
                )}
              </div>

              <div>
                <Checkbox
                  id="ack_data_accuracy_bool"
                  label="I confirm all provided data details match official corporate record"
                  checked={form.ack_data_accuracy_bool}
                  onChange={(checked) => {
                    setForm((previous) => ({
                      ...previous,
                      ack_data_accuracy_bool: checked,
                    }));
                    setErrors((previous) => {
                      if (!previous.ack_data_accuracy_bool) return previous;
                      const next = { ...previous };
                      delete next.ack_data_accuracy_bool;
                      return next;
                    });
                  }}
                />
                {errors.ack_data_accuracy_bool && (
                  <p className="mt-1 text-xs text-error-500">
                    {errors.ack_data_accuracy_bool}
                  </p>
                )}
              </div>
            </div>
          </div>
        </ComponentCard>

        <div className="flex justify-center">
          <Button
            size="md"
            variant="primary"
            className="w-full md:w-1/3"
            onClick={submit}
            disabled={submitting || loadingProfile || requisitions.length === 0}
          >
            {submitting ? "Submitting..." : "Submit Application"}
          </Button>
        </div>

        {applications.length > 0 && (
          <ComponentCard title="My Applications">
            <div className="max-w-full overflow-x-auto custom-scrollbar">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-xs uppercase text-gray-500 dark:border-gray-800 dark:text-gray-400">
                    <th className="py-2 pr-4 font-medium">Vacancy</th>
                    <th className="py-2 pr-4 font-medium">Qualifications</th>
                    <th className="py-2 pr-4 font-medium">Positions</th>
                    <th className="py-2 pr-4 font-medium">Skills</th>
                    <th className="py-2 pr-4 font-medium">Status</th>
                    <th className="py-2 pr-4 font-medium">Submitted</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {applications.map((application) => (
                    <tr key={application.id} className="text-gray-700 dark:text-gray-300">
                      <td className="py-2.5 pr-4 font-medium text-gray-800 dark:text-white/90">
                        {application.vacancy}
                      </td>
                      <td className="py-2.5 pr-4">{application.education_count}</td>
                      <td className="py-2.5 pr-4">{application.experience_count ?? "—"}</td>
                      <td className="py-2.5 pr-4">{application.skill_count ?? "—"}</td>
                      <td className="py-2.5 pr-4">
                        <Badge color="success" size="sm">
                          {application.status}
                        </Badge>
                      </td>
                      <td className="py-2.5 pr-4">
                        {moment(application.created_at).format("DD MMM YYYY, HH:mm")}
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
