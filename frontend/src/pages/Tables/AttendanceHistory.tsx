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
  checkinout: string;
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
     console.log("Response from API:", response.data);
    // Ensure response.data is an array and format timestamp
    const cleanedData: AttendanceRow[] = response.data.map((item: any) => {
      const picked = _.pick(item, ["name", "status", "timestamp", "checkinout"]);
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
    { accessorKey: "name", header: "Name" },
    { accessorKey: "status", header: "Status" },
    { accessorKey: "timestamp", header: "Timestamp" },
    { accessorKey: "checkinout", header: "CheckInOut" },
  ];


  return (
    <>
      <PageMeta
        title="ISMO - Today's Attendance"
        description="ISMO Admin Dashboard - Today's Attendance"
      />
      <PageBreadcrumb pageTitle="Today's Attendance" />
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
