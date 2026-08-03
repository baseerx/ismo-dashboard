import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import EnhancedDataTable from "../../components/tables/DataTables/DataTableOne";
import axios from "../../api/axios";
import { useState, useEffect, useMemo } from "react";
import moment from "moment";
import { ToastContainer, toast } from "react-toastify";
import { ColumnDef } from "@tanstack/react-table";
import Label from "../../components/form/Label";
import Select from "../../components/form/Select";
import MonthlyAttendanceDetailModal, {
  DetailTab,
} from "./MonthlyAttendanceDetailModal";

type MonthlyRow = {
  erp_id: string;
  name: string;
  designation: string;
  department: string;
  location: string;
  is_shift: boolean;
  shift_names: string;
  shift_types: string;
  total_present: number;
  total_absent: number;
  approved_leaves: number;
};

type ShiftInfo = { shifts: string[]; types: string[] };

// How far back the year dropdown reaches. Attendance older than this is not
// worth offering — the picker stays short enough to scan at a glance.
const YEARS_BACK = 4;

export default function MonthlyAttendanceReport() {
  const now = moment();

  // Default to the running month, and pull its report straight away.
  const [month, setMonth] = useState<string>(now.format("MM"));
  const [year, setYear] = useState<string>(now.format("YYYY"));
  const [rows, setRows] = useState<MonthlyRow[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  // Shift roster for the selected month, keyed by ERP ID. Built from the same
  // endpoints the /attendance/shifts and /attendance/rcc-shift screens use.
  const [shiftMap, setShiftMap] = useState<Map<string, ShiftInfo>>(new Map());

  // The employee whose day-wise detail is open, and which tally was clicked.
  const [detailRow, setDetailRow] = useState<MonthlyRow | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>("present");

  const currentYear = now.year();
  const currentMonth = now.month(); // 0-based

  const yearOptions = useMemo(
    () =>
      Array.from({ length: YEARS_BACK + 1 }, (_, i) => {
        const y = String(currentYear - i);
        return { label: y, value: y };
      }),
    [currentYear]
  );

  // A future month of the running year would only ever report zeros, so the
  // list stops at the current month; past years offer all twelve.
  const monthOptions = useMemo(() => {
    const last = Number(year) === currentYear ? currentMonth : 11;
    return Array.from({ length: last + 1 }, (_, i) => ({
      label: moment().month(i).format("MMMM"),
      value: String(i + 1).padStart(2, "0"),
    }));
  }, [year, currentYear, currentMonth]);

  // Moving back to the current year from a past one can leave a month selected
  // that is no longer offered — fall back to the current month.
  useEffect(() => {
    if (!monthOptions.some((o) => o.value === month)) {
      setMonth(now.format("MM"));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [monthOptions]);

  const monthStart = useMemo(
    () => moment(`${year}-${month}`, "YYYY-MM"),
    [year, month]
  );

  useEffect(() => {
    fetchReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year, month]);

  /**
   * Who was rostered on a shift during the selected month.
   *
   * Walks every shift from /attendance/get-shifts and pulls its roster from
   * /attendance/shift-history — the same pair of calls behind the shift
   * screens, so this report agrees with them by construction. It also yields
   * the NCC / RCC type, which the summary query cannot know because that
   * split only exists in the SDXP roster.
   *
   * Never throws: a shift that fails simply contributes nothing, leaving the
   * summary's own is_shift flag as the answer for those employees.
   */
  const fetchShiftRoster = async (
    fromdate: string,
    todate: string
  ): Promise<Map<string, ShiftInfo>> => {
    const map = new Map<string, ShiftInfo>();
    try {
      const { data: shifts } = await axios.get("/attendance/get-shifts/");

      const rosters = await Promise.allSettled(
        (shifts || []).map((shift: any) =>
          axios.post("/attendance/shift-history/", {
            shiftid: shift.shift_id,
            fromdate,
            todate,
          })
        )
      );

      rosters.forEach((result) => {
        if (result.status !== "fulfilled") return;
        const members = result.value.data?.attendance ?? [];
        members.forEach((member: any) => {
          const key = String(member.erp_id ?? "").trim();
          if (!key) return;
          const entry = map.get(key) ?? { shifts: [], types: [] };
          if (member.shiftname && !entry.shifts.includes(member.shiftname)) {
            entry.shifts.push(member.shiftname);
          }
          if (member.shifttype && !entry.types.includes(member.shifttype)) {
            entry.types.push(member.shifttype);
          }
          map.set(key, entry);
        });
      });
    } catch (err) {
      // The rosters are a supplement, not a hard dependency — the report still
      // renders using whatever the summary reported.
      console.error("Shift roster lookup failed", err);
    }
    return map;
  };

  const fetchReport = async () => {
    setLoading(true);
    const fromdate = monthStart.clone().startOf("month").format("YYYY-MM-DD");
    const todate = monthStart.clone().endOf("month").format("YYYY-MM-DD");

    // Both in flight together — the roster must land with the summary so the
    // Shift column never renders a premature "No" and then flips to "Yes".
    const rosterPromise = fetchShiftRoster(fromdate, todate);

    try {
      const response = await axios.post("/attendance/monthly-summary/", {
        fromdate,
        todate,
      });

      const cleaned: MonthlyRow[] = (response.data || []).map((item: any) => ({
        erp_id: item.erp_id ?? "-",
        name: item.name ?? "-",
        designation: item.designation ?? "-",
        department: item.department ?? "-",
        location: item.location ?? "-",
        is_shift: Boolean(item.is_shift),
        shift_names: item.shift_names ?? "-",
        shift_types: "-",
        total_present: Number(item.total_present) || 0,
        total_absent: Number(item.total_absent) || 0,
        approved_leaves: Number(item.approved_leaves) || 0,
      }));

      setShiftMap(await rosterPromise);
      setRows(cleaned);
    } catch (err) {
      console.error(err);
      toast.error("Failed to fetch monthly attendance report.");
      setShiftMap(new Map());
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  // An employee counts as shift staff if either source says so: the roster
  // pulled from the shift screens, or the summary's own shift_user_map flag.
  // Older backends omit is_shift entirely, so the roster carries it alone.
  const tableRows = useMemo<MonthlyRow[]>(
    () =>
      rows.map((row) => {
        const info = shiftMap.get(String(row.erp_id).trim());
        if (!info) return row;
        return {
          ...row,
          is_shift: true,
          shift_names: info.shifts.length
            ? info.shifts.join(", ")
            : row.shift_names,
          shift_types: info.types.length ? info.types.join(", ") : "-",
        };
      }),
    [rows, shiftMap]
  );

  const openDetail = (row: MonthlyRow, tab: DetailTab) => {
    setDetailTab(tab);
    setDetailRow(row);
  };

  // Each of the three tallies opens the day-wise detail behind it, so the cell
  // is a button rather than a plain badge — the chevron only hints at that on
  // screen and is dropped from print.
  const countCell = (row: MonthlyRow, tab: DetailTab, value: number, tone: string) => (
    <button
      type="button"
      onClick={() => openDetail(row, tab)}
      title={`View day-wise detail for ${row.name}`}
      className={`group inline-flex items-center gap-1.5 rounded-full px-4 py-1 font-semibold transition-all hover:shadow-theme-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/40 ${tone}`}
    >
      {value}
      <svg
        className="no-print h-3 w-3 opacity-0 transition-opacity group-hover:opacity-70"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M9 18l6-6-6-6" />
      </svg>
    </button>
  );

  const columns: ColumnDef<MonthlyRow>[] = [
    {
      accessorKey: "erp_id",
      header: "ERP ID",
    },
    {
      accessorKey: "name",
      header: "Name",
    },
    {
      accessorKey: "designation",
      header: "Designation",
    },
    {
      accessorKey: "department",
      header: "Department",
    },
    {
      accessorKey: "location",
      header: "Location",
    },
    {
      accessorKey: "is_shift",
      header: "Shift",
      // Sort and filter on the word shown, not the raw boolean.
      accessorFn: (row) => (row.is_shift ? "Yes" : "No"),
      cell: ({ row }) => {
        const { is_shift: shift, shift_names, shift_types } = row.original;
        return (
          <span
            title={
              shift
                ? `Shift employee — ${shift_names}${
                    shift_types !== "-" ? ` (${shift_types})` : ""
                  }`
                : "Not on any shift roster"
            }
            className={`inline-flex items-center justify-center rounded-full px-3 py-1 font-semibold ${
              shift
                ? "bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-400"
                : "bg-gray-100 text-gray-500 dark:bg-white/5 dark:text-gray-400"
            }`}
          >
            {shift ? "Yes" : "No"}
          </span>
        );
      },
    },
    {
      accessorKey: "total_present",
      header: "Total Presents",
      cell: ({ row, getValue }) =>
        countCell(
          row.original,
          "present",
          getValue<number>(),
          "bg-success-50 text-success-600 hover:bg-success-100 dark:bg-success-500/15 dark:text-success-500 dark:hover:bg-success-500/25"
        ),
    },
    {
      accessorKey: "total_absent",
      header: "Total Absents",
      cell: ({ row, getValue }) =>
        countCell(
          row.original,
          "absent",
          getValue<number>(),
          "bg-error-50 text-error-600 hover:bg-error-100 dark:bg-error-500/15 dark:text-error-500 dark:hover:bg-error-500/25"
        ),
    },
    {
      accessorKey: "approved_leaves",
      header: "Approved Leaves",
      cell: ({ row, getValue }) =>
        countCell(
          row.original,
          "leave",
          getValue<number>(),
          "bg-warning-50 text-warning-600 hover:bg-warning-100 dark:bg-warning-500/15 dark:text-warning-500 dark:hover:bg-warning-500/25"
        ),
    },
  ];

  return (
    <>
      <PageMeta
        title="ISMO - Monthly Attendance Report"
        description="ISMO Admin Dashboard - Monthly Attendance Report"
      />

      <PageBreadcrumb pageTitle="Monthly Attendance Report" />
      <div className="space-y-6">
        <ComponentCard
          title="Monthly Attendance Report"
          desc={monthStart.format("MMMM YYYY")}
        >
          <ToastContainer position="bottom-right" />

          <div className="no-print mb-4 flex w-full flex-wrap gap-3">
            <div className="w-full sm:w-56">
              <Label>Select Month</Label>
              <Select
                options={monthOptions}
                value={month}
                placeholder="Select a month"
                onChange={(value) => setMonth(value)}
                className="dark:bg-dark-900"
              />
            </div>

            <div className="w-full sm:w-40">
              <Label>Select Year</Label>
              <Select
                options={yearOptions}
                value={year}
                placeholder="Select a year"
                onChange={(value) => setYear(value)}
                className="dark:bg-dark-900"
              />
            </div>
          </div>

          {loading ? (
            <div className="flex h-40 items-center justify-center text-sm text-gray-400 dark:text-gray-500">
              Loading monthly attendance report...
            </div>
          ) : (
            <div className="print-area">
              {/* Letterhead — only rendered on paper, where the page chrome and
                  the card title are not printed. */}
              <div className="print-only mb-3 border-b border-gray-300 pb-2 text-center">
                <div className="text-[13pt] font-bold">
                  Independent System &amp; Market Operator (ISMO)
                </div>
                <div className="text-[10pt] font-semibold">
                  Monthly Attendance Report — {monthStart.format("MMMM YYYY")}
                </div>
                <div className="text-[7pt] text-gray-600">
                  {tableRows.length} employee(s) · Generated{" "}
                  {moment().format("DD-MMM-YYYY HH:mm")}
                </div>
              </div>

              <EnhancedDataTable<MonthlyRow>
                data={tableRows}
                columns={columns}
                fromdate={monthStart.clone().startOf("month").format("YYYY-MM-DD")}
                todate={monthStart.clone().endOf("month").format("YYYY-MM-DD")}
                printable
                getExportHeaders={() => [
                  "ERP ID",
                  "Name",
                  "Designation",
                  "Department",
                  "Location",
                  "Shift",
                  "Total Presents",
                  "Total Absents",
                  "Approved Leaves",
                ]}
                getExportRows={(data) =>
                  data.map((row) => [
                    row.erp_id,
                    row.name,
                    row.designation,
                    row.department,
                    row.location,
                    row.is_shift ? "Yes" : "No",
                    row.total_present,
                    row.total_absent,
                    row.approved_leaves,
                  ])
                }
              />

              <div className="mt-3 text-[11px] text-gray-500 dark:text-gray-400">
                Every working day of the month counts once — present, then
                approved leave, then official work, holiday or weekend, and
                anything left over as absent. Days still to come are not
                counted as absent.{" "}
                <span className="no-print">
                  Click any tally to see the days behind it.
                </span>
              </div>
            </div>
          )}
        </ComponentCard>
      </div>

      <MonthlyAttendanceDetailModal
        isOpen={detailRow !== null}
        onClose={() => setDetailRow(null)}
        employee={detailRow}
        initialTab={detailTab}
        fromdate={monthStart.clone().startOf("month").format("YYYY-MM-DD")}
        todate={monthStart.clone().endOf("month").format("YYYY-MM-DD")}
        monthLabel={monthStart.format("MMMM YYYY")}
      />
    </>
  );
}
