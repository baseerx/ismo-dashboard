import { Fragment, useEffect, useMemo, useState } from "react";
import { ToastContainer, toast } from "react-toastify";
import PageMeta from "../../components/common/PageMeta";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import Label from "../../components/form/Label";
import Input from "../../components/form/input/InputField";
import TextArea from "../../components/form/input/TextArea";
import Checkbox from "../../components/form/input/Checkbox";
import Button from "../../components/ui/button/Button";
import Badge from "../../components/ui/badge/Badge";
import axios from "../../api/axios";
import moment from "moment";

/**
 * The job description library.
 *
 * Descriptions are written here once and attached to vacancies from Job
 * Openings, so the duties for a post are not retyped every time it is
 * advertised. Whoever is applying sees the attached description under the
 * position they pick on the application form.
 */

/** Kept in step with jobs/jd_views.py, which enforces the same rules. */
const MAX_TITLE = 200;
const MAX_CODE = 60;
const MAX_DEPARTMENT = 200;
const MAX_GRADE = 40;
const MAX_REPORTS_TO = 200;
const MAX_BODY = 8000;
const MIN_RESPONSIBILITIES = 20;

type Description = {
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
  is_active: boolean;
  /** How many vacancies point at this description. */
  requisition_count: number;
  created_at: string | null;
};

type FormState = {
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
  is_active: boolean;
};

const blankForm = (): FormState => ({
  title: "",
  code: "",
  department: "",
  grade: "",
  reports_to: "",
  job_purpose: "",
  key_responsibilities: "",
  qualifications: "",
  experience_required: "",
  skills_competencies: "",
  is_active: true,
});

const Counter = ({ value, limit }: { value: number; limit: number }) => (
  <p className="mt-1 text-right text-xs text-gray-400 dark:text-gray-500">
    {value} / {limit}
  </p>
);

export default function JobDescriptions() {
  const [descriptions, setDescriptions] = useState<Description[]>([]);
  const [form, setForm] = useState<FormState>(blankForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Writes need the login token; the shared axios instance does not attach it.
  const authHeader = useMemo(() => {
    const token = localStorage.getItem("token");
    return token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;
  }, []);

  useEffect(() => {
    load();
  }, []);

  const load = async () => {
    setLoading(true);
    try {
      const response = await axios.get("/jobs/descriptions/manage/");
      setDescriptions(Array.isArray(response.data) ? response.data : []);
    } catch {
      setDescriptions([]);
      toast.error("Could not load the job descriptions");
    } finally {
      setLoading(false);
    }
  };

  const set = (field: keyof FormState, value: string | boolean) => {
    setForm((previous) => ({ ...previous, [field]: value }));
    setErrors((previous) => {
      if (!previous[field]) return previous;
      const next = { ...previous };
      delete next[field];
      return next;
    });
  };

  const validate = (): boolean => {
    const problems: Record<string, string> = {};
    const title = form.title.trim();

    if (!title) problems.title = "A job title is required";
    else if (title.length < 3) problems.title = "That title looks too short";
    else if (title.length > MAX_TITLE) {
      problems.title = `Keep the title within ${MAX_TITLE} characters`;
    }

    if (form.code.length > MAX_CODE) {
      problems.code = `Keep the code within ${MAX_CODE} characters`;
    }
    if (form.department.length > MAX_DEPARTMENT) {
      problems.department = `Keep the department within ${MAX_DEPARTMENT} characters`;
    }
    if (form.grade.length > MAX_GRADE) {
      problems.grade = `Keep the grade within ${MAX_GRADE} characters`;
    }
    if (form.reports_to.length > MAX_REPORTS_TO) {
      problems.reports_to = `Keep this within ${MAX_REPORTS_TO} characters`;
    }

    const responsibilities = form.key_responsibilities.trim();
    if (!responsibilities) {
      problems.key_responsibilities = "Key responsibilities are required";
    } else if (responsibilities.length < MIN_RESPONSIBILITIES) {
      problems.key_responsibilities = "Add a little more detail";
    }

    setErrors(problems);
    if (Object.keys(problems).length) toast.error("Please correct the highlighted fields");
    return Object.keys(problems).length === 0;
  };

  const payload = () => ({
    title: form.title.trim(),
    code: form.code.trim(),
    department: form.department.trim(),
    grade: form.grade.trim(),
    reports_to: form.reports_to.trim(),
    job_purpose: form.job_purpose.trim(),
    key_responsibilities: form.key_responsibilities.trim(),
    qualifications: form.qualifications.trim(),
    experience_required: form.experience_required.trim(),
    skills_competencies: form.skills_competencies.trim(),
    is_active: form.is_active,
  });

  const save = async () => {
    if (!validate()) return;

    setSaving(true);
    try {
      if (editingId) {
        await axios.post(`/jobs/descriptions/${editingId}/update/`, payload(), authHeader);
        toast.success("Job description updated");
      } else {
        await axios.post("/jobs/descriptions/create/", payload(), authHeader);
        toast.success("Job description added — it can now be attached to a vacancy");
      }
      reset();
      load();
    } catch (error: any) {
      const returned = error?.response?.data;
      if (returned?.errors) {
        setErrors(returned.errors);
        toast.error("Please correct the highlighted fields");
      } else if (returned?.error) {
        // The server's own words: a rights refusal or a duplicate.
        toast.error(returned.error);
      } else if (!error?.response) {
        toast.error("Could not reach the server. Please try again.");
      } else {
        toast.error("The job description could not be saved");
      }
    } finally {
      setSaving(false);
    }
  };

  const edit = (description: Description) => {
    setEditingId(description.id);
    setErrors({});
    setForm({
      title: description.title,
      code: description.code,
      department: description.department,
      grade: description.grade,
      reports_to: description.reports_to,
      job_purpose: description.job_purpose,
      key_responsibilities: description.key_responsibilities,
      qualifications: description.qualifications,
      experience_required: description.experience_required,
      skills_competencies: description.skills_competencies,
      is_active: description.is_active,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const reset = () => {
    setEditingId(null);
    setForm(blankForm());
    setErrors({});
  };

  /** Retiring one leaves it on the vacancies that use it. */
  const toggleActive = async (description: Description) => {
    try {
      await axios.post(
        `/jobs/descriptions/${description.id}/update/`,
        { ...description, is_active: !description.is_active },
        authHeader
      );
      toast.success(
        description.is_active
          ? "Description retired — it stays on the vacancies already using it"
          : "Description is active again"
      );
      load();
    } catch (error: any) {
      toast.error(error?.response?.data?.error ?? "Could not change the description");
    }
  };

  const remove = async (description: Description) => {
    if (!window.confirm(`Delete "${description.title}"? This cannot be undone.`)) return;

    try {
      await axios.post(`/jobs/descriptions/${description.id}/delete/`, {}, authHeader);
      toast.success("Job description deleted");
      if (editingId === description.id) reset();
      load();
    } catch (error: any) {
      // A description in use is refused with an explanation worth showing whole.
      toast.error(error?.response?.data?.error ?? "Could not delete the description");
    }
  };

  const body = (description: Description) =>
    [
      ["Job Purpose", description.job_purpose],
      ["Key Responsibilities", description.key_responsibilities],
      ["Qualifications", description.qualifications],
      ["Experience Required", description.experience_required],
      ["Skills & Competencies", description.skills_competencies],
    ].filter(([, value]) => value) as [string, string][];

  return (
    <>
      <PageMeta
        title="ISMO - Job Descriptions"
        description="The library of job descriptions attached to internal vacancies"
      />
      <PageBreadcrumb pageTitle="Job Descriptions" />
      <ToastContainer position="bottom-right" />

      <div className="space-y-6">
        <ComponentCard
          title={editingId ? "Edit Job Description" : "Add a Job Description"}
          desc="Attach one of these to a vacancy in Job Openings. Applicants see it under the position they select on the application form."
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="jd_title">
                Job Title <span className="text-error-500">*</span>
              </Label>
              <Input
                id="jd_title"
                placeholder="e.g., Deputy Manager (System Operations)"
                value={form.title}
                onChange={(e) => set("title", e.target.value)}
                error={!!errors.title}
                hint={errors.title}
              />
            </div>

            <div>
              <Label htmlFor="jd_code">JD Code</Label>
              <Input
                id="jd_code"
                placeholder="e.g., JD/SO/DM-09"
                value={form.code}
                onChange={(e) => set("code", e.target.value)}
                error={!!errors.code}
                hint={errors.code}
              />
            </div>

            <div>
              <Label htmlFor="jd_department">Department / Function</Label>
              <Input
                id="jd_department"
                placeholder="e.g., System Operation"
                value={form.department}
                onChange={(e) => set("department", e.target.value)}
                error={!!errors.department}
                hint={errors.department}
              />
            </div>

            <div>
              <Label htmlFor="jd_grade">Grade</Label>
              <Input
                id="jd_grade"
                placeholder="e.g., G-09"
                value={form.grade}
                onChange={(e) => set("grade", e.target.value)}
                error={!!errors.grade}
                hint={errors.grade}
              />
            </div>

            <div>
              <Label htmlFor="jd_reports_to">Reports To</Label>
              <Input
                id="jd_reports_to"
                placeholder="e.g., Manager (System Operations)"
                value={form.reports_to}
                onChange={(e) => set("reports_to", e.target.value)}
                error={!!errors.reports_to}
                hint={errors.reports_to}
              />
            </div>

            <div className="flex items-end pb-2">
              <Checkbox
                id="jd_is_active"
                label="Active — offer this when advertising a vacancy"
                checked={form.is_active}
                onChange={(checked) => set("is_active", checked)}
              />
            </div>

            <div className="md:col-span-2">
              <Label htmlFor="jd_purpose">Job Purpose</Label>
              <TextArea
                id="jd_purpose"
                rows={3}
                placeholder="Why the post exists, in a sentence or two..."
                value={form.job_purpose}
                onChange={(value) => set("job_purpose", value.slice(0, MAX_BODY))}
                error={!!errors.job_purpose}
                hint={errors.job_purpose}
              />
              <Counter value={form.job_purpose.length} limit={MAX_BODY} />
            </div>

            <div className="md:col-span-2">
              <Label htmlFor="jd_responsibilities">
                Key Responsibilities <span className="text-error-500">*</span>
              </Label>
              <TextArea
                id="jd_responsibilities"
                rows={6}
                placeholder="One duty per line..."
                value={form.key_responsibilities}
                onChange={(value) => set("key_responsibilities", value.slice(0, MAX_BODY))}
                error={!!errors.key_responsibilities}
                hint={errors.key_responsibilities}
              />
              <Counter value={form.key_responsibilities.length} limit={MAX_BODY} />
            </div>

            <div className="md:col-span-2">
              <Label htmlFor="jd_qualifications">Qualifications</Label>
              <TextArea
                id="jd_qualifications"
                rows={3}
                placeholder="e.g., Bachelor's degree in Electrical Engineering from an HEC-recognised university"
                value={form.qualifications}
                onChange={(value) => set("qualifications", value.slice(0, MAX_BODY))}
                error={!!errors.qualifications}
                hint={errors.qualifications}
              />
              <Counter value={form.qualifications.length} limit={MAX_BODY} />
            </div>

            <div className="md:col-span-2">
              <Label htmlFor="jd_experience">Experience Required</Label>
              <TextArea
                id="jd_experience"
                rows={3}
                placeholder="e.g., At least 8 years in power system operations, 3 of them at G-08 or above"
                value={form.experience_required}
                onChange={(value) => set("experience_required", value.slice(0, MAX_BODY))}
                error={!!errors.experience_required}
                hint={errors.experience_required}
              />
              <Counter value={form.experience_required.length} limit={MAX_BODY} />
            </div>

            <div className="md:col-span-2">
              <Label htmlFor="jd_skills">Skills &amp; Competencies</Label>
              <TextArea
                id="jd_skills"
                rows={3}
                placeholder="e.g., SCADA/EMS, grid code compliance, incident command, report writing"
                value={form.skills_competencies}
                onChange={(value) => set("skills_competencies", value.slice(0, MAX_BODY))}
                error={!!errors.skills_competencies}
                hint={errors.skills_competencies}
              />
              <Counter value={form.skills_competencies.length} limit={MAX_BODY} />
            </div>
          </div>

          <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
            <Button size="sm" variant="primary" onClick={save} disabled={saving}>
              {saving ? "Saving..." : editingId ? "Save Changes" : "Add Job Description"}
            </Button>
            {editingId && (
              <Button size="sm" variant="outline" onClick={reset}>
                Cancel
              </Button>
            )}
          </div>
        </ComponentCard>

        <ComponentCard
          title="Job Descriptions"
          desc="A description attached to a vacancy cannot be deleted — retire it instead, and it stays with the vacancies that used it."
        >
          {loading ? (
            <p className="py-8 text-center text-sm text-gray-400 dark:text-gray-500">
              Loading job descriptions...
            </p>
          ) : descriptions.length === 0 ? (
            <p className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
              No job descriptions yet. Add one above and it becomes available when
              advertising a vacancy.
            </p>
          ) : (
            <div className="max-w-full overflow-x-auto custom-scrollbar">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-xs uppercase text-gray-500 dark:border-gray-800 dark:text-gray-400">
                    <th className="py-2 pr-4 font-medium">Job Title</th>
                    <th className="py-2 pr-4 font-medium">Code</th>
                    <th className="py-2 pr-4 font-medium">Department / Function</th>
                    <th className="py-2 pr-4 font-medium">Grade</th>
                    <th className="py-2 pr-4 font-medium">Vacancies</th>
                    <th className="py-2 pr-4 font-medium">Status</th>
                    <th className="py-2 pr-4 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {descriptions.map((description) => (
                    <Fragment key={description.id}>
                      <tr
                        className="text-gray-700 dark:text-gray-300"
                        data-description-row={description.id}
                      >
                        <td className="py-2.5 pr-4 font-medium text-gray-800 dark:text-white/90">
                          {description.title}
                          {description.reports_to ? (
                            <div className="text-xs text-gray-400">
                              Reports to {description.reports_to}
                            </div>
                          ) : null}
                        </td>
                        <td className="py-2.5 pr-4">{description.code || "—"}</td>
                        <td className="py-2.5 pr-4">{description.department || "—"}</td>
                        <td className="py-2.5 pr-4">{description.grade || "—"}</td>
                        <td className="py-2.5 pr-4">{description.requisition_count}</td>
                        <td className="py-2.5 pr-4">
                          <Badge
                            size="sm"
                            color={description.is_active ? "success" : "light"}
                          >
                            {description.is_active ? "Active" : "Retired"}
                          </Badge>
                        </td>
                        <td className="py-2.5 pr-4">
                          <div className="flex flex-wrap gap-2">
                            <Button
                              size="xs"
                              variant="outline"
                              onClick={() =>
                                setExpandedId(
                                  expandedId === description.id ? null : description.id
                                )
                              }
                            >
                              {expandedId === description.id ? "Hide" : "View"}
                            </Button>
                            <Button size="xs" variant="outline" onClick={() => edit(description)}>
                              Edit
                            </Button>
                            <Button
                              size="xs"
                              variant="outline"
                              onClick={() => toggleActive(description)}
                            >
                              {description.is_active ? "Retire" : "Reinstate"}
                            </Button>
                            <Button
                              size="xs"
                              variant="outline"
                              onClick={() => remove(description)}
                            >
                              Delete
                            </Button>
                          </div>
                        </td>
                      </tr>
                      {expandedId === description.id && (
                        <tr>
                          <td colSpan={7} className="pb-4">
                            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-white/[0.02]">
                              {body(description).length === 0 ? (
                                <p className="text-sm text-gray-500">
                                  Nothing written in this description yet.
                                </p>
                              ) : (
                                <div className="space-y-3">
                                  {body(description).map(([label, value]) => (
                                    <div key={label}>
                                      <p className="text-xs font-medium uppercase tracking-wide text-brand-500">
                                        {label}
                                      </p>
                                      <p className="mt-1 whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300">
                                        {value}
                                      </p>
                                    </div>
                                  ))}
                                </div>
                              )}
                              {description.created_at && (
                                <p className="mt-3 text-xs text-gray-400">
                                  Added {moment(description.created_at).format("DD MMM YYYY")}
                                </p>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </ComponentCard>
      </div>
    </>
  );
}
