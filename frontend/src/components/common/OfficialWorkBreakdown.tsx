import { ColumnDef } from "@tanstack/react-table";
import EnhancedDataTable from "../tables/DataTables/DataTableOne";
import Badge from "../ui/badge/Badge";

export type OfficialWorkRow = {
  erp_id: any;
  employee_name?: string;
  section?: string;
  leave_type?: string;
  start_date?: string;
  end_date?: string;
  days?: number;
  status?: string;
  reason?: string;
  /** Which table the record came from. */
  source?: string;
};

export type OfficialWorkSummaryRow = {
  leave_type: string;
  records: number;
  days: number;
};

interface OfficialWorkBreakdownProps {
  records: OfficialWorkRow[];
  summary: OfficialWorkSummaryRow[];
  /** Shown when the report ran but the range holds no official work. */
  emptyMessage?: string;
}

const statusColor = (status?: string) => {
  switch ((status || "").toLowerCase()) {
    case "approved":
      return "success" as const;
    case "rejected":
      return "error" as const;
    default:
      return "warning" as const;
  }
};

/**
 * Official work is not a single leave type — it is its own module whose
 * records carry sub-types (Meetings, Official Tour, Work From Home, ...).
 * A one-line "Official Work" summary therefore says nothing useful, so the
 * leave reports render this breakdown underneath instead.
 */
export default function OfficialWorkBreakdown({
  records,
  summary,
  emptyMessage = "No official work records found for the selected range.",
}: OfficialWorkBreakdownProps) {
  const columns: ColumnDef<OfficialWorkRow>[] = [
    { header: "ERP ID", accessorKey: "erp_id" },
    { header: "Name", accessorKey: "employee_name" },
    { header: "Section", accessorKey: "section" },
    { header: "Type", accessorKey: "leave_type" },
    { header: "Start Date", accessorKey: "start_date" },
    { header: "End Date", accessorKey: "end_date" },
    {
      header: "Days",
      accessorKey: "days",
      cell: ({ getValue }) => (
        <span className="inline-flex items-center px-6 py-0.5 justify-center gap-1 rounded-full font-semibold text-theme-lg bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500">
          {getValue<number>() ?? 0}
        </span>
      ),
    },
    {
      header: "Status",
      accessorKey: "status",
      cell: ({ getValue }) => {
        const value = getValue<string>();
        return (
          <Badge size="sm" color={statusColor(value)}>
            {value || "—"}
          </Badge>
        );
      },
    },
    {
      header: "Source",
      accessorKey: "source",
      cell: ({ getValue }) => {
        const value = getValue<string>();
        // Historical rows came from the leave form before official work moved
        // to its own module; flagged so the two are never confused.
        const isHistorical = (value || "").toLowerCase().includes("historical");
        return (
          <Badge size="sm" color={isHistorical ? "warning" : "info"}>
            {value || "—"}
          </Badge>
        );
      },
    },
    { header: "Reason", accessorKey: "reason" },
  ];

  const totalDays = summary.reduce((sum, item) => sum + item.days, 0);

  return (
    <div className="mt-8 border-t border-gray-200 pt-6 dark:border-gray-800">
      <h4 className="mb-1 text-lg font-semibold text-gray-800 dark:text-white/90">
        Official Work Records
      </h4>
      <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
        Official work is recorded in its own module and split across several
        types. Entries made through the leave form before that module existed
        are included too, marked <span className="font-medium">Leave form
        (historical)</span> — the leave form no longer offers Official Work.
        Day totals count each calendar day once, even if both sources record it.
      </p>

      {records.length === 0 ? (
        <p className="rounded-lg bg-gray-50 px-4 py-6 text-center text-sm text-gray-500 dark:bg-white/[0.03] dark:text-gray-400">
          {emptyMessage}
        </p>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap gap-2">
            {summary.map((item) => (
              <span
                key={item.leave_type}
                className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-sm text-gray-700 dark:border-gray-800 dark:bg-white/[0.03] dark:text-gray-300"
              >
                <span className="font-medium">{item.leave_type}</span>
                <Badge size="sm" color="info">
                  {item.days} {item.days === 1 ? "day" : "days"}
                </Badge>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {item.records} {item.records === 1 ? "record" : "records"}
                </span>
              </span>
            ))}
            <span className="inline-flex items-center gap-2 rounded-lg border border-brand-200 bg-brand-50 px-3 py-1.5 text-sm font-medium text-brand-700 dark:border-brand-500/30 dark:bg-brand-500/10 dark:text-brand-400">
              Total
              <Badge size="sm" color="primary">
                {totalDays} {totalDays === 1 ? "day" : "days"}
              </Badge>
            </span>
          </div>

          <EnhancedDataTable<OfficialWorkRow>
            data={records}
            columns={columns}
          />
        </>
      )}
    </div>
  );
}
