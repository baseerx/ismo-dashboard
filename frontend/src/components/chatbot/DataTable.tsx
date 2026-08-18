import { useState } from "react";
import type { DataBlock } from "../../types/chat";

// Long tables collapse: an attendance year is 365 rows, and a chat panel is not
// where anyone wants to scroll through all of them by default.
const COLLAPSED_ROWS = 8;

const STATUS_TONE: Record<string, string> = {
  present: "text-[var(--chat-good)]",
  absent: "text-[var(--chat-bad)]",
  approved: "text-[var(--chat-good)]",
  rejected: "text-[var(--chat-bad)]",
  pending: "text-[var(--chat-warn)]",
  late: "text-[var(--chat-warn)]",
  early: "text-[var(--chat-warn)]",
  weekend: "text-[var(--chat-dim)]",
};

/** Colours the words that carry a verdict, so a table can be read at a glance. */
function tone(value: unknown): string {
  if (typeof value !== "string") return "";
  const key = value.trim().toLowerCase();
  for (const [word, className] of Object.entries(STATUS_TONE)) {
    if (key === word || key.startsWith(word)) return className;
  }
  return "";
}

const isNumeric = (value: unknown) =>
  typeof value === "number" || (typeof value === "string" && /^-?\d+(\.\d+)?$/.test(value));

export default function DataTable({ block }: { block: DataBlock }) {
  const [expanded, setExpanded] = useState(false);

  const rows = expanded ? block.rows : block.rows.slice(0, COLLAPSED_ROWS);
  const hidden = block.rows.length - rows.length;
  const summary = Object.entries(block.summary ?? {});

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-[var(--chat-rule)] bg-[var(--chat-card)] table-in">
      <div className="flex items-center justify-between gap-2 border-b border-[var(--chat-rule)] px-3 py-2">
        <p className="truncate text-[11px] font-semibold uppercase tracking-wider text-[var(--chat-dim)]">
          {block.title}
        </p>
        <span className="shrink-0 rounded-full bg-[var(--chat-accent-soft)] px-2 py-0.5 text-[10px] font-medium text-[var(--chat-accent-ink)]">
          {block.rows.length} row{block.rows.length === 1 ? "" : "s"}
        </span>
      </div>

      <div className="max-h-[22rem] overflow-auto custom-scrollbar">
        <table className="w-full border-collapse text-[11.5px]">
          <thead className="sticky top-0 z-10">
            <tr>
              {block.columns.map((column) => (
                <th
                  key={column.key}
                  className="whitespace-nowrap border-b border-[var(--chat-rule)] bg-[var(--chat-head)] px-2.5 py-1.5 text-left font-semibold text-[var(--chat-text)]"
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr
                key={index}
                className="transition-colors odd:bg-[var(--chat-row)] hover:bg-[var(--chat-accent-soft)]"
              >
                {block.columns.map((column) => {
                  const value = row[column.key];
                  return (
                    <td
                      key={column.key}
                      className={`whitespace-nowrap px-2.5 py-1.5 align-top text-[var(--chat-text)] ${
                        isNumeric(value) ? "font-mono tabular-nums" : ""
                      } ${tone(value)}`}
                    >
                      {value === null || value === undefined || value === "" ? "—" : String(value)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {hidden > 0 && (
        <button
          onClick={() => setExpanded(true)}
          className="w-full border-t border-[var(--chat-rule)] px-3 py-1.5 text-[11px] font-medium text-[var(--chat-accent-ink)] transition-colors hover:bg-[var(--chat-accent-soft)]"
        >
          Show {hidden} more row{hidden === 1 ? "" : "s"}
        </button>
      )}

      {expanded && block.rows.length > COLLAPSED_ROWS && (
        <button
          onClick={() => setExpanded(false)}
          className="w-full border-t border-[var(--chat-rule)] px-3 py-1.5 text-[11px] font-medium text-[var(--chat-dim)] transition-colors hover:bg-[var(--chat-accent-soft)]"
        >
          Collapse
        </button>
      )}

      {summary.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-t border-[var(--chat-rule)] px-3 py-2">
          {summary.map(([label, value]) => (
            <span
              key={label}
              className="inline-flex items-center gap-1 rounded-md bg-[var(--chat-head)] px-2 py-0.5 text-[10.5px] text-[var(--chat-dim)]"
            >
              {label.replace(/_/g, " ")}
              <b className="font-mono text-[var(--chat-text)]">{value}</b>
            </span>
          ))}
        </div>
      )}

      {block.note && (
        <p className="border-t border-[var(--chat-rule)] px-3 py-2 text-[10.5px] leading-relaxed text-[var(--chat-dim)]">
          {block.note}
        </p>
      )}
    </div>
  );
}
