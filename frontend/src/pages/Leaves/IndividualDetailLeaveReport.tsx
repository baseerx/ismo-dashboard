import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import EnhancedDataTable from "../../components/tables/DataTables/DataTableOne";
import axios from "../../api/axios";
import { useState, useEffect } from "react";
import _ from "lodash";
import { ToastContainer, toast } from "react-toastify";
import { ColumnDef } from "@tanstack/react-table";
import SearchableDropdown from "../../components/form/input/SearchableDropDown";
import Button from "../../components/ui/button/Button";
import Label from "../../components/form/Label";
import Select from "../../components/form/Select";
import moment from "moment";
// import DatePicker from "../../components/form/date-picker";

type AttendanceRow = {
    id?: number;
    employee_id: any;
    employee_name?: string;
    section: string;
    erp_id: any;
    leave_type?: string;
    total_leaves?: number;
    leave_count?: number;
    remaining_leaves?: number;
    availed?: boolean;
    status?: string;
    start_date?: string;
    end_date?: string;
};

export default function IndividualDetailLeaveReport() {
  const [IndividualLeaveReport, setIndividualLeaveReport] = useState<
    AttendanceRow[]
  >([]);

  const [employeeOptions, setEmployeeOptions] = useState<
    { label: string; value: string }[]
  >([]);
  const [sectionOptions, setSectionOptions] = useState<
    { label: string; value: string }[]
  >([]);
   const [year, setYear] = useState<string>(moment().format("YYYY"));
  useEffect(() => {
    fetchEmployeesOptions();
    getSectionsData();
  }, []);

  const handleSelectChange = (value: string) => {
    setData({
      ...data,
      section: value,
    });
  };
const handleSubmit = async () => {
    if (!data.section || !data.erp_id) {
        toast.error("Please select a section and employee");
        return;
    }
    
    const startYear = parseInt(year);
    const endYear = startYear + 1;
    const startDate = `${startYear}-07-01`;
    const endDate = `${endYear}-06-30`;
    
    const updatedData = {
        ...data,
        start_date: startDate,
        end_date: endDate,
    };
    
    
    try {
        const response = await axios.post(
          "/leaves/individual-detail-report/",
          updatedData
        );
        setIndividualLeaveReport(response.data.attendance);
        toast.success("Report generated successfully");
    } catch (error) {
        console.error("Error generating report:", error);
        toast.error("Failed to generate report");
    }
};

  const getSectionsData = async () => {
    try {
      const response = await axios.get("/sections/get");
      setSectionOptions(
        response.data.map((section: any) => ({
          value: section.id,
          label: section.name,
        }))
      );
    } catch (error) {
      console.error("Error fetching sections:", error);
      toast.error("Failed to load sections");
    }
  };

  const [data, setData] = useState<{
    erp_id: number;
    section: string;
 
    start_date: string;
    end_date: string;
   
  }>({
    erp_id: 0,
    section: "",

    start_date: "",
    end_date: "",});

const columns: ColumnDef<AttendanceRow>[] = [
    {
        header: "ERP ID",
        accessorKey: "erp_id",
    },
    {
        header: "Name",
        accessorKey: "employee_name",
    },
    {
        header: "Section",
        accessorKey: "section",
    },
    {
        header: "Leave Type",
        accessorKey: "leave_type",
    },
    {
        header: "Total Allowed",
        accessorKey: "total_leaves",
        cell: ({ getValue }) => {
            const value = getValue<number | undefined>();
            return (
                <span className="inline-flex items-center px-6 py-0.5 justify-center gap-1 rounded-full font-semibold text-theme-lg bg-gray-100 text-gray-700 dark:bg-white/5 dark:text-white/80">
                    {value ?? "-"}
                </span>
            );
        },
    },
    {
        header: "Availed (Days)",
        accessorKey: "leave_count",
        cell: ({ getValue }) => {
            const value = getValue<number>();
            const color =
                "inline-flex items-center px-6 py-0.5 justify-center gap-1 rounded-full font-semibold text-theme-lg bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500";
            return <span className={color}>{value ?? 0}</span>;
        },
    },
    {
        header: "Remaining Leaves",
        accessorKey: "remaining_leaves",
        cell: ({ getValue }) => {
            const value = getValue<number>();
            const color =
                "inline-flex items-center px-6 py-0.5 justify-center gap-1 rounded-full font-semibold text-theme-lg bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-500";
            return <span className={color}>{value ?? 0}</span>;
        },
    },
    {
        header: "Status",
        accessorKey: "status",
        cell: ({ getValue }) => {
            const value = getValue<string>() || "Not Availed";
            const color =
                value === "Availed"
                    ? "bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500"
                    : value === "Partially Availed"
                        ? "bg-warning-50 text-warning-600 dark:bg-warning-500/15 dark:text-orange-400"
                        : "bg-gray-100 text-gray-600 dark:bg-white/5 dark:text-gray-300";
            return (
                <span
                    className={`inline-flex items-center px-4 py-0.5 justify-center gap-1 rounded-full font-medium text-theme-sm ${color}`}
                >
                    {value}
                </span>
            );
        },
    },
    {
        header: "Period From",
        accessorKey: "start_date",
    },
    {
        header: "Period To",
        accessorKey: "end_date",
    },
];

  const fetchEmployeesOptions = async () => {
    try {
      const response = await axios.get("/users/employees/");
      const employees = response.data.map((employee: any) => ({
        label: `${employee.name} (${employee.erp_id})`,
        value: employee.erp_id + "-" + employee.id,
      }));
      setEmployeeOptions(employees);
    } catch (error) {
      console.error("Error fetching employee options:", error);
      toast.error("Failed to load employee options");
    }
  };

  return (
    <>
      <PageMeta
        title="ISMO - Attendance History"
        description="ISMO Admin Dashboard - Attendance History"
      />
      <PageBreadcrumb pageTitle="Attendance History" />
      <div className="space-y-6">
        <ComponentCard title={`Individual Leave Report`}>
          <ToastContainer position="bottom-right" />

          <div className="grid grid-cols-1 sm:grid-cols-2 mb-4 gap-1 justify-center items-center">
            {/* Employee Dropdown */}
            <div className="w-full">
              <SearchableDropdown
                options={employeeOptions}
                placeholder="Select an employee"
                label="Employees"
                id="employee-dropdown"
                value={
                  employeeOptions.find(
                    (opt) => opt.value.split("-")[0] === data.erp_id.toString()
                  )?.value || ""
                }
                onChange={(value) => {
                  const vals = value?.toString().split("-");
                  setData({
                    ...data,
                    erp_id: parseInt(vals[0] || "0"),
                  });
                }}
              />
            </div>

            {/* Section Dropdown */}
            <div className="w-full">
              <Label>Select Section</Label>
              <Select
                options={sectionOptions}
                placeholder="Select an option"
                onChange={handleSelectChange}
                className="dark:bg-dark-900"
              />
            </div>


                      
                    <div className="w-full">
                        <Label>Year</Label>
                        <Select
                            options={Array.from({ length: 10 }, (_, i) => {
                                const year = new Date().getFullYear() - i;
                                return {
                                    label: year.toString(),
                                    value: year.toString(),
                                };
                            })}
                            placeholder="Select a year"
                            onChange={(value) =>
                                setYear(value)
                            }
                            className="dark:bg-dark-900"
                        />
                    </div>
          </div>

          <div className="w-full flex justify-center items-center">
            <Button
              size="sm"
              className="w-1/3 mt-7 ml-5"
              variant="primary"
              onClick={handleSubmit}
            >
              Apply
            </Button>
          </div>

          <EnhancedDataTable<AttendanceRow>
            data={IndividualLeaveReport}
            columns={columns}
          />
        </ComponentCard>
      </div>
    </>
  );
}
