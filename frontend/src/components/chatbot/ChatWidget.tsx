import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
} from "react";
import {
  deleteConversation,
  describeError,
  getConversationMessages,
  getDocumentStatus,
  listConversations,
  listDocuments,
  sendChatMessage,
  uploadDocument,
} from "../../api/api";
import type {
  ChatMessage,
  ConversationSummary,
  DocumentRecord,
  UploadingFile,
} from "../../types/chat";
import DocumentSelector from "./DocumentSelector";
import MessageBubble from "./MessageBubble";

const POLL_INTERVAL_MS = 1500;

// Keeping the thread id here means walking to another page and back continues
// the same conversation, while a new sign-in starts fresh.
const THREAD_KEY = "ismo:chat:conversation";

const SUGGESTIONS = [
  "How many casual leaves do I have left?",
  "My attendance last month",
  "What is the medical leave policy?",
  "Leave report for this financial year",
];

// Completions offered as the user types. Data questions first: they are the
// ones where exact phrasing helps the assistant answer precisely.
const QUESTION_BANK = [
  "How many casual leaves do I have left?",
  "What is my leave balance?",
  "My medical leave balance",
  "My leave history for this financial year",
  "My attendance today",
  "Was I late today?",
  "My attendance last month",
  "My attendance last 7 days",
  "My attendance from 01-07-2026 to 31-07-2026",
  "My official work this year",
  "Attendance report for last month in Excel",
  "Leave report for this financial year as PDF",
  "What is the leave policy?",
  "What is the medical leave policy?",
  "What is the maternity leave policy?",
  "What is the probation period?",
  "How do I apply for leave?",
  "What are the office timings?",
  "What is the policy on official tours?",
  "Who approves my leave?",
];

// Shown in turn while a reply is being prepared, so a slow model still looks
// like it is doing something specific.
const WAITING_STAGES = [
  "Thinking…",
  "Checking your records…",
  "Reading the HR manual…",
  "Putting the answer together…",
];

function readUser(): { name?: string; erpid?: number; is_superuser?: boolean } {
  try {
    return JSON.parse(localStorage.getItem("user") || "{}");
  } catch {
    return {};
  }
}

interface Props {
  /** Overrides the cached profile's flag; the service enforces this regardless. */
  isAdmin?: boolean;
}

export default function ChatWidget({ isAdmin }: Props) {
  const user = useMemo(readUser, []);
  const resolvedIsAdmin = isAdmin ?? Boolean(user.is_superuser);
  const signedIn = Boolean(user.erpid);

  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(() => {
    const stored = sessionStorage.getItem(THREAD_KEY);
    return stored ? Number(stored) : null;
  });
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [stage, setStage] = useState(0);
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [documentId, setDocumentId] = useState<number | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [pinnedToBottom, setPinnedToBottom] = useState(true);
  // An attendance table is six columns wide; the default panel is sized for
  // conversation, so give the reader a way to widen it for the tables.
  const [wide, setWide] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const pollTimers = useRef<number[]>([]);

  // ---- scrolling -------------------------------------------------------
  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    const node = scrollRef.current;
    if (node) node.scrollTo({ top: node.scrollHeight, behavior });
  }, []);

  useEffect(() => {
    if (isOpen && pinnedToBottom) scrollToBottom();
  }, [messages, isOpen, isSending, pinnedToBottom, scrollToBottom]);

  const handleScroll = () => {
    const node = scrollRef.current;
    if (!node) return;
    const distance = node.scrollHeight - node.scrollTop - node.clientHeight;
    setPinnedToBottom(distance < 80);
  };

  // ---- waiting stages --------------------------------------------------
  useEffect(() => {
    if (!isSending) {
      setStage(0);
      return;
    }
    const timer = window.setInterval(
      () => setStage((current) => Math.min(current + 1, WAITING_STAGES.length - 1)),
      2200,
    );
    return () => window.clearInterval(timer);
  }, [isSending]);

  // ---- opening ---------------------------------------------------------
  useEffect(() => {
    if (!isOpen || !signedIn) return;

    listDocuments()
      .then(setDocuments)
      .catch(() => setDocuments([]));

    // Re-attach to the thread this browser tab was already using.
    if (conversationId && messages.length === 0) {
      getConversationMessages(conversationId)
        .then((history) =>
          setMessages(
            history.map((entry) => ({
              role: entry.role as ChatMessage["role"],
              content: entry.content,
              sources: entry.sources,
            })),
          ),
        )
        .catch(() => {
          sessionStorage.removeItem(THREAD_KEY);
          setConversationId(null);
        });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, signedIn]);

  useEffect(
    () => () => {
      pollTimers.current.forEach(window.clearInterval);
    },
    [],
  );

  useEffect(() => {
    if (conversationId) sessionStorage.setItem(THREAD_KEY, String(conversationId));
  }, [conversationId]);

  // ---- autocomplete ----------------------------------------------------
  const topMatch =
    input.length > 1
      ? QUESTION_BANK.find(
          (q) => q.toLowerCase().startsWith(input.toLowerCase()) && q.length > input.length,
        )
      : undefined;

  const ghostRemainder = topMatch ? topMatch.slice(input.length) : "";

  const dropdownMatches =
    input.trim().length > 1
      ? QUESTION_BANK.filter((q) =>
          q.toLowerCase().includes(input.trim().toLowerCase()),
        ).slice(0, 5)
      : [];

  const acceptSuggestion = (text?: string) => {
    const value = text ?? topMatch;
    if (!value) return;
    setInput(value);
    setShowDropdown(false);
    setActiveIndex(-1);
    textareaRef.current?.focus();
  };

  // ---- sending ---------------------------------------------------------
  const handleSend = async (text?: string) => {
    const question = (text ?? input).trim();
    if (!question || isSending) return;

    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setShowDropdown(false);
    setPinnedToBottom(true);
    setIsSending(true);

    try {
      const response = await sendChatMessage(question, conversationId, documentId);
      setConversationId(response.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.answer,
          sources: response.sources,
          actions: response.actions,
          data: response.data ?? null,
          report: response.report ?? null,
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: describeError(error), isError: true },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    const dropdownVisible = showDropdown && dropdownMatches.length > 0;

    if (dropdownVisible && event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((prev) => (prev + 1) % dropdownMatches.length);
      return;
    }
    if (dropdownVisible && event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((prev) => (prev - 1 + dropdownMatches.length) % dropdownMatches.length);
      return;
    }
    if (event.key === "Escape") {
      if (dropdownVisible) {
        setShowDropdown(false);
        setActiveIndex(-1);
      } else {
        setIsOpen(false);
      }
      return;
    }
    if (event.key === "Tab" && topMatch) {
      event.preventDefault();
      acceptSuggestion(topMatch);
      return;
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (dropdownVisible && activeIndex >= 0) {
        acceptSuggestion(dropdownMatches[activeIndex]);
        return;
      }
      setShowDropdown(false);
      void handleSend();
    }
  };

  const handleInputChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    setInput(event.target.value);
    setShowDropdown(true);
    setActiveIndex(-1);
  };

  // ---- conversations ---------------------------------------------------
  const openHistory = async () => {
    setShowHistory(true);
    try {
      setConversations(await listConversations());
    } catch {
      setConversations([]);
    }
  };

  const loadConversation = async (id: number) => {
    setShowHistory(false);
    setIsSending(true);
    try {
      const history = await getConversationMessages(id);
      setMessages(
        history.map((entry) => ({
          role: entry.role as ChatMessage["role"],
          content: entry.content,
          sources: entry.sources,
        })),
      );
      setConversationId(id);
      setPinnedToBottom(true);
    } catch (error) {
      setMessages([{ role: "assistant", content: describeError(error), isError: true }]);
    } finally {
      setIsSending(false);
    }
  };

  const removeConversation = async (id: number) => {
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((item) => item.id !== id));
      if (id === conversationId) startNewChat();
    } catch {
      /* leaving the row in place is a fair signal that it did not delete */
    }
  };

  const startNewChat = () => {
    setMessages([]);
    setConversationId(null);
    sessionStorage.removeItem(THREAD_KEY);
    setShowHistory(false);
    setUploadingFiles([]);
  };

  // ---- training (admin) ------------------------------------------------
  const pollStatus = (id: number) => {
    const timer = window.setInterval(async () => {
      try {
        const status = await getDocumentStatus(id);
        setUploadingFiles((prev) =>
          prev.map((file) =>
            file.documentId === id
              ? { ...file, status: status.status, progressPercent: status.progress_percent }
              : file,
          ),
        );
        if (status.status === "indexed" || status.status === "failed") {
          window.clearInterval(timer);
          listDocuments().then(setDocuments).catch(() => undefined);
          if (status.status === "indexed") {
            // Clear the finished row after a moment so the panel does not
            // accumulate green bars for the rest of the session.
            window.setTimeout(
              () =>
                setUploadingFiles((prev) => prev.filter((file) => file.documentId !== id)),
              4000,
            );
            setMessages((prev) => [
              ...prev,
              {
                role: "assistant",
                content: `**${status.filename}** is trained and ready — ${status.total_chunks} passages indexed. Everyone can now ask about it.`,
              },
            ]);
          }
        }
      } catch {
        window.clearInterval(timer);
        setUploadingFiles((prev) =>
          prev.map((file) =>
            file.documentId === id
              ? { ...file, status: "error", error: "Lost contact while training" }
              : file,
          ),
        );
      }
    }, POLL_INTERVAL_MS);

    pollTimers.current.push(timer);
  };

  const handleFilesSelected = async (fileList: FileList) => {
    const files = Array.from(fileList);
    setUploadingFiles((prev) => [
      ...prev,
      ...files.map((file) => ({
        documentId: null,
        filename: file.name,
        status: "uploading" as const,
        progressPercent: 0,
      })),
    ]);

    for (const file of files) {
      try {
        const document = await uploadDocument(file);
        setUploadingFiles((prev) =>
          prev.map((entry) =>
            entry.filename === file.name && entry.documentId === null
              ? { ...entry, documentId: document.id, status: document.status as UploadingFile["status"] }
              : entry,
          ),
        );
        pollStatus(document.id);
      } catch (error) {
        const reason = describeError(error);
        setUploadingFiles((prev) =>
          prev.map((entry) =>
            entry.filename === file.name && entry.documentId === null
              ? { ...entry, status: "error", error: reason }
              : entry,
          ),
        );
      }
    }
  };

  const indexedDocuments = documents.filter((document) => document.status === "indexed");

  if (!signedIn) return null;

  return (
    <div className="ismo-chat">
      {isOpen && (
        <div
          role="dialog"
          aria-label="HR Assistant"
          className={`fixed bottom-24 right-5 z-[60] flex flex-col overflow-hidden rounded-2xl border border-[var(--chat-rule)] bg-[var(--chat-panel)] shadow-[0_24px_60px_-12px_rgba(15,27,56,0.45)] panel-in transition-[width,height] duration-300 ${
            wide
              ? "w-[min(720px,calc(100vw-2.5rem))]"
              : "w-[min(408px,calc(100vw-2.5rem))]"
          }`}
          // Kept clear of the dashboard's own sticky header, which sits above
          // this panel in the stacking order.
          style={{ height: wide ? "min(720px, 80vh)" : "min(620px, 78vh)" }}
        >
          {/* Header */}
          <div className="relative flex shrink-0 items-center gap-2.5 border-b border-[var(--chat-rule)] bg-[var(--chat-header)] px-3.5 py-3">
            <div className="relative flex h-9 w-9 items-center justify-center rounded-full bg-[var(--chat-accent)] text-[var(--chat-on-accent)]">
              <BotIcon />
              <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-[var(--chat-header)] bg-[var(--chat-good)]" />
            </div>

            <div className="min-w-0 flex-1">
              <p className="truncate text-[13.5px] font-semibold text-[var(--chat-strong)]">
                HR Assistant
              </p>
              <p className="truncate text-[10.5px] text-[var(--chat-dim)]">
                {indexedDocuments.length > 0
                  ? `Policy, leave & attendance · ${indexedDocuments.length} document${
                      indexedDocuments.length === 1 ? "" : "s"
                    } trained`
                  : "Policy, leave & attendance"}
              </p>
            </div>

            <HeaderButton
              label={wide ? "Shrink panel" : "Widen panel"}
              onClick={() => setWide((current) => !current)}
            >
              {wide ? <ShrinkIcon /> : <ExpandIcon />}
            </HeaderButton>
            <HeaderButton label="New chat" onClick={startNewChat}>
              <PlusCircleIcon />
            </HeaderButton>
            <HeaderButton label="Past chats" onClick={openHistory}>
              <HistoryIcon />
            </HeaderButton>
            <HeaderButton label="Close" onClick={() => setIsOpen(false)}>
              <CloseIcon />
            </HeaderButton>
          </div>

          {indexedDocuments.length > 1 && (
            <div className="shrink-0 border-b border-[var(--chat-rule)] bg-[var(--chat-header)] px-3.5 py-2">
              <DocumentSelector
                documents={indexedDocuments}
                selectedDocumentId={documentId}
                onSelect={setDocumentId}
              />
            </div>
          )}

          {/* Messages */}
          <div className="relative flex-1 overflow-hidden">
            <div
              ref={scrollRef}
              onScroll={handleScroll}
              className="h-full space-y-3 overflow-y-auto px-3.5 py-4 custom-scrollbar"
            >
              {messages.length === 0 ? (
                <EmptyState
                  name={user.name}
                  isAdmin={resolvedIsAdmin}
                  onPick={(question) => void handleSend(question)}
                />
              ) : (
                messages.map((message, index) => (
                  <MessageBubble key={index} message={message} />
                ))
              )}

              {isSending && (
                <div className="flex items-center gap-2 msg-in">
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--chat-accent)] text-[var(--chat-on-accent)]">
                    <BotIcon small />
                  </div>
                  <div className="flex items-center gap-2 rounded-2xl rounded-tl-sm border border-[var(--chat-rule)] bg-[var(--chat-bubble)] px-3 py-2">
                    <span className="flex gap-1">
                      <Dot delay="0ms" />
                      <Dot delay="140ms" />
                      <Dot delay="280ms" />
                    </span>
                    <span className="text-[11.5px] text-[var(--chat-dim)]">
                      {WAITING_STAGES[stage]}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {!pinnedToBottom && messages.length > 0 && (
              <button
                onClick={() => {
                  setPinnedToBottom(true);
                  scrollToBottom();
                }}
                aria-label="Jump to latest"
                className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full border border-[var(--chat-rule)] bg-[var(--chat-card)] p-1.5 text-[var(--chat-dim)] shadow-md transition-transform hover:scale-105 fade-in"
              >
                <ChevronDownIcon />
              </button>
            )}

            {showHistory && (
              <HistoryPanel
                conversations={conversations}
                activeId={conversationId}
                onClose={() => setShowHistory(false)}
                onPick={loadConversation}
                onDelete={removeConversation}
              />
            )}
          </div>

          {/* Training progress (admin) */}
          {resolvedIsAdmin && uploadingFiles.length > 0 && (
            <div className="max-h-28 shrink-0 space-y-2 overflow-y-auto border-t border-[var(--chat-rule)] bg-[var(--chat-header)] px-3.5 py-2 custom-scrollbar">
              {uploadingFiles.map((file, index) => (
                <div key={`${file.filename}-${index}`}>
                  <div className="flex items-center justify-between gap-2 text-[10.5px]">
                    <span className="truncate text-[var(--chat-text)]">{file.filename}</span>
                    <span
                      className={
                        file.status === "failed" || file.status === "error"
                          ? "text-[var(--chat-bad)]"
                          : file.status === "indexed"
                            ? "text-[var(--chat-good)]"
                            : "text-[var(--chat-dim)]"
                      }
                    >
                      {file.status === "error"
                        ? (file.error ?? "failed")
                        : file.status === "embedding"
                          ? `training ${file.progressPercent}%`
                          : file.status}
                    </span>
                  </div>
                  <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-[var(--chat-rule)]">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${file.status === "uploading" ? 8 : file.progressPercent}%`,
                        background:
                          file.status === "failed" || file.status === "error"
                            ? "var(--chat-bad)"
                            : file.status === "indexed"
                              ? "var(--chat-good)"
                              : "var(--chat-accent)",
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Composer */}
          <div className="relative shrink-0 border-t border-[var(--chat-rule)] bg-[var(--chat-header)] p-3">
            {showDropdown && dropdownMatches.length > 0 && (
              <div className="dropdown-in absolute bottom-full left-3 right-3 mb-2 overflow-hidden rounded-xl border border-[var(--chat-rule)] bg-[var(--chat-card)] shadow-lg">
                {dropdownMatches.map((match, index) => (
                  <button
                    key={match}
                    type="button"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => acceptSuggestion(match)}
                    onMouseEnter={() => setActiveIndex(index)}
                    className={`block w-full px-3 py-2 text-left text-[11.5px] transition-colors ${
                      index === activeIndex
                        ? "bg-[var(--chat-accent-soft)] text-[var(--chat-accent-ink)]"
                        : "text-[var(--chat-text)]"
                    }`}
                  >
                    {match}
                  </button>
                ))}
              </div>
            )}

            <div className="flex items-end gap-1.5 rounded-xl border border-[var(--chat-rule)] bg-[var(--chat-card)] px-1.5 py-1.5 transition-colors focus-within:border-[var(--chat-accent)]">
              {resolvedIsAdmin && (
                <>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    title="Train a document (PDF, DOCX, TXT, MD)"
                    aria-label="Train a document"
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[var(--chat-dim)] transition-colors hover:bg-[var(--chat-accent-soft)] hover:text-[var(--chat-accent-ink)]"
                  >
                    <PaperclipIcon />
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.docx,.txt,.md"
                    className="hidden"
                    onChange={(event) => {
                      if (event.target.files) void handleFilesSelected(event.target.files);
                      event.target.value = "";
                    }}
                  />
                </>
              )}

              <div className="relative min-w-0 flex-1">
                {/* The typed part is transparent here purely to line the ghost
                    remainder up with the real text in the textarea above it. */}
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-0 whitespace-pre-wrap break-words px-1.5 py-1.5 text-[13px]"
                >
                  <span className="text-transparent">{input}</span>
                  <span className="text-[var(--chat-ghost)]">{ghostRemainder}</span>
                </div>

                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  onBlur={() => window.setTimeout(() => setShowDropdown(false), 120)}
                  placeholder="Ask about policy, your leave or attendance…"
                  rows={1}
                  disabled={isSending}
                  className="relative max-h-24 w-full resize-none bg-transparent px-1.5 py-1.5 text-[13px] text-[var(--chat-text)] outline-none placeholder:text-[var(--chat-ghost)] disabled:opacity-60"
                />

                {ghostRemainder && (
                  <button
                    type="button"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => acceptSuggestion(topMatch)}
                    className="absolute right-1 top-1/2 -translate-y-1/2 rounded border border-[var(--chat-rule)] bg-[var(--chat-head)] px-1.5 py-0.5 text-[9.5px] text-[var(--chat-dim)]"
                  >
                    Tab ⇥
                  </button>
                )}
              </div>

              <button
                onClick={() => void handleSend()}
                disabled={isSending || !input.trim()}
                aria-label="Send"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--chat-accent)] text-[var(--chat-on-accent)] transition-all hover:brightness-110 disabled:opacity-40"
              >
                <SendIcon />
              </button>
            </div>

            <p className="mt-1.5 text-center text-[9.5px] text-[var(--chat-ghost)]">
              Answers come from your own records and ISMO's trained HR documents.
            </p>
          </div>
        </div>
      )}

      {/* Launcher */}
      <div className="fixed bottom-5 right-5 z-[60]">
        {!isOpen && (
          <span
            aria-hidden="true"
            className="absolute inset-0 rounded-full bg-[var(--chat-accent)] pulse-ring"
          />
        )}
        <button
          onClick={() => setIsOpen((open) => !open)}
          aria-label={isOpen ? "Close HR Assistant" : "Open HR Assistant"}
          className={`relative flex h-14 w-14 items-center justify-center rounded-full bg-[var(--chat-accent)] text-[var(--chat-on-accent)] shadow-[0_10px_30px_-6px_var(--chat-accent)] transition-transform hover:scale-105 ${
            isOpen ? "" : "fab-float"
          }`}
        >
          <span
            className="inline-flex transition-transform duration-300"
            style={{ transform: isOpen ? "rotate(90deg) scale(0.92)" : "none" }}
          >
            {isOpen ? <CloseIcon large /> : <BotIcon large />}
          </span>
        </button>
      </div>

      <style>{`
        .ismo-chat {
          --chat-panel: #ffffff;
          --chat-header: #f7f9fc;
          --chat-card: #ffffff;
          --chat-bubble: #ffffff;
          --chat-head: #eef2f8;
          --chat-row: #fafbfd;
          --chat-rule: #dfe4ec;
          --chat-text: #29323f;
          --chat-strong: #101828;
          --chat-dim: #6b7787;
          --chat-ghost: #9aa5b4;
          --chat-accent: #1d7f92;
          --chat-accent-ink: #14636f;
          --chat-accent-soft: #e6f4f7;
          --chat-on-accent: #ffffff;
          --chat-good: #16a34a;
          --chat-warn: #d97706;
          --chat-bad: #dc2626;
          --chat-bad-soft: #fef2f2;
          --chat-excel: #157a45;
          --chat-excel-soft: #e9f6ee;
          --chat-pdf: #c0392b;
          --chat-pdf-soft: #fdeceb;
        }
        :is(.dark) .ismo-chat {
          --chat-panel: #151d2e;
          --chat-header: #101725;
          --chat-card: #1a2334;
          --chat-bubble: #1c2537;
          --chat-head: #212c40;
          --chat-row: #1b2434;
          --chat-rule: #2c3850;
          --chat-text: #dde3ec;
          --chat-strong: #f4f7fb;
          --chat-dim: #93a0b4;
          --chat-ghost: #64728a;
          --chat-accent: #22b8cf;
          --chat-accent-ink: #7fe0ee;
          --chat-accent-soft: rgba(34,184,207,0.14);
          --chat-on-accent: #04222a;
          --chat-good: #34d399;
          --chat-warn: #fbbf24;
          --chat-bad: #f87171;
          --chat-bad-soft: rgba(248,113,113,0.12);
          --chat-excel: #4ade80;
          --chat-excel-soft: rgba(74,222,128,0.12);
          --chat-pdf: #fb8f7f;
          --chat-pdf-soft: rgba(251,143,127,0.12);
        }

        .panel-in { animation: panel-in .34s cubic-bezier(.34,1.4,.64,1) both; transform-origin: bottom right; }
        @keyframes panel-in {
          from { opacity: 0; transform: scale(.9) translateY(20px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
        .msg-in { animation: msg-in .26s cubic-bezier(.22,1,.36,1) both; }
        @keyframes msg-in {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .table-in { animation: table-in .3s ease-out both; }
        @keyframes table-in {
          from { opacity: 0; transform: translateY(-4px) scaleY(.98); }
          to { opacity: 1; transform: translateY(0) scaleY(1); }
        }
        .fade-in { animation: fade-in .2s ease-out both; }
        @keyframes fade-in { from { opacity: 0 } to { opacity: 1 } }
        .chip-in { animation: chip-in .3s ease-out both; }
        @keyframes chip-in {
          from { opacity: 0; transform: translateY(6px) scale(.97); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .dropdown-in { animation: dropdown-in .16s ease-out both; transform-origin: bottom center; }
        @keyframes dropdown-in {
          from { opacity: 0; transform: translateY(6px) scaleY(.96); }
          to { opacity: 1; transform: translateY(0) scaleY(1); }
        }
        .history-in { animation: history-in .24s cubic-bezier(.22,1,.36,1) both; }
        @keyframes history-in {
          from { opacity: 0; transform: translateX(14px); }
          to { opacity: 1; transform: translateX(0); }
        }
        .pulse-ring { animation: pulse-ring 2.4s cubic-bezier(.4,0,.6,1) infinite; }
        @keyframes pulse-ring {
          0% { opacity: .5; transform: scale(1); }
          100% { opacity: 0; transform: scale(1.65); }
        }
        .fab-float { animation: fab-float 3.4s ease-in-out infinite; }
        @keyframes fab-float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-5px); }
        }
        .typing-dot { animation: typing-dot 1s infinite ease-in-out; }
        @keyframes typing-dot {
          0%, 80%, 100% { opacity: .3; transform: scale(.75); }
          40% { opacity: 1; transform: scale(1); }
        }

        /* Respect the visitor's motion preference: the widget still works, it
           simply stops moving. */
        @media (prefers-reduced-motion: reduce) {
          .ismo-chat *, .ismo-chat *::before, .ismo-chat *::after {
            animation-duration: .01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: .01ms !important;
          }
        }
      `}</style>
    </div>
  );
}

// ------------------------------------------------------------------ pieces

function EmptyState({
  name,
  isAdmin,
  onPick,
}: {
  name?: string;
  isAdmin: boolean;
  onPick: (question: string) => void;
}) {
  const firstName = (name ?? "").replace(/^(Mr\.|Ms\.|Mrs\.)\s*/i, "").split(" ")[0];

  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-3 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--chat-accent-soft)] text-[var(--chat-accent-ink)] chip-in">
        <BotIcon large />
      </div>
      <div>
        <p className="text-[14px] font-semibold text-[var(--chat-strong)]">
          {firstName ? `Hello ${firstName.charAt(0)}${firstName.slice(1).toLowerCase()}` : "Hello"} 👋
        </p>
        <p className="mt-1 text-[11.5px] leading-relaxed text-[var(--chat-dim)]">
          Ask about HR policy, your leave balance or your attendance.
          {isAdmin && " As an administrator you can also train new documents."}
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-1.5">
        {SUGGESTIONS.map((question, index) => (
          <button
            key={question}
            onClick={() => onPick(question)}
            style={{ animationDelay: `${60 + index * 70}ms` }}
            className="chip-in rounded-full border border-[var(--chat-rule)] bg-[var(--chat-card)] px-2.5 py-1.5 text-[11px] text-[var(--chat-text)] transition-all hover:-translate-y-px hover:border-[var(--chat-accent)] hover:text-[var(--chat-accent-ink)]"
          >
            {question}
          </button>
        ))}
      </div>
    </div>
  );
}

function HistoryPanel({
  conversations,
  activeId,
  onClose,
  onPick,
  onDelete,
}: {
  conversations: ConversationSummary[];
  activeId: number | null;
  onClose: () => void;
  onPick: (id: number) => void;
  onDelete: (id: number) => void;
}) {
  return (
    <div className="absolute inset-0 flex flex-col bg-[var(--chat-panel)] history-in">
      <div className="flex items-center justify-between border-b border-[var(--chat-rule)] px-3.5 py-2.5">
        <p className="text-[12px] font-semibold text-[var(--chat-strong)]">Past chats</p>
        <button
          onClick={onClose}
          aria-label="Back to chat"
          className="rounded-md p-1 text-[var(--chat-dim)] transition-colors hover:bg-[var(--chat-head)]"
        >
          <CloseIcon />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2 custom-scrollbar">
        {conversations.length === 0 ? (
          <p className="px-2 py-6 text-center text-[11.5px] text-[var(--chat-dim)]">
            No earlier conversations yet.
          </p>
        ) : (
          conversations.map((conversation) => (
            <div
              key={conversation.id}
              className={`group flex items-center gap-1 rounded-lg px-2 py-2 transition-colors hover:bg-[var(--chat-head)] ${
                conversation.id === activeId ? "bg-[var(--chat-accent-soft)]" : ""
              }`}
            >
              <button
                onClick={() => onPick(conversation.id)}
                className="min-w-0 flex-1 text-left"
              >
                <span className="block truncate text-[11.5px] text-[var(--chat-text)]">
                  {conversation.title || `Conversation ${conversation.id}`}
                </span>
                <span className="block text-[9.5px] text-[var(--chat-dim)]">
                  {new Date(conversation.created_at.replace(" ", "T")).toLocaleString()}
                </span>
              </button>
              <button
                onClick={() => onDelete(conversation.id)}
                aria-label="Delete conversation"
                className="rounded p-1 text-[var(--chat-dim)] opacity-0 transition-opacity hover:text-[var(--chat-bad)] group-hover:opacity-100"
              >
                <TrashIcon />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function HeaderButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-[var(--chat-dim)] transition-colors hover:bg-[var(--chat-head)] hover:text-[var(--chat-strong)]"
    >
      {children}
    </button>
  );
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      className="typing-dot inline-block h-1.5 w-1.5 rounded-full bg-[var(--chat-dim)]"
      style={{ animationDelay: delay }}
    />
  );
}

// -------------------------------------------------------------------- icons

function BotIcon({ large, small }: { large?: boolean; small?: boolean }) {
  const size = large ? 24 : small ? 12 : 17;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="8" width="16" height="12" rx="2.5" />
      <path d="M12 8V4.5" />
      <circle cx="12" cy="3.2" r="1.2" />
      <path d="M8.5 13h.01M15.5 13h.01" />
      <path d="M9.5 17h5" />
    </svg>
  );
}

function CloseIcon({ large }: { large?: boolean }) {
  const size = large ? 22 : 15;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m22 2-7 20-4-9-9-4Z" />
      <path d="M22 2 11 13" />
    </svg>
  );
}

function PaperclipIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" />
    </svg>
  );
}

function HistoryIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3v5h5" />
      <path d="M3.05 13A9 9 0 1 0 6 5.3L3 8" />
      <path d="M12 7v5l4 2" />
    </svg>
  );
}

function PlusCircleIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v8M8 12h8" />
    </svg>
  );
}

function ExpandIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
    </svg>
  );
}

function ShrinkIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 14h6v6M20 10h-6V4M14 10l7-7M3 21l7-7" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" />
    </svg>
  );
}
