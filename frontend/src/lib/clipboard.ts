/**
 * Copy text to the clipboard with a fallback for non-secure contexts.
 *
 * navigator.clipboard is only available in secure contexts (HTTPS or
 * localhost). When the UI is opened from another host over plain HTTP
 * (e.g. http://my-server.local:8090 from a different machine), the API
 * is undefined and writeText() throws. We fall back to the legacy
 * document.execCommand("copy") via a hidden textarea, which works in
 * every browser that ships our React+Vite bundle target.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  if (typeof navigator !== "undefined" && navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // fall through to legacy
    }
  }
  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    // Keep it off-screen but in the layout tree so .select() works.
    textarea.style.position = "fixed";
    textarea.style.top = "0";
    textarea.style.left = "0";
    textarea.style.width = "1px";
    textarea.style.height = "1px";
    textarea.style.opacity = "0";
    textarea.setAttribute("readonly", "");
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(textarea);
    return ok;
  } catch {
    return false;
  }
}
