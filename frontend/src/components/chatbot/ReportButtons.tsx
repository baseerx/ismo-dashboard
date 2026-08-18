import { useEffect, useRef, useState } from "react";
import { describeError, downloadReport } from "../../api/api";
import type { ReportOffer } from "../../types/chat";

type State = { format: "excel" | "pdf" | null; error: string | null; done: string | null };

const LABELS: Record<ReportOffer["subject"], string> = {
  leave: "Leave report",
  attendance: "Attendance report",
  official_work: "Official work report",
};

export default function ReportButtons({ offer }: { offer: ReportOffer }) {
  const [state, setState] = useState<State>({ format: null, error: null, done: null });

  // A question that already named a format ("...in excel") should not need a
  // second click. Guarded by a ref so a re-render cannot start it twice.
  const autoStarted = useRef(false);

  const run = async (format: "excel" | "pdf") => {
    setState({ format, error: null, done: null });
    try {
      const filename = await downloadReport(offer, format);
      setState({ format: null, error: null, done: filename });
    } catch (error) {
      setState({ format: null, error: describeError(error), done: null });
    }
  };

  useEffect(() => {
    if (offer.preferred_format && !autoStarted.current) {
      autoStarted.current = true;
      void run(offer.preferred_format);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offer.preferred_format]);

  return (
    <div className="mt-3 rounded-xl border border-[var(--chat-rule)] bg-[var(--chat-card)] p-3 table-in">
      <div className="mb-2 flex items-start gap-2">
        <span className="mt-0.5 text-[var(--chat-accent-ink)]">
          <DownloadIcon />
        </span>
        <div className="min-w-0">
          <p className="text-[12px] font-semibold text-[var(--chat-text)]">
            {LABELS[offer.subject]}
          </p>
          <p className="truncate text-[10.5px] text-[var(--chat-dim)]">
            {offer.employee_name ? `${offer.employee_name} · ` : ""}
            {offer.label}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {offer.formats.map((format) => {
          const busy = state.format === format;
          return (
            <button
              key={format}
              onClick={() => run(format)}
              disabled={state.format !== null}
              className={`group inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[11.5px] font-medium transition-all disabled:opacity-60 ${
                format === "excel"
                  ? "border-[var(--chat-rule)] text-[var(--chat-excel)] hover:border-[var(--chat-excel)] hover:bg-[var(--chat-excel-soft)]"
                  : "border-[var(--chat-rule)] text-[var(--chat-pdf)] hover:border-[var(--chat-pdf)] hover:bg-[var(--chat-pdf-soft)]"
              } hover:-translate-y-px active:translate-y-0`}
            >
              {busy ? <Spinner /> : format === "excel" ? <SheetIcon /> : <PdfIcon />}
              {busy ? "Preparing…" : format === "excel" ? "Excel" : "PDF"}
            </button>
          );
        })}
      </div>

      {state.done && (
        <p className="mt-2 flex items-center gap-1.5 text-[10.5px] text-[var(--chat-good)] fade-in">
          <CheckIcon />
          <span className="truncate">Saved {state.done}</span>
        </p>
      )}
      {state.error && (
        <p className="mt-2 text-[10.5px] text-[var(--chat-bad)] fade-in">{state.error}</p>
      )}
    </div>
  );
}

function Spinner() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" className="animate-spin" aria-hidden="true">
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v12M7 11l5 5 5-5M5 21h14" />
    </svg>
  );
}

function SheetIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18M9 3v18" />
    </svg>
  );
}

function PdfIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
      <path d="M14 2v6h6" />
      <path d="M8 15h1.5a1.5 1.5 0 0 0 0-3H8v6M14 12v6h1a2 2 0 0 0 2-2v-2a2 2 0 0 0-2-2Z" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="m20 6-11 11-5-5" />
    </svg>
  );
}
