import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import EnhancedDataTable from "../../components/tables/DataTables/DataTableOne";
import axios from "../../api/axios"; // Adjust the import path as necessary
import { useState, useEffect } from "react";
import moment from "moment";
import _ from "lodash";

import { ColumnDef } from "@tanstack/react-table";
import DatePicker from "../../components/form/date-picker";
      
    type AttendanceRow = {
  name: string;
  status: string;
  timestamp: string;
    
        flag: string;
        late: string;
    };

export default function DataTable() {
const [attendancedata, setAttendanceData] = useState<AttendanceRow[]>([]);
const [selectedDate, setSelectedDate] = useState<String>(moment().format("YYYY-MM-DD"));
    
    useEffect(() => {
        
        fetchAttendanceData();
    }, [selectedDate]);
    
    
  const fetchAttendanceData = async () => {
    try {
        const response = await axios.post("/attendance/history/", {
        date: selectedDate});
  
    // Ensure response.data is an array and format timestamp
        const cleanedData: AttendanceRow[] = response.data.map((item: any) => {
       
      const picked = _.pick(item, ["name", "status", "timestamp", "flag","late"]);
      if (picked.timestamp && typeof picked.timestamp === "string") {
        picked.timestamp = picked.timestamp.replace("T", " ");
      }
      return picked;
    });
      setAttendanceData(cleanedData);
    } catch (error) {
      console.error("Error fetching attendance data:", error);
    }
  };
    
     
 const columns: ColumnDef<AttendanceRow>[] = [
     {
         accessorKey: "name",
         header: "Name",
     },
     {
         accessorKey: "status",
         header: "Status",
     },
     {
         accessorKey: "timestamp",
         header: "Timestamp",
     },
     {
         accessorKey: "flag",
         header: "Present/Absent",
     },
     {
   accessorKey: "late",
   header: "Late/On Time",
   cell: ({ getValue }) => {
     const value = getValue<string>();
     const color =
       value?.toLowerCase() === "late"
         ? "inline-flex items-center px-6 py-0.5 justify-center gap-1 rounded-full font-semibold text-theme-lg bg-warning-50 text-warning-600 dark:bg-warning-500/15 dark:text-warning-500"
         : value?.toLowerCase() === "on time"
         ? "inline-flex items-center px-6 py-0.5 justify-center gap-1 rounded-full font-semibold text-theme-lg bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500"
         : "";
     return <span className={color}>{value}</span>;
   },
   meta: {
     getTdClassName: (value: string) =>
       value?.toLowerCase() === "late"
         ? "bg-gray-50"
         : value?.toLowerCase() === "on time"
         ? "bg-gray-50"
         : "",
         },
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
        <ComponentCard
          title={`Attendance on ${selectedDate}`}
              >
           <DatePicker
                       id="attendance-date-picker"
                       defaultDate={selectedDate.toString()}
                       placeholder="Select a date"
                      onChange={(dates, currentDateString) => {
                         // Handle your logic
                         setSelectedDate(currentDateString)
                       }}
                     />
                  
          <EnhancedDataTable<AttendanceRow>
            data={attendancedata}
            columns={columns}
          />
        </ComponentCard>
      </div>
    </>
  );
}
