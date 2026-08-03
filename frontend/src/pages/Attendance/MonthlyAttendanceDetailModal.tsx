import { useCallback, useEffect, useMemo, useState } from "react";
import moment from "moment";
import { Modal } from "../../components/ui/modal";
import axios from "../../api/axios";

export type DetailTab = "present" | "absent" | "leave";

export type DetailEmployee = {
  erp_id: string;
  name: string;
  designation: string;
  department: string;
  location: string;
  is_shift: boolean;
  shift_names: string;
  total_present: number;
  total_absent: number;
  approved_leaves: number;
};

type DayRow = {
  date: string;
  day_name: string;
  checkin_time: string;
  checkout_time: string;
  late_status: string;
  early_status: string;
  status: string;
  status_type: string;
};

type LeaveDate = {
  date: string;
  day_name: string;
  weekend: boolean;
  attended: boolean;
};

type LeaveRow = {
  id: number;
  leave_type: string;
  start_date: string;
  end_date: string;
  total_days: number;
  days_in_month: number;
  counted_days: number;
  reason: string;
  status: string;
  approved_by: string;
  applied_on: string;
  dates: LeaveDate[];
};

type DetailPayload = {
  days: DayRow[];
  leaves: LeaveRow[];
};

interface Props {
  isOpen: boolean;
  onClose: () => void;
  employee: DetailEmployee | null;
  initialTab: DetailTab;
  fromdate: string;
  todate: string;
  monthLabel: string;
}

// Each tab carries its own accent so the modal keeps the colour the user
// clicked in the table — green for presents, red for absents, amber for leave.
const TABS: {
  key: DetailTab;
  label: string;
  chip: string;
  activeChip: string;
  ring: string;
}[] = [
  {
    key: "present",
    label: "Presents",
    chip: "text-success-600 dark:text-success-500",
    activeChip:
      "bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-500",
    ring: "border-success-200 dark:border-success-500/30",
  },
  {
    key: "absent",
    label: "Absents",
    chip: "text-error-600 dark:text-error-500",
    activeChip:
      "bg-error-50 text-error-700 dark:bg-error-500/15 dark:text-error-500",
    ring: "border-error-200 dark:border-error-500/30",
  },
  {
    key: "leave",
    label: "Approved Leaves",
    chip: "text-warning-600 dark:text-warning-500",
    activeChip:
      "bg-warning-50 text-warning-700 dark:bg-warning-500/15 dark:text-warning-500",
    ring: "border-warning-200 dark:border-warning-500/30",
  },
];

const leaveStatusTone = (status: string) => {
  switch (status) {
    case "approved":
      return "bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-500";
    case "rejected":
      return "bg-error-50 text-error-700 dark:bg-error-500/15 dark:text-error-500";
    default:
      return "bg-warning-50 text-warning-700 dark:bg-warning-500/15 dark:text-warning-500";
  }
};

const pill = (text: string, tone: string) => (
  <span
    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium ${tone}`}
  >
    {text}
  </span>
);

// Labelled chip for the employee's posting details in the header.
const meta = (label: string, value?: string) => (
  <span className="inline-flex items-center gap-1 rounded-lg bg-white/70 px-2 py-1 text-[11px] dark:bg-white/[0.06]">
    <span className="text-gray-400 dark:text-gray-500">{label}</span>
    <span className="font-medium text-gray-700 dark:text-gray-300">
      {value || "-"}
    </span>
  </span>
);

const timingTone = (value: string) =>
  value === "Late" || value === "Early"
    ? "bg-warning-50 text-warning-700 dark:bg-warning-500/15 dark:text-warning-500"
    : value === "On Time"
    ? "bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-500"
    : "bg-gray-100 text-gray-500 dark:bg-white/5 dark:text-gray-400";

export default function MonthlyAttendanceDetailModal({
  isOpen,
  onClose,
  employee,
  initialTab,
  fromdate,
  todate,
  monthLabel,
}: Props) {
  const [tab, setTab] = useState<DetailTab>(initialTab);
  const [data, setData] = useState<DetailPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Follow the cell that was clicked — reopening on a different column should
  // land on that column's tab.
  useEffect(() => {
    setTab(initialTab);
  }, [initialTab, employee?.erp_id]);

  const fetchDetail = useCallback(async () => {
    if (!employee) return;
    setLoading(true);
    setError(null);
    try {
      const response = await axios.post("/attendance/monthly-employee-days/", {
        erp_id: employee.erp_id,
        fromdate,
        todate,
      });
      setData({
        days: response.data?.days ?? [],
        leaves: response.data?.leaves ?? [],
      });
    } catch (err) {
      console.error(err);
      setError("Could not load the day-wise detail for this employee.");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [employee, fromdate, todate]);

  useEffect(() => {
    if (isOpen && employee) {
      fetchDetail();
    }
    if (!isOpen) {
      setData(null);
      setError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, employee?.erp_id, fromdate, todate]);

  const presentDays = useMemo(
    () => (data?.days ?? []).filter((d) => d.status_type === "present"),
    [data]
  );

  const absentDays = useMemo(
    () => (data?.days ?? []).filter((d) => d.status_type === "absent"),
    [data]
  );

  const counts: Record<DetailTab, number> = {
    present: employee?.total_present ?? 0,
    absent: employee?.total_absent ?? 0,
    leave: employee?.approved_leaves ?? 0,
  };

  const active = TABS.find((t) => t.key === tab) ?? TABS[0];

  const initials = (employee?.name ?? "")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");

  const renderAttendanceTable = (rows: DayRow[], mode: "present" | "absent") => {
    if (!rows.length) {
      return (
        <div className="flex h-40 flex-col items-center justify-center gap-1 text-center">
          <span className="text-sm font-medium text-gray-500 dark:text-gray-400">
            No {mode === "present" ? "present" : "absent"} days recorded
          </span>
          <span className="text-xs text-gray-400 dark:text-gray-500">
            {monthLabel}
          </span>
        </div>
      );
    }

    return (
      <div className="overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-gray-50 text-[11px] uppercase tracking-wide text-gray-500 dark:bg-white/[0.03] dark:text-gray-400">
            <tr>
              <th className="px-4 py-3 font-medium">Date</th>
              <th className="px-4 py-3 font-medium">Day</th>
              <th className="px-4 py-3 font-medium">Check In</th>
              <th className="px-4 py-3 font-medium">Check Out</th>
              <th className="px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {rows.map((row) => (
              <tr
                key={row.date}
                className="transition-colors hover:bg-gray-50 dark:hover:bg-white/[0.03]"
              >
                <td className="whitespace-nowrap px-4 py-3 font-medium text-gray-800 dark:text-white/90">
                  {moment(row.date).format("DD MMM YYYY")}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-gray-500 dark:text-gray-400">
                  {row.day_name}
                </td>
                <td className="whitespace-nowrap px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="text-gray-700 dark:text-gray-300">
                      {row.checkin_time}
                    </span>
                    {row.checkin_time !== "-" &&
                      pill(row.late_status, timingTone(row.late_status))}
                  </div>
                </td>
                <td className="whitespace-nowrap px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="text-gray-700 dark:text-gray-300">
                      {row.checkout_time}
                    </span>
                    {row.checkout_time !== "-" &&
                      pill(row.early_status, timingTone(row.early_status))}
                  </div>
                </td>
                <td className="whitespace-nowrap px-4 py-3">
                  {pill(
                    row.status,
                    mode === "present"
                      ? "bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-500"
                      : "bg-error-50 text-error-700 dark:bg-error-500/15 dark:text-error-500"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const renderLeaves = (rows: LeaveRow[]) => {
    if (!rows.length) {
      return (
        <div className="flex h-40 flex-col items-center justify-center gap-1 text-center">
          <span className="text-sm font-medium text-gray-500 dark:text-gray-400">
            No leave requests in this month
          </span>
          <span className="text-xs text-gray-400 dark:text-gray-500">
            {monthLabel}
          </span>
        </div>
      );
    }

    return (
      <div className="space-y-3">
        {rows.map((leave) => (
          <div
            key={leave.id}
            className="rounded-xl border border-gray-200 bg-white p-4 transition-shadow hover:shadow-theme-sm dark:border-gray-800 dark:bg-white/[0.02]"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-gray-800 dark:text-white/90">
                    {leave.leave_type}
                  </span>
                  {pill(
                    leave.status.charAt(0).toUpperCase() + leave.status.slice(1),
                    leaveStatusTone(leave.status)
                  )}
                </div>
                <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  {moment(leave.start_date).format("DD MMM YYYY")} —{" "}
                  {moment(leave.end_date).format("DD MMM YYYY")}
                </div>
              </div>

              <div className="flex gap-4 text-right">
                <div>
                  <div className="text-lg font-semibold text-gray-800 dark:text-white/90">
                    {leave.days_in_month}
                  </div>
                  <div className="text-[11px] text-gray-500 dark:text-gray-400">
                    day(s) in {moment(fromdate).format("MMM")}
                  </div>
                </div>
                <div>
                  <div className="text-lg font-semibold text-gray-800 dark:text-white/90">
                    {leave.total_days}
                  </div>
                  <div className="text-[11px] text-gray-500 dark:text-gray-400">
                    total applied
                  </div>
                </div>
              </div>
            </div>

            {/* Day-wise chips: which dates this request actually covers, and
                where the employee still turned up (those count as present). */}
            <div className="mt-3 flex flex-wrap gap-1.5">
              {leave.dates.map((d) => (
                <span
                  key={d.date}
                  title={`${moment(d.date).format("DD MMM YYYY")} · ${d.day_name}${
                    d.attended ? " · attended" : ""
                  }`}
                  className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium ${
                    d.attended
                      ? "bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-500"
                      : d.weekend
                      ? "bg-gray-100 text-gray-500 dark:bg-white/5 dark:text-gray-400"
                      : leave.status === "approved"
                      ? "bg-warning-50 text-warning-700 dark:bg-warning-500/15 dark:text-warning-500"
                      : "bg-gray-100 text-gray-600 dark:bg-white/5 dark:text-gray-300"
                  }`}
                >
                  {moment(d.date).format("DD MMM")}
                  <span className="opacity-60">
                    {d.day_name.slice(0, 3)}
                  </span>
                </span>
              ))}
            </div>

            <dl className="mt-3 grid grid-cols-1 gap-3 border-t border-gray-100 pt-3 text-xs sm:grid-cols-3 dark:border-gray-800">
              <div>
                <dt className="text-gray-400 dark:text-gray-500">Reason</dt>
                <dd className="mt-0.5 text-gray-700 dark:text-gray-300">
                  {leave.reason}
                </dd>
              </div>
              <div>
                <dt className="text-gray-400 dark:text-gray-500">Approved By</dt>
                <dd className="mt-0.5 text-gray-700 dark:text-gray-300">
                  {leave.approved_by}
                </dd>
              </div>
              <div>
                <dt className="text-gray-400 dark:text-gray-500">Applied On</dt>
                <dd className="mt-0.5 text-gray-700 dark:text-gray-300">
                  {leave.applied_on === "-"
                    ? "-"
                    : moment(leave.applied_on).format("DD MMM YYYY")}
                </dd>
              </div>
            </dl>

            {leave.status === "approved" && (
              <div className="mt-2 text-[11px] text-gray-400 dark:text-gray-500">
                {leave.counted_days} day(s) counted as approved leave in this
                report
                {leave.days_in_month - leave.counted_days > 0 &&
                  ` · ${leave.days_in_month - leave.counted_days} day(s) counted as present instead`}
              </div>
            )}
          </div>
        ))}
      </div>
    );
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      className="m-4 max-w-4xl overflow-hidden"
    >
      {/* Header */}
      <div className="border-b border-gray-200 bg-gradient-to-r from-brand-50 to-white px-6 pb-5 pt-6 dark:border-gray-800 dark:from-brand-500/10 dark:to-transparent">
        <div className="flex items-start gap-4 pr-12">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-500 text-sm font-semibold text-white">
            {initials || "?"}
          </div>
          <div className="min-w-0">
            <h4 className="truncate text-lg font-semibold text-gray-800 dark:text-white/90">
              {employee?.name ?? "-"}
            </h4>
            <p className="mt-0.5 truncate text-xs text-gray-500 dark:text-gray-400">
              {employee?.designation ?? "-"} · ERP {employee?.erp_id ?? "-"} ·{" "}
              {monthLabel}
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {meta("Department", employee?.department)}
              {meta("Location", employee?.location)}
              {meta(
                "Shift",
                employee?.is_shift ? `Yes · ${employee.shift_names}` : "No"
              )}
            </div>
          </div>
        </div>

        {/* Tabs double as stat tiles — the count stays visible while switching */}
        <div className="mt-5 grid grid-cols-3 gap-2">
          {TABS.map((t) => {
            const isActive = t.key === tab;
            return (
              <button
                key={t.key}
                type="button"
                onClick={() => setTab(t.key)}
                className={`rounded-xl border px-3 py-2.5 text-left transition-all ${
                  isActive
                    ? `${t.ring} bg-white shadow-theme-xs dark:bg-white/[0.04]`
                    : "border-transparent bg-white/60 hover:bg-white dark:bg-white/[0.02] dark:hover:bg-white/[0.05]"
                }`}
              >
                <div
                  className={`text-xl font-semibold leading-none ${t.chip}`}
                >
                  {counts[t.key]}
                </div>
                <div className="mt-1 text-[11px] font-medium text-gray-500 dark:text-gray-400">
                  {t.label}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Body */}
      <div className="max-h-[60vh] overflow-y-auto px-6 py-5">
        {loading ? (
          <div className="flex h-40 items-center justify-center gap-2 text-sm text-gray-400 dark:text-gray-500">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-brand-500" />
            Loading day-wise detail...
          </div>
        ) : error ? (
          <div className="flex h-40 flex-col items-center justify-center gap-3">
            <span className="text-sm text-error-500">{error}</span>
            <button
              type="button"
              onClick={fetchDetail}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-white/5"
            >
              Try again
            </button>
          </div>
        ) : tab === "leave" ? (
          renderLeaves(data?.leaves ?? [])
        ) : (
          renderAttendanceTable(
            tab === "present" ? presentDays : absentDays,
            tab
          )
        )}
      </div>

      {/* Footer */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-gray-200 px-6 py-4 dark:border-gray-800">
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {tab === "leave"
            ? `${data?.leaves?.length ?? 0} leave request(s) touching ${monthLabel}`
            : `${
                (tab === "present" ? presentDays : absentDays).length
              } day(s) listed`}
          {tab !== "leave" && (
            <span className={`ml-1 font-medium ${active.chip}`}>
              · {active.label}
            </span>
          )}
        </span>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white shadow-theme-xs transition hover:bg-brand-600"
        >
          Close
        </button>
      </div>
    </Modal>
  );
}
