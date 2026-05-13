import { Badge } from "@/components/ui/badge";

interface Props { state: string }

export function StatusBadge({ state }: Props) {
  switch (state) {
    case "running":
      return <Badge variant="success">Running</Badge>;
    case "starting":
      return <Badge variant="warning">Starting</Badge>;
    case "failed":
      return <Badge variant="destructive">Failed</Badge>;
    case "stopped":
      return <Badge variant="muted">Stopped</Badge>;
    case "disabled":
      return <Badge variant="outline">Disabled</Badge>;
    default:
      return <Badge variant="outline">{state}</Badge>;
  }
}
