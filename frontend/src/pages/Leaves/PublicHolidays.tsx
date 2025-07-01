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
import Input from "../../components/form/input/InputField";
import TextArea from "../../components/form/input/TextArea";
import Button from "../../components/ui/button/Button";
      
    type AttendanceRow = {
  name: string;
  status: string;
  timestamp: string;
        checkinout: string;
        flag: string;
        late: string;
};

type HolidayData = {
    date: string;
    name: string;
    description: string;
};

export default function PublicHoliday() {
const [attendancedata, setAttendanceData] = useState<AttendanceRow[]>([]);
    

    const [holidayData, setHolidayData] = useState<HolidayData>({ date:moment().format('YYYY-MM-DD'), name: "", description: "" });
    const [fielderror, setFieldError] = useState<HolidayData>({
        date: "",
        name: "",
        description: ""
    });
    useEffect(() => {
        
        fetchAttendanceData();
    }, []);
    

    const handleSubmit = async () => {
       if (!holidayData.date || !holidayData.name || !holidayData.description) {
            setFieldError({
                date: !holidayData.date ? "Date is required" : "",
                name: !holidayData.name ? "Name is required" : "",
                description: !holidayData.description ? "Description is required" : ""
            });
            toast.error("Please fill all fields");
            return;
        }
    }        
    
  const fetchAttendanceData = async () => {
    try {
      const response = await axios.get("/attendance/today");

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
        title="ISMO - Today's Attendance"
        description="ISMO Admin Dashboard - Today's Attendance"
      />
      <PageBreadcrumb pageTitle="Today's Attendance" />
      <div className="space-y-6">
        <ComponentCard
          title={`Attendance on ${moment().format("DD MMMM YYYY")}`}
        >
          <div className="mb-4 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-3 gap-4">
            <DatePicker
              id="holiday-date"
              mode="single"
              placeholder="Pick a date"
              defaultDate={holidayData.date.toString()}
              onChange={(date, currentdatestring) => {
                setHolidayData({ ...holidayData, date: currentdatestring });
                // You can call fetchAttendanceData with the selected date here if needed
                // Example: fetchAttendanceData(date)
              }}
            />
            <Input
              id="holiday-name"
              name="holiday-name"
              placeholder="Holiday Name"
              value={holidayData.name}
              onChange={(e) =>
                setHolidayData({ ...holidayData, name: e.target.value })
              }
              error={!!fielderror.name}
              hint={fielderror.name}
            />
            <TextArea
              placeholder="Holiday Description"
              value={holidayData.description}
              onChange={(val) =>
                setHolidayData({ ...holidayData, description: val })
              }
              error={!!fielderror.description}
              hint={fielderror.description}
            />
          </div>
          <div className="flex justify-center items-center mb-4">
            <Button size="md" variant="primary" onClick={handleSubmit}>
              Add Holiday
            </Button>

            <ToastContainer position="bottom-right" />
          </div>
          <EnhancedDataTable<AttendanceRow>
            data={attendancedata}
            columns={columns}
          />
        </ComponentCard>
      </div>
    </>
  );
}
