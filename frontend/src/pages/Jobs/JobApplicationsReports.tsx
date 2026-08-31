import { useEffect, useMemo, useState } from "react";
import { ToastContainer, toast } from "react-toastify";
import PageMeta from "../../components/common/PageMeta";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import Label from "../../components/form/Label";
import Input from "../../components/form/input/InputField";
import Select from "../../components/form/Select";
import Button from "../../components/ui/button/Button";
import Badge from "../../components/ui/badge/Badge";
import axios from "../../api/axios";
import moment from "moment";

// ----------------------------
// Types
// ----------------------------
type ApplicationSummary = {
  id: number;
  /** ISMO/IJA/2026/00042 - issued on submission. */
  reference_no: string;
  vacancy: string;
  vacancy_reference_no: string;
  target_job_req_id: number;
  full_name: string;
  emp_id: number;
  department_function: string;
  current_designation: string;
  current_grade: string;
  official_email: string;
  mobile_no: string;
  status: string;
  hr_verification_status: string;
  created_at: string;
  education_count: number;
  experience_count: number;
  certification_count: number;
  training_count: number;
};

type EducationRow = {
  degree_qualification: string;
  major_field_of_study: string;
  institution_university: string;
  country: string;
  year_of_completion: number;
  cgpa_division: string;
};

type ExperienceRow = {
  organization_employer: string;
  designation: string;
  grade: string;
  from_date: string | null;
  to_date: string | null;
  is_current: boolean;
  duration: string;
  key_responsibilities: string;
};

type CertificationRow = {
  certification_membership: string;
  certifying_body: string;
  date_obtained: string | null;
  expiry_date: string | null;
  registration_no: string;
};

type TrainingRow = {
  training_title: string;
  training_provider: string;
  duration: string;
  date_or_year: string;
  relevant_to_position: boolean;
};

type ApplicationDetail = ApplicationSummary & {
  // 1. vacancy information
  vacancy_grade: string;
  vacancy_department: string;
  vacancy_advertisement_date: string | null;
  vacancy_closing_date: string | null;
  // 2. personal & contact information
  father_or_husband_name: string;
  cnic: string;
  date_of_birth: string | null;
  gender: string;
  current_office_location: string;
  emergency_contact_no: string;
  // 3. current employment details
  date_of_joining_ismo: string | null;
  date_of_appointment_to_current_grade: string | null;
  total_service_ismo: string;
  total_relevant_experience: string;
  date_of_joining_current_position: string | null;
  // 4 to 7
  education: EducationRow[];
  experience: ExperienceRow[];
  certifications: CertificationRow[];
  trainings: TrainingRow[];
  // 8 and 9
  declaration_accepted: boolean;
  applicant_signature: string;
};

type Requisition = { id: number; title: string };

const DASH_SPACED = "—";

const STATUS_COLORS: Record<string, "success" | "warning" | "error" | "light"> = {
  submitted: "light",
  under_review: "warning",
  verified: "success",
  shortlisted: "success",
  rejected: "error",
  hired: "success",
};

export default function JobApplicationsReport() {
  const [applications, setApplications] = useState<ApplicationSummary[]>([]);
  const [statuses, setStatuses] = useState<string[]>([]);
  const [requisitions, setRequisitions] = useState<Requisition[]>([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [vacancyId, setVacancyId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [page, setPage] = useState(1);
  const [numPages, setNumPages] = useState(1);
  const [count, setCount] = useState(0);

  const [selected, setSelected] = useState<ApplicationDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [pdfBusyId, setPdfBusyId] = useState<number | null>(null);
  // Why the list is empty, when it is empty because something failed. An empty
  // table with a toast that has already faded is impossible to diagnose.
  const [loadError, setLoadError] = useState<string | null>(null);
  // A refused session needs a different remedy from a retry - signing in again.
  const [sessionExpired, setSessionExpired] = useState(false);

  // Requests to /jobs/applications/... are permission-gated; the shared axios
  // instance does not attach the login token, so it is added explicitly here.
  // Read per request rather than once, so signing in again in another tab does
  // not leave this page holding a stale token.
  const authHeader = () => {
    const token = localStorage.getItem("token");
    return token ? { Authorization: `Bearer ${token}` } : undefined;
  };

  const signedInAs = useMemo(() => {
    try {
      const stored = JSON.parse(localStorage.getItem("user") || "{}");
      if (!stored?.erpid) return "not signed in";
      return `${stored.employee_name || stored.username || "signed in"} (ERP ${stored.erpid})` +
        (stored.is_superuser ? ", administrator" : "");
    } catch {
      return "not signed in";
    }
  }, []);

  /** A sentence that says what actually went wrong, and what to do about it. */
  const describeFailure = (error: any, what: string): string => {
    const server = error?.response?.data?.error;
    const status = error?.response?.status;

    if (!error?.response) {
      return `Could not reach the server to ${what}. It is not answering at ` +
        `${axios.defaults.baseURL} — check the backend is running and reachable from this machine.`;
    }
    if (status === 401 || status === 403) {
      return server || `You are not allowed to ${what}. Signed in as ${signedInAs}.`;
    }
    if (status === 404) {
      return `The server answered 404 for this request, which means it is not running the ` +
        `job reports code yet. Deploy the latest backend and restart it, then reload this page.`;
    }
    if (status === 400) {
      return server || "One of the filters was not understood by the server.";
    }
    if (status >= 500) {
      return `The server failed while trying to ${what} (HTTP ${status}). Its log will say why.`;
    }
    return server || `Could not ${what} (HTTP ${status}).`;
  };

  useEffect(() => {
    loadRequisitions();
  }, []);

  useEffect(() => {
    loadApplications(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, vacancyId, dateFrom, dateTo]);

  const loadRequisitions = async () => {
    try {
      const response = await axios.get("/jobs/requisitions/manage/");
      setRequisitions(
        (Array.isArray(response.data) ? response.data : []).map((r: any) => ({
          id: r.id,
          title: r.title,
        }))
      );
    } catch {
      setRequisitions([]);
    }
  };

  const loadApplications = async (targetPage: number) => {
    setLoading(true);
    try {
      const response = await axios.get("/jobs/applications/manage/", {
        headers: authHeader(),
        params: {
          page: targetPage,
          search: search || undefined,
          status: status || undefined,
          target_job_req_id: vacancyId || undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
        },
      });
      setApplications(response.data?.results || []);
      setStatuses(response.data?.statuses || []);
      setNumPages(response.data?.num_pages || 1);
      setCount(response.data?.count || 0);
      setPage(response.data?.page || 1);
      setLoadError(null);
      setSessionExpired(false);
    } catch (error: any) {
      setApplications([]);
      setCount(0);
      setNumPages(1);
      const reason = describeFailure(error, "load the applications");
      const status = error?.response?.status;
      setSessionExpired(
        (status === 401 || status === 403) && /session|sign in/i.test(String(reason))
      );
      setLoadError(reason);
      // One id, so a re-render or a retry replaces the message instead of
      // stacking another copy of it.
      toast.error(reason, { toastId: "job-reports-load" });
    } finally {
      setLoading(false);
    }
  };

  const runSearch = () => loadApplications(1);

  const clearFilters = () => {
    setSearch("");
    setStatus("");
    setVacancyId("");
    setDateFrom("");
    setDateTo("");
  };

  // ----------------------------
  // Popup detail view
  // ----------------------------
  const openDetail = async (id: number) => {
    setDetailLoading(true);
    try {
      const response = await axios.get(`/jobs/applications/${id}/detail/`, {
        headers: authHeader(),
      });
      setSelected(response.data);
    } catch (error: any) {
      toast.error(describeFailure(error, "open this application"));
    } finally {
      setDetailLoading(false);
    }
  };

  const closeDetail = () => setSelected(null);

  // ----------------------------
  // PDF download / print (both require the auth header, so the PDF is
  // fetched as a blob first rather than opened directly by URL)
  // ----------------------------
  const fetchApplicationPdf = async (id: number, inline: boolean) => {
    const response = await axios.get(`/jobs/applications/${id}/pdf/`, {
      headers: authHeader(),
      responseType: "blob",
      params: inline ? { inline: 1 } : undefined,
    });
    return new Blob([response.data], { type: "application/pdf" });
  };

  // A download is never blocked the way a new window is, so this doubles as the
  // fallback when a browser cannot show a PDF for printing.
  const saveToDisk = (url: string, filename: string) => {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const pdfFilename = (application: { id: number; full_name?: string }) =>
    `${application.id}_${(application.full_name || "application").replace(/\s+/g, "_")}.pdf`;

  /** The server's message, dug out of a blob response. */
  const blobError = async (error: any) => {
    if (error?.response?.data instanceof Blob) {
      try {
        const parsed = JSON.parse(await error.response.data.text());
        if (parsed?.error) {
          return { ...error, response: { ...error.response, data: parsed } };
        }
      } catch {
        /* not JSON - fall through to the generic description */
      }
    }
    return error;
  };

  const downloadPdf = async (application: { id: number; full_name: string }) => {
    setPdfBusyId(application.id);
    try {
      const blob = await fetchApplicationPdf(application.id, false);
      const url = window.URL.createObjectURL(blob);
      saveToDisk(url, pdfFilename(application));
      window.URL.revokeObjectURL(url);
    } catch (error: any) {
      toast.error(error?.response?.data?.error ?? "Could not generate the PDF");
    } finally {
      setPdfBusyId(null);
    }
  };

  const printPdf = async (application: { id: number; full_name?: string }) => {
    setPdfBusyId(application.id);
    try {
      const blob = await fetchApplicationPdf(application.id, true);
      const url = window.URL.createObjectURL(blob);

      // Printed from a hidden frame rather than a new tab: the PDF is fetched
      // first (it needs the auth header), and by the time that request comes
      // back the click is no longer a fresh user gesture, so a new window gets
      // treated as a pop-up and blocked. A frame also puts the print dialog up
      // directly instead of leaving the reviewer to find the viewer's own
      // print button.
      const frame = document.createElement("iframe");
      frame.style.position = "fixed";
      frame.style.right = "0";
      frame.style.bottom = "0";
      frame.style.width = "1px";
      frame.style.height = "1px";
      frame.style.opacity = "0";
      frame.style.border = "0";
      frame.setAttribute("aria-hidden", "true");
      frame.dataset.printFrame = String(application.id);
      frame.src = url;

      let displayed = false;
      frame.onload = () => {
        displayed = true;
        try {
          frame.contentWindow?.focus();
          frame.contentWindow?.print();
        } catch {
          saveToDisk(url, pdfFilename(application));
        }
      };

      document.body.appendChild(frame);

      // Not every browser can display a PDF inside a frame; where it cannot,
      // nothing loads and no dialog would ever appear, so hand over the file.
      window.setTimeout(() => {
        if (!displayed) {
          saveToDisk(url, pdfFilename(application));
          toast.info(
            "This browser cannot show a print preview for PDFs, so the file was downloaded - open it and print from there."
          );
        }
      }, 4000);

      // Kept alive well past the dialog: removing the frame while the dialog is
      // open cancels the job, and revoking the URL any earlier does the same.
      window.setTimeout(() => {
        frame.remove();
        window.URL.revokeObjectURL(url);
      }, 60000);
    } catch (error: any) {
      toast.error(describeFailure(await blobError(error), "prepare the PDF for printing"));
    } finally {
      setPdfBusyId(null);
    }
  };

  // ----------------------------
  // Bulk ZIP export (respects current filters)
  // ----------------------------
  const exportZip = async () => {
    setExporting(true);
    try {
      const response = await axios.get("/jobs/applications/export/zip/", {
        headers: authHeader(),
        responseType: "blob",
        params: {
          search: search || undefined,
          status: status || undefined,
          target_job_req_id: vacancyId || undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
        },
      });
      const blob = new Blob([response.data], { type: "application/zip" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `job_applications_${moment().format("YYYYMMDD_HHmm")}.zip`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Export downloaded");
    } catch (error: any) {
      toast.error(describeFailure(await blobError(error), "export the applications"));
    } finally {
      setExporting(false);
    }
  };

  const showDate = (value: string | null) =>
    value ? moment(value).format("DD MMM YYYY") : "—";

  const statusBadge = (value: string) => (
    <Badge color={STATUS_COLORS[value] ?? "light"} size="sm">
      {value.replace(/_/g, " ")}
    </Badge>
  );

  return (
    <>
      <PageMeta
        title="ISMO - Job Applications Report"
        description="Review, download, and export internal job applications"
      />
      <PageBreadcrumb pageTitle="Job Applications Report" />
      <ToastContainer position="bottom-right" />

      <div className="space-y-6">
        <ComponentCard
          title="Filters"
          desc="Narrow the list before exporting — the ZIP export downloads exactly what's shown here."
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-5">
            <div className="lg:col-span-2">
              <Label htmlFor="search">Search</Label>
              <Input
                id="search"
                placeholder="Name, email, employee ID, or CNIC"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && runSearch()}
              />
            </div>
            <div>
              <Label>Vacancy</Label>
              <Select
                options={[
                  { label: "All vacancies", value: "" },
                  ...requisitions.map((r) => ({ label: r.title, value: String(r.id) })),
                ]}
                placeholder="All vacancies"
                value={vacancyId}
                onChange={(value) => setVacancyId(value)}
              />
            </div>
            <div>
              <Label>Status</Label>
              <Select
                options={[
                  { label: "All statuses", value: "" },
                  ...statuses.map((s) => ({ label: s.replace(/_/g, " "), value: s })),
                ]}
                placeholder="All statuses"
                value={status}
                onChange={(value) => setStatus(value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label htmlFor="date_from">From</Label>
                <Input
                  id="date_from"
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="date_to">To</Label>
                <Input
                  id="date_to"
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button size="sm" variant="primary" onClick={runSearch}>
              Search
            </Button>
            <Button size="sm" variant="outline" onClick={clearFilters}>
              Clear Filters
            </Button>
            <div className="flex-1" />
            <Button size="sm" variant="outline" onClick={exportZip} disabled={exporting || count === 0}>
              {exporting ? "Preparing ZIP..." : `Download All as ZIP (${count})`}
            </Button>
          </div>
        </ComponentCard>

        <ComponentCard title={`Applications (${count})`}>
          {loading ? (
            <p className="py-8 text-center text-sm text-gray-400 dark:text-gray-500">
              Loading applications...
            </p>
          ) : loadError ? (
            // Nothing loaded, and this says why - which beats an empty table.
            <div className="my-4 rounded-lg border border-error-200 bg-error-50 p-5 text-sm dark:border-error-500/40 dark:bg-error-500/10">
              <p className="font-medium text-error-600 dark:text-error-400">
                The applications could not be loaded
              </p>
              <p className="mt-1.5 text-gray-700 dark:text-gray-300">{loadError}</p>
              <p className="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
                Signed in as {signedInAs} · server {axios.defaults.baseURL}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={() => loadApplications(1)}>
                  Try again
                </Button>
                {sessionExpired && (
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => {
                      // A token the server will not accept - most often one
                      // issued by a different backend - is only fixed by
                      // signing in again against this one.
                      localStorage.removeItem("token");
                      localStorage.removeItem("user");
                      window.location.href = "/";
                    }}
                  >
                    Sign in again
                  </Button>
                )}
              </div>
            </div>
          ) : applications.length === 0 ? (
            <p className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
              {search || status || vacancyId || dateFrom || dateTo
                ? "No applications match these filters."
                : "No applications have been submitted yet."}
            </p>
          ) : (
            <>
              <div className="max-w-full overflow-x-auto custom-scrollbar">
                <table className="min-w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 text-xs uppercase text-gray-500 dark:border-gray-800 dark:text-gray-400">
                      <th className="py-2 pr-4 font-medium">Reference No.</th>
                      <th className="py-2 pr-4 font-medium">Applicant</th>
                      <th className="py-2 pr-4 font-medium">Position Applied For</th>
                      <th className="py-2 pr-4 font-medium">Emp ID</th>
                      <th className="py-2 pr-4 font-medium">Contact</th>
                      <th className="py-2 pr-4 font-medium">HR Verification</th>
                      <th className="py-2 pr-4 font-medium">Submitted</th>
                      <th className="py-2 pr-4 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                    {applications.map((application) => (
                      <tr key={application.id} className="text-gray-700 dark:text-gray-300">
                        <td className="py-2.5 pr-4 font-medium text-gray-800 dark:text-white/90">
                          {application.reference_no || `#${application.id}`}
                        </td>
                        <td className="py-2.5 pr-4">
                          <div className="font-medium text-gray-800 dark:text-white/90">
                            {application.full_name}
                          </div>
                          <div className="text-xs text-gray-400">
                            {application.current_designation || "—"}
                            {application.current_grade ? ` (${application.current_grade})` : ""}
                          </div>
                        </td>
                        <td className="py-2.5 pr-4">
                          {application.vacancy}
                          {application.vacancy_reference_no ? (
                            <div className="text-xs text-gray-400">
                              {application.vacancy_reference_no}
                            </div>
                          ) : null}
                        </td>
                        <td className="py-2.5 pr-4">{application.emp_id}</td>
                        <td className="py-2.5 pr-4">
                          <div>{application.official_email}</div>
                          <div className="text-xs text-gray-400">{application.mobile_no}</div>
                        </td>
                        <td className="py-2.5 pr-4">{statusBadge(application.status)}</td>
                        <td className="py-2.5 pr-4">
                          {moment(application.created_at).format("DD MMM YYYY, HH:mm")}
                        </td>
                        <td className="py-2.5 pr-4">
                          <div className="flex flex-wrap gap-2">
                            <Button size="xs" variant="outline" onClick={() => openDetail(application.id)}>
                              View
                            </Button>
                            <Button
                              size="xs"
                              variant="outline"
                              onClick={() => downloadPdf(application)}
                              disabled={pdfBusyId === application.id}
                            >
                              PDF
                            </Button>
                            <Button
                              size="xs"
                              variant="outline"
                              onClick={() => printPdf(application)}
                              disabled={pdfBusyId === application.id}
                            >
                              Print
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {numPages > 1 && (
                <div className="mt-4 flex items-center justify-center gap-3">
                  <Button
                    size="xs"
                    variant="outline"
                    onClick={() => loadApplications(page - 1)}
                    disabled={page <= 1}
                  >
                    Previous
                  </Button>
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    Page {page} of {numPages}
                  </span>
                  <Button
                    size="xs"
                    variant="outline"
                    onClick={() => loadApplications(page + 1)}
                    disabled={page >= numPages}
                  >
                    Next
                  </Button>
                </div>
              )}
            </>
          )}
        </ComponentCard>
      </div>

      {/* ---------------- Detail popup ---------------- */}
      {(selected || detailLoading) && (
        <div
          className="fixed inset-0 z-99999 flex items-center justify-center bg-black/50 p-4"
          onClick={closeDetail}
        >
          <div
            className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-6 shadow-xl dark:bg-gray-900"
            onClick={(e) => e.stopPropagation()}
          >
            {detailLoading || !selected ? (
              <p className="py-10 text-center text-sm text-gray-400">Loading application...</p>
            ) : (
              <>
                <div className="mb-4 flex items-start justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
                      {selected.full_name}
                    </h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {selected.reference_no || `Application #${selected.id}`} ·{" "}
                      {selected.vacancy}
                    </p>
                  </div>
                  {statusBadge(selected.status)}
                </div>

                <DetailSection title="1. Vacancy Information">
                  <DetailGrid
                    rows={[
                      ["Position Title", selected.vacancy],
                      ["Advertisement / Reference No.", selected.vacancy_reference_no],
                      ["Grade", selected.vacancy_grade],
                      ["Department / Function", selected.vacancy_department],
                      ["Date of Advertisement", showDate(selected.vacancy_advertisement_date)],
                      ["Closing Date", showDate(selected.vacancy_closing_date)],
                      ["Current Designation", selected.current_designation],
                      ["Current Grade", selected.current_grade],
                    ]}
                  />
                </DetailSection>

                <DetailSection title="2. Personal & Contact Information">
                  <DetailGrid
                    rows={[
                      ["Employee ID", selected.emp_id],
                      ["Full Name", selected.full_name],
                      ["Father's / Husband's Name", selected.father_or_husband_name],
                      ["CNIC No.", selected.cnic],
                      ["Date of Birth", showDate(selected.date_of_birth)],
                      ["Gender", selected.gender],
                      ["Official Email Address", selected.official_email],
                      ["Mobile / Contact No.", selected.mobile_no],
                      ["Current Office / Location", selected.current_office_location],
                      ["Emergency Contact No.", selected.emergency_contact_no],
                    ]}
                  />
                </DetailSection>

                <DetailSection title="3. Current Employment Details">
                  <DetailGrid
                    rows={[
                      ["Date of Joining ISMO", showDate(selected.date_of_joining_ismo)],
                      ["Current Designation", selected.current_designation],
                      ["Current Grade", selected.current_grade],
                      ["Department / Function", selected.department_function],
                      [
                        "Date of Appointment to Current Grade",
                        showDate(selected.date_of_appointment_to_current_grade),
                      ],
                      ["Total Service in ISMO", selected.total_service_ismo],
                      ["Total Relevant Experience", selected.total_relevant_experience],
                      [
                        "Date of Joining Current Position",
                        showDate(selected.date_of_joining_current_position),
                      ],
                    ]}
                  />
                </DetailSection>

                <DetailSection title="4. Educational Background">
                  {selected.education.length === 0 ? (
                    <p className="text-sm text-gray-400">No qualifications listed.</p>
                  ) : (
                    <DetailTable
                      headers={[
                        "Degree / Qualification",
                        "Major / Field of Study",
                        "Institution / University",
                        "Country",
                        "Year",
                        "CGPA / Division",
                      ]}
                      rows={selected.education.map((row) => [
                        row.degree_qualification,
                        row.major_field_of_study,
                        row.institution_university,
                        row.country,
                        String(row.year_of_completion),
                        row.cgpa_division,
                      ])}
                    />
                  )}
                </DetailSection>

                <DetailSection title="5. Employment History / Professional Experience">
                  {selected.experience.length === 0 ? (
                    <p className="text-sm text-gray-400">No employment history listed.</p>
                  ) : (
                    <div className="space-y-3">
                      {selected.experience.map((row, i) => (
                        <div
                          key={i}
                          className="rounded-lg border border-gray-200 p-3 text-sm dark:border-gray-800"
                        >
                          <div className="font-medium text-gray-800 dark:text-white/90">
                            {row.designation} {DASH_SPACED} {row.organization_employer}
                            {row.grade ? ` (${row.grade})` : ""}
                          </div>
                          <div className="text-xs text-gray-400">
                            {row.from_date ? moment(row.from_date).format("MMM YYYY") : "?"} –{" "}
                            {row.is_current
                              ? "Present"
                              : row.to_date
                                ? moment(row.to_date).format("MMM YYYY")
                                : "?"}
                            {row.duration ? ` · ${row.duration}` : ""}
                          </div>
                          {row.key_responsibilities && (
                            <p className="mt-1 text-gray-600 dark:text-gray-300">
                              {row.key_responsibilities}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </DetailSection>

                <DetailSection title="6. Professional Certifications / Memberships">
                  {selected.certifications.length === 0 ? (
                    <p className="text-sm text-gray-400">None declared.</p>
                  ) : (
                    <DetailTable
                      headers={[
                        "Certification / Membership",
                        "Certifying Body",
                        "Date Obtained",
                        "Expiry Date",
                        "Registration No.",
                      ]}
                      rows={selected.certifications.map((row) => [
                        row.certification_membership,
                        row.certifying_body,
                        showDate(row.date_obtained),
                        showDate(row.expiry_date),
                        row.registration_no,
                      ])}
                    />
                  )}
                </DetailSection>

                <DetailSection title="7. Trainings & Professional Development">
                  {selected.trainings.length === 0 ? (
                    <p className="text-sm text-gray-400">None declared.</p>
                  ) : (
                    <DetailTable
                      headers={[
                        "Training / Course Title",
                        "Provider / Institute",
                        "Duration",
                        "Date / Year",
                        "Relevant",
                      ]}
                      rows={selected.trainings.map((row) => [
                        row.training_title,
                        row.training_provider,
                        row.duration,
                        row.date_or_year,
                        row.relevant_to_position ? "Yes" : "No",
                      ])}
                    />
                  )}
                </DetailSection>

                <DetailSection title="8. Declaration & Undertaking">
                  <p className="text-sm">
                    Accepted by the applicant:{" "}
                    <strong>{selected.declaration_accepted ? "Yes" : "No"}</strong>
                  </p>
                </DetailSection>

                <DetailSection title="9. Submission Record">
                  <DetailGrid
                    rows={[
                      ["Applicant Name", selected.full_name],
                      ["Employee ID", selected.emp_id],
                      [
                        "Date of Submission",
                        moment(selected.created_at).format("DD MMM YYYY, HH:mm"),
                      ],
                      ["Application Reference No.", selected.reference_no],
                      ["Electronic Signature / Confirmation", selected.applicant_signature],
                      ["HR Verification Status", selected.hr_verification_status],
                    ]}
                  />
                </DetailSection>

                <div className="mt-5 flex flex-wrap justify-end gap-3">
                  <Button size="sm" variant="outline" onClick={() => downloadPdf(selected)}>
                    Download PDF
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => printPdf(selected)}>
                    Print
                  </Button>
                  <Button size="sm" variant="primary" onClick={closeDetail}>
                    Close
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
      
    </>
  );
}

// ----------------------------
// Small popup building blocks
// ----------------------------
function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <h4 className="mb-2 text-sm font-semibold text-brand-600 dark:text-brand-400">{title}</h4>
      {children}
    </div>
  );
}

function DetailGrid({ rows }: { rows: [string, string | number][] }) {
  return (
    <div className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
      {rows.map(([label, value]) => (
        <div key={label}>
          <div className="text-xs text-gray-400">{label}</div>
          <div className="text-sm text-gray-700 dark:text-gray-300">{value || "—"}</div>
        </div>
      ))}
    </div>
  );
}
/** One of the form's repeating tables: same columns, same order. */
function DetailTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="max-w-full overflow-x-auto custom-scrollbar">
      <table className="min-w-full border-collapse text-left text-xs">
        <thead>
          <tr className="bg-gray-50 dark:bg-white/[0.03]">
            {headers.map((header) => (
              <th
                key={header}
                className="border border-gray-200 px-2 py-1.5 font-medium text-gray-600 dark:border-gray-800 dark:text-gray-300"
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {row.map((cell, cellIndex) => (
                <td
                  key={cellIndex}
                  className="border border-gray-200 px-2 py-1.5 align-top text-gray-700 dark:border-gray-800 dark:text-gray-300"
                >
                  {cell || "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
