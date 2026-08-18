import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useNavigate } from "react-router";
import type { ChatMessage } from "../../types/chat";
import DataTable from "./DataTable";
import ReportButtons from "./ReportButtons";

const MARKDOWN_STYLES =
  "text-[13px] leading-relaxed text-[var(--chat-text)] " +
  "[&_p]:mb-2 [&_p:last-child]:mb-0 " +
  "[&_ul]:list-disc [&_ul]:pl-4 [&_ul]:mb-2 [&_ul]:space-y-1 " +
  "[&_ol]:list-decimal [&_ol]:pl-4 [&_ol]:mb-2 [&_ol]:space-y-1 " +
  "[&_strong]:font-semibold [&_strong]:text-[var(--chat-strong)] " +
  "[&_em]:text-[var(--chat-dim)] " +
  "[&_a]:text-[var(--chat-accent-ink)] [&_a]:underline " +
  "[&_code]:rounded [&_code]:bg-[var(--chat-head)] [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[11px] " +
  "[&_pre]:mb-2 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:border [&_pre]:border-[var(--chat-rule)] [&_pre]:bg-[var(--chat-head)] [&_pre]:p-2.5 " +
  "[&_h1]:mb-1.5 [&_h1]:text-[14px] [&_h1]:font-semibold " +
  "[&_h2]:mb-1.5 [&_h2]:mt-2 [&_h2]:text-[13px] [&_h2]:font-semibold " +
  "[&_h3]:mb-1 [&_h3]:mt-2 [&_h3]:text-[12.5px] [&_h3]:font-semibold " +
  "[&_blockquote]:border-l-2 [&_blockquote]:border-[var(--chat-accent)] [&_blockquote]:pl-2.5 [&_blockquote]:text-[var(--chat-dim)] " +
  "[&_table]:mb-2 [&_table]:w-full [&_table]:border-collapse " +
  "[&_th]:border [&_th]:border-[var(--chat-rule)] [&_th]:bg-[var(--chat-head)] [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:text-[11px] " +
  "[&_td]:border [&_td]:border-[var(--chat-rule)] [&_td]:px-2 [&_td]:py-1 [&_td]:text-[11px]";

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const navigate = useNavigate();
  const isUser = message.role === "user";

  return (
    <div className={`flex items-start gap-2 msg-in ${isUser ? "flex-row-reverse" : ""}`}>
      <Avatar isUser={isUser} />

      <div className={isUser ? "max-w-[78%]" : "max-w-[88%] min-w-0"}>
        <div
          className={
            isUser
              ? "rounded-2xl rounded-tr-sm bg-[var(--chat-accent)] px-3.5 py-2 text-[13px] leading-relaxed text-[var(--chat-on-accent)] whitespace-pre-wrap"
              : `rounded-2xl rounded-tl-sm border px-3.5 py-2.5 shadow-sm ${
                  message.isError
                    ? "border-[var(--chat-bad)] bg-[var(--chat-bad-soft)]"
                    : "border-[var(--chat-rule)] bg-[var(--chat-bubble)]"
                }`
          }
        >
          {isUser ? (
            message.content
          ) : (
            <div className={MARKDOWN_STYLES}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>

        {!isUser && message.data && <DataTable block={message.data} />}
        {!isUser && message.report && <ReportButtons offer={message.report} />}

        {!isUser && message.actions && message.actions.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {message.actions.map((action, index) => (
              <button
                key={`${action.path}-${index}`}
                onClick={() => navigate(action.path)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--chat-accent)] bg-[var(--chat-accent-soft)] px-2.5 py-1.5 text-[11.5px] font-medium text-[var(--chat-accent-ink)] transition-all hover:-translate-y-px hover:brightness-105"
              >
                <ArrowIcon />
                {action.label}
              </button>
            ))}
          </div>
        )}

        {!isUser && message.sources && message.sources.length > 0 && (
          <Sources sources={message.sources} />
        )}
      </div>
    </div>
  );
}

/** Which document and page an answer came from, so a claim can be checked. */
function Sources({ sources }: { sources: NonNullable<ChatMessage["sources"]> }) {
  // One chip per page, not per chunk: three passages from page 16 is one place
  // to look, and the model cited the page.
  const seen = new Map<string, { filename: string; page: number | null }>();
  for (const source of sources) {
    const filename = source.filename ?? "document";
    const page = source.page_number ?? null;
    seen.set(`${filename}#${page}`, { filename, page });
  }

  return (
    <div className="mt-2 border-t border-dashed border-[var(--chat-rule)] pt-2">
      <p className="mb-1.5 text-[9.5px] font-semibold uppercase tracking-widest text-[var(--chat-dim)]">
        From the HR documents
      </p>
      <div className="flex flex-wrap gap-1.5">
        {[...seen.values()].map(({ filename, page }, index) => (
          <span
            key={index}
            title={filename}
            className="inline-flex max-w-full items-center gap-1 rounded-md border border-[var(--chat-rule)] bg-[var(--chat-head)] px-1.5 py-0.5 text-[10px] text-[var(--chat-dim)]"
          >
            <DocIcon />
            <span className="max-w-[130px] truncate">{prettyName(filename)}</span>
            {page !== null && <b className="font-mono text-[9.5px]">p.{page}</b>}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Uploads are stored under a uuid prefix; nobody needs to read that. */
function prettyName(filename: string): string {
  return filename.replace(/^[0-9a-f]{16,}_/i, "").replace(/\.(pdf|docx|txt|md)$/i, "");
}

function Avatar({ isUser }: { isUser: boolean }) {
  return (
    <div
      className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
        isUser
          ? "bg-[var(--chat-accent-soft)] text-[var(--chat-accent-ink)]"
          : "bg-[var(--chat-accent)] text-[var(--chat-on-accent)]"
      }`}
    >
      {isUser ? <UserIcon /> : <BotGlyph />}
    </div>
  );
}

function UserIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20c0-4 3.5-6 8-6s8 2 8 6" />
    </svg>
  );
}

function BotGlyph() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="8" width="16" height="12" rx="2" />
      <path d="M12 8V4" />
      <circle cx="12" cy="3" r="1" />
      <path d="M8.5 13h.01M15.5 13h.01" />
      <path d="M9.5 17h5" />
    </svg>
  );
}

function DocIcon() {
  return (
    <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 opacity-70">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
      <path d="M14 2v6h6" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}
