import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Copy, ExternalLink } from "lucide-react";
import { api, type ServerDetail as ServerDetailT } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/StatusBadge";
import { ConfigForm } from "@/components/ConfigForm";
import { LogViewer } from "@/components/LogViewer";

function copy(text: string) {
  void navigator.clipboard.writeText(text);
}

export function ServerDetail() {
  const { id = "" } = useParams();
  const [server, setServer] = useState<ServerDetailT | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [sseUrl, setSseUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, t, st] = await Promise.all([api.getServer(id), api.getToken(), api.serverStatus(id)]);
      setServer(s);
      setToken(t.token);
      setSseUrl(new URL(st.sse_url, window.location.origin).toString());
    } catch (err) {
      setError(err instanceof Error ? err.message : "load failed");
    }
  }, [id]);

  useEffect(() => {
    void refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  if (!server) return <p className="text-muted-foreground">Loading…</p>;

  return (
    <div className="space-y-4">
      <div>
        <Link to="/" className="text-sm text-primary hover:underline">← Servers</Link>
        <div className="mt-1 flex items-center gap-3 flex-wrap">
          <h1 className="text-2xl font-semibold tracking-tight">{server.display_name}</h1>
          <StatusBadge state={server.enabled ? server.state : "disabled"} />
          {server.doc_url && (
            <a href={server.doc_url} target="_blank" rel="noreferrer" className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
              docs <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
        {server.description && <p className="text-sm text-muted-foreground mt-1">{server.description}</p>}
      </div>

      {error && <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">{error}</div>}

      <div className="grid lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Configuration</CardTitle>
            <CardDescription>Environment variables for <code className="font-mono text-xs">{server.definition.npm_package}</code></CardDescription>
          </CardHeader>
          <CardContent>
            <ConfigForm
              server={server}
              onSave={async (state) => {
                await api.updateConfig(id, {
                  config: state.config,
                  cli_args: state.cli_args,
                  telemetry_enabled: state.telemetry_enabled,
                  restart_policy: state.restart_policy,
                });
                await refresh();
              }}
            />
          </CardContent>
        </Card>

        <div className="space-y-4 flex flex-col">
          <Card>
            <CardHeader>
              <CardTitle>Endpoint</CardTitle>
              <CardDescription>Connect an MCP client to this server.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">SSE URL</p>
                <div className="flex gap-2 items-center">
                  <code className="flex-1 truncate bg-muted px-2 py-1 rounded text-xs font-mono">{sseUrl ?? ""}</code>
                  <Button size="icon" variant="ghost" onClick={() => sseUrl && copy(sseUrl)} aria-label="Copy SSE URL">
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Bearer token (global)</p>
                <div className="flex gap-2 items-center">
                  <code className="flex-1 truncate bg-muted px-2 py-1 rounded text-xs font-mono">{token ?? ""}</code>
                  <Button size="icon" variant="ghost" onClick={() => token && copy(token)} aria-label="Copy bearer token">
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 pt-2">
                <Button variant="outline" disabled={server.enabled} onClick={() => api.enableServer(id).then(refresh)}>Start</Button>
                <Button variant="outline" disabled={!server.enabled} onClick={() => api.disableServer(id).then(refresh)}>Stop</Button>
                <Button variant="outline" disabled={!server.enabled} onClick={() => api.restartServer(id).then(refresh)}>Restart</Button>
              </div>
              <div className="text-xs text-muted-foreground pt-2">
                <span>State: <strong className="text-foreground">{server.state}</strong></span>
                {server.pid && <span className="ml-3">PID: {server.pid}</span>}
                {server.uptime_seconds > 0 && <span className="ml-3">Uptime: {Math.round(server.uptime_seconds)}s</span>}
              </div>
              {server.last_error && (
                <div className="text-xs text-destructive border border-destructive/30 bg-destructive/5 rounded px-2 py-1">
                  {server.last_error}
                </div>
              )}
            </CardContent>
          </Card>

          <div className="flex-1 min-h-[400px]">
            <LogViewer serverId={id} />
          </div>
        </div>
      </div>
    </div>
  );
}
