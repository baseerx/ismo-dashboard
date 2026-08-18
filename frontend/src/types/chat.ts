export interface SourceChunk {
  document_id: number | null;
  filename: string | null;
  chunk_index: number | null;
  page_number?: number | null;
  distance: number | null;
}

export interface Action {
  type: string; // "navigate"
  path: string;
  label: string;
}

export interface Column {
  key: string;
  label: string;
}

/** A table of live data the assistant returned alongside its answer. */
export interface DataBlock {
  title: string;
  columns: Column[];
  rows: Record<string, string | number | null>[];
  summary?: Record<string, string | number>;
  note?: string | null;
}

/** An offer to build a downloadable report of what was just shown. */
export interface ReportOffer {
  subject: "leave" | "attendance" | "official_work";
  erp_id: number;
  start: string;
  end: string;
  label: string;
  employee_name?: string | null;
  formats: ("excel" | "pdf")[];
  /** Set when the question already named a format, e.g. "...in excel". */
  preferred_format?: "excel" | "pdf" | null;
}

export interface ChatMessage {
  id?: number;
  role: "user" | "assistant";
  content: string;
  sources?: SourceChunk[];
  actions?: Action[];
  data?: DataBlock | null;
  report?: ReportOffer | null;
  created_at?: string;
  /** Set on messages the widget itself produced, e.g. a connection failure. */
  isError?: boolean;
}

export interface ChatResponse {
  conversation_id: number;
  answer: string;
  intent?: string;
  sources: SourceChunk[];
  actions: Action[];
  data?: DataBlock | null;
  report?: ReportOffer | null;
}

export interface ConversationSummary {
  id: number;
  title: string | null;
  created_at: string;
}

export interface DocumentRecord {
  id: number;
  filename: string;
  status: string;
  created_at: string;
}

export interface DocumentStatus {
  id: number;
  filename: string;
  status: "uploaded" | "extracting" | "embedding" | "indexed" | "failed";
  total_chunks: number;
  processed_chunks: number;
  progress_percent: number;
}

export type UploadStatus = DocumentStatus["status"] | "uploading" | "error";

export interface UploadingFile {
  documentId: number | null;
  filename: string;
  status: UploadStatus;
  progressPercent: number;
  error?: string;
}
