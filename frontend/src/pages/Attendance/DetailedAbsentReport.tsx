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
  total_absent: number;
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

    const cleanedData: AttendanceRow[] =
      response.data.map((item: any) => ({
        date: moment(item.date).format("DD-MM-YYYY"),
        section: item.section,
        total_employees: item.total_employees,
        total_present: item.total_present,
        total_absent: item.total_absent,
      }));

    toast.dismiss("attendance-fetch-success");

    setAttendanceData(cleanedData);

  } catch (err) {
    console.log(err);
  }
};
    
 
const columns: ColumnDef<AttendanceRow>[] = [

{
    accessorKey:"date",
    header:"Date",
},

{
    accessorKey:"section",
    header:"Section",
},

{
    accessorKey:"total_employees",
    header:"Total Employees",
},

{
    accessorKey:"total_present",
    header:"Present",

    cell:({getValue})=>{

        const value=getValue<number>();

        return(

            <span className="inline-flex items-center px-6 py-0.5 rounded-full font-semibold bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500">

                {value}

            </span>

        );

    }

},

{
    accessorKey:"total_absent",
    header:"Absent",

    cell:({getValue})=>{

        const value=getValue<number>();

        return(

            <span className="inline-flex items-center px-6 py-0.5 rounded-full font-semibold bg-danger-50 text-danger-600 dark:bg-danger-500/15 dark:text-danger-500">

                {value}

            </span>

        );

    }

}

];

  return (
    <>
      <PageMeta
        title="ISMO - Total Absent Attendance Report"
        description="ISMO Admin Dashboard - Total Absent Attendance Report"
      />
      <PageBreadcrumb pageTitle="Total Absent Attendance Report" />
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
