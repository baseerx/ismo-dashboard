/**
 * Shared password policy for every form that sets a password.
 *
 * Kept in one place so the sign-up form, the change-password form and any
 * future form cannot drift apart on what counts as acceptable.
 *
 * NOTE: this runs in the browser, so it is a usability guard, not a security
 * boundary — anything here can be bypassed by posting to the API directly.
 * The same rules need to hold server side to actually be enforced; see
 * `validate_password` in Django's auth package.
 */

/** Single place to adjust the length floor. */
export const PASSWORD_MIN_LENGTH = 12;

/** Guards against absurd inputs (and against slow hashing on the server). */
export const PASSWORD_MAX_LENGTH = 128;

/** Characters that count as "special" — anything not a letter or a digit. */
const SPECIAL_CHARACTER_PATTERN = /[^A-Za-z0-9]/;

/**
 * Passwords common enough that an attacker tries them first. Not exhaustive —
 * a full list belongs server side — but it catches the usual suspects, plus
 * the ones this deployment is most likely to see.
 */
const COMMON_PASSWORDS = new Set([
  "password", "password1", "password123", "passw0rd", "p@ssword", "p@ssw0rd",
  "123456", "1234567", "12345678", "123456789", "1234567890", "12345",
  "qwerty", "qwerty123", "qwertyuiop", "asdfghjkl", "zxcvbnm",
  "111111", "000000", "654321", "abc123", "abcd1234", "a1b2c3d4",
  "iloveyou", "admin", "admin123", "administrator", "root", "toor",
  "welcome", "welcome1", "welcome123", "letmein", "monkey", "dragon",
  "sunshine", "princess", "football", "baseball", "master", "shadow",
  "superman", "trustno1", "changeme", "secret", "default", "test123",
  "pakistan", "pakistan123", "islamabad", "karachi", "lahore",
  "ismo", "ismo123", "ismo@123", "hris", "hris123", "leave123",
]);

/** Sequences we treat as predictable in either direction. */
const SEQUENCE_SOURCES = [
  "abcdefghijklmnopqrstuvwxyz",
  "0123456789",
  "qwertyuiop",
  "asdfghjkl",
  "zxcvbnm",
];

/** Length of a run before we call it a sequence. */
const SEQUENCE_RUN = 4;

export type PasswordContext = {
  username?: string;
  email?: string;
  firstName?: string;
  lastName?: string;
  erpId?: string;
  /** The password being replaced — the new one must differ. */
  currentPassword?: string;
};

export type PasswordRuleResult = {
  id: string;
  label: string;
  passed: boolean;
  /** Advisory rules do not block submission. */
  advisory?: boolean;
};

export type PasswordStrength = "empty" | "weak" | "fair" | "good" | "strong";

export type PasswordEvaluation = {
  rules: PasswordRuleResult[];
  /** True when every blocking rule passes. */
  isValid: boolean;
  /** First blocking failure, suitable for an inline field hint. */
  firstError: string | null;
  strength: PasswordStrength;
  /** 0-100, for the meter width. */
  score: number;
};

const containsSequence = (lowered: string): boolean => {
  for (const source of SEQUENCE_SOURCES) {
    const reversed = [...source].reverse().join("");
    for (const haystack of [source, reversed]) {
      for (let i = 0; i + SEQUENCE_RUN <= haystack.length; i += 1) {
        if (lowered.includes(haystack.slice(i, i + SEQUENCE_RUN))) return true;
      }
    }
  }
  return false;
};

/**
 * Personal details an attacker can look up, so a password must not embed
 * them. Mirrors the intent of Django's UserAttributeSimilarityValidator.
 */
const personalTokens = (context: PasswordContext): string[] => {
  const raw = [
    context.username,
    context.firstName,
    context.lastName,
    context.erpId,
    // Compare against the local part of the address, not the domain, or
    // every user at the same organisation would trip on it.
    context.email?.split("@")[0],
  ];

  return raw
    .map((value) => (value || "").trim().toLowerCase())
    // Two-character fragments match far too easily to be useful.
    .filter((value) => value.length >= 3);
};

/**
 * Evaluate a password against the policy.
 *
 * Every rule is returned (passed or not) so the UI can show a live checklist
 * rather than revealing one failure at a time.
 */
export function evaluatePassword(
  password: string,
  context: PasswordContext = {}
): PasswordEvaluation {
  const lowered = password.toLowerCase();
  const tokens = personalTokens(context);

  const rules: PasswordRuleResult[] = [
    {
      id: "length",
      label: `At least ${PASSWORD_MIN_LENGTH} characters`,
      passed: password.length >= PASSWORD_MIN_LENGTH,
    },
    {
      id: "uppercase",
      label: "An uppercase letter (A-Z)",
      passed: /[A-Z]/.test(password),
    },
    {
      id: "lowercase",
      label: "A lowercase letter (a-z)",
      passed: /[a-z]/.test(password),
    },
    {
      id: "digit",
      label: "A number (0-9)",
      passed: /[0-9]/.test(password),
    },
    {
      id: "special",
      label: "A special character (e.g. ! @ # $ % & *)",
      passed: SPECIAL_CHARACTER_PATTERN.test(password),
    },
    {
      id: "no-whitespace",
      label: "No spaces or tabs",
      passed: password.length > 0 && !/\s/.test(password),
    },
    {
      id: "max-length",
      label: `No longer than ${PASSWORD_MAX_LENGTH} characters`,
      passed: password.length <= PASSWORD_MAX_LENGTH,
    },
    {
      id: "not-common",
      label: "Not a commonly used password",
      passed: password.length > 0 && !COMMON_PASSWORDS.has(lowered),
    },
    {
      id: "no-repeats",
      label: "No character repeated 3+ times in a row",
      passed: password.length > 0 && !/(.)\1{2,}/.test(password),
    },
    {
      id: "no-sequence",
      label: "No obvious sequences (abcd, 1234, qwerty)",
      passed: password.length > 0 && !containsSequence(lowered),
    },
    {
      id: "not-personal",
      label: "Does not contain your name, username, email or ERP ID",
      passed:
        password.length === 0
          ? false
          : !tokens.some((token) => lowered.includes(token)),
    },
  ];

  if (context.currentPassword !== undefined) {
    rules.push({
      id: "differs-from-current",
      label: "Different from your current password",
      passed: password.length > 0 && password !== context.currentPassword,
    });
  }

  const blocking = rules.filter((rule) => !rule.advisory);
  const isValid =
    password.length > 0 && blocking.every((rule) => rule.passed);
  const firstError = blocking.find((rule) => !rule.passed)?.label ?? null;

  // Score rewards satisfying rules, with a bonus for genuine extra length —
  // a 20-character passphrase should read stronger than a bare 12.
  const satisfied = blocking.filter((rule) => rule.passed).length;
  const ruleScore = (satisfied / blocking.length) * 80;
  const lengthBonus = Math.min(
    20,
    Math.max(0, password.length - PASSWORD_MIN_LENGTH) * 2
  );
  const score = password.length === 0 ? 0 : Math.round(ruleScore + lengthBonus);

  let strength: PasswordStrength = "empty";
  if (password.length > 0) {
    if (!isValid) strength = score >= 55 ? "fair" : "weak";
    else strength = score >= 95 ? "strong" : "good";
  }

  return { rules, isValid, firstError, strength, score };
}

/** Convenience wrapper for callers that only need a yes/no plus a message. */
export function validatePassword(
  password: string,
  context: PasswordContext = {}
): { isValid: boolean; error: string | null } {
  const { isValid, firstError } = evaluatePassword(password, context);
  return { isValid, error: isValid ? null : firstError };
}
