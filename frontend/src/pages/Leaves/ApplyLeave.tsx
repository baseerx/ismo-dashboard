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
import Label from "../../components/form/Label";
import Select from "../../components/form/Select";
import TextArea from "../../components/form/input/TextArea";
import Radio from "../../components/form/input/Radio";

type AttendanceRow = {
  id?: number;
  employee_id: any;
  erp_id: any;
  leave_type: string;
  start_date: string;
  end_date: string;
  reason: string;
  status: string;
  created_at?: string;
};

export default function IndividualAttendance() {
  const [leaves, setLeaves] = useState<AttendanceRow[]>([]);

  const [options, setOptions] = useState<{ label: string; value: string }[]>(
    []
  );
  const leavetype = [
    "Sick Leave",
    "Casual Leave",
    "Annual Leave",
    "Maternity Leave",
    "External Meeting",
    "Official Leave",
    "Umrah Leave",
    "Hajj Leave",
    "Recreational Leave",
    "Compensatory Leave",
    "Short Leave",
    "Study Leave",
    "Marriage Leave",
    "Paternity Leave",
  ];

  useEffect(() => {
    fetchEmployeesOptions();
    getEmployeesLeaves();
  }, []);

  const [data, setData] = useState<AttendanceRow>({
    erp_id: 0,
    employee_id: 0,
    leave_type: "",
    reason: "",
    status: "",
    start_date: moment().format("YYYY-MM-DD").toString(),
    end_date: moment().format("YYYY-MM-DD").toString(),
  });
  const [fielderror, setFieldError] = useState<AttendanceRow>({
    erp_id: "",
    employee_id: "",
    leave_type: "",
    reason: "",
    status: "",
    start_date: "",
    end_date: "",
  });

  const getEmployeesLeaves = async () => {
    try {
      const response = await axios.get("/leaves/get/");

      const cleanedData: AttendanceRow[] = response.data.leaves.map(
        (item: any) => {
          const picked = _.pick(item, [
            "id",
            "employee_name",
            "employee_id",
            "erp_id",
            "leave_type",
            "start_date",
            "end_date",
            "reason",
            "status",
            "created_at",
          ]);
          return picked;
        }
      );
      setLeaves(cleanedData);
    } catch (error) {
      console.error("Error fetching employee leaves:", error);
      toast.error("Failed to load employee leaves");
    }
  };
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
      header: "Employee ID",
      accessorKey: "employee_id",
    },
    {
      header: "Leave Type",
      accessorKey: "leave_type",
    },
    {
      header: "Start Date",
      accessorKey: "start_date",
    },
    {
      header: "End Date",
      accessorKey: "end_date",
    },
    {
      header: "Reason",
      accessorKey: "reason",
    },
    {
      header: "Status",
      accessorKey: "status",
      cell: ({ getValue }) => {
        const value = getValue<string>();
        const color =
          value?.toLowerCase() === "rejected"
            ? "inline-flex items-center px-6 py-0.5 justify-center gap-1 rounded-full font-semibold text-theme-lg bg-warning-50 text-warning-600 dark:bg-warning-500/15 dark:text-warning-500"
            : value?.toLowerCase() === "approved"
            ? "inline-flex items-center px-6 py-0.5 justify-center gap-1 rounded-full font-semibold text-theme-lg bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500"
            : "";
        return <span className={color}>{value}</span>;
      },
    },
  ];
  const fetchEmployeesOptions = async () => {
    try {
      const response = await axios.get("/users/employees/");
      const employees = response.data.map((employee: any) => ({
        label: `${employee.name} (${employee.erp_id})`,
        value: employee.erp_id + "-" + employee.id, // Assuming employee.id is the unique identifier
      }));
      setOptions(employees);
    } catch (error) {
      console.error("Error fetching employee options:", error);
      toast.error("Failed to load employee options");
    }
  };

  const applyLeave = async (data: AttendanceRow) => {
    try {
      if (
        !data.employee_id ||
        !data.leave_type ||
        !data.start_date ||
        !data.end_date ||
        !data.reason ||
        !data.status
      ) {
        setFieldError({
          erp_id: !data.erp_id ? "ERP ID is required" : "",
          employee_id: !data.employee_id ? "Employee ID is required" : "",
          leave_type: !data.leave_type ? "Leave Type is required" : "",
          reason: !data.reason ? "Reason is required" : "",
          status: !data.status ? "Status is required" : "",
          start_date: !data.start_date ? "Start Date is required" : "",
          end_date: !data.end_date ? "End Date is required" : "",
        });
        return;
      }

      const response = await axios.post("/leaves/apply/", data);
      console.log("Leave application response:", response.data);
      setData({
        erp_id: 0,
        employee_id: 0,
        leave_type: "",
        reason: "",
        status: "",
        start_date: moment().format("YYYY-MM-DD").toString(),
        end_date: moment().format("YYYY-MM-DD").toString(),
      });
      getEmployeesLeaves();
      toast.success("Leave application submitted successfully");
    } catch (error) {
      console.error("Error applying for leave:", error);
      toast.error("Failed to submit leave application");
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
        <ComponentCard title={`Leave Application Form`}>
          <ToastContainer position="bottom-right" />

          <div className="grid grid-cols-1 sm:grid-cols-2 mb-4 gap-1 justify-center items-center">
            <div className="w-full">
              <SearchableDropdown
                options={options}
                placeholder="Select a employee"
                label="Employees"
                id="employee-dropdown"
                value={
                  options.find(
                    (opt) => opt.value === `${data.erp_id}-${data.employee_id}`
                  )?.value || ""
                }
                onChange={(value) => {
                  const vals = value?.toString().split("-");
                  setData({
                    ...data,
                    employee_id: parseInt(vals[1] || "0"),
                    erp_id: parseInt(vals[0] || "0"),
                  });
                }}
                error={!!fielderror.employee_id}
                hint={fielderror.employee_id}
              />
            </div>
            <div className="w-full my-3">
              <Label>Leave Type</Label>
              <Select
                options={leavetype.map((type) => ({
                  label: type,
                  value: type,
                }))}
                placeholder="Select an option"
                onChange={(value) => {
                  setData({ ...data, leave_type: value?.toString() || "" });
                }}
                className="dark:bg-dark-900"
                error={!!fielderror.leave_type}
                hint={fielderror.leave_type}
              />
            </div>
            <div className="w-full my-3">
              <DatePicker
                id="from-date-picker"
                defaultDate={data.start_date.toString()}
                label="from date"
                placeholder="Select a date"
                onChange={(dates, currentDateString) => {
                  console.log(dates);
                  // Handle your logic
                  setData({ ...data, start_date: currentDateString });
                }}
              />
            </div>
            <div className="w-full">
              <DatePicker
                id="to-date-picker"
                defaultDate={data.end_date.toString()}
                label="to date"
                placeholder="Select a date"
                onChange={(dates, currentDateString) => {
                  console.log(dates);
                  // Handle your logic
                  setData({ ...data, end_date: currentDateString });
                }}
              />
            </div>
            <div className="my-5">
              <TextArea
                value={data.reason}
                onChange={(value) => {
                  setData({ ...data, reason: value });
                }}
                error={!!fielderror.reason}
                hint={fielderror.reason}
              />
            </div>
            <div className="flex justify-center items-center gap-4 my-3">
              <Radio
                id="status-approved"
                name="leave-status"
                value="approved"
                checked={data.status === "approved"}
                label="Approved"
                onChange={() => setData({ ...data, status: "approved" })}
              />
              <Radio
                id="status-rejected"
                name="leave-status"
                value="rejected"
                checked={data.status === "rejected"}
                label="Rejected"
                onChange={() => setData({ ...data, status: "rejected" })}
              />
              <Radio
                id="status-pending"
                name="leave-status"
                value="pending"
                checked={data.status === "pending"}
                label="Pending"
                onChange={() => setData({ ...data, status: "pending" })}
              />

              {!!fielderror.status && (
                <p className="mt-1 text-xs text-red-600 dark:text-red-400">
                  {fielderror.status}
                </p>
              )}
            </div>
          </div>
          <div className="w-full flex justify-center items-center">
            <Button
              size="sm"
              className="w-1/3 mt-7 ml-5"
              variant="primary"
              onClick={() => {
                // Handle your logic
                applyLeave(data);
              }}
            >
              Search
            </Button>
          </div>
          <EnhancedDataTable<AttendanceRow> data={leaves} columns={columns} />
        </ComponentCard>
      </div>
    </>
  );
}
