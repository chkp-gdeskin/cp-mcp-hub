import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type ServerListItem } from "@/api/client";
import { ServerCard } from "@/components/ServerCard";
import { PILLARS, pillarFor } from "@/lib/pillars";

export function Dashboard() {
  const [items, setItems] = useState<ServerListItem[]>([]);
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const r = await api.listServers();
      setItems(r.servers);
    } catch (err) {
      setError(err instanceof Error ? err.message : "load failed");
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [refresh]);

  async function toggle(id: string, next: boolean) {
    setBusy(b => ({ ...b, [id]: true }));
    try {
      if (next) await api.enableServer(id);
      else await api.disableServer(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "toggle failed");
    } finally {
      setBusy(b => ({ ...b, [id]: false }));
    }
  }

  // Group items by pillar, preserving pillar order
  const grouped = useMemo(() => {
    const byPillar = new Map<string, ServerListItem[]>();
    for (const it of items) {
      const key = pillarFor(it.id);
      const arr = byPillar.get(key) ?? [];
      arr.push(it);
      byPillar.set(key, arr);
    }
    return PILLARS.filter(p => (byPillar.get(p.id)?.length ?? 0) > 0).map(p => ({
      pillar: p,
      servers: (byPillar.get(p.id) ?? []).sort((a, b) => a.display_name.localeCompare(b.display_name)),
    }));
  }, [items]);

  const totalEnabled = items.filter(i => i.enabled).length;

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Servers</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Organized by Check Point solution pillar.
          </p>
        </div>
        <div className="text-sm text-muted-foreground">
          <span className="text-foreground font-medium">{totalEnabled}</span> of {items.length} enabled
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">{error}</div>
      )}

      {grouped.map(({ pillar, servers }) => (
        <section key={pillar.id} className="space-y-3">
          <div className="flex items-baseline gap-3 border-b pb-2">
            <h2 className="text-base font-semibold tracking-tight text-foreground">{pillar.label}</h2>
            <span className="text-xs text-muted-foreground">{pillar.description}</span>
            <span className="ml-auto text-xs text-muted-foreground">
              {servers.filter(s => s.enabled).length}/{servers.length}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {servers.map(s => (
              <ServerCard key={s.id} server={s} onToggle={(next) => toggle(s.id, next)} busy={!!busy[s.id]} />
            ))}
          </div>
        </section>
      ))}

      {items.length === 0 && (
        <p className="text-sm text-muted-foreground">No servers loaded yet…</p>
      )}
    </div>
  );
}
