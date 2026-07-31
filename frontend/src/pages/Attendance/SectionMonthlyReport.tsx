import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import axios from "../../api/axios";
import { useState, useEffect, useMemo, useRef, Fragment } from "react";
import moment from "moment";
import { ToastContainer, toast } from "react-toastify";
import Label from "../../components/form/Label";
import Select from "../../components/form/Select";
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
  section: string;
  days: Record<string, DayCell>;
};

type SectionGroup = {
  section: string;
  employees: EmployeeMonthly[];
};

// Most senior employee of a section — the report shows them as the officer
// the section works under.
type SectionHead = {
  section_id: number;
  section: string;
  erp_id: string;
  name: string;
  designation: string;
  grade: string;
};

// Sentinel for the "every section" choice — the backend reads 0 as "no
// section filter" (see attendance_section_monthly).
const ALL_SECTIONS = "0";

// How many days go on one printed / exported page before the grid continues
// on the next. Keeps the type at a readable size instead of shrinking a whole
// month onto a single sheet.
const PRINT_DAYS_PER_PAGE = 8;

// Attendance timestamps come back as full datetimes; the grid only needs the time.
const fmtTime = (val: string) =>
  val && val !== "-" ? moment(val).format("HH:mm") : "-";

export default function SectionMonthlyReport() {
  const user = JSON.parse(localStorage.getItem("user") || "{}");

  const [month, setMonth] = useState<string>(moment().format("YYYY-MM"));
  const [rows, setRows] = useState<MonthlyRow[]>([]);
  const [heads, setHeads] = useState<SectionHead[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  // Default to the logged in user's own section, falling back to every
  // section when their profile has none.
  const [sectionId, setSectionId] = useState<string>(
    user.section_id ? String(user.section_id) : ALL_SECTIONS
  );
  const [sectionOptions, setSectionOptions] = useState<
    { label: string; value: string }[]
  >([{ label: "All Sections", value: ALL_SECTIONS }]);

  const monthInputRef = useRef<HTMLInputElement>(null);

  const monthStart = moment(month, "YYYY-MM");
  const daysInMonth = monthStart.daysInMonth();

  const days = useMemo(
    () => Array.from({ length: daysInMonth }, (_, i) => i + 1),
    [daysInMonth]
  );

  // Days per printed page. Eight days (17 columns with the employee column)
  // is what a landscape sheet holds at a readable body size — the rest of the
  // month continues on the following pages.
  const printDayChunks = useMemo(() => {
    const chunks: number[][] = [];
    for (let i = 0; i < days.length; i += PRINT_DAYS_PER_PAGE) {
      chunks.push(days.slice(i, i + PRINT_DAYS_PER_PAGE));
    }
    return chunks;
  }, [days]);

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
    fetchSections();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month, sectionId]);

  const fetchSections = async () => {
    try {
      const response = await axios.get("/sections/get/");
      setSectionOptions([
        { label: "All Sections", value: ALL_SECTIONS },
        ...(response.data || []).map((s: any) => ({
          label: s.name,
          value: String(s.id),
        })),
      ]);
    } catch (error) {
      console.error("Error fetching sections:", error);
      toast.error("Failed to load sections");
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const fromdate = monthStart.clone().startOf("month").format("YYYY-MM-DD");
      const todate = monthStart.clone().endOf("month").format("YYYY-MM-DD");
      const response = await axios.post("/attendance/section-monthly/", {
        erp_id: user.erpid,
        section_id: sectionId,
        fromdate,
        todate,
      });
      // The endpoint returns { records, heads }; tolerate the older bare-array
      // shape so a stale backend still renders the grid.
      const payload = response.data;
      setRows(Array.isArray(payload) ? payload : payload?.records || []);
      setHeads(Array.isArray(payload) ? [] : payload?.heads || []);
    } catch (error) {
      console.error("Error fetching section monthly report:", error);
      toast.error("Failed to load monthly report");
      setRows([]);
      setHeads([]);
    } finally {
      setLoading(false);
    }
  };

  // Pivot the flat (employee, day) rows into one record per employee keyed by
  // date, then bucket the employees under their section. The backend already
  // orders by section → grade → name, so insertion order is the report order.
  const sectionGroups: SectionGroup[] = useMemo(() => {
    const empMap = new Map<string, EmployeeMonthly>();
    const empOrder: string[] = [];

    for (const r of rows) {
      const key = String(r.erp_id);
      let emp = empMap.get(key);
      if (!emp) {
        emp = {
          erp_id: r.erp_id,
          name: r.name,
          designation: r.designation,
          grade: r.grade,
          section: r.section || "Unassigned",
          days: {},
        };
        empMap.set(key, emp);
        empOrder.push(key);
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

    const groups = new Map<string, EmployeeMonthly[]>();
    for (const key of empOrder) {
      const emp = empMap.get(key)!;
      if (!groups.has(emp.section)) groups.set(emp.section, []);
      groups.get(emp.section)!.push(emp);
    }

    return Array.from(groups, ([section, employees]) => ({
      section,
      employees,
    }));
  }, [rows]);

  const employees = useMemo(
    () => sectionGroups.flatMap((g) => g.employees),
    [sectionGroups]
  );

  // Only label rows with their section once more than one is on the report.
  const showSectionBands = sectionGroups.length > 1;

  const headBySection = useMemo(() => {
    const map = new Map<string, SectionHead>();
    for (const h of heads) if (!map.has(h.section)) map.set(h.section, h);
    return map;
  }, [heads]);

  // With a single section on the report its head heads the whole page.
  const primaryHead =
    sectionGroups.length === 1
      ? headBySection.get(sectionGroups[0].section)
      : undefined;

  const headRank = (h: SectionHead) =>
    [h.designation, h.grade].filter(Boolean).join(" · ");

  // Supervision block for the Excel / PDF headers: one line for a single
  // section, otherwise a "section — head" line per section on the report.
  const supervisionLines = (): string[] => {
    if (primaryHead) {
      return [
        `Under the supervision of: ${primaryHead.name} — ${headRank(
          primaryHead
        )}`,
      ];
    }
    return heads.map(
      (h) => `${h.section} — ${h.name}${h.grade ? ` (${h.grade})` : ""}`
    );
  };

  const sectionLabel =
    sectionId === ALL_SECTIONS
      ? "All Sections"
      : sectionOptions.find((o) => o.value === sectionId)?.label ||
        sectionGroups[0]?.section ||
        "";

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
    sectionLabel ? ` — ${sectionLabel}` : ""
  } (${monthStart.format("MMMM YYYY")})`;

  // The browser prints whatever is on screen, so force the light palette for
  // the duration of the dialog — white-on-white is unreadable on paper.
  const handlePrint = () => {
    const root = document.documentElement;
    if (!root.classList.contains("dark")) {
      window.print();
      return;
    }
    root.classList.remove("dark");
    const restore = () => {
      root.classList.add("dark");
      window.removeEventListener("afterprint", restore);
    };
    window.addEventListener("afterprint", restore);
    window.print();
  };

  const exportToExcel = () => {
    if (employees.length === 0) return;
    const header: string[] = ["Employee", "Designation", "Grade"];
    if (showSectionBands) header.push("Section");
    days.forEach((d) => {
      header.push(`Day ${d} In`);
      header.push(`Day ${d} Out`);
    });

    const body = employees.map((emp) => {
      const row: (string | number)[] = [emp.name, emp.designation, emp.grade];
      if (showSectionBands) row.push(emp.section);
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
      ...supervisionLines().map((line) => [line]),
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
    // A4 landscape: standard office paper, so nothing is scaled down by the
    // printer. The month runs over several pages instead of being squeezed
    // onto one oversized sheet.
    const doc = new jsPDF({ orientation: "landscape", unit: "pt", format: "a4" });

    doc.setFontSize(12);
    doc.text("Independent System & Market Operator (ISMO)", 20, 22);
    doc.setFontSize(10);
    doc.text(reportTitle, 20, 38);

    // Supervising head(s) sit between the title and the grid.
    const supervision = supervisionLines();
    let cursorY = 38;
    doc.setFontSize(8);
    supervision.forEach((line) => {
      cursorY += 11;
      doc.text(line, 20, cursorY);
    });

    const head = [
      [
        "Employee",
        ...(showSectionBands ? ["Section"] : []),
        ...days.map((d) => `D${d}`),
      ],
    ];
    const bodyRows = employees.map((emp) => {
      // Match the webpage: name on the first line, designation · grade beneath.
      const empInfo = [emp.designation, emp.grade].filter(Boolean).join(" · ");
      const row: string[] = [empInfo ? `${emp.name}\n${empInfo}` : emp.name];
      if (showSectionBands) row.push(emp.section);
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

    // Readable body text rather than a whole month squeezed onto one sheet:
    // autoTable carries the surplus day columns onto further pages, repeating
    // the employee (and section) columns so every page identifies its rows.
    const repeatColumns = showSectionBands ? [0, 1] : [0];

    // Day columns get a width that comfortably fits "On Time" on one line at
    // 8pt; that width is what pushes the surplus days onto the next page —
    // roughly PRINT_DAYS_PER_PAGE of them per sheet, matching the printout.
    const firstDayColumn = showSectionBands ? 2 : 1;
    const dayColumnStyles: Record<number, { cellWidth: number }> = {};
    days.forEach((_, i) => {
      dayColumnStyles[firstDayColumn + i] = { cellWidth: 62 };
    });

    autoTable(doc, {
      startY: cursorY + 12,
      head,
      body: bodyRows,
      theme: "grid",
      horizontalPageBreak: true,
      horizontalPageBreakRepeat: repeatColumns,
      // Finish every employee for one block of days before moving on to the
      // next block, so the PDF paginates the same way the printed page does.
      horizontalPageBreakBehaviour: "afterAllRows",
      styles: {
        fontSize: 8,
        cellPadding: 3,
        halign: "center",
        valign: "middle",
        overflow: "linebreak",
      },
      headStyles: { fillColor: [70, 95, 255], fontSize: 8, textColor: 255 },
      columnStyles: {
        0: { halign: "left", cellWidth: 130, fontStyle: "bold", fontSize: 8 },
        ...(showSectionBands
          ? { 1: { halign: "left", cellWidth: 90, fontSize: 8 } }
          : {}),
        ...dayColumnStyles,
      },
    });

    doc.setFontSize(9);
    doc.text(
      "Each day shows check-in time and status, then check-out time and status.",
      20,
      doc.internal.pageSize.getHeight() - 14
    );
    doc.save(`section_monthly_${month}.pdf`);
  };

  const renderEmployeeRow = (emp: EmployeeMonthly, dayList: number[]) => (
    <tr key={emp.erp_id} className="text-gray-700 dark:text-gray-300">
      <td className="sticky left-0 z-10 min-w-[180px] border-r border-gray-200 bg-white px-3 py-2 dark:border-gray-800 dark:bg-gray-900">
        <div className="font-medium text-gray-800 dark:text-white/90">
          {emp.name}
        </div>
        <div className="text-[11px] text-gray-400">
          {emp.designation}
          {emp.grade ? ` · ${emp.grade}` : ""}
        </div>
      </td>
      {dayList.map((d) => {
        const dateObj = monthStart.clone().date(d);
        const rec = emp.days[dayKey(d)];
        const isWeekend = [0, 6].includes(dateObj.day());
        const cellBg = isWeekend ? "bg-gray-50 dark:bg-white/[0.02]" : "";

        // Non-present days (leave, official work, holiday, weekend, future,
        // absent) show the status across both columns. The backend supplies
        // the label directly ("Weekend", "-" for not-yet-reached days, leave
        // type…).
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
              <span className={statusColor(flagType)}>{label}</span>
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
  );

  // The day-wise grid over a slice of the month. On screen it is called once
  // with the whole month inside a horizontal scroller; for print it is called
  // per slice so the text keeps a readable size and the month spills onto
  // further pages rather than being shrunk to fit one.
  const renderGrid = (dayList: number[]) => {
    const totalColumns = 1 + dayList.length * 2;

    return (
      <table className="print-grid min-w-full border-collapse text-xs">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-800">
            <th
              rowSpan={2}
              className="sticky left-0 z-10 min-w-[180px] border-r border-gray-200 bg-white px-3 py-2 text-left font-medium text-gray-700 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-300"
            >
              Employee
            </th>
            {dayList.map((d) => {
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
            {dayList.map((d) => (
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
          {sectionGroups.map((group) => (
            <Fragment key={group.section}>
              {showSectionBands && (
                <tr className="bg-gray-100 dark:bg-white/[0.06]">
                  <td colSpan={totalColumns} className="p-0">
                    {/* Sticky inner box keeps the section name in view while
                        the day columns scroll sideways. */}
                    <div className="sticky left-0 inline-block px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-gray-700 dark:text-gray-200">
                      {group.section}
                      <span className="ml-2 font-normal normal-case text-gray-400">
                        ({group.employees.length})
                      </span>
                      {headBySection.get(group.section) && (
                        <span className="ml-2 font-normal normal-case text-gray-500 dark:text-gray-400">
                          · Head: {headBySection.get(group.section)!.name}
                          {headBySection.get(group.section)!.grade
                            ? ` (${headBySection.get(group.section)!.grade})`
                            : ""}
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              )}
              {group.employees.map((emp) => renderEmployeeRow(emp, dayList))}
            </Fragment>
          ))}
        </tbody>
      </table>
    );
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
          title={`Monthly Attendance${sectionLabel ? ` — ${sectionLabel}` : ""}`}
          desc={monthStart.format("MMMM YYYY")}
        >
          <ToastContainer position="bottom-right" />

          <div className="no-print mb-4 flex flex-wrap items-end justify-between gap-3">
            <div className="flex w-full flex-wrap gap-3 sm:w-auto">
              <div className="w-full sm:w-56">
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

              <div className="w-full sm:w-64">
                <Label>Select Section</Label>
                <Select
                  options={sectionOptions}
                  value={sectionId}
                  placeholder="Select a section"
                  onChange={(value) => setSectionId(value)}
                  className="dark:bg-dark-900"
                />
                {/* Highest-graded employee of the chosen section. */}
                {primaryHead && (
                  <p className="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
                    <span className="text-gray-400">Section Head:</span>{" "}
                    <span className="font-medium text-gray-700 dark:text-gray-200">
                      {primaryHead.name}
                    </span>
                    {primaryHead.grade ? ` (${primaryHead.grade})` : ""}
                  </p>
                )}
              </div>
            </div>

            <div className="flex gap-2">
              <button
                onClick={handlePrint}
                disabled={employees.length === 0}
                className="rounded bg-brand-500 px-4 py-2 text-sm text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Print
              </button>
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
              No attendance data for {sectionLabel || "this section"} in{" "}
              {monthStart.format("MMMM YYYY")}.
            </div>
          ) : (
            <div className="print-area">
              {/* Letterhead — only rendered on paper, where the page chrome
                  and the card title are not printed. */}
              <div className="print-only mb-3 border-b border-gray-300 pb-2 text-center">
                <div className="text-[13pt] font-bold">
                  Independent System &amp; Market Operator (ISMO)
                </div>
                <div className="text-[10pt] font-semibold">{reportTitle}</div>
                <div className="text-[7pt] text-gray-600">
                  {employees.length} employee(s) ·{" "}
                  {sectionGroups.length > 1
                    ? `${sectionGroups.length} sections · `
                    : ""}
                  Generated {moment().format("DD-MMM-YYYY HH:mm")}
                </div>
              </div>

              {/* Who the report's section(s) answer to. */}
              {primaryHead ? (
                <div className="mb-4 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-800 dark:bg-white/[0.03]">
                  <div className="text-[10px] font-medium uppercase tracking-wide text-gray-400">
                    Under the supervision of
                  </div>
                  <div className="mt-0.5 text-sm font-semibold text-gray-800 dark:text-white/90">
                    {primaryHead.name}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    {headRank(primaryHead)}
                    {primaryHead.section ? ` — ${primaryHead.section}` : ""}
                  </div>
                </div>
              ) : (
                heads.length > 0 && (
                  <div className="mb-4 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-800 dark:bg-white/[0.03]">
                    <div className="text-[10px] font-medium uppercase tracking-wide text-gray-400">
                      Sections under supervision
                    </div>
                    <div className="mt-1 grid gap-x-6 gap-y-1 sm:grid-cols-2 lg:grid-cols-3">
                      {heads.map((h) => (
                        <div key={h.section_id} className="text-xs">
                          <span className="font-medium text-gray-700 dark:text-gray-200">
                            {h.section}
                          </span>
                          <span className="text-gray-500 dark:text-gray-400">
                            {" — "}
                            {h.name}
                            {h.grade ? ` (${h.grade})` : ""}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              )}

              {/* Screen: the whole month in one horizontally scrolling grid. */}
              <div className="no-print max-w-full overflow-x-auto custom-scrollbar">
                {renderGrid(days)}
              </div>

              {/* Paper: the same grid, sliced into page-width blocks so every
                  column prints at a legible size. Identical columns, headers
                  and cell contents — only the number of pages changes. */}
              <div className="print-only">
                {printDayChunks.map((chunk, i) => {
                  const first = monthStart.clone().date(chunk[0]);
                  const last = monthStart.clone().date(chunk[chunk.length - 1]);
                  return (
                    <div
                      key={chunk[0]}
                      className={
                        i < printDayChunks.length - 1 ? "print-page-break" : ""
                      }
                    >
                      <div className="mb-1 text-[8pt] font-semibold text-gray-700">
                        {first.format("DD MMM")} – {last.format("DD MMM YYYY")}
                        {printDayChunks.length > 1
                          ? ` · Part ${i + 1} of ${printDayChunks.length}`
                          : ""}
                      </div>
                      {renderGrid(chunk)}
                    </div>
                  );
                })}
              </div>

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
            </div>
          )}
        </ComponentCard>
      </div>
    </>
  );
}
