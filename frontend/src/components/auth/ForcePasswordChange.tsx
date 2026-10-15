import { useState } from "react";
import { toast, ToastContainer } from "react-toastify";
import axios from "../../api/axios";
import Label from "../form/Label";
import Input from "../form/input/InputField";
import PasswordInput from "../form/input/PasswordInput";
import PasswordStrengthMeter from "../form/PasswordStrengthMeter";
import Button from "../ui/button/Button";
import { evaluatePassword } from "../../utils/passwordPolicy";

const EMAIL = /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/;

/**
 * The one thing a user can do after an administrator has reset their
 * password: confirm their email and choose their own password. Shown by
 * ProtectedRoute in place of every page until it is done; the only other way
 * out is signing out.
 */
export default function ForcePasswordChange({
  email: startingEmail,
  onDone,
  onSignOut,
}: {
  email: string;
  onDone: (email: string) => void;
  onSignOut: () => void;
}) {
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const [email, setEmail] = useState(startingEmail || user.email || "");
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const check = evaluatePassword(next, {
    username: user.username,
    email,
    firstName: user.first_name,
    lastName: user.last_name,
    erpId: user.erpid ? String(user.erpid) : undefined,
    currentPassword: current,
  });

  const submit = async () => {
    const problems: Record<string, string> = {};
    if (!email.trim()) problems.email = "Your email address is required";
    else if (!EMAIL.test(email.trim())) problems.email = "Enter a valid email address";
    if (!current) problems.current = "Enter the password the administrator gave you";
    if (!next) problems.next = "Choose a new password";
    else if (!check.isValid) problems.next = check.firstError || "The password does not meet the policy";
    if (next && confirm !== next) problems.confirm = "Passwords do not match";
    setErrors(problems);
    if (Object.keys(problems).length) return;

    setSaving(true);
    try {
      const token = localStorage.getItem("token");
      const response = await axios.post(
        "/users/change-password/",
        { old_password: current, new_password1: next, new_password2: confirm, email: email.trim() },
        { headers: token ? { Authorization: `Bearer ${token}` } : undefined }
      );
      toast.success("Your password has been changed");
      onDone(response.data?.email ?? email.trim());
    } catch (error: any) {
      const returned = error?.response?.data;
      if (returned?.field === "email") setErrors({ email: returned.error });
      else if (/old password/i.test(returned?.error ?? "")) {
        setErrors({ current: "That is not the password the administrator gave you" });
      } else if (returned?.password_errors?.length) setErrors({ next: returned.password_errors[0] });
      else toast.error(returned?.error ?? "Could not change the password. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-10 dark:bg-gray-900" data-force-password-change>
      <ToastContainer position="bottom-right" />
      <div className="w-full max-w-lg rounded-2xl border border-gray-200 bg-white p-6 shadow-theme-xs dark:border-gray-800 dark:bg-white/[0.03] sm:p-8">
        <div className="mb-5 rounded-lg border border-warning-200 bg-warning-50 px-4 py-3 text-sm text-warning-700 dark:border-warning-500/30 dark:bg-warning-500/10 dark:text-warning-400">
          <p className="font-semibold">Set your own password to continue</p>
          <p className="mt-0.5">
            An administrator reset your password. Confirm your email address and choose a new
            password before using the system.
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <Label htmlFor="force-email">Email address</Label>
            <Input
              id="force-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              error={!!errors.email}
              hint={errors.email || "Correct it here if it is wrong - you sign in with this address."}
            />
          </div>
          <div>
            <Label htmlFor="force-current">Password from the administrator</Label>
            <PasswordInput
              id="force-current"
              value={current}
              onChange={setCurrent}
              autoComplete="current-password"
              error={!!errors.current}
              hint={errors.current}
            />
          </div>
          <div>
            <Label htmlFor="force-new">New password</Label>
            <PasswordInput id="force-new" value={next} onChange={setNext} error={!!errors.next} hint={errors.next} />
            <PasswordStrengthMeter password={next} evaluation={check} />
          </div>
          <div>
            <Label htmlFor="force-confirm">Confirm new password</Label>
            <PasswordInput
              id="force-confirm"
              value={confirm}
              onChange={setConfirm}
              error={!!errors.confirm || (!!confirm && confirm !== next)}
              hint={errors.confirm || (confirm && confirm !== next ? "Passwords do not match" : "")}
            />
          </div>
        </div>

        <div className="mt-6 flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={onSignOut}
            className="text-sm font-medium text-gray-500 hover:text-gray-700 dark:text-gray-400"
          >
            Sign out
          </button>
          <Button size="sm" variant="primary" onClick={submit} disabled={saving}>
            {saving ? "Saving..." : "Change password and continue"}
          </Button>
        </div>
      </div>
    </div>
  );
}
