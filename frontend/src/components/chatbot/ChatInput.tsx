import { useState, type KeyboardEvent } from "react";

interface Props {
  onSend: (question: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState("");

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="flex items-end gap-2 border border-[var(--rule)] rounded-xl p-2 bg-white focus-within:border-[var(--accent)] transition-colors">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask a question about your documents…"
        rows={1}
        disabled={disabled}
        className="flex-1 resize-none border-none outline-none text-sm px-2 py-1.5 text-[var(--ink)] placeholder:text-[var(--ink-faint)] disabled:opacity-50 bg-transparent"
      />
      <button
        onClick={submit}
        disabled={disabled || !value.trim()}
        className="px-4 py-1.5 rounded-lg bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-hover)] disabled:opacity-40 disabled:hover:bg-[var(--accent)] transition-colors"
      >
        Send
      </button>
    </div>
  );
}