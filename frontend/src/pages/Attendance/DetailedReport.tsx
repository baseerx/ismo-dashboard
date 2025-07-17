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
    erp_id: string;
    name: string;
    designation: string;
    grade: string;
    section: string;
    checkout_time: string;
    checkin_time: string;
    timestamp: string;
    late: string;

};

export default function DetailedReport() {
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
                  `Fetching attendance data from ${fromdate} to ${todate}`,{toastId: "attendance-fetch-success"}
                );

      const response = await axios.post("/attendance/detailed/", {
        fromdate: fromdate,
        todate: todate,
      });

      // Ensure response.data is an array and format timestamp
      const cleanedData: AttendanceRow[] = response.data.map((item: any) => {
          const picked = {
            erp_id: item.erp_id,
            name: item.name,
            designation: item.designation,
            grade: item.grade,
            section: item.section,
            checkout_time:
              item.checkout_time && item.checkout_time !== '-'
                ? moment(item.checkout_time).format('YYYY-MM-DD HH:mm:ss')
                : "-",
            checkin_time:
              item.checkin_time && item.checkin_time !== '-'
                ? moment(item.checkin_time).format('YYYY-MM-DD HH:mm:ss')
                : "-",
            timestamp: moment(item.timestamp).format('DD-MM-YYYY'),
            late: item.late,
          };
        if (picked.timestamp && typeof picked.timestamp === "string") {
          picked.timestamp = picked.timestamp.replace("T", " ");
        }
        return picked;
      });
      toast.dismiss("attendance-fetch-success");
      setAttendanceData(cleanedData);
    } catch (error) {
      console.error("Error fetching attendance data:", error);
    }
  };
const columns: ColumnDef<AttendanceRow>[] = [
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
    accessorKey: "grade",
    header: "Grade",
  },
  {
    accessorKey: "section",
    header: "Section",
  },
  {
    accessorKey: "timestamp",
    header: "Date",
  },
  {
    accessorKey: "checkin_time",
    header: "Checkin Time",
  },
  {
    accessorKey: "checkout_time",
    header: "Checkout Time",
  },

  {
    accessorKey: "late",
    header: "Late Status",
  },
];

  return (
    <>
      <PageMeta
        title="ISMO - Attendance History"
        description="ISMO Admin Dashboard - Attendance History"
      />
      <PageBreadcrumb pageTitle="Attendance History" />
      <div className="space-y-6">
        <ComponentCard title={`Attendance on ${fromdate}`}>
          <ToastContainer position="bottom-right" />

          <div className="flex justify-between items-center mb-4 gap-1">
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

          <EnhancedDataTable<AttendanceRow>
            data={attendancedata}
                      columns={columns}
            fromdate={fromdate.toString()}
            todate={todate.toString()}
          />
        </ComponentCard>
      </div>
    </>
  );
}
