import { useEffect, useMemo, useState } from "react";
import { ToastContainer, toast } from "react-toastify";
import PageMeta from "../../components/common/PageMeta";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import Label from "../../components/form/Label";
import Input from "../../components/form/input/InputField";
import TextArea from "../../components/form/input/TextArea";
import Checkbox from "../../components/form/input/Checkbox";
import Select from "../../components/form/Select";
import DateField from "../../components/form/DateField";
import Button from "../../components/ui/button/Button";
import Badge from "../../components/ui/badge/Badge";
import axios from "../../api/axios";
import moment from "moment";

/** Kept in step with jobs/requisition_views.py, which enforces the same rules. */
const MAX_TITLE = 200;
const MAX_REFERENCE = 100;
const MAX_GRADE = 40;
const MAX_DEPARTMENT = 200;
const MAX_LOCATION = 200;
const MAX_DESCRIPTION = 4000;
const MAX_ADVERTISEMENT_MB = 10;

/** The API serves the advertisement; links open it in the browser's PDF viewer. */
const advertisementHref = (url: string) => `${axios.defaults.baseURL}${url}`;

type Requisition = {
  id: number;
  /** "Position Title" in section 1 of the application form. */
  title: string;
  reference_no: string | null;
  grade: string | null;
  department: string | null;
  location: string | null;
  description: string | null;
  advertisement_date: string | null;
  closing_date: string | null;
  /** The description attached to this vacancy, from the JD library. */
  job_description_id: number | null;
  job_description_title: string;
  job_description_code: string;
  is_open: boolean;
  /** Open, but its closing date has already passed. */
  has_expired: boolean;
  /** Open and not past its closing date - on the application form right now. */
  is_live: boolean;
  application_count: number;
  /** False while live or once applied for; the reason says which. */
  can_delete: boolean;
  delete_blocked_reason: string;
  /** Relative to the API root; empty when no PDF is attached. */
  advertisement_url: string;
  advertisement_name: string;
  created_at: string | null;
};

type FormState = {
  title: string;
  reference_no: string;
  grade: string;
  department: string;
  location: string;
  advertisement_date: string;
  closing_date: string;
  description: string;
  job_description_id: string;
  is_open: boolean;
};

const blankForm = (): FormState => ({
  title: "",
  reference_no: "",
  grade: "",
  department: "",
  location: "",
  advertisement_date: "",
  closing_date: "",
  description: "",
  job_description_id: "",
  is_open: true,
});

type DescriptionOption = {
  id: number;
  title: string;
  code: string;
  department: string;
  grade: string;
  /** The opening this description already belongs to, if any. */
  requisition_id: number | null;
  requisition_title: string;
};

export default function JobRequisitions() {
  const [requisitions, setRequisitions] = useState<Requisition[]>([]);
  const [jobDescriptions, setJobDescriptions] = useState<DescriptionOption[]>([]);
  const [form, setForm] = useState<FormState>(blankForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  // Grade, department and location choices, from the grades, sections and
  // locations tables.
  const [grades, setGrades] = useState<string[]>([]);
  const [departments, setDepartments] = useState<string[]>([]);
  const [locations, setLocations] = useState<string[]>([]);
  const [optionsError, setOptionsError] = useState(false);
  // The advertisement PDF picked for upload with the next save.
  const [advertisementFile, setAdvertisementFile] = useState<File | null>(null);
  // Remounts the file input so it empties after a save or cancel.
  const [fileInputKey, setFileInputKey] = useState(0);

  // Writes need the login token; the shared axios instance does not attach it.
  const authHeader = useMemo(() => {
    const token = localStorage.getItem("token");
    return token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;
  }, []);

  useEffect(() => {
    load();
    loadDescriptions();
    loadOptions();
  }, []);

  /** The grades, departments (sections) and locations a vacancy can name. */
  const loadOptions = async () => {
    try {
      const response = await axios.get("/jobs/requisitions/options/");
      setGrades(response.data?.grades ?? []);
      setDepartments(response.data?.departments ?? []);
      setLocations(response.data?.locations ?? []);
      setOptionsError(false);
    } catch {
      setOptionsError(true);
    }
  };

  /**
   * Dropdown choices, plus the value an older vacancy was saved with when it
   * is no longer in the table - so editing it shows what it holds.
   */
  const choices = (list: string[], current: string) => [
    ...list.map((value) => ({ label: value, value })),
    ...(current && !list.includes(current)
      ? [{ label: `${current} (not in the list)`, value: current }]
      : []),
  ];

  /** The active descriptions a vacancy can be advertised against. */
  const loadDescriptions = async () => {
    try {
      const response = await axios.get("/jobs/descriptions/");
      setJobDescriptions(Array.isArray(response.data) ? response.data : []);
    } catch {
      setJobDescriptions([]);
    }
  };

  const load = async () => {
    setLoading(true);
    try {
      const response = await axios.get("/jobs/requisitions/manage/");
      setRequisitions(Array.isArray(response.data) ? response.data : []);
    } catch {
      setRequisitions([]);
      toast.error("Could not load the list of vacancies");
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
    else if (title.length > MAX_TITLE) problems.title = `Keep the title within ${MAX_TITLE} characters`;

    if (form.reference_no.length > MAX_REFERENCE) {
      problems.reference_no = `Keep the reference number within ${MAX_REFERENCE} characters`;
    }
    if (form.grade.length > MAX_GRADE) {
      problems.grade = `Keep the grade within ${MAX_GRADE} characters`;
    }
    if (form.advertisement_date && form.advertisement_date > moment().format("YYYY-MM-DD")) {
      problems.advertisement_date = "The advertisement date cannot be in the future";
    }
    if (
      form.advertisement_date &&
      form.closing_date &&
      form.closing_date < form.advertisement_date
    ) {
      problems.closing_date = "The closing date is before the advertisement date";
    }
    if (form.department.length > MAX_DEPARTMENT) {
      problems.department = `Keep the department within ${MAX_DEPARTMENT} characters`;
    }
    if (form.location.length > MAX_LOCATION) {
      problems.location = `Keep the location within ${MAX_LOCATION} characters`;
    }
    if (form.description.length > MAX_DESCRIPTION) {
      problems.description = `Keep the description within ${MAX_DESCRIPTION} characters`;
    }

    if (form.closing_date) {
      const editing = editingId
        ? requisitions.find((item) => item.id === editingId)
        : undefined;
      // An unchanged past date on an old vacancy is left alone; a new or edited
      // one cannot close in the past, or it would advertise a post nobody can
      // apply for.
      const unchanged = editing?.closing_date === form.closing_date;
      if (!unchanged && form.closing_date < moment().format("YYYY-MM-DD")) {
        problems.closing_date = "The closing date cannot be in the past";
      }
    }

    // Each opening has its own job description. Only an older opening that was
    // advertised without one may still be saved without.
    if (!form.job_description_id) {
      const editing = editingId
        ? requisitions.find((item) => item.id === editingId)
        : undefined;
      if (!editing) {
        problems.job_description_id = "Choose the job description for this position";
      } else if (editing.job_description_id) {
        problems.job_description_id = "A job description cannot be removed from an opening";
      }
    }

    const fileProblem = checkAdvertisement(advertisementFile);
    if (fileProblem) problems.advertisement_pdf = fileProblem;

    setErrors(problems);
    if (Object.keys(problems).length) toast.error("Please correct the highlighted fields");
    return Object.keys(problems).length === 0;
  };

  /** The same checks the server makes, so a bad file is caught before upload. */
  const checkAdvertisement = (file: File | null): string | null => {
    if (!file) return null;
    if (!file.name.toLowerCase().endsWith(".pdf")) return "The advertisement must be a PDF file";
    if (file.size === 0) return "That file is empty";
    if (file.size > MAX_ADVERTISEMENT_MB * 1024 * 1024) {
      return `Keep the PDF within ${MAX_ADVERTISEMENT_MB} MB`;
    }
    return null;
  };

  const chooseAdvertisement = (file: File | null) => {
    setAdvertisementFile(file);
    setErrors((previous) => {
      const next = { ...previous };
      const problem = checkAdvertisement(file);
      if (problem) next.advertisement_pdf = problem;
      else delete next.advertisement_pdf;
      return next;
    });
  };

  /** Sends the chosen PDF for a saved vacancy. True when it was stored. */
  const uploadAdvertisement = async (requisitionId: number): Promise<boolean> => {
    if (!advertisementFile) return true;
    const body = new FormData();
    body.append("file", advertisementFile);
    try {
      await axios.post(`/jobs/requisitions/${requisitionId}/advertisement/`, body, {
        headers: { ...(authHeader?.headers ?? {}), "Content-Type": "multipart/form-data" },
      });
      return true;
    } catch (error: any) {
      const returned = error?.response?.data;
      toast.error(
        returned?.errors?.advertisement_pdf ??
          returned?.error ??
          "The vacancy was saved, but the advertisement PDF could not be uploaded"
      );
      return false;
    }
  };

  const removeAdvertisement = async (requisition: Requisition) => {
    if (!window.confirm(`Remove the advertisement PDF from "${requisition.title}"?`)) return;
    try {
      await axios.post(
        `/jobs/requisitions/${requisition.id}/advertisement/remove/`,
        {},
        authHeader
      );
      toast.success("Advertisement removed");
      load();
    } catch (error: any) {
      toast.error(error?.response?.data?.error ?? "Could not remove the advertisement");
    }
  };

  const save = async () => {
    if (!validate()) return;

    setSaving(true);
    const payload = {
      title: form.title.trim(),
      reference_no: form.reference_no.trim(),
      grade: form.grade.trim(),
      department: form.department.trim(),
      location: form.location.trim(),
      description: form.description.trim(),
      advertisement_date: form.advertisement_date || null,
      closing_date: form.closing_date || null,
      job_description_id: form.job_description_id || null,
      is_open: form.is_open,
    };

    try {
      let savedId: number;
      if (editingId) {
        await axios.post(`/jobs/requisitions/${editingId}/update/`, payload, authHeader);
        savedId = editingId;
      } else {
        const response = await axios.post("/jobs/requisitions/create/", payload, authHeader);
        savedId = response.data.id;
      }
      // The vacancy is saved either way; a failed upload says so on its own.
      const uploaded = await uploadAdvertisement(savedId);
      if (uploaded) {
        toast.success(
          editingId
            ? "Vacancy updated"
            : "Vacancy advertised — it now appears on the application form"
        );
      }
      reset();
      load();
      loadDescriptions();
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
        toast.error("The vacancy could not be saved");
      }
    } finally {
      setSaving(false);
    }
  };

  const edit = (requisition: Requisition) => {
    setEditingId(requisition.id);
    setErrors({});
    setForm({
      title: requisition.title,
      reference_no: requisition.reference_no ?? "",
      grade: requisition.grade ?? "",
      department: requisition.department ?? "",
      location: requisition.location ?? "",
      advertisement_date: requisition.advertisement_date ?? "",
      closing_date: requisition.closing_date ?? "",
      description: requisition.description ?? "",
      job_description_id: requisition.job_description_id
        ? String(requisition.job_description_id)
        : "",
      is_open: requisition.is_open,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const reset = () => {
    setEditingId(null);
    setForm(blankForm());
    setErrors({});
    setAdvertisementFile(null);
    setFileInputKey((key) => key + 1);
  };

  /** Closing takes a post off the form; the applications already filed stay. */
  const toggleOpen = async (requisition: Requisition) => {
    try {
      await axios.post(
        `/jobs/requisitions/${requisition.id}/update/`,
        {
          title: requisition.title,
          reference_no: requisition.reference_no ?? "",
          grade: requisition.grade ?? "",
          department: requisition.department ?? "",
          location: requisition.location ?? "",
          description: requisition.description ?? "",
          advertisement_date: requisition.advertisement_date,
          closing_date: requisition.closing_date,
          job_description_id: requisition.job_description_id,
          is_open: !requisition.is_open,
        },
        authHeader
      );
      toast.success(requisition.is_open ? "Vacancy closed" : "Vacancy reopened");
      load();
    } catch (error: any) {
      toast.error(error?.response?.data?.error ?? "Could not change the vacancy");
    }
  };

  const remove = async (requisition: Requisition) => {
    if (!requisition.can_delete) {
      toast.error(requisition.delete_blocked_reason);
      return;
    }
    if (
      !window.confirm(
        `Delete "${requisition.title}"? This cannot be undone.`
      )
    ) {
      return;
    }

    try {
      await axios.post(`/jobs/requisitions/${requisition.id}/delete/`, {}, authHeader);
      toast.success("Vacancy deleted");
      if (editingId === requisition.id) reset();
      load();
      loadDescriptions();
    } catch (error: any) {
      // A vacancy with applications is refused with an explanation worth
      // showing in full rather than replacing with "failed".
      toast.error(error?.response?.data?.error ?? "Could not delete the vacancy");
    }
  };

  /**
   * Descriptions this opening may use: those no other opening holds, plus the
   * one it already has. Each opening has its own.
   */
  const availableDescriptions = jobDescriptions.filter(
    (item) => !item.requisition_id || item.requisition_id === editingId
  );

  // Closing dates start from today, or from the advertisement date if later.
  // An older vacancy already past its closing date is left showing that date
  // (the calendar would otherwise blank it); the check on save still applies.
  const earliestClosing = [moment().format("YYYY-MM-DD"), form.advertisement_date]
    .filter(Boolean)
    .sort()
    .pop();
  const closingMinDate =
    form.closing_date && earliestClosing && form.closing_date < earliestClosing
      ? undefined
      : earliestClosing;

  const statusOf = (requisition: Requisition) => {
    if (!requisition.is_open) return { text: "Closed", color: "light" as const };
    if (requisition.has_expired) return { text: "Past closing date", color: "warning" as const };
    return { text: "Open", color: "success" as const };
  };

  return (
    <>
      <PageMeta
        title="ISMO - Job Openings"
        description="Advertise and maintain internal job openings"
      />
      <PageBreadcrumb pageTitle="Job Openings" />
      <ToastContainer position="bottom-right" />

      <div className="space-y-6">
        <ComponentCard
          title={editingId ? "Edit Vacancy" : "Advertise a Vacancy"}
          desc="What is entered here becomes section 1 (Vacancy Information) of the application form."
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="title">
                Position Title <span className="text-error-500">*</span>
              </Label>
              <Input
                id="title"
                placeholder="e.g., Deputy Manager (System Operations)"
                value={form.title}
                onChange={(e) => set("title", e.target.value)}
                error={!!errors.title}
                hint={errors.title}
              />
            </div>

            <div>
              <Label htmlFor="reference_no">Advertisement / Reference No.</Label>
              <Input
                id="reference_no"
                placeholder="e.g., ISMO/HR/IR-2026/07"
                value={form.reference_no}
                onChange={(e) => set("reference_no", e.target.value)}
                error={!!errors.reference_no}
                hint={errors.reference_no}
              />
            </div>

            <div>
              <Label htmlFor="grade">Grade</Label>
              <div id="grade">
                <Select
                  key={`grade-${editingId ?? "new"}-${grades.length}`}
                  options={[
                    { label: "Not specified", value: "" },
                    ...choices(grades, form.grade),
                  ]}
                  placeholder="e.g., MG-09"
                  value={form.grade}
                  onChange={(value) => set("grade", value)}
                  error={!!errors.grade}
                  hint={errors.grade}
                />
              </div>
            </div>

            <div>
              <Label htmlFor="department">Department / Function</Label>
              <div id="department">
                <Select
                  key={`department-${editingId ?? "new"}-${departments.length}`}
                  options={[
                    { label: "Not specified", value: "" },
                    ...choices(departments, form.department),
                  ]}
                  placeholder="Select department"
                  value={form.department}
                  onChange={(value) => set("department", value)}
                  error={!!errors.department}
                  hint={errors.department}
                />
              </div>
              {optionsError && (
                <p className="mt-1 text-xs text-warning-600">
                  The grade, department and location lists could not be loaded.{" "}
                  <button type="button" onClick={loadOptions} className="underline">
                    Try again
                  </button>
                </p>
              )}
            </div>

            <div>
              <Label htmlFor="advertisement_date">Date of Advertisement</Label>
              <DateField
                id="advertisement_date"
                placeholder="Select advertisement date"
                value={form.advertisement_date}
                maxDate={moment().format("YYYY-MM-DD")}
                onChange={(value) => set("advertisement_date", value)}
                error={!!errors.advertisement_date}
                hint={errors.advertisement_date}
              />
            </div>

            <div>
              <Label htmlFor="closing_date">Closing Date</Label>
              <DateField
                id="closing_date"
                placeholder="Select closing date"
                value={form.closing_date}
                minDate={closingMinDate}
                onChange={(value) => set("closing_date", value)}
                error={!!errors.closing_date}
                hint={errors.closing_date}
              />
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                Leave empty to keep it open until closed by hand. Past the closing
                date it stops appearing on the form.
              </p>
            </div>

            <div>
              <Label htmlFor="location">Location</Label>
              <div id="location">
                <Select
                  key={`location-${editingId ?? "new"}-${locations.length}`}
                  options={[
                    { label: "Not specified", value: "" },
                    ...choices(locations, form.location),
                  ]}
                  placeholder="Select location"
                  value={form.location}
                  onChange={(value) => set("location", value)}
                  error={!!errors.location}
                  hint={errors.location}
                />
              </div>
            </div>

            <div>
              <Label htmlFor="job_description_id">
                Job Description <span className="text-error-500">*</span>
              </Label>
              <div id="job_description_id">
                <Select
                  key={`jd-${editingId ?? "new"}-${availableDescriptions.length}`}
                  options={availableDescriptions.map((item) => ({
                    label: [item.code, item.title].filter(Boolean).join(" - "),
                    value: String(item.id),
                  }))}
                  placeholder="Select this position's job description"
                  value={form.job_description_id}
                  onChange={(value) => set("job_description_id", value)}
                  error={!!errors.job_description_id}
                  hint={errors.job_description_id}
                />
              </div>
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500" data-jd-help>
                {availableDescriptions.length === 0 ? (
                  <>
                    Every job description is already attached to an opening. Each
                    position needs its own - write one in{" "}
                    <a
                      href="/job-descriptions"
                      className="font-medium text-brand-500 underline hover:text-brand-600"
                    >
                      Job Descriptions
                    </a>{" "}
                    and it appears here.
                  </>
                ) : (
                  <>
                    Each opening has its own job description; ones already attached to
                    another opening are not listed.{" "}
                    <a
                      href="/job-descriptions"
                      className="font-medium text-brand-500 underline hover:text-brand-600"
                    >
                      Write a new one
                    </a>
                    .
                  </>
                )}
              </p>
            </div>

            <div className="flex items-end pb-2">
              <Checkbox
                id="is_open"
                label="Open for applications"
                checked={form.is_open}
                onChange={(checked) => set("is_open", checked)}
              />
            </div>

            <div className="md:col-span-2">
              <Label htmlFor="advertisement_pdf">Advertisement (PDF)</Label>
              {(() => {
                const current = editingId
                  ? requisitions.find((item) => item.id === editingId)
                  : undefined;
                return current?.advertisement_url ? (
                  <p className="mb-2 text-sm text-gray-600 dark:text-gray-400">
                    Attached:{" "}
                    <a
                      href={advertisementHref(current.advertisement_url)}
                      target="_blank"
                      rel="noreferrer"
                      className="font-medium text-brand-500 underline hover:text-brand-600"
                    >
                      {current.advertisement_name || "advertisement.pdf"}
                    </a>
                    {" · "}
                    <button
                      type="button"
                      onClick={() => removeAdvertisement(current)}
                      className="text-error-500 hover:text-error-600"
                    >
                      Remove
                    </button>
                    <span className="ml-1 text-xs text-gray-400">
                      (choosing a new file replaces it)
                    </span>
                  </p>
                ) : null;
              })()}
              <input
                key={fileInputKey}
                id="advertisement_pdf"
                type="file"
                accept="application/pdf,.pdf"
                onChange={(e) => chooseAdvertisement(e.target.files?.[0] ?? null)}
                className={`h-11 w-full overflow-hidden rounded-lg border bg-transparent text-sm text-gray-500 shadow-theme-xs file:mr-5 file:cursor-pointer file:border-0 file:border-r file:border-solid file:border-gray-200 file:bg-gray-50 file:py-3 file:pl-3.5 file:pr-3 file:text-sm file:text-gray-700 hover:file:bg-gray-100 dark:bg-gray-900 dark:text-gray-400 dark:file:border-gray-800 dark:file:bg-white/[0.03] dark:file:text-gray-400 ${
                  errors.advertisement_pdf
                    ? "border-error-500"
                    : "border-gray-300 dark:border-gray-700"
                }`}
              />
              {errors.advertisement_pdf ? (
                <p className="mt-1 text-xs text-error-500">{errors.advertisement_pdf}</p>
              ) : (
                <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                  The published advertisement, up to {MAX_ADVERTISEMENT_MB} MB. Applicants
                  can open it from the application form.
                </p>
              )}
            </div>

            <div className="md:col-span-2">
              <Label htmlFor="description">Description</Label>
              <TextArea
                rows={4}
                placeholder="What the role covers, and who it suits..."
                value={form.description}
                onChange={(value) => set("description", value.slice(0, MAX_DESCRIPTION))}
                error={!!errors.description}
                hint={errors.description}
              />
              <p className="mt-1 text-right text-xs text-gray-400 dark:text-gray-500">
                {form.description.length} / {MAX_DESCRIPTION}
              </p>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
            <Button size="sm" variant="primary" onClick={save} disabled={saving}>
              {saving
                ? "Saving..."
                : editingId
                  ? "Save Changes"
                  : "Advertise Vacancy"}
            </Button>
            {editingId && (
              <Button size="sm" variant="outline" onClick={reset}>
                Cancel
              </Button>
            )}
          </div>
        </ComponentCard>

        <ComponentCard
          title="Vacancies"
          desc="Closing a vacancy removes it from the application form. A live vacancy, or one with applications, cannot be deleted."
        >
          {loading ? (
            <p className="py-8 text-center text-sm text-gray-400 dark:text-gray-500">
              Loading vacancies...
            </p>
          ) : requisitions.length === 0 ? (
            <p className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
              No vacancies yet. Advertise one above and it will appear on the
              application form straight away.
            </p>
          ) : (
            <div className="max-w-full overflow-x-auto custom-scrollbar">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-xs uppercase text-gray-500 dark:border-gray-800 dark:text-gray-400">
                    <th className="py-2 pr-4 font-medium">Position Title</th>
                    <th className="py-2 pr-4 font-medium">Reference No.</th>
                    <th className="py-2 pr-4 font-medium">Grade</th>
                    <th className="py-2 pr-4 font-medium">Department / Function</th>
                    <th className="py-2 pr-4 font-medium">Job Description</th>
                    <th className="py-2 pr-4 font-medium">Advertisement</th>
                    <th className="py-2 pr-4 font-medium">Advertised</th>
                    <th className="py-2 pr-4 font-medium">Closing</th>
                    <th className="py-2 pr-4 font-medium">Status</th>
                    <th className="py-2 pr-4 font-medium">Applications</th>
                    <th className="py-2 pr-4 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {requisitions.map((requisition) => {
                    const status = statusOf(requisition);
                    return (
                      <tr key={requisition.id} className="text-gray-700 dark:text-gray-300">
                        <td className="py-2.5 pr-4 font-medium text-gray-800 dark:text-white/90">
                          {requisition.title}
                        </td>
                        <td className="py-2.5 pr-4">{requisition.reference_no || "—"}</td>
                        <td className="py-2.5 pr-4">{requisition.grade || "—"}</td>
                        <td className="py-2.5 pr-4">
                          {requisition.department || "—"}
                          {requisition.location ? (
                            <div className="text-xs text-gray-400">{requisition.location}</div>
                          ) : null}
                        </td>
                        <td className="py-2.5 pr-4">
                          {requisition.job_description_title ? (
                            <>
                              {requisition.job_description_title}
                              {requisition.job_description_code ? (
                                <div className="text-xs text-gray-400">
                                  {requisition.job_description_code}
                                </div>
                              ) : null}
                            </>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="py-2.5 pr-4" data-advertisement-cell={requisition.id}>
                          {requisition.advertisement_url ? (
                            <a
                              href={advertisementHref(requisition.advertisement_url)}
                              target="_blank"
                              rel="noreferrer"
                              title={requisition.advertisement_name}
                              className="inline-flex items-center gap-1 font-medium text-brand-500 hover:text-brand-600"
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                                stroke="currentColor" strokeWidth="2" aria-hidden="true">
                                <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
                                <path d="M14 3v5h5" />
                              </svg>
                              View PDF
                            </a>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                        </td>
                        <td className="py-2.5 pr-4">
                          {requisition.advertisement_date
                            ? moment(requisition.advertisement_date).format("DD MMM YYYY")
                            : "—"}
                        </td>
                        <td className="py-2.5 pr-4">
                          {requisition.closing_date
                            ? moment(requisition.closing_date).format("DD MMM YYYY")
                            : "—"}
                        </td>
                        <td className="py-2.5 pr-4">
                          <Badge color={status.color} size="sm">
                            {status.text}
                          </Badge>
                        </td>
                        <td className="py-2.5 pr-4">{requisition.application_count}</td>
                        <td className="py-2.5 pr-4">
                          <div className="flex flex-wrap gap-2">
                            <Button size="xs" variant="outline" onClick={() => edit(requisition)}>
                              Edit
                            </Button>
                            <Button
                              size="xs"
                              variant="outline"
                              onClick={() => toggleOpen(requisition)}
                            >
                              {requisition.is_open ? "Close" : "Reopen"}
                            </Button>
                            {/* A live or applied-for vacancy is refused by the
                                server; disabling it here says why up front. */}
                            <span title={requisition.delete_blocked_reason || undefined}>
                              <Button
                                size="xs"
                                variant="danger"
                                onClick={() => remove(requisition)}
                                disabled={!requisition.can_delete}
                              >
                                Delete
                              </Button>
                            </span>
                          </div>
                          {!requisition.can_delete && (
                            <p className="mt-1 max-w-56 text-[11px] leading-snug text-gray-400">
                              {requisition.is_live
                                ? "Live on the form - close it to delete."
                                : "Has applications - cannot be deleted."}
                            </p>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </ComponentCard>
      </div>
    </>
  );
}
