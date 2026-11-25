import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import EnhancedDataTable from "../../components/tables/DataTables/DataTableOne";
import axios from "../../api/axios";
import { useEffect, useMemo, useState } from "react";
import moment from "moment";
import { ToastContainer, toast } from "react-toastify";
import { ColumnDef } from "@tanstack/react-table";
import DatePicker from "../../components/form/date-picker";

/**
 * Individual Detailed Report - the signed-in employee's own attendance for a
 * date range. The server works out who is asking from the sign-in token, so
 * this page cannot show anyone else's attendance.
 *
 * Averages follow the Section Report rules (worked out on the server): only
 * days with both a check-in and a check-out count, full leave days do not, and
 * a short leave exempts just its hours.
 */

type DayRecord = {
  date: string;
  checkin_time: string;
  checkout_time: string;
  worked_hours: string;
  late_status: string;
  early_status: string;
  flag: string;
  flag_type: string;
  short_leave: string | null;
  short_leave_hours: string | null;
  counted_for_average: boolean;
  adjusted_checkin?: string;
  adjusted_checkout?: string;
};

type Summary = {
  days: number;
  checkin_count: number;
  checkout_count: number;
  avg_checkin: string;
  avg_checkout: string;
  avg_worked: string;
  avg_days: number;
};

type Employee = {
  erp_id: number | string;
  name: string;
  designation: string;
  grade: string;
  section: string;
};

type Row = {
  date: string;
  day: string;
  checkin: string;
  checkout: string;
  worked: string;
  shortLeave: string;
  status: string;
  statusType: string;
  late: string;
  early: string;
  counted: string;
  countedNote: string;
};

const badge = (tone: "good" | "warn" | "muted") =>
  `inline-flex items-center px-3 py-0.5 justify-center rounded-full font-semibold text-theme-xs ${
    tone === "good"
      ? "bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500"
      : tone === "warn"
        ? "bg-warning-50 text-warning-600 dark:bg-warning-500/15 dark:text-warning-500"
        : "bg-gray-100 text-gray-600 dark:bg-white/5 dark:text-gray-400"
  }`;

const clock = (value?: string) =>
  value && value !== "-" ? moment(value, "YYYY-MM-DD HH:mm:ss").format("hh:mm A") : "-";

/** "08:19:21" -> "08:19 AM"; "-" stays "-". */
const timeOfDay = (value?: string) =>
  value && value !== "-" ? moment(value, "HH:mm:ss").format("hh:mm A") : "-";

/** "08:42:10" as a duration -> "8h 42m". */
const duration = (value?: string) => {
  if (!value || value === "-") return "-";
  const [h, m] = value.split(":").map(Number);
  return `${h}h ${String(m).padStart(2, "0")}m`;
};

/** Why a day was left out of the averages, in plain words. */
const exclusionReason = (day: DayRecord) => {
  if (day.counted_for_average) {
    return day.short_leave && day.adjusted_checkin
      ? `Short leave ${day.short_leave} exempted: counted as ${clock(day.adjusted_checkin)} – ${clock(day.adjusted_checkout)}`
      : "";
  }
  if (day.flag_type === "leave" && !day.short_leave) return "Leave day";
  if (day.checkin_time === "-" && day.checkout_time === "-") return "No attendance";
  if (day.checkin_time === "-") return "Missing check-in";
  if (day.checkout_time === "-") return "Missing check-out";
  return "Check-in and check-out less than a minute apart";
};

export default function MyDetailedReport() {
  const [days, setDays] = useState<DayRecord[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [employee, setEmployee] = useState<Employee | null>(null);
  const [fromdate, setFromdate] = useState<string>(moment().startOf("month").format("YYYY-MM-DD"));
  const [todate, setTodate] = useState<string>(moment().format("YYYY-MM-DD"));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!fromdate || !todate) return;
    if (fromdate > todate) {
      toast.error("From date cannot be after to date");
      return;
    }
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      try {
        const token = localStorage.getItem("token");
        const response = await axios.post(
          "/attendance/my-detailed/",
          { fromdate, todate },
          { headers: token ? { Authorization: `Bearer ${token}` } : undefined }
        );
        if (cancelled) return;
        setEmployee(response.data?.employee ?? null);
        setSummary(response.data?.summary ?? null);
        setDays(Array.isArray(response.data?.days) ? response.data.days : []);
        setError(null);
      } catch (err: unknown) {
        if (cancelled) return;
        const message =
          (err as { response?: { data?: { error?: string } } })?.response?.data?.error ||
          "Your attendance could not be loaded.";
        setDays([]);
        setSummary(null);
        setError(message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [fromdate, todate]);

  const rows: Row[] = useMemo(
    () =>
      days.map((day) => ({
        date: moment(day.date).format("DD-MM-YYYY"),
        day: moment(day.date).format("dddd"),
        checkin: clock(day.checkin_time),
        checkout: clock(day.checkout_time),
        worked: day.worked_hours && day.worked_hours !== "-" ? day.worked_hours : "-",
        shortLeave: day.short_leave
          ? `${day.short_leave}${day.short_leave_hours ? ` (${day.short_leave_hours})` : ""}`
          : "-",
        status: day.flag,
        statusType: day.flag_type,
        late: day.late_status,
        early: day.early_status,
        counted: day.counted_for_average ? "Yes" : "No",
        countedNote: exclusionReason(day),
      })),
    [days]
  );

  const counts = useMemo(() => {
    const of = (type: string) => days.filter((d) => d.flag_type === type).length;
    return {
      present: of("present"),
      absent: of("absent"),
      leave: of("leave") + of("official") + of("holiday"),
      late: days.filter((d) => d.late_status === "Late").length,
      early: days.filter((d) => d.early_status === "Early").length,
    };
  }, [days]);

  const columns: ColumnDef<Row>[] = [
    { accessorKey: "date", header: "Date" },
    { accessorKey: "day", header: "Day" },
    { accessorKey: "checkin", header: "Check-in" },
    { accessorKey: "checkout", header: "Check-out" },
    { accessorKey: "worked", header: "Worked Hours" },
    { accessorKey: "shortLeave", header: "Short Leave" },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => {
        const { status, statusType } = row.original;
        const tone = statusType === "present" ? "good" : statusType === "absent" ? "warn" : "muted";
        return <span className={badge(tone)}>{status}</span>;
      },
    },
    {
      accessorKey: "late",
      header: "Late In",
      cell: ({ getValue }) => {
        const value = getValue<string>();
        return value === "-" ? "-" : <span className={badge(value === "Late" ? "warn" : "good")}>{value}</span>;
      },
    },
    {
      accessorKey: "early",
      header: "Early Out",
      cell: ({ getValue }) => {
        const value = getValue<string>();
        return value === "-" ? "-" : <span className={badge(value === "Early" ? "warn" : "good")}>{value}</span>;
      },
    },
    {
      accessorKey: "counted",
      header: "Counted for Average",
      cell: ({ row }) => {
        const { counted, countedNote } = row.original;
        return (
          <div>
            <span className={badge(counted === "Yes" ? "good" : "muted")}>{counted}</span>
            {countedNote && (
              <div className="mt-1 max-w-56 text-[11px] leading-snug text-gray-400">{countedNote}</div>
            )}
          </div>
        );
      },
    },
  ];

  const averageTiles = [
    { label: "Average Check-in", value: timeOfDay(summary?.avg_checkin) },
    { label: "Average Check-out", value: timeOfDay(summary?.avg_checkout) },
    { label: "Average Working Hours", value: duration(summary?.avg_worked) },
    {
      label: "No. of Days Counted for Average Working Hours",
      value: summary ? String(summary.avg_days) : "-",
    },
  ];
  const countTiles = [
    { label: "Present", value: counts.present },
    { label: "Absent", value: counts.absent },
    { label: "Leave / Official / Holiday", value: counts.leave },
    { label: "Late In", value: counts.late },
    { label: "Early Out", value: counts.early },
  ];

  return (
    <>
      <PageMeta
        title="ISMO - Individual Detailed Report"
        description="ISMO Admin Dashboard - your own detailed attendance report"
      />
      <PageBreadcrumb pageTitle="Individual Detailed Report" />
      <ToastContainer position="bottom-right" />
      <div className="space-y-6">
        <ComponentCard
          title={employee ? `${employee.name} (ERP ${employee.erp_id})` : "My Attendance"}
          desc={
            employee
              ? [employee.designation, employee.grade, employee.section].filter(Boolean).join(" · ")
              : "Your own attendance for the dates you choose."
          }
        >
          <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            <DatePicker
              id="my-from-date"
              defaultDate={fromdate}
              label="From date"
              placeholder="Select a date"
              onChange={(_dates, value) => value && setFromdate(value)}
            />
            <DatePicker
              id="my-to-date"
              defaultDate={todate}
              label="To date"
              placeholder="Select a date"
              onChange={(_dates, value) => value && setTodate(value)}
            />
          </div>

          {error ? (
            <p className="py-8 text-center text-sm text-error-500">{error}</p>
          ) : (
            <>
              <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {averageTiles.map((tile) => (
                  <div
                    key={tile.label}
                    className="rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 dark:border-brand-800 dark:bg-brand-500/10"
                  >
                    <div className="text-xs text-gray-600 dark:text-gray-300">{tile.label}</div>
                    <div className="mt-1 text-xl font-semibold text-gray-800 dark:text-white/90">
                      {loading ? "…" : tile.value}
                    </div>
                  </div>
                ))}
              </div>
              <p className="mb-4 text-xs text-gray-500 dark:text-gray-400">
                Averages count only days with both a check-in and a check-out. Days missing
                either, and full leave days, are left out. On a short-leave day only the leave
                hours are exempted: first-half leave moves the check-in earlier, second-half
                leave moves the check-out later.
              </p>
              <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
                {countTiles.map((tile) => (
                  <div
                    key={tile.label}
                    className="rounded-xl border border-gray-200 px-4 py-3 dark:border-gray-800"
                  >
                    <div className="text-xs text-gray-500 dark:text-gray-400">{tile.label}</div>
                    <div className="mt-1 text-lg font-semibold text-gray-800 dark:text-white/90">
                      {loading ? "…" : tile.value}
                    </div>
                  </div>
                ))}
              </div>
              <EnhancedDataTable<Row>
                data={rows}
                columns={columns}
                fromdate={fromdate}
                todate={todate}
              />
            </>
          )}
        </ComponentCard>
      </div>
    </>
  );
}
