import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import EnhancedDataTable from "../../components/tables/DataTables/DataTableOne";
import axios from "../../api/axios";
import { useState, useEffect } from "react";
import moment from "moment";
import { ToastContainer, toast } from "react-toastify";
import { ColumnDef } from "@tanstack/react-table";
import DatePicker from "../../components/form/date-picker";
import Button from "../../components/ui/button/Button";
import Label from "../../components/form/Label";
import Select from "../../components/form/Select";
import Input from "../../components/form/input/InputField";
import PasswordInput from "../../components/form/input/PasswordInput";
import Radio from "../../components/form/input/Radio";
import PasswordStrengthMeter from "../../components/form/PasswordStrengthMeter";
import { Modal } from "../../components/ui/modal";
import { evaluatePassword } from "../../utils/passwordPolicy";

type UserRow = {
  id?: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  is_staff: boolean;
  is_active: boolean;
  is_superuser: boolean;
  date_joined?: string;
};

/** Sign-in lock status of one account (users/lockout.py). */
type AccountStatus = {
  failed_attempts: number;
  is_locked: boolean;
  locked_at: string | null;
  locked_reason: string;
  locked_by_admin: boolean;
};

type UserFormData = {
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  erpid: string;
  verify_password: string;
  is_staff: boolean;
  is_active: boolean;
  is_superuser: boolean;
  date_joined: string;
};

const EMAIL = /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/;

const blankForm = (): UserFormData => ({
  username: "",
  first_name: "",
  last_name: "",
  email: "",
  password: "",
  erpid: "",
  verify_password: "",
  is_staff: false,
  is_active: true,
  is_superuser: false,
  date_joined: moment().format("YYYY-MM-DD"),
});

/** Account management needs the signed-in administrator's token. */
const authHeader = () => {
  const token = localStorage.getItem("token");
  return token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;
};

/** The server's own explanation, when it gave one. */
const serverMessage = (error: any, fallback: string) =>
  error?.response?.data?.error ?? (error?.response ? fallback : "Could not reach the server");

export default function CreateUser() {
  const currentUser = JSON.parse(localStorage.getItem("user") || "{}");
  const canMakeSuperusers = !!currentUser.is_superuser;

  const [users, setUsers] = useState<UserRow[]>([]);
  const [accountStatus, setAccountStatus] = useState<Record<string, AccountStatus>>({});
  // Until the lock status arrives the table says nothing rather than "Active".
  const [statusLoaded, setStatusLoaded] = useState(false);
  const [data, setData] = useState<UserFormData>(blankForm);
  const [fielderror, setFieldError] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  // Remounts the date picker so it clears with the rest of the form.
  const [formKey, setFormKey] = useState(0);

  // Reset-password dialog.
  const [resetFor, setResetFor] = useState<UserRow | null>(null);
  const [resetMode, setResetMode] = useState<"generate" | "choose">("generate");
  const [resetPassword, setResetPassword] = useState("");
  const [resetError, setResetError] = useState("");
  const [resetting, setResetting] = useState(false);
  const [newPassword, setNewPassword] = useState<string | null>(null);

  const passwordCheck = evaluatePassword(data.password, {
    username: data.username,
    email: data.email,
    firstName: data.first_name,
    lastName: data.last_name,
    erpId: data.erpid,
  });

  const resetCheck = evaluatePassword(resetPassword, {
    username: resetFor?.username,
    email: resetFor?.email,
    firstName: resetFor?.first_name,
    lastName: resetFor?.last_name,
  });

  useEffect(() => {
    getUsers();
  }, []);

  const getUsers = async () => {
    try {
      const response = await axios.get("/users/get_auth_users/");
      setUsers(
        (Array.isArray(response.data) ? response.data : []).map((user: any) => ({
          id: user.id,
          username: user.username,
          first_name: user.first_name,
          last_name: user.last_name,
          email: user.email,
          is_staff: user.is_staff,
          is_active: user.is_active,
          is_superuser: user.is_superuser,
        }))
      );
    } catch (error) {
      console.error("Error fetching users:", error);
      toast.error("Failed to load users");
    }
    try {
      const response = await axios.get("/users/account_status/", authHeader());
      setAccountStatus(response.data ?? {});
      setStatusLoaded(true);
    } catch {
      setAccountStatus({});
      setStatusLoaded(false);
    }
  };

  const toggleLock = async (user: UserRow) => {
    const locked = accountStatus[String(user.id)]?.is_locked;
    let reason = "";
    if (!locked) {
      const answer = window.prompt(
        `Lock the account "${user.username}"? They will not be able to sign in until it is unlocked.

Reason (optional):`,
        ""
      );
      if (answer === null) return;
      reason = answer;
    } else if (!window.confirm(`Unlock the account "${user.username}"?`)) {
      return;
    }
    try {
      await axios.post(
        `/users/${locked ? "unlock_user" : "lock_user"}/${user.id}/`,
        locked ? {} : { reason },
        authHeader()
      );
      toast.success(locked ? `${user.username} unlocked` : `${user.username} locked`);
      getUsers();
    } catch (error: any) {
      toast.error(serverMessage(error, locked ? "Failed to unlock" : "Failed to lock"));
    }
  };

  const set = (field: keyof UserFormData, value: string | boolean) => {
    setData((previous) => ({ ...previous, [field]: value }));
    setFieldError((previous) => {
      if (!previous[field]) return previous;
      const next = { ...previous };
      delete next[field];
      return next;
    });
  };

  const handleDeleteUser = async (user: UserRow) => {
    if (!window.confirm(`Delete the account "${user.username}"? This cannot be undone.`)) return;
    try {
      await axios.post(`/users/delete_user/${user.id}/`, {}, authHeader());
      toast.success("User deleted successfully");
      getUsers();
    } catch (error: any) {
      toast.error(serverMessage(error, "Failed to delete user"));
    }
  };

  const openReset = (user: UserRow) => {
    setResetFor(user);
    setResetMode("generate");
    setResetPassword("");
    setResetError("");
    setNewPassword(null);
  };

  const closeReset = () => {
    setResetFor(null);
    setNewPassword(null);
    setResetPassword("");
  };

  const submitReset = async () => {
    if (!resetFor) return;
    if (resetMode === "choose" && !resetCheck.isValid) {
      setResetError(resetCheck.firstError || "The password does not meet the policy");
      return;
    }
    setResetting(true);
    try {
      const response = await axios.post(
        `/users/reset_password/${resetFor.id}/`,
        resetMode === "choose" ? { password: resetPassword } : {},
        authHeader()
      );
      setNewPassword(response.data?.password ?? "");
      setResetError("");
      toast.success(`Password reset for ${resetFor.username}`);
    } catch (error: any) {
      setResetError(serverMessage(error, "Failed to reset the password"));
    } finally {
      setResetting(false);
    }
  };

  const copyNewPassword = async () => {
    if (!newPassword) return;
    try {
      await navigator.clipboard.writeText(newPassword);
      toast.success("Password copied");
    } catch {
      toast.error("Copy failed - select the password and copy it by hand");
    }
  };

  const columns: ColumnDef<UserRow>[] = [
    { header: "Username", accessorKey: "username" },
    { header: "First Name", accessorKey: "first_name" },
    { header: "Last Name", accessorKey: "last_name" },
    { header: "Email", accessorKey: "email" },
    {
      header: "Staff",
      accessorKey: "is_staff",
      cell: ({ getValue }) => (getValue<boolean>() ? "Yes" : "No"),
    },
    {
      header: "Active",
      accessorKey: "is_active",
      cell: ({ getValue }) => (getValue<boolean>() ? "Yes" : "No"),
    },
    {
      header: "Superuser",
      accessorKey: "is_superuser",
      cell: ({ getValue }) => (getValue<boolean>() ? "Yes" : "No"),
    },
    {
      header: "Status",
      id: "lock_status",
      cell: ({ row }) => {
        const status = accountStatus[String(row.original.id)];
        if (row.original.is_superuser) {
          // Superusers are outside the lockout policy (users/lockout.py).
          return (
            <span
              data-lock-status={row.original.username}
              title="Superusers are exempt from account locking"
              className="inline-flex whitespace-nowrap rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400"
            >
              Exempt
            </span>
          );
        }
        if (!statusLoaded) {
          return <span className="text-gray-400" data-lock-status={row.original.username}>—</span>;
        }
        if (status?.is_locked) {
          return (
            <div data-lock-status={row.original.username}>
              <span className="inline-flex whitespace-nowrap rounded-full bg-error-50 px-2.5 py-0.5 text-xs font-medium text-error-700 dark:bg-error-500/15 dark:text-error-400">
                Locked
              </span>
              <div className="mt-1 max-w-48 text-[11px] leading-snug text-gray-500">
                {status.locked_reason}
                {status.locked_at ? ` · ${moment(status.locked_at).format("DD MMM YYYY HH:mm")}` : ""}
              </div>
            </div>
          );
        }
        return (
          <div data-lock-status={row.original.username}>
            <span className="inline-flex whitespace-nowrap rounded-full bg-success-50 px-2.5 py-0.5 text-xs font-medium text-success-700 dark:bg-success-500/15 dark:text-success-500">
              Active
            </span>
            {status?.failed_attempts ? (
              <div className="mt-1 text-[11px] text-warning-600">
                {status.failed_attempts} failed attempt{status.failed_attempts === 1 ? "" : "s"}
              </div>
            ) : null}
          </div>
        );
      },
    },
    {
      header: "Actions",
      id: "actions",
      cell: ({ row }) => {
        const self = row.original.id === currentUser.user_id;
        // Only a superuser may touch another superuser's password.
        const protectedAccount = row.original.is_superuser && !canMakeSuperusers;
        return (
          <div className="flex gap-2">
            <Button
              size="xs"
              variant="danger"
              disabled={self || protectedAccount}
              onClick={() => handleDeleteUser(row.original)}
            >
              Delete
            </Button>
            <Button
              size="xs"
              variant="primary"
              disabled={protectedAccount}
              onClick={() => openReset(row.original)}
            >
              Reset Password
            </Button>
            <span
              title={row.original.is_superuser ? "Superusers are exempt from account locking" : undefined}
            >
              <Button
                size="xs"
                variant="outline"
                disabled={self || row.original.is_superuser}
                onClick={() => toggleLock(row.original)}
              >
                {accountStatus[String(row.original.id)]?.is_locked && !row.original.is_superuser
                  ? "Unlock"
                  : "Lock"}
              </Button>
            </span>
          </div>
        );
      },
    },
  ];

  const createUser = async () => {
    const errors: Record<string, string> = {};

    if (!data.username.trim()) errors.username = "Username is required";
    if (!data.first_name.trim()) errors.first_name = "First name is required";
    if (!data.last_name.trim()) errors.last_name = "Last name is required";
    if (!data.email.trim()) errors.email = "Email is required";
    else if (!EMAIL.test(data.email.trim())) errors.email = "Enter a valid email address";
    if (!data.erpid.trim()) errors.erpid = "ERP ID is required";
    else if (!/^\d+$/.test(data.erpid.trim())) errors.erpid = "ERP ID must be a number";
    if (!data.password) errors.password = "Password is required";
    else if (!passwordCheck.isValid) {
      errors.password = passwordCheck.firstError || "The password does not meet the policy";
    }
    if (!data.verify_password) errors.verify_password = "Confirm the password";
    else if (data.password !== data.verify_password) {
      errors.verify_password = "Passwords do not match";
    }
    if (!data.date_joined) errors.date_joined = "Date joined is required";

    if (Object.keys(errors).length > 0) {
      setFieldError(errors);
      toast.error("Please fix the highlighted fields");
      return;
    }

    setSaving(true);
    try {
      await axios.post(
        "/users/create_user/",
        { ...data, username: data.username.trim(), email: data.email.trim(), erpid: data.erpid.trim() },
        authHeader()
      );
      setData(blankForm());
      setFieldError({});
      setFormKey((key) => key + 1);
      getUsers();
      toast.success("User created successfully");
    } catch (error: any) {
      const returned = error?.response?.data;
      if (returned?.password_errors?.length) {
        setFieldError({ password: returned.password_errors[0] });
      }
      toast.error(serverMessage(error, "Failed to create the user"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <PageMeta title="ISMO - Create User" description="ISMO Admin Dashboard - Create User" />
      <PageBreadcrumb pageTitle="Create User" />
      <div className="space-y-6">
        <ComponentCard title="Create New User">
          <ToastContainer position="bottom-right" />

          <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2" key={formKey}>
            <div className="w-full">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                type="text"
                placeholder="Enter username"
                value={data.username}
                onChange={(e) => set("username", e.target.value)}
                error={!!fielderror.username}
                hint={fielderror.username}
              />
            </div>

            <div className="w-full">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="Enter email"
                value={data.email}
                onChange={(e) => set("email", e.target.value)}
                error={!!fielderror.email}
                hint={fielderror.email}
              />
            </div>

            <div className="w-full">
              <Label htmlFor="first_name">First Name</Label>
              <Input
                id="first_name"
                type="text"
                placeholder="Enter first name"
                value={data.first_name}
                onChange={(e) => set("first_name", e.target.value)}
                error={!!fielderror.first_name}
                hint={fielderror.first_name}
              />
            </div>

            <div className="w-full">
              <Label htmlFor="last_name">Last Name</Label>
              <Input
                id="last_name"
                type="text"
                placeholder="Enter last name"
                value={data.last_name}
                onChange={(e) => set("last_name", e.target.value)}
                error={!!fielderror.last_name}
                hint={fielderror.last_name}
              />
            </div>

            <div className="w-full">
              <Label htmlFor="password">Password</Label>
              <PasswordInput
                id="password"
                placeholder="Enter password"
                value={data.password}
                onChange={(value) => set("password", value)}
                error={!!fielderror.password}
                hint={fielderror.password}
              />
              <PasswordStrengthMeter password={data.password} evaluation={passwordCheck} />
            </div>

            <div className="w-full">
              <Label htmlFor="verify_password">Verify Password</Label>
              <PasswordInput
                id="verify_password"
                placeholder="Confirm password"
                value={data.verify_password}
                onChange={(value) => set("verify_password", value)}
                error={
                  !!fielderror.verify_password ||
                  (!!data.verify_password && data.verify_password !== data.password)
                }
                hint={
                  fielderror.verify_password ||
                  (data.verify_password && data.verify_password !== data.password
                    ? "Passwords do not match"
                    : data.verify_password
                      ? "Passwords match"
                      : "")
                }
              />
            </div>

            <div className="w-full">
              <DatePicker
                id="date-joined-picker"
                defaultDate={data.date_joined}
                label="Date Joined"
                placeholder="Select date joined"
                onChange={(_dates, currentDateString) => set("date_joined", currentDateString)}
              />
            </div>

            <div className="w-full">
              <Label>Superuser Status</Label>
              <Select
                options={[
                  { label: "No", value: "false" },
                  ...(canMakeSuperusers ? [{ label: "Yes", value: "true" }] : []),
                ]}
                placeholder="Select superuser status"
                value={data.is_superuser ? "true" : "false"}
                onChange={(value) => set("is_superuser", value === "true")}
              />
              {!canMakeSuperusers && (
                <p className="mt-1 text-xs text-gray-400">Only a superuser can create another superuser.</p>
              )}
            </div>

            <div className="w-full">
              <Label htmlFor="erpid">Erp Id</Label>
              <Input
                id="erpid"
                type="text"
                placeholder="Enter ERP ID"
                value={data.erpid}
                onChange={(e) => set("erpid", e.target.value)}
                error={!!fielderror.erpid}
                hint={fielderror.erpid}
              />
            </div>
          </div>

          <div className="my-6 flex items-center justify-center gap-12">
            <div className="flex items-center gap-2">
              <Label className="mr-2">Is Staff</Label>
              <Radio id="staff-yes" name="is_staff" value="1" checked={data.is_staff === true}
                label="Yes" onChange={() => set("is_staff", true)} />
              <Radio id="staff-no" name="is_staff" value="0" checked={data.is_staff === false}
                label="No" onChange={() => set("is_staff", false)} />
            </div>
            <div className="flex items-center gap-2">
              <Label className="mr-2">Is Active</Label>
              <Radio id="active-yes" name="is_active" value="1" checked={data.is_active === true}
                label="Yes" onChange={() => set("is_active", true)} />
              <Radio id="active-no" name="is_active" value="0" checked={data.is_active === false}
                label="No" onChange={() => set("is_active", false)} />
            </div>
          </div>

          <div className="flex w-full items-center justify-center">
            <Button size="sm" className="mt-7 w-1/3" variant="primary" onClick={createUser} disabled={saving}>
              {saving ? "Creating..." : "Create User"}
            </Button>
          </div>

          <EnhancedDataTable<UserRow> data={users} columns={columns} />
        </ComponentCard>
      </div>

      {/* ------------------------ reset password dialog ----------------------- */}
      <Modal isOpen={!!resetFor} onClose={closeReset} className="m-4 max-w-lg">
        <div className="p-6 sm:p-8" data-reset-modal>
          <h3 className="pr-12 text-lg font-semibold text-gray-800 dark:text-white/90">
            Reset password - {resetFor?.username}
          </h3>

          {newPassword === null ? (
            <>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Stored passwords are encrypted and cannot be shown. Set a new one, then pass it
                on to the user.
              </p>
              <div className="mt-5 space-y-3">
                <Radio id="reset-generate" name="reset-mode" value="generate"
                  checked={resetMode === "generate"} label="Generate a strong password"
                  onChange={() => { setResetMode("generate"); setResetError(""); }} />
                <Radio id="reset-choose" name="reset-mode" value="choose"
                  checked={resetMode === "choose"} label="Set a password myself"
                  onChange={() => { setResetMode("choose"); setResetError(""); }} />
              </div>
              {resetMode === "choose" && (
                <div className="mt-4">
                  <Label htmlFor="reset-password">New password</Label>
                  <PasswordInput
                    id="reset-password"
                    value={resetPassword}
                    onChange={(value) => { setResetPassword(value); setResetError(""); }}
                    placeholder="Enter the new password"
                    error={!!resetError}
                  />
                  <PasswordStrengthMeter password={resetPassword} evaluation={resetCheck} />
                </div>
              )}
              {resetError && <p className="mt-3 text-sm text-error-500">{resetError}</p>}
              <div className="mt-6 flex justify-end gap-3">
                <Button size="sm" variant="outline" onClick={closeReset}>Cancel</Button>
                <Button size="sm" variant="primary" onClick={submitReset} disabled={resetting}>
                  {resetting ? "Resetting..." : "Reset Password"}
                </Button>
              </div>
            </>
          ) : (
            <>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                The new password for <strong>{resetFor?.username}</strong>. It is shown only now -
                copy it and pass it on securely.
              </p>
              <div className="mt-5">
                <Label htmlFor="new-password-display">New password</Label>
                <PasswordInput
                  id="new-password-display"
                  value={newPassword}
                  onChange={() => undefined}
                  readOnly
                  autoComplete="off"
                />
              </div>
              <div className="mt-6 flex justify-end gap-3">
                <Button size="sm" variant="outline" onClick={copyNewPassword}>Copy</Button>
                <Button size="sm" variant="primary" onClick={closeReset}>Done</Button>
              </div>
            </>
          )}
        </div>
      </Modal>
    </>
  );
}
