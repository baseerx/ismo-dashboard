import { useState } from "react";
import { EyeCloseIcon, EyeIcon } from "../../../icons";

/**
 * A password box with an eye button to show or hide what is typed.
 *
 * Starts hidden. The button is a real button - reachable by keyboard and
 * announced by screen readers - and sits on the input itself, so it does not
 * move when an error message appears underneath.
 */
type PasswordInputProps = {
  id?: string;
  name?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  error?: boolean;
  hint?: string;
  disabled?: boolean;
  autoComplete?: "new-password" | "current-password" | "off";
  /** Read-only display of a password (e.g. one just generated). */
  readOnly?: boolean;
};

export default function PasswordInput({
  id,
  name,
  value,
  onChange,
  placeholder,
  error = false,
  hint,
  disabled = false,
  autoComplete = "new-password",
  readOnly = false,
}: PasswordInputProps) {
  const [visible, setVisible] = useState(false);

  const tone = disabled
    ? "cursor-not-allowed border-gray-300 bg-gray-100 text-gray-500 opacity-40 dark:border-gray-700 dark:bg-gray-800"
    : error
      ? "border-error-500 focus:border-error-300 focus:ring-error-500/20 dark:border-error-500"
      : "border-gray-300 bg-transparent text-gray-800 focus:border-brand-300 focus:ring-brand-500/20 dark:border-gray-700 dark:text-white/90";

  return (
    <div>
      <div className="relative">
        <input
          id={id}
          name={name}
          type={visible ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          readOnly={readOnly}
          autoComplete={autoComplete}
          spellCheck={false}
          data-password-input={id}
          className={`h-11 w-full appearance-none rounded-lg border px-4 py-2.5 pr-12 text-sm shadow-theme-xs placeholder:text-gray-400 focus:outline-hidden focus:ring-3 dark:bg-gray-900 dark:placeholder:text-white/30 ${
            readOnly ? "font-mono" : ""
          } ${tone}`}
        />
        <button
          type="button"
          onClick={() => setVisible((shown) => !shown)}
          disabled={disabled}
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          title={visible ? "Hide password" : "Show password"}
          className="absolute right-3 top-1/2 -translate-y-1/2 rounded p-1 text-gray-500 hover:text-gray-700 focus:outline-hidden focus-visible:ring-2 focus-visible:ring-brand-500/40 disabled:cursor-not-allowed"
        >
          {visible ? (
            <EyeIcon className="size-5 fill-gray-500 dark:fill-gray-400" />
          ) : (
            <EyeCloseIcon className="size-5 fill-gray-500 dark:fill-gray-400" />
          )}
        </button>
      </div>
      {hint && (
        <p className={`mt-1.5 text-xs ${error ? "text-error-500" : "text-gray-500"}`}>{hint}</p>
      )}
    </div>
  );
}
