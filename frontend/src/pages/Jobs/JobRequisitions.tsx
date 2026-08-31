import { useEffect, useMemo, useState } from "react";
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

/** Kept in step with jobs/requisition_views.py, which enforces the same rules. */
const MAX_TITLE = 200;
const MAX_REFERENCE = 100;
const MAX_GRADE = 40;
const MAX_DEPARTMENT = 200;
const MAX_LOCATION = 200;
const MAX_DESCRIPTION = 4000;

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
  is_open: boolean;
  /** Open, but its closing date has already passed. */
  has_expired: boolean;
  application_count: number;
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
  is_open: true,
});

export default function JobRequisitions() {
  const [requisitions, setRequisitions] = useState<Requisition[]>([]);
  const [form, setForm] = useState<FormState>(blankForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

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

    setErrors(problems);
    if (Object.keys(problems).length) toast.error("Please correct the highlighted fields");
    return Object.keys(problems).length === 0;
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
      is_open: form.is_open,
    };

    try {
      if (editingId) {
        await axios.post(`/jobs/requisitions/${editingId}/update/`, payload, authHeader);
        toast.success("Vacancy updated");
      } else {
        await axios.post("/jobs/requisitions/create/", payload, authHeader);
        toast.success("Vacancy advertised — it now appears on the application form");
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
      is_open: requisition.is_open,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const reset = () => {
    setEditingId(null);
    setForm(blankForm());
    setErrors({});
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
    } catch (error: any) {
      // A vacancy with applications is refused with an explanation worth
      // showing in full rather than replacing with "failed".
      toast.error(error?.response?.data?.error ?? "Could not delete the vacancy");
    }
  };

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
              <Input
                id="grade"
                placeholder="e.g., G-09"
                value={form.grade}
                onChange={(e) => set("grade", e.target.value)}
                error={!!errors.grade}
                hint={errors.grade}
              />
            </div>

            <div>
              <Label htmlFor="department">Department / Function</Label>
              <Input
                id="department"
                placeholder="e.g., System Operation"
                value={form.department}
                onChange={(e) => set("department", e.target.value)}
                error={!!errors.department}
                hint={errors.department}
              />
            </div>

            <div>
              <Label htmlFor="advertisement_date">Date of Advertisement</Label>
              <Input
                id="advertisement_date"
                type="date"
                value={form.advertisement_date}
                onChange={(e) => set("advertisement_date", e.target.value)}
                error={!!errors.advertisement_date}
                hint={errors.advertisement_date}
              />
            </div>

            <div>
              <Label htmlFor="closing_date">Closing Date</Label>
              <Input
                id="closing_date"
                type="date"
                value={form.closing_date}
                onChange={(e) => set("closing_date", e.target.value)}
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
              <Input
                id="location"
                placeholder="e.g., Islamabad"
                value={form.location}
                onChange={(e) => set("location", e.target.value)}
                error={!!errors.location}
                hint={errors.location}
              />
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
          desc="Closing a vacancy removes it from the application form. Applications already submitted are kept."
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
                            <Button
                              size="xs"
                              variant="danger"
                              onClick={() => remove(requisition)}
                              // Deleting one with applications is refused by the
                              // server; disabling it here saves the round trip.
                              disabled={requisition.application_count > 0}
                            >
                              Delete
                            </Button>
                          </div>
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
