import { useState } from "react";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import PageMeta from "../../components/common/PageMeta";
import Input from "../../components/form/input/InputField";
import Label from "../../components/form/Label";
import Button from "../../components/ui/button/Button";
import { toast, ToastContainer } from "react-toastify";
import PasswordStrengthMeter from "../../components/form/PasswordStrengthMeter";
import { evaluatePassword } from "../../utils/passwordPolicy";
import axios from "../../api/axios"; // Adjust the import path as necessary
export default function ChangePassword() {
    type ChangePasswordProps = {
        user_id?: string;
    old_password: string;
    new_password1: string;
    new_password2: string;
  };

    const currentUser = JSON.parse(localStorage.getItem("user") || "{}");

    // Built by a function so a reset after a successful change keeps user_id.
    // The previous reset rebuilt the object without it, so the next attempt
    // posted user_id: undefined and the API rejected it as a missing field —
    // the form only worked again after a page reload.
    const buildBlankForm = (): ChangePasswordProps => ({
      user_id: currentUser.user_id,
      old_password: "",
      new_password1: "",
      new_password2: "",
    });

    const buildBlankErrors = (): ChangePasswordProps => ({
      old_password: "",
      new_password1: "",
      new_password2: "",
    });

    const [data, setData] = useState<ChangePasswordProps>(buildBlankForm);
    const [err, setError] = useState<ChangePasswordProps>(buildBlankErrors);

    // The new password is checked against the account's own details and
    // against the password being replaced.
    const passwordCheck = evaluatePassword(data.new_password1, {
      username: currentUser.username,
      email: currentUser.email,
      firstName: currentUser.first_name,
      lastName: currentUser.last_name,
      erpId: currentUser.erpid ? String(currentUser.erpid) : undefined,
      currentPassword: data.old_password,
    });
  const changePassword = async () => {
    // Logic to handle password change
    const { old_password, new_password1, new_password2 } = data;
    if (old_password === "" || new_password1 === "" || new_password2 === "") {
      setError({
        old_password: old_password === "" ? "Current password is required" : "",
        new_password1: new_password1 === "" ? "New password is required" : "",
        new_password2: new_password2 === "" ? "Confirm new password is required" : "",
      });
      return;
    }
    // Strength policy, before anything is sent.
    if (!passwordCheck.isValid) {
      setError({
        ...buildBlankErrors(),
        new_password1:
          passwordCheck.firstError ||
          "Password does not meet the requirements",
      });
      toast.error("New password does not meet the security requirements");
      return;
    }

    if (new_password1 !== new_password2) {
      setError({
        ...buildBlankErrors(),
        new_password2: "New passwords do not match",
      });
      toast.error("New passwords do not match");
      return;
      }

      try {
          const response = await axios.post("/users/change-password/", data);
            if (response.status === 200) {
                toast.success("Password changed successfully");
                setData(buildBlankForm());
                setError(buildBlankErrors());
          }
          else {
            toast.error(response.data.error || "Failed to change password");
          }
      }
      catch (error: any) {
        console.error("Error changing password:", error);
        toast.error(
          error?.response?.data?.error || "Failed to change password"
        );
      }

    // Call API to change password
  };
  return (
    <>
      <PageMeta
        title="ISMO LEAVE SYSTEM - Change Password"
        description="This is ISMO Leave System, a web application for managing employee leave requests. & Change Password"
      />
      <PageBreadcrumb pageTitle="Profile" />
      <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03] lg:p-6">
        <h3 className="mb-5 text-lg font-semibold text-gray-800 dark:text-white/90 lg:mb-7">
          Change Password
        </h3>
        <div className="space-y- grid grid-cols-2 gap-6">
          <div className="col-span-2 lg:col-span-1">
            <Label htmlFor="old_password">Current Password</Label>
            <Input
              id="old_password"
              name="old_password"
              type="password"
              value={data.old_password}
              onChange={(e) =>
                setData({ ...data, old_password: e.target.value })
              }
              error={!!err.old_password}
              hint={err.old_password}
              placeholder="Enter current password"
            />
          </div>

          <div className="col-span-2 lg:col-span-1">
            <Label htmlFor="new_password1">New Password</Label>
            <Input
              id="new_password1"
              name="new_password1"
                          type="password"
                value={data.new_password1}
              onChange={(e) =>
                setData({ ...data, new_password1: e.target.value })
              }
                error={!!err.new_password1}
              hint={err.new_password1}
              placeholder="Enter new password"
            />
            <PasswordStrengthMeter
              password={data.new_password1}
              evaluation={passwordCheck}
            />
          </div>

          <div className="col-span-2 lg:col-span-1">
            <Label htmlFor="new_password2">Confirm New Password</Label>
            <Input
              id="new_password2"
              name="new_password2"
              type="password"
              value={data.new_password2}
              onChange={(e) =>
                setData({ ...data, new_password2: e.target.value })
              }
              error={
                !!err.new_password2 ||
                (!!data.new_password2 &&
                  data.new_password2 !== data.new_password1)
              }
              hint={
                err.new_password2 ||
                (data.new_password2 &&
                data.new_password2 !== data.new_password1
                  ? "New passwords do not match"
                  : "")
              }
              placeholder="Confirm new password"
            />
          </div>
        </div>
        <div className="flex items-center justify-center">
          <Button
            size="sm"
            className="w-1/4 mt-7 ml-5"
            variant="primary"
            onClick={changePassword}
          >
            Apply
          </Button>
              </div>
              <ToastContainer position="bottom-right" />
      </div>
    </>
  );
}
