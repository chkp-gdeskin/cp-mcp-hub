import { Link } from "react-router-dom";
import type { ServerListItem } from "@/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "./StatusBadge";
import { Switch } from "@/components/ui/switch";

interface Props {
  server: ServerListItem;
  onToggle: (next: boolean) => void;
  busy: boolean;
}

export function ServerCard({ server, onToggle, busy }: Props) {
  const isRunning = server.enabled && server.state === "running";
  return (
    <Card
      className={
        "relative hover:shadow-card transition-shadow flex flex-col overflow-hidden shadow-sm " +
        (isRunning ? "border-l-2 border-l-berry" : "")
      }
    >
      <CardHeader className="flex-row items-start justify-between space-y-0 gap-2">
        <div className="min-w-0">
          <CardTitle className="truncate">{server.display_name}</CardTitle>
          <CardDescription className="line-clamp-2 mt-1">{server.description || "—"}</CardDescription>
        </div>
        <div className="shrink-0">
          <StatusBadge state={server.enabled ? server.state : "disabled"} />
        </div>
      </CardHeader>
      <CardContent className="mt-auto flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Switch checked={server.enabled} onCheckedChange={onToggle} disabled={busy} aria-label={`Enable ${server.display_name}`} />
          <span className="text-xs text-muted-foreground">{server.enabled ? "Enabled" : "Disabled"}</span>
        </div>
        <Link to={`/servers/${server.id}`} className="text-sm font-medium text-berry hover:underline">Configure →</Link>
      </CardContent>
      {server.last_error && (
        <div className="px-6 pb-4 -mt-2 text-xs text-destructive truncate" title={server.last_error}>
          {server.last_error}
        </div>
      )}
    </Card>
  );
}
