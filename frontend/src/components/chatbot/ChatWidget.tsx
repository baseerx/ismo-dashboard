import { useEffect, useRef, useState, type KeyboardEvent, type ChangeEvent } from "react";
import type { ChatMessage } from "../../types/chat";
import { sendChatMessage, uploadDocument, getDocumentStatus } from "../../api/api";

const COLORS = {
  panelBg: "#1B2544",
  headerBg: "#0F1B38",
  bg: "#0F1729",
  border: "rgba(34,184,207,0.22)",
  text: "#E6E9F0",
  textMuted: "#8B94A8",
  accent: "#22B8CF",
  accentHover: "#1B9AAD",
  bubbleUser: "#22B8CF",
  bubbleAssistant: "#232E52",
  danger: "#EF4444",
};

const POLL_INTERVAL_MS = 1500;

// Chips shown before the user has asked anything.
const SUGGESTED_QUESTIONS = [
  "What is the leave policy?",
  "How many sick days do I get?",
  "What are the office hours?",
  "How do I apply for leave?",
];

// Pool used for both the inline ghost-text completion and the dropdown
// matches as the user types. Expand this list as your HR docs grow.
const QUESTION_BANK = [
  "What is the leave policy?",
  "How many sick days do I get per year?",
  "How do I apply for leave?",
  "What is the maternity leave policy?",
  "What are the office hours?",
  "What is the attendance policy?",
  "How is attendance calculated?",
  "What is the public holiday schedule?",
  "Who do I contact for HR questions?",
  "What is the remote work policy?",
  "What is the dress code policy?",
  "How do I update my personal information?",
];

type UploadStatus =
  | "uploading"
  | "uploaded"
  | "extracting"
  | "embedding"
  | "indexed"
  | "failed"
  | "error";

interface UploadingFile {
  documentId: number | null;
  filename: string;
  status: UploadStatus;
  progressPercent: number;
  error?: string;
}

interface Props {
  // Optional override - if you ever want to force it from a parent that
  // already has the user object, pass it explicitly and it wins.
  // Otherwise the widget reads localStorage("user") itself, same pattern
  // your AttendanceOverview.tsx already uses.
  isAdmin?: boolean;
}

function getIsAdminFromStorage(): boolean {
  try {
    const user = JSON.parse(localStorage.getItem("user") || "{}");
    return Boolean(user?.is_superuser);
  } catch {
    return false;
  }
}

export default function ChatWidget({ isAdmin }: Props) {
  const resolvedIsAdmin = isAdmin ?? getIsAdminFromStorage();

  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);

  // Autocomplete state
  const [showDropdown, setShowDropdown] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (isOpen) scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isOpen, isSending]);

  // ---- Autocomplete derived values ----
  const topMatch =
    input.length > 0
      ? QUESTION_BANK.find(
          (q) => q.toLowerCase().startsWith(input.toLowerCase()) && q.length > input.length,
        )
      : undefined;

  const ghostRemainder = topMatch ? topMatch.slice(input.length) : "";

  const dropdownMatches =
    input.trim().length > 0
      ? QUESTION_BANK.filter((q) => q.toLowerCase().includes(input.trim().toLowerCase())).slice(0, 5)
      : [];

  const acceptSuggestion = (text?: string) => {
    const value = text ?? topMatch;
    if (value) {
      setInput(value);
      setShowDropdown(false);
      setActiveIndex(-1);
      textareaRef.current?.focus();
    }
  };

  // ---- Sending ----
  const handleSend = async (text?: string) => {
    const question = (text ?? input).trim();
    if (!question || isSending) return;

    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setShowDropdown(false);
    setIsSending(true);

    try {
      const response = await sendChatMessage(question, conversationId, null);
      setConversationId(response.conversation_id);
      setMessages((prev) => [...prev, { role: "assistant", content: response.answer }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Something went wrong reaching the server. Please try again." },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  const handleInputChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    setShowDropdown(true);
    setActiveIndex(-1);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    const dropdownVisible = showDropdown && dropdownMatches.length > 0;

    if (dropdownVisible && e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((prev) => (prev + 1) % dropdownMatches.length);
      return;
    }

    if (dropdownVisible && e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((prev) => (prev - 1 + dropdownMatches.length) % dropdownMatches.length);
      return;
    }

    if (dropdownVisible && e.key === "Escape") {
      setShowDropdown(false);
      setActiveIndex(-1);
      return;
    }

    if (e.key === "Tab" && topMatch) {
      e.preventDefault();
      acceptSuggestion(topMatch);
      return;
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();

      if (dropdownVisible && activeIndex >= 0) {
        acceptSuggestion(dropdownMatches[activeIndex]);
        return;
      }

      setShowDropdown(false);
      handleSend();
    }
  };

  // ---- Document upload: plus button (admin only) -> file picker -> upload -> poll status ----

  const pollStatus = (documentId: number) => {
    const interval = setInterval(async () => {
      try {
        const status = await getDocumentStatus(documentId);
        setUploadingFiles((prev) =>
          prev.map((f) =>
            f.documentId === documentId
              ? { ...f, status: status.status, progressPercent: status.progress_percent }
              : f,
          ),
        );
        if (status.status === "indexed" || status.status === "failed") {
          clearInterval(interval);
        }
      } catch {
        clearInterval(interval);
        setUploadingFiles((prev) =>
          prev.map((f) =>
            f.documentId === documentId
              ? { ...f, status: "error", error: "Lost connection while checking status" }
              : f,
          ),
        );
      }
    }, POLL_INTERVAL_MS);
  };

  const handleFilesSelected = async (fileList: FileList) => {
    const files = Array.from(fileList);
    const newEntries: UploadingFile[] = files.map((file) => ({
      documentId: null,
      filename: file.name,
      status: "uploading",
      progressPercent: 0,
    }));
    setUploadingFiles((prev) => [...prev, ...newEntries]);

    for (const file of files) {
      try {
        const doc = await uploadDocument(file);
        setUploadingFiles((prev) =>
          prev.map((f) =>
            f.filename === file.name && f.documentId === null
              ? { ...f, documentId: doc.id, status: doc.status as UploadStatus }
              : f,
          ),
        );
        pollStatus(doc.id);
      } catch {
        setUploadingFiles((prev) =>
          prev.map((f) =>
            f.filename === file.name && f.documentId === null
              ? { ...f, status: "error", error: "Upload failed" }
              : f,
          ),
        );
      }
    }
  };

  const uploadStatusColor = (status: UploadStatus) => {
    if (status === "indexed") return COLORS.accent;
    if (status === "failed" || status === "error") return COLORS.danger;
    return COLORS.textMuted;
  };

  return (
    <div style={{ fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif" }}>
      {isOpen && (
        <div
          className="fixed bottom-24 right-6 z-50 flex flex-col overflow-hidden widget-in"
          style={{
            width: 380,
            height: "min(560px, 72vh)",
            background: COLORS.panelBg,
            border: `1px solid ${COLORS.border}`,
            borderRadius: 18,
            boxShadow: "0 20px 48px rgba(0,0,0,0.5), 0 0 0 1px rgba(34,184,207,0.08)",
          }}
        >
          {/* Header */}
          <div
            className="header-glow flex items-center justify-between px-4 py-3.5 shrink-0"
            style={{
              background: COLORS.headerBg,
              borderBottom: `2px solid ${COLORS.accent}33`,
              boxShadow: "0 4px 12px rgba(0,0,0,0.25)",
              position: "relative",
              zIndex: 1,
            }}
          >
            <div className="flex items-center gap-2">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center"
                style={{ background: COLORS.accent }}
              >
                <BotIcon />
              </div>
              <div>
                <p className="text-sm font-semibold" style={{ color: COLORS.text }}>
                  HR Assistant
                </p>
                <p className="text-[11px]" style={{ color: COLORS.textMuted }}>
                  Ask about policies, leave, attendance…
                </p>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="w-8 h-8 rounded-md flex items-center justify-center hover:bg-white/5 transition-colors"
              style={{ color: COLORS.textMuted }}
            >
              <CloseIcon />
            </button>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center px-4 gap-3">
                <div
                  className="w-12 h-12 rounded-full flex items-center justify-center"
                  style={{ background: COLORS.accent }}
                >
                  <BotIcon />
                </div>
                <p className="text-sm" style={{ color: COLORS.text }}>
                  Hi! Ask me anything about HR policy.
                </p>
                <div className="flex flex-wrap gap-1.5 justify-center max-w-[280px]">
                  {SUGGESTED_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      onClick={() => handleSend(q)}
                      className="chip-in text-[11px] px-2.5 py-1.5 rounded-full transition-colors hover:brightness-110"
                      style={{
                        background: COLORS.bubbleAssistant,
                        color: COLORS.text,
                        border: `1px solid ${COLORS.border}`,
                      }}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m, i) => {
                const isUser = m.role === "user";
                return (
                  <div key={i} className={`flex msg-in ${isUser ? "justify-end" : "justify-start"}`}>
                    <div
                      className="max-w-[80%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap"
                      style={{
                        background: isUser ? COLORS.bubbleUser : COLORS.bubbleAssistant,
                        color: isUser ? "#04222A" : COLORS.text,
                        borderTopRightRadius: isUser ? 4 : undefined,
                        borderTopLeftRadius: !isUser ? 4 : undefined,
                      }}
                    >
                      {m.content}
                    </div>
                  </div>
                );
              })
            )}

            {isSending && (
              <div className="flex justify-start msg-in">
                <div
                  className="rounded-xl px-3.5 py-2.5 flex items-center gap-1"
                  style={{ background: COLORS.bubbleAssistant, borderTopLeftRadius: 4 }}
                >
                  <Dot color={COLORS.textMuted} delay="0ms" />
                  <Dot color={COLORS.textMuted} delay="120ms" />
                  <Dot color={COLORS.textMuted} delay="240ms" />
                </div>
              </div>
            )}
          </div>

          {/* Uploading files - admin only, only shows while something is in flight */}
          {resolvedIsAdmin && uploadingFiles.length > 0 && (
            <div
              className="px-4 py-2 shrink-0 space-y-1.5 max-h-28 overflow-y-auto"
              style={{ borderTop: `1px solid ${COLORS.border}` }}
            >
              {uploadingFiles.map((f, i) => (
                <div key={`${f.filename}-${i}`}>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="truncate max-w-[60%]" style={{ color: COLORS.text }}>
                      {f.filename}
                    </span>
                    <span style={{ color: uploadStatusColor(f.status) }}>
                      {f.status === "error" ? f.error ?? "error" : f.status}
                    </span>
                  </div>
                  <div className="h-1 w-full rounded-full overflow-hidden mt-0.5" style={{ background: COLORS.bg }}>
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${f.progressPercent}%`,
                        background: f.status === "failed" || f.status === "error" ? COLORS.danger : COLORS.accent,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Input */}
          <div className="relative p-3 shrink-0" style={{ borderTop: `1px solid ${COLORS.border}` }}>
            {showDropdown && dropdownMatches.length > 0 && (
              <div
                className="dropdown-in absolute bottom-full left-3 right-3 mb-2 rounded-lg overflow-hidden shadow-lg"
                style={{ background: COLORS.headerBg, border: `1px solid ${COLORS.border}` }}
              >
                {dropdownMatches.map((match, i) => (
                  <button
                    key={match}
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => acceptSuggestion(match)}
                    onMouseEnter={() => setActiveIndex(i)}
                    className="w-full text-left px-3 py-2 text-xs transition-colors"
                    style={{
                      background: i === activeIndex ? `${COLORS.accent}22` : "transparent",
                      color: i === activeIndex ? COLORS.accent : COLORS.text,
                    }}
                  >
                    {match}
                  </button>
                ))}
              </div>
            )}

            <div
              className="flex items-end gap-2 rounded-lg px-2 py-1.5"
              style={{ background: COLORS.bg, border: `1px solid ${COLORS.border}` }}
            >
              {resolvedIsAdmin && (
                <>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    title="Upload a document"
                    className="w-8 h-8 rounded-md flex items-center justify-center shrink-0 hover:bg-white/5 transition-colors"
                    style={{ color: COLORS.textMuted }}
                  >
                    <PlusIcon />
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.docx,.txt,.md"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files) handleFilesSelected(e.target.files);
                      e.target.value = "";
                    }}
                  />
                </>
              )}

              <div className="relative flex-1">
                {/* Ghost overlay: shows the greyed-out remainder of the top
                    matching question. The typed part is rendered transparent
                    just to keep the spacing lined up with the real textarea
                    sitting on top of it. */}
                <div
                  aria-hidden="true"
                  className="absolute inset-0 pointer-events-none whitespace-pre-wrap break-words text-sm py-1.5 px-1"
                >
                  <span style={{ color: "transparent" }}>{input}</span>
                  <span style={{ color: COLORS.textMuted }}>{ghostRemainder}</span>
                </div>

                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  onBlur={() => setTimeout(() => setShowDropdown(false), 100)}
                  placeholder="Type a question…"
                  rows={1}
                  disabled={isSending}
                  className="relative w-full resize-none bg-transparent border-none outline-none text-sm py-1.5 px-1"
                  style={{ color: COLORS.text }}
                />

                {ghostRemainder && (
                  <button
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => acceptSuggestion(topMatch)}
                    className="absolute right-1 top-1/2 -translate-y-1/2 text-[10px] px-1.5 py-0.5 rounded"
                    style={{ background: COLORS.panelBg, color: COLORS.textMuted, border: `1px solid ${COLORS.border}` }}
                  >
                    Tab ⇥
                  </button>
                )}
              </div>

              <button
                onClick={() => handleSend()}
                disabled={isSending || !input.trim()}
                className="w-8 h-8 rounded-md flex items-center justify-center shrink-0 transition-colors disabled:opacity-40"
                style={{ background: COLORS.accent }}
              >
                <SendIcon />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating trigger button */}
      <div className="fixed bottom-6 right-6 z-50">
        {!isOpen && (
          <span
            className="absolute inset-0 rounded-full"
            style={{ background: COLORS.accent, animation: "pulse-ring 2.2s cubic-bezier(0.4, 0, 0.6, 1) infinite" }}
          />
        )}
        <button
          onClick={() => setIsOpen((o) => !o)}
          className="relative w-16 h-16 rounded-full flex items-center justify-center transition-transform hover:scale-105"
          style={{
            background: COLORS.accent,
            boxShadow: "0 10px 28px rgba(34,184,207,0.5)",
            animation: isOpen ? undefined : "fab-float 3s ease-in-out infinite",
          }}
        >
          <span
            style={{
              display: "inline-flex",
              transition: "transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1)",
              transform: isOpen ? "rotate(90deg)" : "rotate(0deg)",
            }}
          >
            {isOpen ? <CloseIconLarge /> : <BotIcon large />}
          </span>
        </button>
      </div>

      <style>{`
        .widget-in {
          animation: widget-in 0.32s cubic-bezier(0.34, 1.56, 0.64, 1) both;
          transform-origin: bottom right;
        }
        @keyframes widget-in {
          from { opacity: 0; transform: scale(0.85) translateY(24px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
        .msg-in {
          animation: msg-in 0.22s ease-out both;
        }
        @keyframes msg-in {
          from { opacity: 0; transform: translateY(6px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .chip-in {
          animation: chip-in 0.25s ease-out both;
        }
        .chip-in:nth-child(1) { animation-delay: 0.05s; }
        .chip-in:nth-child(2) { animation-delay: 0.12s; }
        .chip-in:nth-child(3) { animation-delay: 0.19s; }
        .chip-in:nth-child(4) { animation-delay: 0.26s; }
        @keyframes chip-in {
          from { opacity: 0; transform: translateY(4px) scale(0.96); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .dropdown-in {
          animation: dropdown-in 0.15s ease-out both;
          transform-origin: bottom center;
        }
        @keyframes dropdown-in {
          from { opacity: 0; transform: translateY(4px) scaleY(0.95); }
          to { opacity: 1; transform: translateY(0) scaleY(1); }
        }
        .header-glow {
          animation: header-glow 3.5s ease-in-out infinite;
        }
        @keyframes header-glow {
          0%, 100% { border-bottom-color: rgba(34,184,207,0.2); }
          50% { border-bottom-color: rgba(34,184,207,0.5); }
        }
        @keyframes pulse-dot {
          0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
          40% { opacity: 1; transform: scale(1); }
        }
        @keyframes pulse-ring {
          0% { opacity: 0.55; transform: scale(1); }
          100% { opacity: 0; transform: scale(1.7); }
        }
        @keyframes fab-float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-6px); }
        }
      `}</style>
    </div>
  );
}

function Dot({ color, delay }: { color: string; delay: string }) {
  return (
    <span
      className="w-1.5 h-1.5 rounded-full inline-block"
      style={{ background: color, animation: `pulse-dot 1s ${delay} infinite ease-in-out` }}
    />
  );
}

function BotIcon({ large }: { large?: boolean }) {
  const size = large ? 26 : 16;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#04222A" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="8" width="16" height="12" rx="2" />
      <path d="M12 8V4" />
      <circle cx="12" cy="3" r="1" />
      <path d="M8 13h.01M16 13h.01" />
      <path d="M9 17h6" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

function CloseIconLarge() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#04222A" strokeWidth="2.2" strokeLinecap="round">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#04222A" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round">
      <path d="m22 2-7 20-4-9-9-4Z" />
      <path d="M22 2 11 13" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}