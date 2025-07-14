import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import EnhancedDataTable from "../../components/tables/DataTables/DataTableOne";
import axios from "../../api/axios";
import { useState, useEffect } from "react";
import moment from "moment";
import { ToastContainer } from "react-toastify";
import { ColumnDef } from "@tanstack/react-table";
import DatePicker from "../../components/form/date-picker";
import Label from "../../components/form/Label";
import Select from "../../components/form/Select";
import Button from "../../components/ui/button/Button";
type AttendanceRow = {
    id: string;
    uid: string;
    erp_id: string;
    name: string;
    designation: string;
    section: string;
    timestamp: string;
    status: string;
    late: string;
    punch?: string;
    flag?: string;
};

export default function SectionAttendanceReport() {
    const [attendancedata, setAttendanceData] = useState<AttendanceRow[]>([]);
    
    const [options, setOptions] = useState<{ value: string; label: string }[]>([]);
    const [status] = useState<{ value: string; label: string }[]>([
        { value: "present", label: "Present" },
        { value: "absent", label: "Absent" },
    ]);

    const [data, setData] = useState<{ date: string; status: string; section: string }>({
        date: moment().format("YYYY-MM-DD"),
        status: "present",
        section: "",
    });
    useEffect(() => {
        getSectionsData();
    }, []);

    const getSectionsData = async () => {
        const response = await axios.get("/sections/get");
        setOptions(
            response.data.map((section: any) => ({
                value: section.id,
                label: section.name,
            }))
        );
    };

   
    const handleSearch = () => {
        fetchAttendanceData();
    }


    const fetchAttendanceData = async () => {
        try {
            const response = await axios.post("/attendance/status/", data);
            const cleanedData: AttendanceRow[] = response.data.map((item: any) => ({
                erp_id: item.erp_id,
                name: item.name,
                designation: item.designation,
                section: item.section,
                timestamp: data.date,
                late: item.lateintime,
                status: item.status,
                punch: item.uid,
                flag: item.status === "Checked In" ? "Present" : "Absent",
            }));
            setAttendanceData(cleanedData);
        } catch (error) {
            console.error("Error fetching attendance data:", error);
        }
    };

    const columns: ColumnDef<AttendanceRow>[] = [
        { accessorKey: "erp_id", header: "ERP ID" },
        { accessorKey: "name", header: "Name" },
        { accessorKey: "designation", header: "Designation" },
        { accessorKey: "section", header: "Section" },
        { accessorKey: "timestamp", header: "Timestamp" },
        { accessorKey: "flag", header: "Present/Absent" },
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
        { accessorKey: "status", header: "Status" },
 
    ];

    return (
      <>
        <PageMeta
          title="ISMO - Attendance History"
          description="ISMO Admin Dashboard - Attendance History"
        />
        <PageBreadcrumb pageTitle="Attendance History" />
        <div className="space-y-6">
          <ComponentCard title={`Attendance on ${data.date}`}>
            <ToastContainer position="bottom-right" />
            <div className="flex justify-between items-center mb-4 gap-1">
              <div className="w-1/3">
                <DatePicker
                  id="from-date-picker"
                  defaultDate={data.date}
                  label="Date"
                  placeholder="Select a date"
                  onChange={(_, currentDateString) => {
                    setData((prev) => ({ ...prev, date: currentDateString }));
                  }}
                />
              </div>
              <div className="w-1/3">
                <Label>Select Section</Label>
                <Select
                  options={options}
                  placeholder="Select a section"
                  onChange={(value) => {
                    setData((prev) => ({ ...prev, section: value }));
                  }}
                  className="dark:bg-dark-900"
                />
              </div>
              <div className="w-1/3">
                <Label>Select Status</Label>
                <Select
                  options={status}
                  placeholder="Select a status"
                  onChange={(value) => {
                    setData((prev) => ({ ...prev, status: value }));
                  }}
                  className="dark:bg-dark-900"
                />
              </div>
            </div>
            <div className="flex justify-center">
              <Button size="lg" variant="primary" onClick={handleSearch}>
                Search
              </Button>
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
