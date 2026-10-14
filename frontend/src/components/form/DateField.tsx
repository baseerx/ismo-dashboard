import { useEffect, useRef } from "react";
import flatpickr from "flatpickr";
import "flatpickr/dist/flatpickr.css";
import { CalenderIcon } from "../../icons";

/**
 * A date input that opens a calendar, driven by its `value` like any other
 * field. Values go in and out as "YYYY-MM-DD"; an empty string means no date.
 *
 * The month and year are dropdowns in the calendar header, so a date years
 * back (a joining date, say) is two clicks rather than many.
 */
type DateFieldProps = {
  id: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  /** Earliest / latest selectable date, as "YYYY-MM-DD". */
  minDate?: string;
  maxDate?: string;
  error?: boolean;
  hint?: string;
  disabled?: boolean;
};

export default function DateField({
  id,
  value,
  onChange,
  placeholder = "Select date",
  minDate,
  maxDate,
  error = false,
  hint,
  disabled = false,
}: DateFieldProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const pickerRef = useRef<flatpickr.Instance | null>(null);
  // The latest onChange, so the picker never calls a stale one.
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    if (!inputRef.current) return;
    const instance = flatpickr(inputRef.current, {
      dateFormat: "Y-m-d",
      altInput: true,
      altFormat: "d M Y",
      monthSelectorType: "dropdown",
      disableMobile: true,
      allowInput: false,
      onChange: (_dates, dateText) => onChangeRef.current(dateText),
    });
    pickerRef.current = instance;
    return () => {
      instance.destroy();
      pickerRef.current = null;
    };
  }, []);

  // Keep the calendar in step with the value and limits it is given.
  useEffect(() => {
    const picker = pickerRef.current;
    if (!picker) return;
    picker.set("minDate", minDate || undefined);
    picker.set("maxDate", maxDate || undefined);
    const current = picker.selectedDates[0]
      ? picker.formatDate(picker.selectedDates[0], "Y-m-d")
      : "";
    if (current !== value) picker.setDate(value || [], false);
    if (picker.altInput) {
      picker.altInput.disabled = disabled;
      picker.altInput.placeholder = placeholder;
      picker.altInput.id = `${id}-display`;
      picker.altInput.className = inputClass(error, disabled);
    }
  }, [value, minDate, maxDate, disabled, placeholder, error, id]);

  return (
    <div>
      <div className="relative">
        {/* Holds the YYYY-MM-DD value. Hidden from the start: the box the
            user sees is the readable one flatpickr adds next to it. */}
        <input ref={inputRef} id={id} type="hidden" data-date-field={id} />
        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 dark:text-gray-400">
          <CalenderIcon className="size-5" />
        </span>
        {value && !disabled && (
          <button
            type="button"
            aria-label="Clear date"
            onClick={() => onChange("")}
            className="absolute right-10 top-1/2 -translate-y-1/2 text-sm text-gray-400 hover:text-gray-600"
          >
            ×
          </button>
        )}
      </div>
      {hint && (
        <p className={`mt-1.5 text-xs ${error ? "text-error-500" : "text-gray-500"}`}>{hint}</p>
      )}
    </div>
  );
}

const inputClass = (error: boolean, disabled: boolean) =>
  `h-11 w-full cursor-pointer rounded-lg border bg-transparent px-4 py-2.5 pr-16 text-sm shadow-theme-xs placeholder:text-gray-400 focus:outline-hidden focus:ring-3 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30 ${
    disabled
      ? "cursor-not-allowed bg-gray-100 text-gray-500 dark:bg-gray-800"
      : "text-gray-800"
  } ${
    error
      ? "border-error-500 focus:ring-error-500/10"
      : "border-gray-300 focus:border-brand-300 focus:ring-brand-500/20 dark:border-gray-700 dark:focus:border-brand-800"
  }`;
