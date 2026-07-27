import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import axios from "../../api/axios";
import { useState, useEffect, useMemo, useRef, Fragment } from "react";
import moment from "moment";
import { ToastContainer, toast } from "react-toastify";
import Label from "../../components/form/Label";
import flatpickr from "flatpickr";
import monthSelectPlugin from "flatpickr/dist/plugins/monthSelect";
import "flatpickr/dist/flatpickr.css";
import "flatpickr/dist/plugins/monthSelect/style.css";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import * as XLSX from "xlsx";

type MonthlyRow = {
  erp_id: string;
  name: string;
  designation: string;
  grade: string;
  section: string;
  date: string;
  checkin_time: string;
  checkout_time: string;
  late_status: string;
  early_status: string;
  flag: string;
  flag_type: string;
};

type DayCell = {
  checkin: string;
  checkout: string;
  lateStatus: string;
  earlyStatus: string;
  flag: string;
  flagType: string;
};

type EmployeeMonthly = {
  erp_id: string;
  name: string;
  designation: string;
  grade: string;
  days: Record<string, DayCell>;
};

// Attendance timestamps come back as full datetimes; the grid only needs the time.
const fmtTime = (val: string) =>
  val && val !== "-" ? moment(val).format("HH:mm") : "-";

export default function SectionMonthlyReport() {
  const user = JSON.parse(localStorage.getItem("user") || "{}");

  const [month, setMonth] = useState<string>(moment().format("YYYY-MM"));
  const [rows, setRows] = useState<MonthlyRow[]>([]);
  const [section, setSection] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  const monthInputRef = useRef<HTMLInputElement>(null);

  const monthStart = moment(month, "YYYY-MM");
  const daysInMonth = monthStart.daysInMonth();
  const days = useMemo(
    () => Array.from({ length: daysInMonth }, (_, i) => i + 1),
    [daysInMonth]
  );

  // Calendar-style month/year picker — the user can navigate to any month,
  // including upcoming ones, without maintaining a fixed dropdown list.
  useEffect(() => {
    if (!monthInputRef.current) return;
    const fp = flatpickr(monthInputRef.current, {
      defaultDate: moment(month, "YYYY-MM").toDate(),
      plugins: [
        monthSelectPlugin({
          shorthand: false,
          dateFormat: "F Y",
          altFormat: "F Y",
          theme: "light",
        }),
      ],
      onChange: (dates) => {
        if (dates && dates[0]) setMonth(moment(dates[0]).format("YYYY-MM"));
      },
    });
    return () => {
      if (!Array.isArray(fp)) fp.destroy();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const fromdate = monthStart.clone().startOf("month").format("YYYY-MM-DD");
      const todate = monthStart.clone().endOf("month").format("YYYY-MM-DD");
      const response = await axios.post("/attendance/section-monthly/", {
        erp_id: user.erpid,
        fromdate,
        todate,
      });
      const data: MonthlyRow[] = response.data || [];
      setRows(data);
      setSection(data.length > 0 ? data[0].section || "" : "");
    } catch (error) {
      console.error("Error fetching section monthly report:", error);
      toast.error("Failed to load monthly report");
      setRows([]);
      setSection("");
    } finally {
      setLoading(false);
    }
  };

  // Pivot the flat (employee, day) rows into one record per employee keyed by date.
  const employees: EmployeeMonthly[] = useMemo(() => {
    const map = new Map<string, EmployeeMonthly>();
    for (const r of rows) {
      let emp = map.get(r.erp_id);
      if (!emp) {
        emp = {
          erp_id: r.erp_id,
          name: r.name,
          designation: r.designation,
          grade: r.grade,
          days: {},
        };
        map.set(r.erp_id, emp);
      }
      const dayKey = moment(r.date).format("YYYY-MM-DD");
      emp.days[dayKey] = {
        checkin: fmtTime(r.checkin_time),
        checkout: fmtTime(r.checkout_time),
        lateStatus: r.late_status,
        earlyStatus: r.early_status,
        flag: r.flag,
        flagType: r.flag_type,
      };
    }
    return Array.from(map.values());
  }, [rows]);

  const dayKey = (d: number) => monthStart.clone().date(d).format("YYYY-MM-DD");

  // Text color for a non-present day status (leave / official / holiday / etc.).
  const statusColor = (t: string) =>
    t === "leave"
      ? "text-warning-600 dark:text-warning-500"
      : t === "official"
      ? "text-blue-light-500"
      : t === "holiday"
      ? "text-gray-500 dark:text-gray-400"
      : t === "absent"
      ? "text-error-600 dark:text-error-500"
      : "text-gray-400 dark:text-gray-600"; // weekend / fallback
  const reportTitle = `Section Monthly Attendance${
    section ? ` — ${section}` : ""
  } (${monthStart.format("MMMM YYYY")})`;

  const exportToExcel = () => {
    if (employees.length === 0) return;
    const header: string[] = ["Employee", "Designation", "Grade"];
    days.forEach((d) => {
      header.push(`Day ${d} In`);
      header.push(`Day ${d} Out`);
    });

    const body = employees.map((emp) => {
      const row: (string | number)[] = [emp.name, emp.designation, emp.grade];
      days.forEach((d) => {
        const rec = emp.days[dayKey(d)];
        if (!rec || rec.flagType !== "present") {
          // Leave / official work / holiday / weekend / absent in the "In" column.
          row.push(rec ? rec.flag : "-", "");
          return;
        }
        const inCell =
          rec.checkin !== "-"
            ? `${rec.checkin}${rec.lateStatus === "Late" ? " (Late)" : ""}`
            : "-";
        const outCell =
          rec.checkout !== "-"
            ? `${rec.checkout}${rec.earlyStatus === "Early" ? " (Early)" : ""}`
            : "-";
        row.push(inCell, outCell);
      });
      return row;
    });

    const wsData = [
      ["Independent System & Market Operator (ISMO)"],
      [reportTitle],
      [],
      header,
      ...body,
    ];
    const worksheet = XLSX.utils.aoa_to_sheet(wsData);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Monthly");
    XLSX.writeFile(workbook, `section_monthly_${month}.xlsx`);
  };

  const exportToPDF = () => {
    if (employees.length === 0) return;
    const doc = new jsPDF({ orientation: "landscape", unit: "pt", format: "a3" });

    doc.setFontSize(12);
    doc.text("Independent System & Market Operator (ISMO)", 20, 22);
    doc.setFontSize(10);
    doc.text(reportTitle, 20, 38);

    const head = [["Employee", ...days.map((d) => `D${d}`)]];
    const bodyRows = employees.map((emp) => {
      // Match the webpage: name on the first line, designation · grade beneath.
      const empInfo = [emp.designation, emp.grade].filter(Boolean).join(" · ");
      const row: string[] = [empInfo ? `${emp.name}\n${empInfo}` : emp.name];
      days.forEach((d) => {
        const rec = emp.days[dayKey(d)];
        if (!rec || rec.flagType !== "present") {
          row.push(rec ? rec.flag : "-");
          return;
        }
        // Match the webpage: check-in time with its late/on-time status, then
        // check-out time with its early/on-time status — all shown as text.
        const cellLines: string[] = [];
        if (rec.checkin !== "-") {
          cellLines.push(rec.checkin);
          if (rec.lateStatus) cellLines.push(rec.lateStatus);
        } else {
          cellLines.push("-");
        }
        if (rec.checkout !== "-") {
          cellLines.push(rec.checkout);
          if (rec.earlyStatus) cellLines.push(rec.earlyStatus);
        } else {
          cellLines.push("-");
        }
        row.push(cellLines.join("\n"));
      });
      return row;
    });

    autoTable(doc, {
      startY: 50,
      head,
      body: bodyRows,
      theme: "grid",
      styles: { fontSize: 5, cellPadding: 1, halign: "center", valign: "middle" },
      headStyles: { fillColor: [70, 95, 255], fontSize: 5, textColor: 255 },
      columnStyles: {
        0: { halign: "left", cellWidth: 120, fontStyle: "bold", fontSize: 6 },
      },
    });

    doc.setFontSize(8);
    doc.text(
      "Each day shows check-in time and status, then check-out time and status.",
      20,
      doc.internal.pageSize.getHeight() - 14
    );
    doc.save(`section_monthly_${month}.pdf`);
  };

  return (
    <>
      <PageMeta
        title="ISMO - Section Monthly Report"
        description="ISMO Admin Dashboard - Section Monthly Attendance Report"
      />
      <PageBreadcrumb pageTitle="Section Monthly Report" />
      <div className="space-y-6">
        <ComponentCard
          title={`Monthly Attendance${section ? ` — ${section}` : ""}`}
          desc={monthStart.format("MMMM YYYY")}
        >
          <ToastContainer position="bottom-right" />

          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div className="w-full sm:w-1/3">
              <Label htmlFor="month-picker">Select Month</Label>
              <div className="relative">
                <input
                  id="month-picker"
                  ref={monthInputRef}
                  placeholder="Select a month"
                  readOnly
                  className="h-11 w-full appearance-none rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/20 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30"
                />
              </div>
            </div>

            <div className="flex gap-2">
              <button
                onClick={exportToExcel}
                disabled={employees.length === 0}
                className="rounded bg-green-600 px-4 py-2 text-sm text-white hover:bg-green-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Export Excel
              </button>
              <button
                onClick={exportToPDF}
                disabled={employees.length === 0}
                className="rounded bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Export PDF
              </button>
            </div>
          </div>

          {loading ? (
            <div className="flex h-40 items-center justify-center text-sm text-gray-400 dark:text-gray-500">
              Loading monthly report...
            </div>
          ) : employees.length === 0 ? (
            <div className="flex h-40 items-center justify-center text-sm text-gray-400 dark:text-gray-500">
              No attendance data for {monthStart.format("MMMM YYYY")}.
            </div>
          ) : (
            <div className="max-w-full overflow-x-auto custom-scrollbar">
              <table className="min-w-full border-collapse text-xs">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-800">
                    <th
                      rowSpan={2}
                      className="sticky left-0 z-10 min-w-[180px] border-r border-gray-200 bg-white px-3 py-2 text-left font-medium text-gray-700 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-300"
                    >
                      Employee
                    </th>
                    {days.map((d) => {
                      const dateObj = monthStart.clone().date(d);
                      const isWeekend = [0, 6].includes(dateObj.day());
                      return (
                        <th
                          key={d}
                          colSpan={2}
                          className={`border-l border-gray-200 px-2 py-1.5 text-center font-medium dark:border-gray-800 ${
                            isWeekend
                              ? "text-error-500"
                              : "text-gray-700 dark:text-gray-300"
                          }`}
                        >
                          Day {d}
                          <div className="text-[10px] font-normal text-gray-400">
                            {dateObj.format("ddd")}
                          </div>
                        </th>
                      );
                    })}
                  </tr>
                  <tr className="border-b border-gray-200 text-[10px] uppercase text-gray-400 dark:border-gray-800">
                    {days.map((d) => (
                      <Fragment key={d}>
                        <th className="border-l border-gray-100 px-2 py-1 font-medium dark:border-gray-800">
                          In
                        </th>
                        <th className="px-2 py-1 font-medium">Out</th>
                      </Fragment>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {employees.map((emp) => (
                    <tr
                      key={emp.erp_id}
                      className="text-gray-700 dark:text-gray-300"
                    >
                      <td className="sticky left-0 z-10 min-w-[180px] border-r border-gray-200 bg-white px-3 py-2 dark:border-gray-800 dark:bg-gray-900">
                        <div className="font-medium text-gray-800 dark:text-white/90">
                          {emp.name}
                        </div>
                        <div className="text-[11px] text-gray-400">
                          {emp.designation}
                          {emp.grade ? ` · ${emp.grade}` : ""}
                        </div>
                      </td>
                      {days.map((d) => {
                        const dateObj = monthStart.clone().date(d);
                        const rec = emp.days[dayKey(d)];
                        const isWeekend = [0, 6].includes(dateObj.day());
                        const cellBg = isWeekend
                          ? "bg-gray-50 dark:bg-white/[0.02]"
                          : "";

                        // Non-present days (leave, official work, holiday,
                        // weekend, future, absent) show the status across both
                        // columns. The backend supplies the label directly
                        // ("Weekend", "-" for not-yet-reached days, leave type…).
                        if (!rec || rec.flagType !== "present") {
                          const flagType = rec?.flagType || "future";
                          const label = rec?.flag || "-";
                          return (
                            <td
                              key={d}
                              colSpan={2}
                              title={rec?.flag}
                              className={`border-l border-gray-100 px-2 py-2 text-center align-middle text-[10px] dark:border-gray-800 ${cellBg}`}
                            >
                              <span className={statusColor(flagType)}>
                                {label}
                              </span>
                            </td>
                          );
                        }

                        return (
                          <Fragment key={d}>
                            <td
                              className={`whitespace-nowrap border-l border-gray-100 px-2 py-2 text-center align-top dark:border-gray-800 ${cellBg}`}
                            >
                              <div className="leading-tight">
                                <div className="text-gray-800 dark:text-white/90">
                                  {rec.checkin !== "-" ? rec.checkin : "–"}
                                </div>
                                {rec.checkin !== "-" && (
                                  <div
                                    className={`text-[9px] ${
                                      rec.lateStatus === "Late"
                                        ? "text-warning-500"
                                        : "text-success-600 dark:text-success-500"
                                    }`}
                                  >
                                    {rec.lateStatus}
                                  </div>
                                )}
                              </div>
                            </td>
                            <td
                              className={`whitespace-nowrap px-2 py-2 text-center align-top ${cellBg}`}
                            >
                              <div className="leading-tight">
                                <div className="text-gray-800 dark:text-white/90">
                                  {rec.checkout !== "-" ? rec.checkout : "–"}
                                </div>
                                {rec.checkout !== "-" && (
                                  <div
                                    className={`text-[9px] ${
                                      rec.earlyStatus === "Early"
                                        ? "text-error-500"
                                        : "text-success-600 dark:text-success-500"
                                    }`}
                                  >
                                    {rec.earlyStatus}
                                  </div>
                                )}
                              </div>
                            </td>
                          </Fragment>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {employees.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-4 text-[11px] text-gray-500 dark:text-gray-400">
              <span className="inline-flex items-center gap-1">
                <span className="inline-block h-2 w-2 rounded-full bg-success-500" />
                On Time
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="inline-block h-2 w-2 rounded-full bg-warning-500" />
                Late in / Leave
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="inline-block h-2 w-2 rounded-full bg-error-500" />
                Early out / Absent
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="inline-block h-2 w-2 rounded-full bg-blue-light-500" />
                Official Work
              </span>
              <span>Weekends are shaded.</span>
            </div>
          )}
        </ComponentCard>
      </div>
    </>
  );
}
