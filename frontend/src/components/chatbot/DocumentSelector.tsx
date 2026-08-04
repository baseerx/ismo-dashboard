import { useEffect, useState } from "react";
import type { DocumentRecord } from "../../types/chat";
import { listDocuments } from "../../api/api";

interface Props {
  selectedDocumentId: number | null;
  onSelect: (documentId: number | null) => void;
}

export default function DocumentSelector({ selectedDocumentId, onSelect }: Props) {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listDocuments()
      .then(setDocuments)
      .finally(() => setLoading(false));
  }, []);

  const indexedDocs = documents.filter((d) => d.status === "indexed");

  return (
    <div className="flex items-center gap-2 border border-[var(--rule)] rounded-md pl-2.5 pr-1 py-1 bg-white">
      <BookIcon />
      <select
        value={selectedDocumentId ?? ""}
        onChange={(e) => onSelect(e.target.value ? Number(e.target.value) : null)}
        disabled={loading}
        className="text-sm text-[var(--ink)] bg-transparent border-none outline-none py-0.5 pr-1 max-w-[220px] disabled:opacity-50 appearance-none"
      >
        <option value="">General — search all documents</option>
        {indexedDocs.map((d) => (
          <option key={d.id} value={d.id}>
            {d.filename}
          </option>
        ))}
      </select>
      <ChevronIcon />
    </div>
  );
}

function BookIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--ink-faint)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
    </svg>
  );
}

function ChevronIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--ink-faint)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}