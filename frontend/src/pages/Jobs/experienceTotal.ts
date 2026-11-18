import moment from "moment";

type ExperiencePeriod = {
  from_date?: string | null;
  to_date?: string | null;
  is_current?: boolean;
};

/**
 * Total experience across all positions, e.g. "7 years 3 months".
 *
 * Overlapping periods (say, two roles held at once) are counted once, so the
 * total never exceeds the time actually spent working. A current role runs up
 * to `asOf` (today by default). Rows without valid dates are skipped.
 * Returns "" when no row has usable dates.
 */
export const totalExperience = (
  rows: ExperiencePeriod[],
  asOf?: string | null
): string => {
  const reference = asOf ? moment(asOf) : moment();
  const periods = rows
    .map((row) => {
      if (!row.from_date) return null;
      const start = moment(row.from_date, "YYYY-MM-DD");
      const finish = row.is_current
        ? reference.clone()
        : row.to_date
          ? moment(row.to_date, "YYYY-MM-DD")
          : null;
      if (!finish || !start.isValid() || !finish.isValid() || finish.isBefore(start)) {
        return null;
      }
      return { start, finish };
    })
    .filter((p): p is { start: moment.Moment; finish: moment.Moment } => p !== null)
    .sort((a, b) => a.start.valueOf() - b.start.valueOf());

  if (periods.length === 0) return "";

  // Merge overlapping periods.
  const merged: { start: moment.Moment; finish: moment.Moment }[] = [];
  for (const period of periods) {
    const last = merged[merged.length - 1];
    if (last && !period.start.isAfter(last.finish)) {
      if (period.finish.isAfter(last.finish)) last.finish = period.finish;
    } else {
      merged.push({ start: period.start.clone(), finish: period.finish.clone() });
    }
  }

  // Whole months per period; leftover days pooled and folded into months.
  let months = 0;
  let days = 0;
  for (const { start, finish } of merged) {
    const whole = finish.diff(start, "months");
    months += whole;
    days += finish.diff(start.clone().add(whole, "months"), "days");
  }
  months += Math.floor(days / 30);

  const years = Math.floor(months / 12);
  const remainder = months % 12;
  const parts: string[] = [];
  if (years) parts.push(`${years} year${years === 1 ? "" : "s"}`);
  if (remainder) parts.push(`${remainder} month${remainder === 1 ? "" : "s"}`);
  return parts.join(" ") || "less than a month";
};
