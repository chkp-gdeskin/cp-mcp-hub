import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { copyToClipboard } from "@/lib/clipboard";

interface Props {
  value: string | null | undefined;
  label?: string;
  className?: string;
}

/**
 * Icon-button that copies `value` to the clipboard and briefly shows a
 * Check icon for visual confirmation. Works in both secure (HTTPS /
 * localhost) and non-secure (LAN HTTP) contexts.
 */
export function CopyButton({ value, label = "Copy", className }: Props) {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);

  async function handleClick() {
    if (!value) return;
    setFailed(false);
    const ok = await copyToClipboard(value);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } else {
      setFailed(true);
      setTimeout(() => setFailed(false), 1800);
    }
  }

  return (
    <Button
      size="icon"
      variant="ghost"
      onClick={handleClick}
      disabled={!value}
      aria-label={copied ? `${label} (copied)` : label}
      title={failed ? "Copy failed" : label}
      className={className}
    >
      {copied ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}
    </Button>
  );
}
