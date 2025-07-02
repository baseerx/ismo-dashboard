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
import SearchableDropdown from "../../components/form/input/SearchableDropDown";
import Button from "../../components/ui/button/Button";

type AttendanceRow = {
    id: number;
    erp_id: string;
    name: string;
    designation: string;
    section: string;
    uid: string | null;
    user_id: string | null;
    timestamp: string;
    late: string;
    status: string;
    flag: string;
    punch: string;
};

export default function IndividualAttendance() {
  const [attendancedata, setAttendanceData] = useState<AttendanceRow[]>([]);
  const [fromdate, setFromdate] = useState<String>(
    moment().format("YYYY-MM-DD")
  );
  const [erpid, setErpId] = useState<any>(0);
  const [todate, setTodate] = useState<String>(moment().format("YYYY-MM-DD"));
  const [options, setOptions] = useState<{ label: string; value: string }[]>(
    []
  );
  useEffect(() => {
    fetchEmployeesOptions();
  }, []);

  const fetchEmployeesOptions = async () => {
    try {
      const response = await axios.get("/users/employees/");
      const employees = response.data.map((employee: any) => ({
        label: `${employee.name} (${employee.erp_id})`,
        value: employee.erp_id,
      }));
      setOptions(employees);
    } catch (error) {
      console.error("Error fetching employee options:", error);
      toast.error("Failed to load employee options");
    }
  };

  const fetchAttendanceData = async () => {
    try {
      const response = await axios.post("/attendance/individual/", {
          erpid: erpid,
            fromdate: fromdate,
        todate: todate,
      });
      // Ensure response.data is an array and format timestamp
      const cleanedData: AttendanceRow[] = response.data.map((item: any) => {
        const picked = {
          id: item.id,
          erp_id: item.erp_id,
          name: item.name,
          designation: item.designation,
          section: item.section,
          uid: item.uid,
          user_id: item.user_id,
          timestamp: item.timestamp === null ? "-" : item.timestamp,
          late: item.uid === null ? "-" : item.late,
          status: item.status === null ? "-" : item.status,
          flag: item.uid !== null ? "Present" : "Absent",
          punch: item.punch,
        };
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
        accessorKey: "section",
        header: "Section",
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
    {
        accessorKey: "punch",
        header: "Punch",
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

          <div className="grid grid-cols-1 sm:grid-cols-2 mb-4 gap-1">
            <div className="w-full">
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
            <div className="w-full">
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
            <div className="w-full mt-2">
              <SearchableDropdown
                options={options}
                              placeholder="Select a user"
                              label="Employees"
                id="employee-dropdown"
                value={options.find((opt) => opt.value === erpid)?.value || ""}
                onChange={(value) => {
                  value !== null && setErpId(value);
                  

                  // Handle your logic
                }}
              />
            </div>
            <div>
              <Button
                size="sm"
                className="w-1/2 mt-7 ml-5"
                variant="primary"
                onClick={() => {
                  if (!erpid) {
                    toast.error("Please select an employee");
                    return;
                  }

                    fetchAttendanceData();
                  // Handle your logic
                }}
              >
                Search
              </Button>
            </div>
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
