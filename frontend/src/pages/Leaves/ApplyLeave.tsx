import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import EnhancedDataTable from "../../components/tables/DataTables/DataTableOne";
import axios from "../../api/axios"; 
import { useState, useEffect, useMemo, useRef } from "react";
import moment from "moment";
import _ from "lodash";
import { ToastContainer, toast } from "react-toastify";
import { ColumnDef } from "@tanstack/react-table";
import Swal from "sweetalert2"; 
import DatePicker from "../../components/form/date-picker";
import SearchableDropdown from "../../components/form/input/SearchableDropDown";
import Button from "../../components/ui/button/Button";
import Label from "../../components/form/Label";
import Select from "../../components/form/Select";
import TextArea from "../../components/form/input/TextArea";
import Badge from "../../components/ui/badge/Badge";
import { LeaveIcon, InfoIcon } from "../../icons";
import { findSectionHead, sortedApprovers } from "../../utils/sectionHead";
import LeaveHistoryModal from "../../pages/Leaves/LeaveHistoryModal";


const swalTheme = () => {
  const isDark = document.documentElement.classList.contains("dark");
  return {
    background: isDark ? "#1d2939" : "#ffffff",
    color: isDark ? "#f2f4f7" : "#1d2939",
    confirmButtonColor: "#465fff",
    cancelButtonColor: isDark ? "#475467" : "#98a2b3",
   
    customClass: { container: "swal-on-top" },
  };
};


const ATTACHMENT_EXTENSIONS = [
  ".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic", ".doc", ".docx",
];
const ATTACHMENT_MAX_MB = 5;


const CATEGORY_OPTIONS = [
  { label: "All Employees", value: "all" },
  { label: "Jamshoro Employees", value: "jamshoro" },
  { label: "Planning & Lahore Employees", value: "planning_lahore" },
  { label: "CPPA / MO Employees", value: "cppa_mo" },
];

type AttendanceRow = {
  id?: number;
  employee_id: any;
  has_attachment?: boolean;
  attachment_name?: string | null;
  attachment_url?: string | null;
  erp_id: any;
  entry_made_by?: any;
  leave_type: string;
  start_date: string;
  end_date: string;
  head?: any;
  head_erpid?: any;
  reason: string;
  status?: string;
  created_at?: string;
  
  current_stage_label?: string | null;
  current_stage_role?: string | null;
  current_stage_erp_id?: number | null;
 
  designation?: string | null;
  location?: string | null;
  category?: string | null;
  joining_date?: string | null;
  date_of_birth?: string | null;
  official_training_days?: number | null;
};

type LeaveBarInfo = {
  total_allowed: number | null;
  used_days: number;
  remaining_leaves: number | null;
};

const BAR_STYLES = {
  good: {
    fill: "bg-success-500",
    track: "bg-success-50 dark:bg-success-500/15",
    text: "text-success-600 dark:text-success-500",
  },
  warning: {
    fill: "bg-warning-500",
    track: "bg-warning-50 dark:bg-warning-500/15",
    text: "text-warning-600 dark:text-orange-400",
  },
  critical: {
    fill: "bg-error-500",
    track: "bg-error-50 dark:bg-error-500/15",
    text: "text-error-600 dark:text-error-500",
  },
};


function LeaveBar({
  title,
  info,
}: {
  title: string;
  info: LeaveBarInfo | null | undefined;
}) {
  const total = info?.total_allowed ?? null;
  const remaining = info?.remaining_leaves ?? null;
  const used = info?.used_days ?? 0;
  const pct =
    total && total > 0 ? Math.min(100, Math.max(0, (used / total) * 100)) : 0;

  let severity: "good" | "warning" | "critical" = "good";
  if (total !== null) {
    if (remaining === null || remaining <= 0) severity = "critical";
    else if (remaining <= total * 0.2) severity = "warning";
  }
  const styles = BAR_STYLES[severity];

  return (
    <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-semibold text-gray-800 dark:text-white/90">
          {title}
        </span>
        {info && total !== null && (
          <span className={`text-sm font-semibold ${styles.text}`}>
            {remaining !== null && remaining < 0
              ? `Over by ${Math.abs(remaining)}`
              : `${remaining} left`}
          </span>
        )}
      </div>

      {!info ? (
        <div className="flex items-center gap-2 text-sm text-gray-400 dark:text-gray-500">
          <span className="h-2 w-2 animate-pulse rounded-full bg-gray-300 dark:bg-gray-600" />
          Loading...
        </div>
      ) : total === null ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No limit configured.
        </p>
      ) : (
        <>
          <div
            className={`h-2 w-full overflow-hidden rounded-full ${styles.track}`}
          >
            <div
              className={`h-full rounded-full transition-all duration-500 ${styles.fill}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
            Used {used} of {total}
          </p>
        </>
      )}
    </div>
  );
}

export default function ApplyLeave() {
  const [leaves, setLeaves] = useState<AttendanceRow[]>([]);
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  
  const [historyLeaveId, setHistoryLeaveId] = useState<number | null>(null);

  const [options, setOptions] = useState<{ label: string; value: string }[]>(
    []
  );
  
  const leavetype = [
    "Medical Leave",
    "Casual Leave",
    "Maternity Leave First",
    "Maternity Leave Second",
    "Maternity Leave Third",
    "External Meeting",
    "Umrah Leave",
    "Hajj Leave",
    "Shift Leave",
    "Rest & Recreational Leave",
    "IDDAT Leave",
    "Compensatory Leave",
    "Short Leave",
    "Study Leave",
    "Paternity Leave",
    "Earned Leave",
    "Beareavement Leave",
    "Disability Leave",
    "Leave Ex-Pakistan",
  ];

  
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


  const [leaveBars, setLeaveBars] = useState<{
    earned: LeaveBarInfo | null;
    casual: LeaveBarInfo | null;
  } | null>(null);
  
  const [barsRefresh, setBarsRefresh] = useState(0);

  const [categoryFilter, setCategoryFilter] = useState("all");

  const initializedSelf = useRef(false);
  
  const selfDefaults = useRef<Partial<AttendanceRow>>({});

  const buildBlankForm = (): AttendanceRow => ({
    erp_id: 0,
    employee_id: 0,
    entry_made_by: user.erpid,
    leave_type: "",
    reason: "",
  
    status: "pending",
    head: "",
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
    start_date: "",
    end_date: "",
  });

  const [data, setData] = useState<AttendanceRow>(buildBlankForm);
  const [fielderror, setFieldError] =
    useState<AttendanceRow>(buildBlankFieldErrors);

  
  const [financialYear, setFinancialYear] = useState<{
    start: string;
    end: string;
    label: string;
  } | null>(null);

 
  const [attachment, setAttachment] = useState<File | null>(null);
  const [attachmentError, setAttachmentError] = useState("");
 
  const [attachmentKey, setAttachmentKey] = useState(0);

  const pickAttachment = (file: File | null) => {
    if (!file) {
      setAttachment(null);
      setAttachmentError("");
      return;
    }

    const extension = `.${(file.name.split(".").pop() || "").toLowerCase()}`;
    if (!ATTACHMENT_EXTENSIONS.includes(extension)) {
      setAttachment(null);
      setAttachmentError(
        `Unsupported file type. Allowed: ${ATTACHMENT_EXTENSIONS.join(", ")}`
      );
      return;
    }
    if (file.size > ATTACHMENT_MAX_MB * 1024 * 1024) {
      setAttachment(null);
      setAttachmentError(`File must be ${ATTACHMENT_MAX_MB} MB or smaller.`);
      return;
    }

    setAttachment(file);
    setAttachmentError("");
  };

  // Return the form to exactly the state a fresh page load produces.
  const resetForm = () => {
    setData({ ...buildBlankForm(), ...selfDefaults.current });
    setFieldError(buildBlankFieldErrors());
    setBalance(null);
    setAttachment(null);
    setAttachmentError("");
    // Remounts the file input; its value cannot be cleared from state.
    setAttachmentKey((key) => key + 1);
  };

  useEffect(() => {
    fetchEmployeesOptions();
    getEmployeesLeaves();
  }, []);

  // Auto-select the logged in user as the employee, and default their Section
  // Head to the most senior person in their own section - which is themselves
  // when they are that person.
  useEffect(() => {
    if (initializedSelf.current || employeesData.length === 0) return;

    const self = employeesData.find(
      (e: any) => Number(e.erp_id) === Number(user.erpid)
    );
    if (!self) return;

    initializedSelf.current = true;

    const head = findSectionHead(employeesData, self);

    selfDefaults.current = {
      employee_id: self.id,
      erp_id: self.erp_id,
      // A head is always found now, including the applicant themselves; the
      // fallback only covers an employee missing from the list entirely.
      head: head ? head.erp_id : "",
    };

    setData((prev) => ({ ...prev, ...selfDefaults.current }));
  }, [employeesData]);

  // Section Head choices: the applicant's own section first, most senior
  // first, so the head the form defaults to is the top entry rather than
  // something to hunt for among four hundred names.
  const headOptions = useMemo(() => {
    const self = employeesData.find(
      (e: any) => Number(e.erp_id) === Number(user.erpid)
    );

    return sortedApprovers(employeesData, self).map((e: any) => ({
      label: `${e.name} (${e.erp_id})${e.grade ? ` · ${e.grade}` : ""}`,
      value: `${e.erp_id}-${e.id}`,
    }));
  }, [employeesData, user.erpid]);

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

  // Earned + Casual bars for the selected employee. Uses the existing
  // /leaves/balance/ endpoint (one call per type), so no new route is needed.
  useEffect(() => {
    if (!data.erp_id) {
      setLeaveBars(null);
      return;
    }

    let cancelled = false;
    setLeaveBars({ earned: null, casual: null });

    const pick = (res: any): LeaveBarInfo => ({
      total_allowed: res.data.total_allowed,
      used_days: res.data.used_days,
      remaining_leaves: res.data.remaining_leaves,
    });

    const fetchBars = async () => {
      try {
        const [earned, casual] = await Promise.all([
          axios.post("/leaves/balance/", {
            erp_id: data.erp_id,
            leave_type: "Earned Leave",
          }),
          axios.post("/leaves/balance/", {
            erp_id: data.erp_id,
            leave_type: "Casual Leave",
          }),
        ]);
        if (!cancelled) {
          setLeaveBars({ earned: pick(earned), casual: pick(casual) });
        }
      } catch (error) {
        console.error("Error fetching leave bars:", error);
        if (!cancelled) setLeaveBars(null);
      }
    };

    fetchBars();
    return () => {
      cancelled = true;
    };
  }, [data.erp_id, barsRefresh]);

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

  // Anex-B: whoever the CURRENT stage is assigned to can act — not always
  // the section head. Also collects an optional remark ("forward with
  // remarks") that's stored on the stage and shown in the History modal.
  const handleApproveLeave = async (id: any) => {
    const action = id.toString().split("-")[1];
    const empid = parseInt(id.toString().split("-")[0]);

    try {
      if (!empid || !action) {
        toast.error("Invalid leave request ID or action");
        return;
      }

      // SweetAlert2 replacement for window.prompt
      const commentResult = await Swal.fire({
        ...swalTheme(),
        title: action === "reject" ? "Reject Leave" : "Approve Leave",
        text:
          action === "reject"
            ? "Reason for rejecting this leave (shown to the applicant):"
            : "Remarks to forward with this approval (optional):",
        input: "textarea",
        inputPlaceholder: "Type here...",
        showCancelButton: true,
        confirmButtonText: "Continue",
        cancelButtonText: "Cancel",
      });
      if (!commentResult.isConfirmed) return; // user cancelled the prompt
      const comment: string = commentResult.value || "";

      // SweetAlert2 replacement for window.confirm
      const confirmResult = await Swal.fire({
        ...swalTheme(),
        icon: action === "reject" ? "warning" : "question",
        title: "Are you sure?",
        text: `Are you sure you want to ${action} this leave?`,
        showCancelButton: true,
        confirmButtonText: `Yes, ${action}`,
        cancelButtonText: "Cancel",
        reverseButtons: true,
      });

      if (confirmResult.isConfirmed) {
        // /leaves/advance/ checks the actor against the CURRENT stage's
        // assigned approver, not a flat head_erpid comparison, so this
        // call works correctly at every stage of the Anex-B chain.
        const response = await axios.post("/leaves/advance/", {
          recordid: Number(empid),
          action: action,
          actor_erp_id: user.erpid,
          comment: comment || undefined,
        });
        console.log("Leave advance response:", response.data);
        getEmployeesLeaves();
        // An approval/rejection changes used balances.
        setBarsRefresh((n) => n + 1);
        const finalStatus = response.data?.leave_status;
        toast.success(
          finalStatus === "pending"
            ? "Stage approved — moved to the next approver"
            : `Leave ${finalStatus} successfully`
        );
      }
    } catch (error: any) {
      console.error("Error advancing leave:", error);
      toast.error(error.response?.data?.error || "Failed to update leave");
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
            // Needed by the Attachment column — this pick list is a
            // whitelist, so new fields must be added here to survive.
            "has_attachment",
            "attachment_name",
            "attachment_url",
            // Anex-B current approval stage — see Current Approver column.
            "current_stage_label",
            "current_stage_role",
            "current_stage_erp_id",
            // Employee details / category filter / official training.
            "designation",
            "location",
            "category",
            "joining_date",
            "date_of_birth",
            "official_training_days",
          ]);
          return picked;
        }
      );
      setLeaves(cleanedData);
      setFinancialYear(response.data.financial_year ?? null);
    } catch (error) {
      console.error("Error fetching employee leaves:", error);
      toast.error("Failed to load employee leaves");
    }
  };

  // Rows after the category filter ("all" shows everything).
  const visibleLeaves = useMemo(
    () =>
      categoryFilter === "all"
        ? leaves
        : leaves.filter((l) => l.category === categoryFilter),
    [leaves, categoryFilter]
  );

  const dash = <span className="text-gray-400 dark:text-gray-500">—</span>;

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
      header: "Designation",
      accessorKey: "designation",
      cell: ({ getValue }) => getValue<string>() || dash,
    },
    {
      header: "Location",
      accessorKey: "location",
      cell: ({ getValue }) => getValue<string>() || dash,
    },
    {
      header: "Joining Date",
      accessorKey: "joining_date",
      cell: ({ getValue }) => getValue<string>() || dash,
    },
    {
      header: "Date of Birth",
      accessorKey: "date_of_birth",
      cell: ({ getValue }) => getValue<string>() || dash,
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
      header: "Official Training",
      accessorKey: "official_training_days",
      cell: ({ getValue }) => {
        const days = getValue<number>();
        return days ? `${days} day${days === 1 ? "" : "s"}` : dash;
      },
    },
    {
      header: "Reason",
      accessorKey: "reason",
    },
    {
      header: "Attachment",
      id: "attachment",
      cell: ({ row }) =>
        row.original.has_attachment && row.original.attachment_url ? (
          <a
            href={row.original.attachment_url}
            target="_blank"
            rel="noopener noreferrer"
            title={row.original.attachment_name || "Attachment"}
            className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-3 py-0.5 text-sm font-medium text-blue-600 hover:underline dark:bg-blue-500/15 dark:text-blue-400"
          >
            View
          </a>
        ) : (
          <span className="text-gray-400 dark:text-gray-500">—</span>
        ),
    },
    {
      header: "Current Approver",
      id: "current-approver",
      cell: ({ row }) => {
        const stage = row.original;
        if (!stage.current_stage_label) {
          return <span className="text-gray-400 dark:text-gray-500">—</span>;
        }
        const approver = employeesData.find(
          (e: any) => Number(e.erp_id) === Number(stage.current_stage_erp_id)
        );
        return (
          <div className="flex flex-col">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {stage.current_stage_label}
            </span>
            <span className="text-xs text-gray-400 dark:text-gray-500">
              {approver
                ? `${approver.name} (${stage.current_stage_erp_id})`
                : stage.current_stage_erp_id
                ? `ERP ${stage.current_stage_erp_id}`
                : "Unassigned"}
            </span>
          </div>
        );
      },
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
    // Approve/Reject show only when the CURRENT stage is assigned to the
    // logged-in user (Anex-B: this rotates through Reporting Officer,
    // Functional Head, HR & Admin, CEO, etc. as the leave advances — it's
    // no longer always the section head). History is always available.
    {
      header: "Actions",
      id: "actions-approve",
      cell: ({ row }) => (
        <div className="flex gap-2">
          {row.original.status?.toLowerCase() === "pending" &&
          Number(row.original.current_stage_erp_id) === Number(user.erpid) ? (
            <>
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
            </>
          ) : null}
          <Button
            size="xs"
            variant="outline"
            onClick={() => setHistoryLeaveId(row.original.id ?? null)}
          >
            History
          </Button>
        </div>
      ),
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
        !data.reason ||
        !data.head
      ) {
        setFieldError({
          erp_id: !data.erp_id ? "ERP ID is required" : "",
          employee_id: !data.employee_id ? "Employee ID is required" : "",
          leave_type: !data.leave_type ? "Leave Type is required" : "",
          reason: !data.reason ? "Reason is required" : "",
          head: !data.head ? "Section Head is required" : "",
          start_date: !data.start_date ? "Start Date is required" : "",
          end_date: !data.end_date ? "End Date is required" : "",
        });
        return;
      }

      if (attachmentError) {
        toast.error(attachmentError);
        return;
      }

      // SweetAlert2 replacement for window.confirm
      const confirmation = await Swal.fire({
        ...swalTheme(),
        icon: "question",
        title: "Apply for this leave?",
        text: "Are you sure you want to apply for this leave?",
        showCancelButton: true,
        confirmButtonText: "Yes, apply",
        cancelButtonText: "Cancel",
        reverseButtons: true,
      });

      if (confirmation.isConfirmed) {
        try {
          let response;
          if (attachment) {
            // Multipart when a document is attached. Content-Type is
            // left unset so the browser adds the multipart boundary — the
            // shared axios instance otherwise forces application/json.
            const form = new FormData();
            Object.entries(data).forEach(([key, value]) => {
              if (value !== undefined && value !== null) {
                form.append(key, String(value));
              }
            });
            form.append("attachment", attachment);
            response = await axios.post("/leaves/apply/", form, {
              headers: { "Content-Type": undefined },
            });
          } else {
            response = await axios.post("/leaves/apply/", data);
          }
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
      setBarsRefresh((n) => n + 1);
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

          {/* Separate Earned / Casual leave bars, with the employee's
              designation shown alongside the leave details. */}
          {data.erp_id ? (
            <div className="mb-5 overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
              <div className="border-b border-gray-100 px-5 py-4 dark:border-gray-800">
                <h4 className="font-semibold text-gray-800 dark:text-white/90">
                  {selectedEmployee?.name || "Selected employee"}
                  {selectedEmployee?.erp_id
                    ? ` (${selectedEmployee.erp_id})`
                    : ""}
                </h4>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {selectedEmployee?.designation || "Designation not available"}
                  {selectedEmployee?.location
                    ? ` · ${selectedEmployee.location}`
                    : ""}
                </p>
              </div>
              <div className="grid grid-cols-1 gap-4 px-5 py-4 sm:grid-cols-2">
                <LeaveBar title="Earned Leave" info={leaveBars?.earned} />
                <LeaveBar title="Casual Leave" info={leaveBars?.casual} />
              </div>
            </div>
          ) : null}

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
                      {selectedEmployee?.designation
                        ? ` · ${selectedEmployee.designation}`
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
            {/* Shown for every grade — grade 9 and above used to have this
                field hidden and were auto-approved. */}
            <div className="w-full my-3">
              <SearchableDropdown
                options={headOptions}
                placeholder="select approving authority"
                label="Section Head"
                id="head-dropdown"
                value={
                  headOptions.find(
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
            {/* Supporting document — offered for every leave type. */}
            <div className="w-full my-3">
              <Label>
                Attachment <span className="text-gray-400">(optional)</span>
              </Label>
              <input
                key={attachmentKey}
                type="file"
                accept={ATTACHMENT_EXTENSIONS.join(",")}
                onChange={(e) => pickAttachment(e.target.files?.[0] ?? null)}
                className={`h-11 w-full rounded-lg border px-4 py-2.5 text-sm text-gray-800 file:mr-3 file:rounded file:border-0 file:bg-brand-50 file:px-3 file:py-1 file:text-sm file:text-brand-600 dark:bg-gray-900 dark:text-white/90 dark:file:bg-brand-500/15 dark:file:text-brand-400 ${
                  attachmentError
                    ? "border-error-500"
                    : "border-gray-300 dark:border-gray-700"
                }`}
              />
              {attachmentError ? (
                <p className="mt-1 text-xs text-error-600 dark:text-error-500">
                  {attachmentError}
                </p>
              ) : (
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  {attachment
                    ? `Selected: ${attachment.name}`
                    : `Attach a supporting document. ${ATTACHMENT_EXTENSIONS.join(
                        ", "
                      )} up to ${ATTACHMENT_MAX_MB} MB.`}
                </p>
              )}
            </div>

            <div className="my-5">
              <TextArea
                value={data.reason}
                placeholder={
                  data.leave_type === "Leave Ex-Pakistan"
                    ? "Mention the country / destination and purpose of travel"
                    : "Enter reason for leave"
                }
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
          <div className="mt-8 mb-3 flex flex-wrap items-end justify-between gap-3">
            <div className="flex flex-wrap items-baseline gap-2">
              <h4 className="text-lg font-semibold text-gray-800 dark:text-white/90">
                Leave Records
              </h4>
              {financialYear && (
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  Financial year {financialYear.label} ({financialYear.start} to{" "}
                  {financialYear.end})
                </span>
              )}
            </div>
            <div className="w-full sm:w-64">
              <Select
                options={CATEGORY_OPTIONS}
                placeholder="Filter by category"
                value={categoryFilter}
                onChange={(value) => setCategoryFilter(value?.toString() || "all")}
                className="dark:bg-dark-900"
              />
            </div>
          </div>
          <EnhancedDataTable<AttendanceRow>
            data={visibleLeaves}
            columns={columns}
          />
          {historyLeaveId !== null && (
            <LeaveHistoryModal
              leaveId={historyLeaveId}
              employeesData={employeesData}
              onClose={() => setHistoryLeaveId(null)}
            />
          )}
        </ComponentCard>
      </div>
    </>
  );
}