import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "../../types/chat";

const MARKDOWN_STYLES =
  "text-[13.5px] leading-relaxed text-[var(--ink)] " +
  "[&_p]:mb-2 [&_p:last-child]:mb-0 " +
  "[&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-2 " +
  "[&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-2 " +
  "[&_li]:mb-0.5 " +
  "[&_strong]:font-semibold [&_strong]:text-[var(--ink)] " +
  "[&_code]:bg-[var(--rule-soft)] [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-xs [&_code]:font-mono " +
  "[&_pre]:bg-[var(--rule-soft)] [&_pre]:border [&_pre]:border-[var(--rule)] [&_pre]:rounded-lg [&_pre]:p-3 [&_pre]:overflow-x-auto [&_pre]:mb-2 " +
  "[&_h1]:text-base [&_h1]:font-semibold [&_h1]:mb-2 [&_h1]:mt-1 " +
  "[&_h2]:text-sm [&_h2]:font-bold [&_h2]:mb-1.5 [&_h2]:mt-3 " +
  "[&_h3]:text-sm [&_h3]:font-semibold [&_h3]:mb-1 [&_h3]:mt-2 " +
  "[&_blockquote]:border-l-2 [&_blockquote]:border-[var(--accent)] [&_blockquote]:pl-3 [&_blockquote]:text-[var(--ink-muted)] [&_blockquote]:italic " +
  "[&_table]:border-collapse [&_table]:w-full [&_table]:mb-2 " +
  "[&_th]:border [&_th]:border-[var(--rule)] [&_th]:bg-[var(--rule-soft)] [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:text-xs " +
  "[&_td]:border [&_td]:border-[var(--rule)] [&_td]:px-2 [&_td]:py-1 [&_td]:text-xs";

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex items-start gap-2.5 message-in ${isUser ? "flex-row-reverse" : ""}`}>
      <Avatar isUser={isUser} />

      <div
        className={
          isUser
            ? "max-w-[68%] rounded-2xl rounded-tr-sm bg-[var(--accent)] text-white px-4 py-2.5"
            : "max-w-[76%] rounded-2xl rounded-tl-sm bg-white border border-[var(--rule)] px-4 py-3.5 shadow-[0_1px_3px_rgba(28,36,48,0.05)]"
        }
      >
        {isUser ? (
          <p className="text-[13.5px] whitespace-pre-wrap leading-relaxed">{message.content}</p>
        ) : (
          <div className={MARKDOWN_STYLES}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          </div>
        )}

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-dashed border-[var(--rule)]">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--stamp)] mb-2">
              Referenced
            </p>
            <div className="flex flex-wrap gap-1.5">
              {message.sources.map((s, i) => (
                <span
                  key={i}
                  title={`Document ${s.document_id}, chunk ${s.chunk_index}`}
                  className="inline-flex items-center gap-1.5 text-[11px] bg-[var(--stamp-soft)] border border-[var(--stamp-rule)] rounded-[3px] pl-2 pr-2 py-1 text-[var(--stamp-ink)]"
                >
                  <DocIcon />
                  <span className="max-w-[140px] truncate">{s.filename}</span>
                  <span className="font-mono text-[10px] opacity-70">
                    ·{String(s.chunk_index).padStart(2, "0")}
                  </span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Avatar({ isUser }: { isUser: boolean }) {
  return (
    <div
      className={
        "shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5 " +
        (isUser ? "bg-[var(--accent-soft)] text-[var(--accent)]" : "bg-[var(--ink)] text-[var(--canvas)]")
      }
    >
      {isUser ? <UserIcon /> : <DocMarkIcon />}
    </div>
  );
}

function UserIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20c0-4 3.5-6 8-6s8 2 8 6" />
    </svg>
  );
}

function DocMarkIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
      <path d="M14 2v6h6" />
      <path d="M9 13h6M9 17h6" />
    </svg>
  );
}

function DocIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 opacity-70">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
      <path d="M14 2v6h6" />
    </svg>
  );
}