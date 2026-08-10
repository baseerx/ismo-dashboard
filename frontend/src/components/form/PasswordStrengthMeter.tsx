import {
  evaluatePassword,
  PasswordContext,
  PasswordEvaluation,
} from "../../utils/passwordPolicy";

interface PasswordStrengthMeterProps {
  password: string;
  context?: PasswordContext;
  /** Hide until the user has typed something. */
  showWhenEmpty?: boolean;
  /** Pass a pre-computed evaluation to avoid recomputing it. */
  evaluation?: PasswordEvaluation;
}

const STRENGTH_STYLES = {
  empty: { label: "", bar: "bg-gray-200 dark:bg-gray-700", text: "" },
  weak: {
    label: "Weak",
    bar: "bg-error-500",
    text: "text-error-600 dark:text-error-500",
  },
  fair: {
    label: "Fair",
    bar: "bg-warning-500",
    text: "text-warning-600 dark:text-orange-400",
  },
  good: {
    label: "Good",
    bar: "bg-blue-500",
    text: "text-blue-600 dark:text-blue-400",
  },
  strong: {
    label: "Strong",
    bar: "bg-success-500",
    text: "text-success-600 dark:text-success-500",
  },
} as const;

/**
 * Live strength bar plus the full requirement checklist.
 *
 * The whole list is always visible so the user can see what is still missing
 * instead of discovering one failure per submit attempt.
 */
export default function PasswordStrengthMeter({
  password,
  context,
  showWhenEmpty = false,
  evaluation,
}: PasswordStrengthMeterProps) {
  const result = evaluation ?? evaluatePassword(password, context);

  if (!password && !showWhenEmpty) return null;

  const style = STRENGTH_STYLES[result.strength];

  return (
    <div className="mt-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
          <div
            className={`h-full rounded-full transition-all duration-300 ${style.bar}`}
            style={{ width: `${result.score}%` }}
          />
        </div>
        {style.label && (
          <span className={`text-xs font-semibold ${style.text}`}>
            {style.label}
          </span>
        )}
      </div>

      <ul className="space-y-1">
        {result.rules.map((rule) => (
          <li
            key={rule.id}
            className={`flex items-start gap-2 text-xs ${
              rule.passed
                ? "text-success-600 dark:text-success-500"
                : "text-gray-500 dark:text-gray-400"
            }`}
          >
            <span aria-hidden="true" className="mt-px leading-none">
              {rule.passed ? "✓" : "○"}
            </span>
            <span>{rule.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
