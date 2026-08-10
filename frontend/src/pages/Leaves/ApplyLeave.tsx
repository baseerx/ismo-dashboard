import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import EnhancedDataTable from "../../components/tables/DataTables/DataTableOne";
import axios from "../../api/axios"; // Adjust the import path as necessary
import { useState, useEffect, useRef } from "react";
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
import Badge from "../../components/ui/badge/Badge";
import { LeaveIcon, InfoIcon } from "../../icons";

type AttendanceRow = {
  id?: number;
  employee_id: any;
  erp_id: any;
  entry_made_by?: any;
  leave_type: string;
  start_date: string;
  end_date: string;
  head?: any;
  head_erpid?: any;
  reason: string;
  status?: string;
  approved_by?: string;
  created_at?: string;
};

export default function IndividualAttendance() {
  const [leaves, setLeaves] = useState<AttendanceRow[]>([]);
  const user = JSON.parse(localStorage.getItem("user") || "{}");

  const [options, setOptions] = useState<{ label: string; value: string }[]>(
    []
  );
  const leavetype = [
    "Medical Leave",
    "Casual Leave",
    "Annual Leave",
    "Maternity Leave First",
    "Maternity Leave Second",
    "Maternity Leave Third",
    "External Meeting",
    "Official Work",
    "Umrah Leave",
    "Hajj Leave",
    "Shift Leave",
    "Rest & Recreational Leave",
    "IDDAT Leave",
    "Compensatory Leave",
    "Short Leave",
    "Study Leave",
    "Marriage Leave",
    "Paternity Leave",
    "Earned Leave",
    "Beareavement Leave",
  ];

  const approvedby = [
    "CEO ISMO",
    "ED (HR) ISMO",
    "ED (MO) ISMO",
    "ED (SO) ISMO",
    "SECTION HEAD",
  ];

  // Leave types restricted to a specific employee gender ("M"/"F")
  const genderRestrictedLeaveTypes: Record<string, "M" | "F"> = {
    "Maternity Leave First": "F",
    "Maternity Leave Second": "F",
    "Maternity Leave Third": "F",
    "IDDAT Leave": "F",
    "Paternity Leave": "M",
  };

  const [employeesData, setEmployeesData] = useState<any[]>([]);
  const [balance, setBalance] = useState<{
    total_allowed: number | null;
    used_days: number;
    remaining_leaves: number | null;
    financial_year: string;
  } | null>(null);
  const initializedSelf = useRef(false);
  // The logged-in user's own employee and section-head values. Remembered so
  // a reset can restore them immediately — the effect below that derives them
  // runs once and must not be relied on to re-populate the form.
  const selfDefaults = useRef<Partial<AttendanceRow>>({});

  // A blank form, built fresh on every call so a reset picks up today's date
  // rather than the date the page happened to be opened on.
  const buildBlankForm = (): AttendanceRow => ({
    erp_id: 0,
    employee_id: 0,
    entry_made_by: user.erpid,
    leave_type: "",
    reason: "",
    status: user.grade_id >= 9 ? "approved" : "pending",
    approved_by: "",
    head: user.grade_id >= 9 ? user.erpid : "",
    start_date: moment().format("YYYY-MM-DD").toString(),
    end_date: moment().format("YYYY-MM-DD").toString(),
  });

  const buildBlankFieldErrors = (): AttendanceRow => ({
    erp_id: "",
    employee_id: "",
    leave_type: "",
    reason: "",
    head: "",
    status: "",
    approved_by: "",
    start_date: "",
    end_date: "",
  });

  const [data, setData] = useState<AttendanceRow>(buildBlankForm);
  const [fielderror, setFieldError] =
    useState<AttendanceRow>(buildBlankFieldErrors);

  // Return the form to exactly the state a fresh page load produces.
  //
  // The previous reset rebuilt `data` from a partial literal that omitted
  // entry_made_by, approved_by and head, and set status to "". Those fields
  // are required by the validation above, and two of them are never edited
  // directly — so the next Apply always failed on fields the user could not
  // see or fix, which is why the page had to be reloaded between entries.
  // (It also let a leave through with an empty status.)
  const resetForm = () => {
    setData({ ...buildBlankForm(), ...selfDefaults.current });
    setFieldError(buildBlankFieldErrors());
    setBalance(null);
  };

  useEffect(() => {
    fetchEmployeesOptions();
    getEmployeesLeaves();
  }, []);

  // Auto-select the logged in user as the employee, and derive their
  // Section Head (highest-graded employee, grade_id >= 9, in the same section)
  useEffect(() => {
    if (initializedSelf.current || employeesData.length === 0) return;

    const self = employeesData.find(
      (e: any) => Number(e.erp_id) === Number(user.erpid)
    );
    if (!self) return;

    initializedSelf.current = true;

    let headErpId: any = user.grade_id >= 9 ? user.erpid : "";
    if (user.grade_id < 9) {
      const sectionHeads = employeesData.filter(
        (e: any) =>
          Number(e.section_id) === Number(self.section_id) &&
          Number(e.grade_id) >= 9 &&
          Number(e.erp_id) !== Number(self.erp_id)
      );
      if (sectionHeads.length > 0) {
        const topHead = sectionHeads.reduce((max: any, e: any) =>
          Number(e.grade_id) > Number(max.grade_id) ? e : max
        );
        headErpId = topHead.erp_id;
      }
    }

    selfDefaults.current = {
      employee_id: self.id,
      erp_id: self.erp_id,
      head: headErpId,
    };

    setData((prev) => ({ ...prev, ...selfDefaults.current }));
  }, [employeesData]);

  const selectedEmployee = employeesData.find(
    (e: any) => Number(e.erp_id) === Number(data.erp_id)
  );

  const filteredLeaveTypes = leavetype.filter((type) => {
    const restriction = genderRestrictedLeaveTypes[type];
    if (!restriction) return true;
    if (!selectedEmployee) return true;
    return (selectedEmployee.gender || "").toUpperCase() === restriction;
  });

  // Clear the selected leave type if it's not applicable to the currently
  // selected employee's gender (e.g. employee was changed after selection)
  useEffect(() => {
    if (data.leave_type && !filteredLeaveTypes.includes(data.leave_type)) {
      setData((prev) => ({ ...prev, leave_type: "" }));
    }
  }, [selectedEmployee?.gender]);

  // Fetch leave balance whenever the selected employee/leave type changes
  useEffect(() => {
    if (!data.leave_type || !data.erp_id) {
      setBalance(null);
      return;
    }

    const fetchBalance = async () => {
      try {
        const response = await axios.post("/leaves/balance/", {
          erp_id: data.erp_id,
          leave_type: data.leave_type,
        });
        setBalance(response.data);
      } catch (error) {
        console.error("Error fetching leave balance:", error);
        setBalance(null);
      }
    };

    fetchBalance();
  }, [data.leave_type, data.erp_id]);

  // Severity of the remaining balance: plenty left / running low / exhausted
  const balanceTotal = balance?.total_allowed ?? null;
  const balanceRemaining = balance?.remaining_leaves ?? null;
  const balanceUsedPct =
    balanceTotal && balanceTotal > 0
      ? Math.min(100, Math.max(0, ((balance?.used_days || 0) / balanceTotal) * 100))
      : 0;

  let balanceSeverity: "good" | "warning" | "critical" = "good";
  if (balanceTotal !== null) {
    if (balanceRemaining === null || balanceRemaining <= 0) {
      balanceSeverity = "critical";
    } else if (balanceRemaining <= balanceTotal * 0.2) {
      balanceSeverity = "warning";
    }
  }

  const balanceSeverityStyles = {
    good: {
      fill: "bg-success-500",
      track: "bg-success-50 dark:bg-success-500/15",
      text: "text-success-600 dark:text-success-500",
      badge: "success" as const,
    },
    warning: {
      fill: "bg-warning-500",
      track: "bg-warning-50 dark:bg-warning-500/15",
      text: "text-warning-600 dark:text-orange-400",
      badge: "warning" as const,
    },
    critical: {
      fill: "bg-error-500",
      track: "bg-error-50 dark:bg-error-500/15",
      text: "text-error-600 dark:text-error-500",
      badge: "error" as const,
    },
  }[balanceSeverity];

  const handleApproveLeave = async (id: any) => {
    const action = id.toString().split("-")[1];
    const empid = parseInt(id.toString().split("-")[0]);

    try {
      if (!empid || !action) {
        toast.error("Invalid leave request ID or action");
        return;
      }

      if (window.confirm(`Are you sure you want to ${action} this leave?`)) {
        const response = await axios.post("/leaves/approve/", {
          recordid: Number(empid),
          action: action,
        });
        console.log("Leave approval response:", response.data);
        getEmployeesLeaves();
        toast.success("Leave approved successfully");
      }
    } catch (error) {
      console.error("Error approving leave:", error);
      toast.error("Failed to approve leave");
    }
  };

  const getEmployeesLeaves = async () => {
    try {
      const response = await axios.get(`/leaves/get/${user.erpid}/`);

      const cleanedData: AttendanceRow[] = response.data.leaves.map(
        (item: any) => {
          const picked = _.pick(item, [
            "id",
            "employee_name",
            "erp_id",
            "leave_type",
            "start_date",
            "head_erpid",
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
      header: "Head ERP ID",
      accessorKey: "head_erpid",
    },
    {
      header: "Name",
      accessorKey: "employee_name",
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
      header: "Leave Count",
      accessorKey: "leave_count",
      cell: ({ row }) => {
        const start = moment(row.original.start_date);
        const end = moment(row.original.end_date);
        return end.diff(start, "days") + 1; // +1 to include the start date
      },
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
          value?.toLowerCase() === "pending" ||
            value?.toLowerCase() === "rejected"
            ? "inline-flex items-center px-6 py-0.5 justify-center gap-1 rounded-full font-semibold text-theme-lg bg-warning-50 text-warning-600 dark:bg-warning-500/15 dark:text-warning-500"
            : value?.toLowerCase() === "approved"
              ? "inline-flex items-center px-6 py-0.5 justify-center gap-1 rounded-full font-semibold text-theme-lg bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500"
              : "";
        return <span className={color}>{value}</span>;
      },
    },
    // Only show action columns if status is pending
    {
      header: "Actions",
      id: "actions-approve",
      cell: ({ row }) =>
        row.original.status?.toLowerCase() === "pending" &&
          row.original.head_erpid === user.erpid ? (
          <div className="flex gap-2">
            <Button
              size="xs"
              variant="primary"
              onClick={() =>
                handleApproveLeave(`${row.original.id?.toString()}-approve`)
              }
            >
              Approve
            </Button>
            <Button
              size="xs"
              variant="outline"
              onClick={() =>
                handleApproveLeave(`${row.original.id?.toString()}-reject`)
              }
            >
              Reject
            </Button>
          </div>
        ) : null,
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
      setEmployeesData(response.data);
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
        !data.approved_by ||
        !data.end_date ||
        !data.reason ||
        !data.head
      ) {
        setFieldError({
          erp_id: !data.erp_id ? "ERP ID is required" : "",
          employee_id: !data.employee_id ? "Employee ID is required" : "",
          leave_type: !data.leave_type ? "Leave Type is required" : "",
          reason: !data.reason ? "Reason is required" : "",
          approved_by: !data.approved_by ? "Approved By is required" : "",
          head: !data.head ? "Section Head is required" : "",
          start_date: !data.start_date ? "Start Date is required" : "",
          end_date: !data.end_date ? "End Date is required" : "",
        });
        return;
      }

      if (window.confirm("Are you sure you want to apply for this leave?")) {
        try {
          const response = await axios.post("/leaves/apply/", data);
          console.log("Leave application response:", response.data);
        } catch (error: any) {
          const errorMessage = error.response?.data?.error || "Failed to submit leave application, Either limit exceeded or leave limit not found";
          console.error("Error applying for leave:", error);
          toast.error(errorMessage);
          return;
        }
      } else {
        return;
      }

      resetForm();
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

          {data.leave_type && (
            <div className="mb-5 overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 px-5 py-4 dark:border-gray-800">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-50 dark:bg-brand-500/15">
                    <LeaveIcon className="size-5 text-brand-500" />
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-800 dark:text-white/90">
                      {data.leave_type}
                    </h4>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {selectedEmployee?.name || "Selected employee"}
                      {selectedEmployee?.erp_id
                        ? ` (${selectedEmployee.erp_id})`
                        : ""}
                    </p>
                  </div>
                </div>
                {balance?.financial_year && (
                  <Badge color="light" size="sm">
                    FY {balance.financial_year}
                  </Badge>
                )}
              </div>

              <div className="px-5 py-4">
                {!balance ? (
                  <div className="flex items-center gap-2 text-sm text-gray-400 dark:text-gray-500">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-gray-300 dark:bg-gray-600" />
                    Loading leave balance...
                  </div>
                ) : balanceTotal === null ? (
                  <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                    <InfoIcon className="size-4 shrink-0" />
                    No leave limit configured for this leave type.
                  </div>
                ) : (
                  <>
                    <div className="grid grid-cols-3 gap-4 sm:gap-6">
                      <div>
                        <span className="block text-xs text-gray-500 dark:text-gray-400">
                          Entitled
                        </span>
                        <span className="mt-1 block text-title-sm font-bold text-gray-800 dark:text-white/90">
                          {balanceTotal}
                        </span>
                      </div>
                      <div>
                        <span className="block text-xs text-gray-500 dark:text-gray-400">
                          Used
                        </span>
                        <span className="mt-1 block text-title-sm font-bold text-gray-800 dark:text-white/90">
                          {balance.used_days}
                        </span>
                      </div>
                      <div>
                        <span className="block text-xs text-gray-500 dark:text-gray-400">
                          Remaining
                        </span>
                        <span
                          className={`mt-1 block text-title-sm font-bold ${balanceSeverityStyles.text}`}
                        >
                          {balanceRemaining !== null && balanceRemaining < 0
                            ? `Over by ${Math.abs(balanceRemaining)}`
                            : balanceRemaining}
                        </span>
                      </div>
                    </div>

                    <div
                      className={`mt-4 h-2 w-full overflow-hidden rounded-full ${balanceSeverityStyles.track}`}
                    >
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${balanceSeverityStyles.fill}`}
                        style={{ width: `${balanceUsedPct}%` }}
                      />
                    </div>
                  </>
                )}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 mb-4 gap-1 justify-center items-center">
            <div className="w-full">
              <SearchableDropdown
                options={options}
                placeholder="Select a employee"
                label={
                  user.grade_id < 9
                    ? `Employees`
                    : `Employee  (Status for Grade 9 and above is auto approved)`
                }
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
                key={selectedEmployee?.gender || "no-employee"}
                options={filteredLeaveTypes.map((type) => ({
                  label: type,
                  value: type,
                }))}
                placeholder="Select an option"
                // Controlled so clearing `data` after a submission also
                // clears what the user sees.
                value={data.leave_type}
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
            <div className="flex justify-center items-center gap-4 my-3">
              {user.grade_id < 9 && (
                <div className="w-full">
                  <SearchableDropdown
                    options={options}
                    placeholder="select approving authority"
                    label="Section Head"
                    id="head-dropdown"
                    value={
                      options.find(
                        (opt) => opt.value.split("-")[0] === `${data.head}`
                      )?.value || ""
                    }
                    onChange={(value) => {
                      const vals = value?.toString().split("-");
                      setData({
                        ...data,
                        head: parseInt(vals[0]),
                      });
                    }}
                    error={!!fielderror.head}
                    hint={fielderror.head}
                  />
                </div>
              )}
            </div>
            <div className="w-full my-3">
              <Label>Approved By</Label>
              <Select
                options={approvedby.map((type) => ({
                  label: type,
                  value: type,
                }))}
                placeholder="Select an option"
                value={data.approved_by}
                onChange={(value) => {
                  setData({ ...data, approved_by: value?.toString() || "" });
                }}
                className="dark:bg-dark-900"
                error={!!fielderror.approved_by}
                hint={fielderror.approved_by}
              />
            </div>
            <div className="my-5">
              <TextArea
                value={data.reason}
                placeholder="Enter reason for leave"
                onChange={(value) => {
                  setData({ ...data, reason: value });
                }}
                error={!!fielderror.reason}
                hint={fielderror.reason}
              />
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
              Apply
            </Button>
          </div>
          <EnhancedDataTable<AttendanceRow> data={leaves} columns={columns} />
        </ComponentCard>
      </div>
    </>
  );
}
