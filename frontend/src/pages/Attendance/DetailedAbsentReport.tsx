import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import EnhancedDataTable from "../../components/tables/DataTables/DataTableOne";
import axios from "../../api/axios"; // Adjust the import path as necessary
import { useState, useEffect } from "react";
import moment from "moment";
import _ from "lodash";
import { ToastContainer, toast } from "react-toastify";
import { ColumnDef } from "@tanstack/react-table";
import DatePicker from "../../components/form/date-picker";

type AttendanceRow = {
  date: string;
  section: string;
  total_employees: number;
  total_present: number;
  total_leave: number;
  total_official_work: number;
  total_absent: number;
  attendance_percentage: number;
  status: string;
};

export default function TeamLevel() {
  const [attendancedata, setAttendanceData] = useState<AttendanceRow[]>([]);
  const [fromdate, setFromdate] = useState<String>(
    moment().format("YYYY-MM-DD")
  );
  const [todate, setTodate] = useState<String>(moment().format("YYYY-MM-DD"));

  useEffect(() => {
    if (fromdate <= todate) {
      fetchAttendanceData();
    } else {
      toast.error("from date cannot be greater than to date");
    }
  }, [todate, fromdate]);

  const fetchAttendanceData = async () => {
    try {
      toast.loading(
        `Fetching attendance data from ${fromdate} to ${todate}`,
        { toastId: "attendance-fetch-success" }
      );

      const response = await axios.post(
        "/attendance/detailed-absent-report/",
        {
          fromdate,
          todate,
        }
      );

      const cleanedData: AttendanceRow[] = response.data.map((item: any) => {
        const totalEmployees = Number(item.total_employees);
        const totalPresent = Number(item.total_present);

        return {
          date: moment(item.date).format("DD-MM-YYYY"),
          section: item.section ?? "-",
          total_employees: totalEmployees,
          total_present: totalPresent,
          total_leave: Number(item.total_leave),
          total_official_work: Number(item.total_official_work),
          total_absent: Number(item.total_absent),
          // Share of the section that actually marked attendance that day.
          attendance_percentage: totalEmployees
            ? Math.round((totalPresent / totalEmployees) * 1000) / 10
            : 0,
          status: item.status,
        };
      });

      toast.dismiss("attendance-fetch-success");
      setAttendanceData(cleanedData);

    } catch (err) {
      toast.dismiss("attendance-fetch-success");
      console.error(err);
      toast.error("Failed to fetch attendance report.");
    }
  };

  const columns: ColumnDef<AttendanceRow>[] = [

    {
      accessorKey: "date",
      header: "Date",
    },

    {
      accessorKey: "section",
      header: "Section",
    },

    {
      accessorKey: "total_employees",
      header: "Total Employees",
    },

    {
      accessorKey: "total_present",
      header: "Present",

      cell: ({ getValue }) => {

        const value = getValue<number>();

        return (
          <span className="inline-flex items-center justify-center px-5 py-1 rounded-full font-semibold bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500">
            {value}
          </span>
        );

      }

    },

    {
      accessorKey: "total_leave",
      header: "Leave",

      cell: ({ getValue }) => {

        const value = getValue<number>();

        return (

          <span className="inline-flex items-center justify-center px-5 py-1 rounded-full font-semibold bg-warning-50 text-warning-600 dark:bg-warning-500/15 dark:text-warning-500">
            {value}
          </span>

        );

      }

    },

    {
      accessorKey: "total_official_work",
      header: "Official Work",

      cell: ({ getValue }) => {

        const value = getValue<number>();

        return (

          <span className="inline-flex items-center justify-center px-5 py-1 rounded-full font-semibold bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400">
            {value}
          </span>

        );

      }

    },

    {
      accessorKey: "total_absent",
      header: "Absent",

      cell: ({ getValue }) => {

        const value = getValue<number>();

        return (

          <span className="inline-flex items-center justify-center px-5 py-1 rounded-full font-semibold bg-error-50 text-error-600 dark:bg-error-500/15 dark:text-error-500">
            {value}
          </span>

        );

      }

    },

    {
      accessorKey: "attendance_percentage",
      header: "Attendance %",

      cell: ({ getValue }) => {

        const value = getValue<number>();

        const tone =
          value >= 90
            ? "bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500"
            : value >= 75
            ? "bg-warning-50 text-warning-600 dark:bg-warning-500/15 dark:text-warning-500"
            : "bg-error-50 text-error-600 dark:bg-error-500/15 dark:text-error-500";

        return (

          <span
            className={`inline-flex items-center justify-center px-4 py-1 rounded-full font-semibold ${tone}`}
          >
            {value.toFixed(1)}%
          </span>

        );

      }

    },

    {
      accessorKey: "status",
      header: "Summary",

      // The summary is a full sentence of badges; on paper the column is narrow
      // enough that they would stack into a tall vertical strip, so keep the
      // printed cell on a single line.
      meta: { getTdClassName: () => "print-nowrap" },

      cell: ({ row }) => {

        const present = row.original.total_present;
        const leave = row.original.total_leave;
        const official = row.original.total_official_work;
        const absent = row.original.total_absent;

        return (

          <div className="flex flex-wrap gap-2">

            <span className="inline-flex items-center px-3 py-1 rounded-full font-semibold bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500">
              Present : {present}
            </span>

            <span className="inline-flex items-center px-3 py-1 rounded-full font-semibold bg-warning-50 text-warning-600 dark:bg-warning-500/15 dark:text-warning-500">
              Leave : {leave}
            </span>

            <span className="inline-flex items-center px-3 py-1 rounded-full font-semibold bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400">
              Official Work : {official}
            </span>

            <span className="inline-flex items-center px-3 py-1 rounded-full font-semibold bg-error-50 text-error-600 dark:bg-error-500/15 dark:text-error-500">
              Absent : {absent}
            </span>

          </div>

        );

      }

    }

  ];

  return (
    <>
      <PageMeta
        title="ISMO - Detailed Attendance Summary Report"
        description="ISMO Admin Dashboard - Detailed Attendance Summary Report"
      />

      <PageBreadcrumb pageTitle="Detailed Attendance Summary Report" />
      <div className="space-y-6">
        <ComponentCard title={`Attendance on ${fromdate}`}>
          <ToastContainer position="bottom-right" />

          <div className="no-print flex justify-between items-center mb-4 gap-1">
            <div className="w-1/2">
              <DatePicker
                id="from-date-picker"
                defaultDate={fromdate.toString()}
                label="from date"
                placeholder="Select a date"
                onChange={(dates, currentDateString) => {
                  console.log(dates);
                  // Handle your logic
                  setFromdate(currentDateString);
                }}
              />
            </div>
            <div className="w-1/2">
              <DatePicker
                id="to-date-picker"
                defaultDate={todate.toString()}
                label="to date"
                placeholder="Select a date"
                onChange={(dates, currentDateString) => {
                  console.log(dates);
                  // Handle your logic
                  setTodate(currentDateString);
                }}
              />
            </div>
          </div>

          <div className="print-area">
            {/* Letterhead — only rendered on paper, where the page chrome and
                the card title are not printed. */}
            <div className="print-only mb-3 border-b border-gray-300 pb-2 text-center">
              <div className="text-[13pt] font-bold">
                Independent System &amp; Market Operator (ISMO)
              </div>
              <div className="text-[10pt] font-semibold">
                Detailed Attendance Summary Report
              </div>
              <div className="text-[7pt] text-gray-600">
                {moment(fromdate.toString()).format("DD-MMM-YYYY")} –{" "}
                {moment(todate.toString()).format("DD-MMM-YYYY")} · Generated{" "}
                {moment().format("DD-MMM-YYYY HH:mm")}
              </div>
            </div>

            <EnhancedDataTable<AttendanceRow>
              data={attendancedata}
              columns={columns}
              fromdate={fromdate.toString()}
              todate={todate.toString()}
              printable
              getExportHeaders={() => [
                "Date",
                "Section",
                "Total Employees",
                "Present",
                "Leave",
                "Official Work",
                "Absent",
                "Attendance %",
                "Summary",
              ]}
              getExportRows={(rows) =>
                rows.map((row) => [
                  row.date,
                  row.section,
                  row.total_employees,
                  row.total_present,
                  row.total_leave,
                  row.total_official_work,
                  row.total_absent,
                  `${row.attendance_percentage.toFixed(1)}%`,
                  row.status,
                ])
              }
            />
          </div>
        </ComponentCard>
      </div>
    </>
  );
}
