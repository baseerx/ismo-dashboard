export interface SourceChunk {
  document_id: number;
  filename: string;
  chunk_index: number;
  distance: number | null;
}

export interface ChatMessage {
  id?: number;
  role: "user" | "assistant";
  content: string;
  sources?: SourceChunk[];
  created_at?: string;
}

export interface ChatResponse {
  conversation_id: number;
  answer: string;
  sources: SourceChunk[];
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

export interface UploadingFile {
  documentId: number | null;
  filename: string;
  status: DocumentStatus["status"] | "uploading" | "error";
  progressPercent: number;
  error?: string;
}