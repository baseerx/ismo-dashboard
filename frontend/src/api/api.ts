import axios from "axios";
import type {
  ChatMessage,
  ChatResponse,
  ConversationSummary,
  DocumentRecord,
  DocumentStatus,
  ReportOffer,
} from "../types/chat";

// The chatbot is a separate service from the Django API, so it has its own base
// URL. VITE_API_BASE_URL is honoured as well, for environments configured
// before the variable was renamed.
const API_BASE_URL =
  import.meta.env.VITE_CHATBOT_API_URL ??
  import.meta.env.VITE_API_BASE_URL ??
  "http://localhost:8000";

export const api = axios.create({ baseURL: API_BASE_URL });

/**
 * The chatbot identifies the caller from the dashboard's own login token, and
 * derives the ERP id from its signature. Sending the cached user object would
 * be pointless — the service ignores it — and unsafe, since anything the
 * browser asserts about who it is can be edited.
 */
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export class SessionExpired extends Error {
  constructor() {
    super("Your session has expired. Please sign in again.");
    this.name = "SessionExpired";
  }
}

const rethrow = (error: unknown): never => {
  if (axios.isAxiosError(error) && error.response?.status === 401) {
    throw new SessionExpired();
  }
  throw error;
};

// ---------------------------------------------------------------- chat

export async function sendChatMessage(
  question: string,
  conversationId: number | null,
  documentId: number | null,
): Promise<ChatResponse> {
  try {
    const { data } = await api.post<ChatResponse>("/chat/", {
      question,
      conversation_id: conversationId,
      document_id: documentId,
    });
    return data;
  } catch (error) {
    return rethrow(error);
  }
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const { data } = await api.get<ConversationSummary[]>("/chat/conversations");
  return data;
}

export async function getConversationMessages(
  conversationId: number,
): Promise<ChatMessage[]> {
  const { data } = await api.get<ChatMessage[]>(
    `/chat/conversations/${conversationId}/messages`,
  );
  return data;
}

export async function deleteConversation(conversationId: number): Promise<void> {
  await api.delete(`/chat/conversations/${conversationId}`);
}

// ----------------------------------------------------------- documents

export async function uploadDocument(file: File): Promise<DocumentRecord> {
  const formData = new FormData();
  formData.append("file", file);

  try {
    const { data } = await api.post<DocumentRecord>("/documents/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  } catch (error) {
    return rethrow(error);
  }
}

export async function getDocumentStatus(documentId: number): Promise<DocumentStatus> {
  const { data } = await api.get<DocumentStatus>(`/documents/${documentId}/status`);
  return data;
}

export async function listDocuments(): Promise<DocumentRecord[]> {
  const { data } = await api.get<DocumentRecord[]>("/documents/");
  return data;
}

export async function deleteDocument(documentId: number): Promise<void> {
  await api.delete(`/documents/${documentId}`);
}

// ------------------------------------------------------------- reports

/**
 * Fetches the report and hands it to the browser as a download.
 *
 * It has to go through JavaScript rather than a plain link: the request needs
 * the Authorization header, so the file arrives as a blob that we turn into a
 * temporary object URL. The URL is revoked straight after the click to avoid
 * holding a multi-megabyte blob in memory for the rest of the session.
 */
export async function downloadReport(
  offer: Pick<ReportOffer, "subject" | "start" | "end" | "erp_id">,
  format: "excel" | "pdf",
): Promise<string> {
  const response = await api.post(
    "/reports/generate",
    {
      subject: offer.subject,
      start: offer.start,
      end: offer.end,
      erp_id: offer.erp_id,
      report_format: format,
    },
    { responseType: "blob" },
  );

  const disposition = response.headers["content-disposition"] as string | undefined;
  const matched = disposition?.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  const filename =
    matched?.[1] ??
    `${offer.subject}-report.${format === "excel" ? "xlsx" : "pdf"}`;

  const url = URL.createObjectURL(response.data as Blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);

  return filename;
}

/** Reads the error text the service sent, rather than showing "Request failed". */
export function describeError(error: unknown): string {
  if (error instanceof SessionExpired) return error.message;

  if (axios.isAxiosError(error)) {
    const detail = error.response?.data as { detail?: unknown } | undefined;
    if (typeof detail?.detail === "string") return detail.detail;
    if (detail?.detail && typeof detail.detail === "object") {
      const message = (detail.detail as { message?: string }).message;
      if (message) return message;
    }
    if (error.response?.status === 403) return "You are not allowed to do that.";
    if (!error.response) {
      return "I cannot reach the assistant service. It may not be running.";
    }
  }

  return "Something went wrong. Please try again.";
}
