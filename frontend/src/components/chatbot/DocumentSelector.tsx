import type { DocumentRecord } from "../../types/chat";

interface Props {
  documents: DocumentRecord[];
  selectedDocumentId: number | null;
  onSelect: (documentId: number | null) => void;
}

/**
 * Narrows retrieval to one trained document.
 *
 * Only worth showing once more than one document is trained, which is why the
 * widget renders it conditionally — the parent owns the list so the selector
 * does not fetch it a second time.
 */
export default function DocumentSelector({
  documents,
  selectedDocumentId,
  onSelect,
}: Props) {
  return (
    <label className="flex items-center gap-2 text-[11px] text-[var(--chat-dim)]">
      <BookIcon />
      <span className="shrink-0">Search in</span>
      <select
        value={selectedDocumentId ?? ""}
        onChange={(event) => onSelect(event.target.value ? Number(event.target.value) : null)}
        className="min-w-0 flex-1 truncate rounded-md border border-[var(--chat-rule)] bg-[var(--chat-card)] px-1.5 py-1 text-[11px] text-[var(--chat-text)] outline-none transition-colors focus:border-[var(--chat-accent)]"
      >
        <option value="">All documents</option>
        {documents.map((document) => (
          <option key={document.id} value={document.id}>
            {document.filename.replace(/^[0-9a-f]{16,}_/i, "")}
          </option>
        ))}
      </select>
    </label>
  );
}

function BookIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
    </svg>
  );
}
