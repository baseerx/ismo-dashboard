import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import EnhancedDataTable from "../../components/tables/DataTables/DataTableOne";
import axios from "../../api/axios";
import { useState, useEffect } from "react";
import moment from "moment";
import { ToastContainer } from "react-toastify";
import { ColumnDef } from "@tanstack/react-table";
import DateField from "../../components/form/DateField";
import Label from "../../components/form/Label";
import Select from "../../components/form/Select";

/**
 * Section attendance over a date range.
 *
 * One row per employee per day, with that day's first check-in and last
 * check-out side by side - rather than a row per punch.
 */

// Kept in step with SECTION_REPORT_MAX_DAYS in attendance/views.py.
const MAX_DAYS = 93;

type AttendanceRow = {
  date: string;
  erp_id: string;
  name: string;
  designation: string;
  grade: string;
  section: string;
  checkin: string;
  checkout: string;
  worked_hours: string;
  late_status: string;
  early_status: string;
  flag: string;
  flag_type: string;
};

const today = () => moment().format("YYYY-MM-DD");

/** "2026-10-08 08:41:07" -> "08:41"; "-" stays "-". */
const timeOf = (stamp: string) =>
  stamp && stamp !== "-" ? moment(stamp, "YYYY-MM-DD HH:mm:ss").format("HH:mm") : "-";

const pill = (tone: "good" | "warn" | "bad" | "info" | "muted") =>
  `inline-flex items-center justify-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${
    {
      good: "bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-500",
      warn: "bg-warning-50 text-warning-700 dark:bg-warning-500/15 dark:text-warning-400",
      bad: "bg-error-50 text-error-700 dark:bg-error-500/15 dark:text-error-400",
      info: "bg-blue-light-50 text-blue-light-700 dark:bg-blue-light-500/15 dark:text-blue-light-400",
      muted: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
    }[tone]
  }`;

const STATUS_TONE: Record<string, "good" | "warn" | "bad" | "info" | "muted"> = {
  present: "good",
  leave: "info",
  official: "info",
  holiday: "muted",
  weekend: "muted",
  future: "muted",
  absent: "bad",
};

const markCell = (value: string) => {
  if (!value || value === "-") return <span className="text-gray-400">-</span>;
  return <span className={pill(value === "On Time" ? "good" : "warn")}>{value}</span>;
};

const columns: ColumnDef<AttendanceRow>[] = [
  {
    accessorKey: "date",
    header: "Date",
    cell: ({ getValue }) => moment(getValue<string>()).format("ddd, DD MMM YYYY"),
  },
  { accessorKey: "erp_id", header: "ERP ID" },
  { accessorKey: "name", header: "Name" },
  { accessorKey: "designation", header: "Designation" },
  { accessorKey: "grade", header: "Grade" },
  { accessorKey: "checkin", header: "Check-in" },
  { accessorKey: "checkout", header: "Check-out" },
  { accessorKey: "worked_hours", header: "Worked (h:mm)" },
  {
    accessorKey: "late_status",
    header: "Check-in Status",
    cell: ({ getValue }) => markCell(getValue<string>()),
  },
  {
    accessorKey: "early_status",
    header: "Check-out Status",
    cell: ({ getValue }) => markCell(getValue<string>()),
  },
  {
    accessorKey: "flag",
    header: "Status",
    cell: ({ row }) => (
      <span className={pill(STATUS_TONE[row.original.flag_type] ?? "muted")}>
        {row.original.flag}
      </span>
    ),
  },
];

const EXPORT_HEADERS = [
  "Date", "ERP ID", "Name", "Designation", "Grade", "Section", "Check-in", "Check-out",
  "Worked (h:mm)", "Check-in Status", "Check-out Status", "Status",
];

export default function SectionAttendanceReport() {
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const [rows, setRows] = useState<AttendanceRow[]>([]);
  const [section, setSection] = useState("");
  const [fromDate, setFromDate] = useState(today());
  const [toDate, setToDate] = useState(today());
  const [options, setOptions] = useState<{ value: string; label: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    getSectionsData();
  }, []);

  // Default the section to the logged-in user's own section (resolved from the
  // employee list, since the stored user object has no section id).
  useEffect(() => {
    const resolveUserSection = async () => {
      try {
        const response = await axios.get("/users/employees/");
        const self = response.data.find(
          (e: any) => Number(e.erp_id) === Number(user.erpid)
        );
        if (self && self.section_id != null) {
          setSection(String(self.section_id));
        }
      } catch (error) {
        console.error("Error resolving user section:", error);
      }
    };
    resolveUserSection();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const getSectionsData = async () => {
    const response = await axios.get("/sections/get");
    setOptions(
      response.data.map((item: any) => ({ value: String(item.id), label: item.name }))
    );
  };

  /** Why the chosen range cannot be fetched, or null. Same rules as the server. */
  const rangeProblem = (): string | null => {
    if (!fromDate || !toDate) return "Choose both a From and a To date";
    if (toDate < fromDate) return "The To date is before the From date";
    if (moment(toDate).diff(moment(fromDate), "days") + 1 > MAX_DAYS) {
      return `Choose a range of at most ${MAX_DAYS} days`;
    }
    return null;
  };

  useEffect(() => {
    if (!section) return;
    const invalid = rangeProblem();
    setProblem(invalid);
    if (invalid) {
      setRows([]);
      return;
    }
    fetchAttendanceData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fromDate, toDate, section]);

  const fetchAttendanceData = async () => {
    setLoading(true);
    try {
      const response = await axios.post("/attendance/sections/", {
        section,
        fromdate: fromDate,
        todate: toDate,
      });
      setRows(
        (Array.isArray(response.data) ? response.data : []).map((item: any) => ({
          date: item.date,
          erp_id: item.erp_id,
          name: item.name,
          designation: item.designation ?? "-",
          grade: item.grade ?? "-",
          section: item.section ?? "-",
          checkin: timeOf(item.checkin_time),
          checkout: timeOf(item.checkout_time),
          worked_hours: item.worked_hours ?? "-",
          late_status: item.late_status,
          early_status: item.early_status,
          flag: item.flag,
          flag_type: item.flag_type,
        }))
      );
      setProblem(null);
    } catch (error: any) {
      setRows([]);
      setProblem(error?.response?.data?.error ?? "The attendance could not be loaded");
    } finally {
      setLoading(false);
    }
  };

  const sectionName = options.find((option) => option.value === section)?.label;
  const range =
    fromDate === toDate
      ? moment(fromDate).format("DD MMM YYYY")
      : `${moment(fromDate).format("DD MMM YYYY")} to ${moment(toDate).format("DD MMM YYYY")}`;

  return (
    <>
      <PageMeta
        title="ISMO - Section Attendance Report"
        description="ISMO Admin Dashboard - Section Attendance Report"
      />
      <PageBreadcrumb pageTitle="Section Attendance Report" />
      <div className="space-y-6">
        <ComponentCard
          title={`Attendance ${sectionName ? `of ${sectionName} ` : ""}- ${range}`}
          desc="One row per employee per day: the first check-in and the last check-out of the day."
        >
          <ToastContainer position="bottom-right" />

          <div className="mb-4 grid grid-cols-1 gap-4 md:grid-cols-3">
            <div>
              <Label htmlFor="from-date">From</Label>
              <DateField
                id="from-date"
                value={fromDate}
                maxDate={today()}
                onChange={setFromDate}
                placeholder="From date"
              />
            </div>
            <div>
              <Label htmlFor="to-date">To</Label>
              <DateField
                id="to-date"
                value={toDate}
                minDate={fromDate || undefined}
                maxDate={today()}
                onChange={setToDate}
                placeholder="To date"
              />
            </div>
            <div>
              <Label>Section</Label>
              <div id="section-select">
                <Select
                  options={options}
                  placeholder="Select a section"
                  value={section}
                  onChange={setSection}
                  className="dark:bg-dark-900"
                />
              </div>
            </div>
          </div>

          {problem ? (
            <p className="mb-4 rounded-lg border border-warning-200 bg-warning-50 px-4 py-3 text-sm text-warning-700 dark:border-warning-500/30 dark:bg-warning-500/10 dark:text-warning-400" data-report-problem>
              {problem}
            </p>
          ) : null}

          {loading ? (
            <p className="py-8 text-center text-sm text-gray-400">Loading attendance...</p>
          ) : !section ? (
            <p className="py-8 text-center text-sm text-gray-500">Choose a section to see its attendance.</p>
          ) : (
            <EnhancedDataTable<AttendanceRow>
              data={rows}
              columns={columns}
              getExportHeaders={() => EXPORT_HEADERS}
              getExportRows={(data) =>
                data.map((row) => [
                  row.date, row.erp_id, row.name, row.designation, row.grade, row.section,
                  row.checkin, row.checkout, row.worked_hours, row.late_status,
                  row.early_status, row.flag,
                ])
              }
            />
          )}
        </ComponentCard>
      </div>
    </>
  );
}
