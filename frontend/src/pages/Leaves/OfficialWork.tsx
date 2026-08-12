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
  leave_type: string;
  start_date: string;
  end_date: string;
  reason: string;
  status?: string;
  head_erpid?: any; // Assuming head_erpid is optional
  approved_by?: string;
  created_at?: string;
};

export default function OfficialWork() {
  const [leaves, setLeaves] = useState<AttendanceRow[]>([]);

  const [options, setOptions] = useState<{ label: string; value: string }[]>(
    []
  );
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const leavetype = ["Meetings", "ACT Test","Work From Home", "Official Tour", "Foreign Tour"];

  const [employeesData, setEmployeesData] = useState<any[]>([]);
  const [balance, setBalance] = useState<{
    used_days: number;
    financial_year: string;
  } | null>(null);
  const initializedSelf = useRef(false);

  useEffect(() => {
    fetchEmployeesOptions();
    getEmployeesLeaves();
  }, []);

  // The logged-in user's own employee and section-head values, remembered so
  // a reset restores them without depending on the once-only effect below.
  const selfDefaults = useRef<Partial<AttendanceRow>>({});

  // A blank form, rebuilt on every call so a reset uses today's date.
  const buildBlankForm = (): AttendanceRow => ({
    erp_id: 0,
    employee_id: 0,
    leave_type: "",
    reason: "",
    status: user.grade_id >= 9 ? "approved" : "pending",
    head_erpid: user.grade_id >= 9 ? user.erpid : "",
    start_date: moment().format("YYYY-MM-DD").toString(),
    approved_by: "",
    end_date: moment().format("YYYY-MM-DD").toString(),
  });

  const buildBlankFieldErrors = (): AttendanceRow => ({
    erp_id: "",
    employee_id: "",
    leave_type: "",
    reason: "",
    status: "",
    head_erpid: "",
    start_date: "",
    approved_by: "",
    end_date: "",
  });

  const [data, setData] = useState<AttendanceRow>(buildBlankForm);
  const [fielderror, setFieldError] =
    useState<AttendanceRow>(buildBlankFieldErrors);

  // Return the form to a fresh-page-load state.
  //
  // The previous reset blanked status and head_erpid and dropped approved_by
  // entirely — all three are required by the validation above, and none is
  // recoverable from the UI, so every submission after the first failed until
  // the page was reloaded.
  const resetForm = () => {
    setData({ ...buildBlankForm(), ...selfDefaults.current });
    setFieldError(buildBlankFieldErrors());
    setBalance(null);
  };
  const approvedby = [
    "CEO ISMO",
    "ED (HR) ISMO",
    "ED (MO) ISMO",
    "ED (SO) ISMO",
    "SECTION HEAD",
  ];

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
      head_erpid: headErpId,
    };

    setData((prev) => ({ ...prev, ...selfDefaults.current }));
  }, [employeesData]);

  const selectedEmployee = employeesData.find(
    (e: any) => Number(e.erp_id) === Number(data.erp_id)
  );

  // Fetch official work balance whenever the selected employee/work type changes
  useEffect(() => {
    if (!data.leave_type || !data.erp_id) {
      setBalance(null);
      return;
    }

    const fetchBalance = async () => {
      try {
        const response = await axios.post("/officialwork/balance/", {
          erp_id: data.erp_id,
          leave_type: data.leave_type,
        });
        setBalance(response.data);
      } catch (error) {
        console.error("Error fetching official work balance:", error);
        setBalance(null);
      }
    };

    fetchBalance();
  }, [data.leave_type, data.erp_id]);

  const handleApproveLeave = async (id: string) => {
    const [leaveId, action] = id.split("-");
    try {
      await axios.post("/officialwork/handle/", {
        recordid: leaveId,
        action: action,
        // Recorded on the notification sent to the applicant.
        actor_erp_id: user.erpid,
      });
      toast.success(`Leave request ${action}d successfully`);
      getEmployeesLeaves();
    } catch (error) {
      console.error("Error updating leave request:", error);
      toast.error("Failed to update leave request");
    }
  };

  const getEmployeesLeaves = async () => {
    try {
      const loadingToastId = "officialwork-loading";
      toast.loading(
        <span className="text-sm font-semibold">
          Loading/Fetching attendance data...
        </span>,
        { toastId: loadingToastId }
      );
      const response = await axios.get(`/officialwork/get/${user.erpid}/`);

      const cleanedData: AttendanceRow[] = response.data.leaves.map(
        (item: any) => {
          const picked = _.pick(item, [
            "id",
            "employee_name",
            "employee_id",
            "erp_id",
            "leave_type",
            "head_erpid",
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
      toast.dismiss(loadingToastId);
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
          value?.toLowerCase() === "pending" ||
          value?.toLowerCase() === "rejected"
            ? "inline-flex items-center px-6 py-0.5 justify-center gap-1 rounded-full font-semibold text-theme-lg bg-warning-50 text-warning-600 dark:bg-warning-500/15 dark:text-warning-500"
            : value?.toLowerCase() === "approved"
            ? "inline-flex items-center px-6 py-0.5 justify-center gap-1 rounded-full font-semibold text-theme-lg bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500"
            : "";
        return <span className={color}>{value}</span>;
      },
    },
    {
      header: "Actions",
      id: "actions-approve",
      cell: ({ row }) => {
        const user = JSON.parse(localStorage.getItem("user") || "{}");
        return row.original.status?.toLowerCase() === "pending" &&
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
        ) : null;
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
        !data.end_date ||
        !data.head_erpid ||
        !data.approved_by ||
        !data.reason ||
        !data.status
      ) {
        setFieldError({
          erp_id: !data.erp_id ? "ERP ID is required" : "",
          employee_id: !data.employee_id ? "Employee ID is required" : "",
          leave_type: !data.leave_type ? "Leave Type is required" : "",
          reason: !data.reason ? "Reason is required" : "",
          status: !data.status ? "Status is required" : "",
          approved_by: !data.approved_by ? "Approved By is required" : "",
          head_erpid: !data.head_erpid ? "Head ERP ID is required" : "",
          start_date: !data.start_date ? "Start Date is required" : "",
          end_date: !data.end_date ? "End Date is required" : "",
        });
        return;
      }
      if (window.confirm("Are you sure you want to apply for this leave?")) {
        const response = await axios.post("/officialwork/apply/", data);
        console.log("Response:", response.data);
      } else {
        return;
      }

      resetForm();
      getEmployeesLeaves();
      toast.success("Official work application submitted successfully");
    } catch (error: any) {
      console.error("Error applying for leave:", error);
      toast.error(
        error?.response?.data?.error || "Failed to submit leave application"
      );
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
        <ComponentCard title={`Official Work Application Form`}>
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
                    Loading official work record...
                  </div>
                ) : (
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <span className="block text-xs text-gray-500 dark:text-gray-400">
                        Days recorded this financial year
                      </span>
                      <span className="mt-1 block text-title-sm font-bold text-gray-800 dark:text-white/90">
                        {balance.used_days}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                      <InfoIcon className="size-4 shrink-0" />
                      Official Work has no entitlement limit — this is a running count, not a balance.
                    </div>
                  </div>
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
              <Label>Work Type</Label>
              <Select
                options={leavetype.map((type) => ({
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

            <div className="w-full">
              {user.grade_id < 9 && (
                <SearchableDropdown
                  options={options}
                  placeholder="select approving authority"
                  label="Section Head"
                  id="head-dropdown"
                  value={
                    options.find(
                      (opt) => opt.value.split("-")[0] === `${data.head_erpid}`
                    )?.value || ""
                  }
                  onChange={(value) => {
                    const vals = value?.toString().split("-");
                    setData({
                      ...data,
                      head_erpid: parseInt(vals[0]),
                    });
                  }}
                  error={!!fielderror.head_erpid}
                  hint={fielderror.head_erpid}
                />
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
            <div className="w-full">
              <TextArea
                placeholder="Enter reason for official work"
                value={data.reason}
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
