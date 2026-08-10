export type ReportMeta = {
  leave_type?: string;
  start_date?: string;
  end_date?: string;
  statuses_counted?: string[];
  counting_method?: string;
  records_read?: number;
  data_quality_notes?: string[];
};

/**
 * States exactly what the numbers above represent — the window, which
 * statuses were counted, how days were tallied, and anything the underlying
 * data forced the report to skip or merge. Without this the two leave
 * reports look comparable when they are not: the individual report counts
 * approved *and* pending days, the section report counts approved only.
 */
export default function ReportAuditNote({ meta }: { meta: ReportMeta | null }) {
  if (!meta) return null;

  const statuses = meta.statuses_counted?.length
    ? meta.statuses_counted.join(" + ")
    : "—";
  const notes = meta.data_quality_notes ?? [];

  return (
    <div className="mt-6 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-gray-600 dark:text-gray-400">
        <span>
          Period:{" "}
          <span className="font-medium text-gray-800 dark:text-gray-200">
            {meta.start_date} to {meta.end_date}
          </span>
        </span>
        <span>
          Counting:{" "}
          <span className="font-medium text-gray-800 dark:text-gray-200">
            {statuses}
          </span>
        </span>
        <span>
          Method:{" "}
          <span className="font-medium text-gray-800 dark:text-gray-200">
            {meta.counting_method}
          </span>
        </span>
        <span>
          Records read:{" "}
          <span className="font-medium text-gray-800 dark:text-gray-200">
            {meta.records_read ?? 0}
          </span>
        </span>
      </div>

      {notes.length > 0 && (
        <ul className="mt-2 list-inside list-disc space-y-0.5 text-warning-600 dark:text-warning-400">
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
