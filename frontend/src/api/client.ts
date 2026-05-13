export interface EnvVarDef {
  name: string;
  label: string;
  type: "string" | "password" | "boolean" | "enum" | "url" | "integer";
  required: boolean;
  secret: boolean;
  description: string;
  default: string | null;
  options?: string[] | null;
}

export interface ServerDefinition {
  id: string;
  display_name: string;
  npm_package: string;
  description: string;
  doc_url: string;
  icon: string;
  env_vars: EnvVarDef[];
  cli_args: { name: string; description: string; default: string | null; required: boolean }[];
}

export interface Manifest {
  version: string;
  generated_at: string;
  source_commit: string;
  servers: ServerDefinition[];
}

export interface ServerListItem {
  id: string;
  display_name: string;
  description: string;
  icon: string;
  enabled: boolean;
  telemetry_enabled: boolean;
  restart_policy: "always" | "on-failure" | "never";
  last_error: string | null;
  last_started_at: string | null;
  state: "running" | "starting" | "stopped" | "failed" | "disabled" | "unknown";
  pid: number | null;
  uptime_seconds: number;
}

export interface ServerDetail extends ServerListItem {
  doc_url: string;
  definition: ServerDefinition;
  config: Record<string, string | boolean | number>;
  cli_args: string[];
}

export interface LogLine {
  ts: number;
  stream: "stdout" | "stderr" | "system";
  line: string;
}

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function req<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  const res = await fetch(path, { ...init, headers, credentials: "same-origin" });
  const ct = res.headers.get("content-type") || "";
  const body = ct.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/api/auth/")) {
      window.location.href = "/login";
    }
    const detail = typeof body === "object" && body && "detail" in body ? body.detail : body;
    throw new ApiError(res.status, body, typeof detail === "string" ? detail : "request failed");
  }
  return body as T;
}

export const api = {
  login: (username: string, password: string) =>
    req<{ username: string; must_change_password: boolean }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  changePassword: (old_password: string, new_password: string) =>
    req<{ ok: true }>("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ old_password, new_password }),
    }),
  logout: () => req<{ ok: true }>("/api/auth/logout", { method: "POST" }),
  me: () => req<{ username: string; must_change_password: boolean }>("/api/auth/me"),

  systemHealth: () => req<{ status: string; db: string; mcp_proxy: string }>("/api/system/health"),
  systemInfo: () => req<{ version: string; manifest_version: string; manifest_generated_at: string; manifest_source_commit: string; server_count: number }>("/api/system/info"),

  manifest: () => req<Manifest>("/api/manifest"),
  listServers: () => req<{ servers: ServerListItem[] }>("/api/servers"),
  getServer: (id: string) => req<ServerDetail>(`/api/servers/${id}`),
  updateConfig: (id: string, body: { config: Record<string, unknown>; cli_args: string[]; telemetry_enabled: boolean; restart_policy: string }) =>
    req<{ ok: true }>(`/api/servers/${id}/config`, { method: "PUT", body: JSON.stringify(body) }),
  revealField: (id: string, fieldName: string) =>
    req<{ value: string }>(`/api/servers/${id}/config/reveal/${encodeURIComponent(fieldName)}`),
  enableServer: (id: string) => req<{ ok: true }>(`/api/servers/${id}/enable`, { method: "POST" }),
  disableServer: (id: string) => req<{ ok: true }>(`/api/servers/${id}/disable`, { method: "POST" }),
  restartServer: (id: string) => req<{ ok: true }>(`/api/servers/${id}/restart`, { method: "POST" }),
  serverStatus: (id: string) => req<{ id: string; sse_url: string; state: string; pid: number | null; uptime_seconds: number }>(`/api/servers/${id}/status`),
  recentLogs: (id: string, lines = 200) => req<{ lines: LogLine[] }>(`/api/servers/${id}/logs?lines=${lines}`),

  getToken: () => req<{ token: string; rotated_at: string }>("/api/token"),
  rotateToken: () => req<{ token: string; rotated_at: string }>("/api/token/rotate", { method: "POST" }),
};
