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
  vacancy: string;
  target_job_req_id: number;
  emp_full_name: string;
  emp_id: number;
  current_dept_code: string;
  current_job_title: string;
  corporate_email: string;
  contact_phone_no: string;
  status: string;
  created_at: string;
  education_count: number;
  experience_count: number;
  skill_count: number;
};

type EducationRow = {
  edu_degree_title: string;
  edu_institution_name: string;
  edu_major_specialization: string;
  edu_graduation_year: number;
  edu_grade_score: string;
};

type ExperienceRow = {
  exp_job_title: string;
  exp_company_name: string;
  exp_start_date: string | null;
  exp_end_date: string | null;
  exp_is_current: boolean;
  exp_key_responsibilities: string;
  exp_key_achievements: string;
};

type ApplicationDetail = ApplicationSummary & {
  current_supervisor_id: string;
  cnic: string;
  personal_email: string | null;
  preferred_contact_method: string;
  certifications_list: string | null;
  application_rationale_sop: string;
  ack_manager_notified_bool: boolean;
  ack_data_accuracy_bool: boolean;
  education: EducationRow[];
  experience: ExperienceRow[];
  skills_technical: string[];
  skills_soft: string[];
};

type Requisition = { id: number; title: string };

const STATUS_COLORS: Record<string, "success" | "warning" | "error" | "light"> = {
  submitted: "light",
  under_review: "warning",
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

  // Requests to /jobs/applications/... are permission-gated; the shared axios
  // instance does not attach the login token, so it is added explicitly here.
  const authHeader = useMemo(() => {
    const token = localStorage.getItem("token");
    return token ? { Authorization: `Bearer ${token}` } : undefined;
  }, []);

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
        headers: authHeader,
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
    } catch (error: any) {
      setApplications([]);
      toast.error(error?.response?.data?.error ?? "Could not load applications");
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
        headers: authHeader,
      });
      setSelected(response.data);
    } catch (error: any) {
      toast.error(error?.response?.data?.error ?? "Could not load this application");
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
      headers: authHeader,
      responseType: "blob",
      params: inline ? { inline: 1 } : undefined,
    });
    return new Blob([response.data], { type: "application/pdf" });
  };

  const downloadPdf = async (application: { id: number; emp_full_name: string }) => {
    setPdfBusyId(application.id);
    try {
      const blob = await fetchApplicationPdf(application.id, false);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${application.id}_${application.emp_full_name.replace(/\s+/g, "_")}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error: any) {
      toast.error(error?.response?.data?.error ?? "Could not generate the PDF");
    } finally {
      setPdfBusyId(null);
    }
  };

  const printPdf = async (application: { id: number }) => {
    setPdfBusyId(application.id);
    try {
      const blob = await fetchApplicationPdf(application.id, true);
      const url = window.URL.createObjectURL(blob);
      // Opens in the browser's built-in PDF viewer, whose own print button
      // handles the rest — no extra print pipeline needed.
      window.open(url, "_blank");
    } catch (error: any) {
      toast.error(error?.response?.data?.error ?? "Could not generate the PDF");
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
        headers: authHeader,
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
      // The blob response has to be read as text to see the JSON error body.
      let message = "Could not export the applications";
      if (error?.response?.data instanceof Blob) {
        try {
          const text = await error.response.data.text();
          message = JSON.parse(text)?.error || message;
        } catch {
          /* keep default message */
        }
      } else {
        message = error?.response?.data?.error ?? message;
      }
      toast.error(message);
    } finally {
      setExporting(false);
    }
  };

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
          ) : applications.length === 0 ? (
            <p className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
              No applications match these filters.
            </p>
          ) : (
            <>
              <div className="max-w-full overflow-x-auto custom-scrollbar">
                <table className="min-w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 text-xs uppercase text-gray-500 dark:border-gray-800 dark:text-gray-400">
                      <th className="py-2 pr-4 font-medium">Applicant</th>
                      <th className="py-2 pr-4 font-medium">Vacancy</th>
                      <th className="py-2 pr-4 font-medium">Emp ID</th>
                      <th className="py-2 pr-4 font-medium">Contact</th>
                      <th className="py-2 pr-4 font-medium">Status</th>
                      <th className="py-2 pr-4 font-medium">Submitted</th>
                      <th className="py-2 pr-4 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                    {applications.map((application) => (
                      <tr key={application.id} className="text-gray-700 dark:text-gray-300">
                        <td className="py-2.5 pr-4">
                          <div className="font-medium text-gray-800 dark:text-white/90">
                            {application.emp_full_name}
                          </div>
                          <div className="text-xs text-gray-400">
                            {application.current_job_title || "—"}
                          </div>
                        </td>
                        <td className="py-2.5 pr-4">{application.vacancy}</td>
                        <td className="py-2.5 pr-4">{application.emp_id}</td>
                        <td className="py-2.5 pr-4">
                          <div>{application.corporate_email}</div>
                          <div className="text-xs text-gray-400">{application.contact_phone_no}</div>
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
                      {selected.emp_full_name}
                    </h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Application #{selected.id} · {selected.vacancy}
                    </p>
                  </div>
                  {statusBadge(selected.status)}
                </div>

                <DetailSection title="Target Position & Applicant Identity">
                  <DetailGrid
                    rows={[
                      ["Employee ID", selected.emp_id],
                      ["Current Department", selected.current_dept_code],
                      ["Current Position Title", selected.current_job_title],
                      ["Current Supervisor", selected.current_supervisor_id],
                      ["CNIC", selected.cnic],
                    ]}
                  />
                </DetailSection>

                <DetailSection title="Contact Information">
                  <DetailGrid
                    rows={[
                      ["Corporate Email", selected.corporate_email],
                      ["Personal Email", selected.personal_email || "—"],
                      ["Contact Phone", selected.contact_phone_no],
                      ["Preferred Channel", selected.preferred_contact_method],
                    ]}
                  />
                </DetailSection>

                <DetailSection title="Educational Background">
                  {selected.education.length === 0 ? (
                    <p className="text-sm text-gray-400">No education records provided.</p>
                  ) : (
                    <div className="space-y-2">
                      {selected.education.map((row, i) => (
                        <div
                          key={i}
                          className="rounded-lg border border-gray-200 p-3 text-sm dark:border-gray-800"
                        >
                          <span className="font-medium text-gray-800 dark:text-white/90">
                            {row.edu_degree_title}
                          </span>{" "}
                          — {row.edu_institution_name} ({row.edu_graduation_year})
                          <div className="text-xs text-gray-400">
                            {row.edu_major_specialization} · {row.edu_grade_score}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </DetailSection>

                <DetailSection title="Professional Experience">
                  {selected.experience.length === 0 ? (
                    <p className="text-sm text-gray-400">No experience records provided.</p>
                  ) : (
                    <div className="space-y-3">
                      {selected.experience.map((row, i) => (
                        <div
                          key={i}
                          className="rounded-lg border border-gray-200 p-3 text-sm dark:border-gray-800"
                        >
                          <div className="font-medium text-gray-800 dark:text-white/90">
                            {row.exp_job_title} — {row.exp_company_name}
                          </div>
                          <div className="text-xs text-gray-400">
                            {row.exp_start_date ? moment(row.exp_start_date).format("MMM YYYY") : "—"} –{" "}
                            {row.exp_is_current
                              ? "Present"
                              : row.exp_end_date
                                ? moment(row.exp_end_date).format("MMM YYYY")
                                : "—"}
                          </div>
                          {row.exp_key_responsibilities && (
                            <p className="mt-1 text-gray-600 dark:text-gray-300">
                              {row.exp_key_responsibilities}
                            </p>
                          )}
                          {row.exp_key_achievements && (
                            <p className="mt-1 italic text-gray-500 dark:text-gray-400">
                              {row.exp_key_achievements}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </DetailSection>

                <DetailSection title="Skills & Certifications">
                  <p className="text-sm">
                    <span className="font-medium">Technical:</span>{" "}
                    {selected.skills_technical.join(", ") || "—"}
                  </p>
                  <p className="text-sm">
                    <span className="font-medium">Soft Skills:</span>{" "}
                    {selected.skills_soft.join(", ") || "—"}
                  </p>
                  <p className="text-sm">
                    <span className="font-medium">Certifications:</span>{" "}
                    {selected.certifications_list || "—"}
                  </p>
                </DetailSection>

                <DetailSection title="Statement of Purpose">
                  <p className="whitespace-pre-wrap text-sm text-gray-600 dark:text-gray-300">
                    {selected.application_rationale_sop}
                  </p>
                </DetailSection>

                <DetailSection title="Acknowledgements">
                  <p className="text-sm">
                    Manager notified: <strong>{selected.ack_manager_notified_bool ? "Yes" : "No"}</strong>
                    {"  ·  "}
                    Data accuracy confirmed:{" "}
                    <strong>{selected.ack_data_accuracy_bool ? "Yes" : "No"}</strong>
                  </p>
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