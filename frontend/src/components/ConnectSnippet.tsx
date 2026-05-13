import { useMemo, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CopyButton } from "@/components/CopyButton";

interface Props {
  serverId: string;
  sseUrl: string | null;
  token: string | null;
}

type Mode = "desktop" | "code";

/**
 * Renders a ready-to-paste connection snippet for the most common MCP
 * clients: a JSON object for `claude_desktop_config.json` and a one-line
 * `claude mcp add` command for Claude Code. The strings are kept in
 * useMemo so copying multiple times during a 5s parent refresh doesn't
 * mutate them between clicks.
 */
export function ConnectSnippet({ serverId, sseUrl, token }: Props) {
  const [mode, setMode] = useState<Mode>("desktop");

  const desktopJson = useMemo(() => {
    if (!sseUrl || !token) return "";
    const obj = {
      mcpServers: {
        [`cp-${serverId}`]: {
          command: "npx",
          args: [
            "-y",
            "mcp-remote",
            sseUrl,
            "--header",
            `Authorization: Bearer ${token}`,
          ],
        },
      },
    };
    return JSON.stringify(obj, null, 2);
  }, [serverId, sseUrl, token]);

  const codeCommand = useMemo(() => {
    if (!sseUrl || !token) return "";
    return `claude mcp add cp-${serverId} \\\n  --transport sse \\\n  --header "Authorization: Bearer ${token}" \\\n  ${sseUrl}`;
  }, [serverId, sseUrl, token]);

  const active = mode === "desktop" ? desktopJson : codeCommand;
  const ready = !!sseUrl && !!token;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Connect a client</CardTitle>
        <CardDescription>Copy-paste configuration for the most common MCP clients.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-1 border-b">
          <TabButton active={mode === "desktop"} onClick={() => setMode("desktop")}>
            Claude Desktop
          </TabButton>
          <TabButton active={mode === "code"} onClick={() => setMode("code")}>
            Claude Code
          </TabButton>
          <div className="ml-auto pb-1">
            <CopyButton value={ready ? active : null} label={`Copy ${mode === "desktop" ? "Claude Desktop snippet" : "Claude Code command"}`} />
          </div>
        </div>

        <pre className="bg-muted px-3 py-2 rounded text-xs font-mono overflow-x-auto whitespace-pre leading-relaxed">
{ready ? active : "// waiting for endpoint and token..."}
        </pre>

        {mode === "desktop" ? (
          <p className="text-xs text-muted-foreground leading-relaxed">
            Merge into <code className="font-mono">claude_desktop_config.json</code> (macOS:{" "}
            <code className="font-mono">~/Library/Application Support/Claude/</code>, Windows:{" "}
            <code className="font-mono">%APPDATA%\Claude\</code>), then fully quit and reopen Claude Desktop (Cmd/Ctrl+Q).
          </p>
        ) : (
          <p className="text-xs text-muted-foreground leading-relaxed">
            Run in your terminal. Verify with <code className="font-mono">claude mcp list</code>.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "px-3 py-1.5 text-sm border-b-2 -mb-px transition-colors " +
        (active
          ? "border-berry text-foreground font-medium"
          : "border-transparent text-muted-foreground hover:text-foreground")
      }
    >
      {children}
    </button>
  );
}
