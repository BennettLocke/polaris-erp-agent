import { useEffect, useRef, useState } from "react";
import { Check, Copy } from "lucide-react";

import { Button } from "@/components/ui/button";

export type PurchaseResultCopyButtonProps = {
  text: string;
  disabled?: boolean;
  onError?: (message: string) => void;
};

function fallbackCopyText(text: string) {
  const activeElement = document.activeElement;
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  // Keep fallback focus inside a modal's focus trap when present.
  const container = activeElement?.closest('[role="dialog"]') || document.body;
  container.appendChild(textarea);
  try {
    textarea.select();
    if (!document.execCommand("copy")) throw new Error("copy failed");
  } finally {
    textarea.remove();
    if (activeElement && "focus" in activeElement) {
      (activeElement as HTMLElement).focus({ preventScroll: true });
    }
  }
}

export function PurchaseResultCopyButton({ text, disabled, onError }: PurchaseResultCopyButtonProps) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const [copying, setCopying] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  const request = useRef(0);
  const busy = useRef(false);

  useEffect(() => {
    setCopied(false);
    setError("");
    setCopying(false);
    busy.current = false;
    return () => {
      request.current += 1;
      if (timer.current !== undefined) window.clearTimeout(timer.current);
    };
  }, [text]);

  async function handleCopy() {
    if (disabled || !text || busy.current) return;
    busy.current = true;
    const attempt = ++request.current;
    if (timer.current !== undefined) window.clearTimeout(timer.current);
    setCopied(false);
    setError("");
    setCopying(true);
    try {
      try {
        if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
        await navigator.clipboard.writeText(text);
      } catch {
        if (attempt !== request.current) return;
        fallbackCopyText(text);
      }
      if (attempt !== request.current) return;
      setCopied(true);
      timer.current = window.setTimeout(() => setCopied(false), 1600);
    } catch {
      if (attempt !== request.current) return;
      const message = "复制失败，请选择下方进货信息手动复制。";
      setError(message);
      onError?.(message);
    } finally {
      if (attempt === request.current) {
        busy.current = false;
        setCopying(false);
      }
    }
  }

  return (
    <div className="purchase-result-copy-control">
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled || !text || copying}
        onClick={handleCopy}
        aria-label={copied ? "已复制" : "复制进货信息"}
        title={copied ? "已复制" : "复制进货信息"}
      >
        {copied ? <Check data-icon="inline-start" /> : <Copy data-icon="inline-start" />}
        {copied ? "已复制" : "复制进货信息"}
      </Button>
      {error ? (
        <div className="purchase-result-copy-error">
          <p role="alert">{error}</p>
          <textarea aria-label="进货信息（手动复制）" readOnly value={text} onFocus={(event) => event.currentTarget.select()} />
        </div>
      ) : null}
    </div>
  );
}
