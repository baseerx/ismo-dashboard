import { useEffect, useState } from "react";
import moment from "moment";
import { ToastContainer } from "react-toastify";
import { ColumnDef } from "@tanstack/react-table";
import PageBreadcrumb from "../common/PageBreadCrumb";
import ComponentCard from "../common/ComponentCard";
import PageMeta from "../common/PageMeta";
import EnhancedDataTable from "../tables/DataTables/DataTableOne";
import DateField from "../form/DateField";
import Label from "../form/Label";
import Select from "../form/Select";
import axios from "../../api/axios";

/**
 * Attendance over a date range for one group of employees - a section or an
 * office location - with one row per employee.
 *
 * Days is the number of calendar days in the range. Check-ins and check-outs
 * count the days on which the employee checked in or out, and the averages are
 * the mean time of the day's first check-in and last check-out over those days
 * (attendance/views.py, summarize_by_employee). Shared by the Section and
 * Location reports so the two always work the same way.
 */

// Kept in step with SECTION_REPORT_MAX_DAYS in attendance/views.py.
const MAX_DAYS = 93;

export type GroupKind = {
  /** "Section" or "Location": the filter's label and the page's name. */
  noun: string;
  /** Where the dropdown's choices come from: [{id, name}]. */
  optionsUrl: string;
  /** The employees field that holds the signed-in user's own group. */
  employeeField: "section_id" | "location_id";
  /** The report endpoint and the request field carrying the chosen id. */
  reportUrl: string;
  requestField: "section" | "location";
};

type AttendanceRow = {
  erp_id: string;
  name: string;
  designation: string;
  grade: string;
  section: string;
  days: number;
  checkin_count: number;
  checkout_count: number;
  avg_checkin: string;
  avg_checkout: string;
};

const today = () => moment().format("YYYY-MM-DD");

const columns: ColumnDef<AttendanceRow>[] = [
  { accessorKey: "erp_id", header: "ERP ID" },
  { accessorKey: "name", header: "Name" },
  { accessorKey: "designation", header: "Designation" },
  { accessorKey: "grade", header: "Grade" },
  { accessorKey: "section", header: "Section" },
  { accessorKey: "days", header: "Days" },
  { accessorKey: "checkin_count", header: "Check-ins" },
  { accessorKey: "checkout_count", header: "Check-outs" },
  { accessorKey: "avg_checkin", header: "Avg Check-in" },
  { accessorKey: "avg_checkout", header: "Avg Check-out" },
];

const EXPORT_HEADERS = [
  "ERP ID", "Name", "Designation", "Grade", "Section", "Days", "Check-ins", "Check-outs",
  "Avg Check-in", "Avg Check-out",
];

export default function GroupAttendanceReport({ kind }: { kind: GroupKind }) {
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const [rows, setRows] = useState<AttendanceRow[]>([]);
  const [group, setGroup] = useState("");
  const [fromDate, setFromDate] = useState(today());
  const [toDate, setToDate] = useState(today());
  const [options, setOptions] = useState<{ value: string; label: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    axios
      .get(kind.optionsUrl)
      .then((response) =>
        setOptions(
          (Array.isArray(response.data) ? response.data : []).map((item: any) => ({
            value: String(item.id),
            label: item.name,
          }))
        )
      )
      .catch(() => setProblem(`The ${kind.noun.toLowerCase()} list could not be loaded`));
  }, [kind.optionsUrl, kind.noun]);

  // Default to the signed-in user's own section / location (from the employee
  // list, since the stored user object does not carry it).
  useEffect(() => {
    axios
      .get("/users/employees/")
      .then((response) => {
        const self = (response.data || []).find(
          (e: any) => Number(e.erp_id) === Number(user.erpid)
        );
        if (self && self[kind.employeeField] != null) setGroup(String(self[kind.employeeField]));
      })
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind.employeeField]);

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
    if (!group) return;
    const invalid = rangeProblem();
    setProblem(invalid);
    if (invalid) {
      setRows([]);
      return;
    }
    fetchAttendance();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fromDate, toDate, group]);

  const fetchAttendance = async () => {
    setLoading(true);
    try {
      const response = await axios.post(kind.reportUrl, {
        [kind.requestField]: group,
        fromdate: fromDate,
        todate: toDate,
      });
      setRows(
        (Array.isArray(response.data) ? response.data : []).map((item: any) => ({
          erp_id: item.erp_id,
          name: item.name,
          designation: item.designation ?? "-",
          grade: item.grade ?? "-",
          section: item.section ?? "-",
          days: item.days,
          checkin_count: item.checkin_count,
          checkout_count: item.checkout_count,
          avg_checkin: item.avg_checkin,
          avg_checkout: item.avg_checkout,
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

  const groupName = options.find((option) => option.value === group)?.label;
  const range =
    fromDate === toDate
      ? moment(fromDate).format("DD MMM YYYY")
      : `${moment(fromDate).format("DD MMM YYYY")} to ${moment(toDate).format("DD MMM YYYY")}`;
  const noun = kind.noun.toLowerCase();

  return (
    <>
      <PageMeta
        title={`ISMO - ${kind.noun} Attendance Report`}
        description={`ISMO Admin Dashboard - ${kind.noun} Attendance Report`}
      />
      <PageBreadcrumb pageTitle={`${kind.noun} Attendance Report`} />
      <div className="space-y-6">
        <ComponentCard
          title={`Attendance ${groupName ? `of ${groupName} ` : ""}- ${range}`}
          desc="One row per employee. Days counts the days in the range; check-ins and check-outs count the days each was recorded; averages use the first check-in and last check-out of each day."
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
              <Label>{kind.noun}</Label>
              <div id={`${kind.requestField}-select`}>
                <Select
                  options={options}
                  placeholder={`Select a ${noun}`}
                  value={group}
                  onChange={setGroup}
                  className="dark:bg-dark-900"
                />
              </div>
            </div>
          </div>

          {problem ? (
            <p
              className="mb-4 rounded-lg border border-warning-200 bg-warning-50 px-4 py-3 text-sm text-warning-700 dark:border-warning-500/30 dark:bg-warning-500/10 dark:text-warning-400"
              data-report-problem
            >
              {problem}
            </p>
          ) : null}

          {loading ? (
            <p className="py-8 text-center text-sm text-gray-400">Loading attendance...</p>
          ) : !group ? (
            <p className="py-8 text-center text-sm text-gray-500">
              Choose a {noun} to see its attendance.
            </p>
          ) : (
            <EnhancedDataTable<AttendanceRow>
              data={rows}
              columns={columns}
              getExportHeaders={() => EXPORT_HEADERS}
              getExportRows={(data) =>
                data.map((row) => [
                  row.erp_id, row.name, row.designation, row.grade, row.section, row.days,
                  row.checkin_count, row.checkout_count, row.avg_checkin, row.avg_checkout,
                ])
              }
            />
          )}
        </ComponentCard>
      </div>
    </>
  );
}
