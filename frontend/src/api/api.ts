import axios from "axios";
import type {
  ChatMessage,
  ChatResponse,
  ConversationSummary,
  DocumentRecord,
  DocumentStatus,
} from "../types/chat";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const api = axios.create({ baseURL: API_BASE_URL });

export async function uploadDocument(file: File): Promise<DocumentRecord> {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await api.post<DocumentRecord>("/documents/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
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

export async function sendChatMessage(
  question: string,
  conversationId: number | null,
  documentId: number | null,
): Promise<ChatResponse> {
  const { data } = await api.post<ChatResponse>("/chat/", {
    question,
    conversation_id: conversationId,
    document_id: documentId,
  });
  return data;
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

// --- New: conversation management -----------------------------------------
// NOTE: these three call endpoints that don't exist on the backend yet.
// PATCH /chat/conversations/:id            body: {title}
// DELETE /chat/conversations/:id
// POST   /chat/conversations/:id/generate-title   (LLM-generated title from history)

export async function renameConversation(
  conversationId: number,
  title: string,
): Promise<ConversationSummary> {
  const { data } = await api.patch<ConversationSummary>(
    `/chat/conversations/${conversationId}`,
    { title },
  );
  return data;
}

export async function deleteConversation(conversationId: number): Promise<void> {
  await api.delete(`/chat/conversations/${conversationId}`);
}

export async function generateConversationTitle(
  conversationId: number,
): Promise<ConversationSummary> {
  const { data } = await api.post<ConversationSummary>(
    `/chat/conversations/${conversationId}/generate-title`,
  );
  return data;
}