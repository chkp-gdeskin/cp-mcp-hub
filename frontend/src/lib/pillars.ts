/**
 * Check Point's four official solution pillars (2026 brand guidelines).
 * Each server in the manifest maps to exactly one pillar; unmapped servers
 * fall into "General".
 */
export interface Pillar {
  id: string;
  label: string;
  description: string;
}

export const PILLARS: Pillar[] = [
  {
    id: "hybrid-mesh",
    label: "Hybrid Mesh Network Security",
    description: "Network gateways, policies, logs, and inspection.",
  },
  {
    id: "workspace",
    label: "Workspace Security",
    description: "Secure access, SASE, and remote workforce.",
  },
  {
    id: "exposure",
    label: "Exposure Management",
    description: "External risk, threat intel, and reputation.",
  },
  {
    id: "ai-security",
    label: "AI Security",
    description: "AI-powered threat analysis and emulation.",
  },
  {
    id: "general",
    label: "General",
    description: "Documentation and shared tooling.",
  },
];

// Server-id → pillar-id. Update this map when new @chkp/*-mcp packages are added.
const SERVER_PILLAR: Record<string, string> = {
  // Hybrid Mesh Network Security
  "quantum-management": "hybrid-mesh",
  "management-logs": "hybrid-mesh",
  "threat-prevention": "hybrid-mesh",
  "https-inspection": "hybrid-mesh",
  "quantum-gw-cli": "hybrid-mesh",
  "quantum-gw-connection-analysis": "hybrid-mesh",
  "quantum-gaia": "hybrid-mesh",
  "spark-management": "hybrid-mesh",
  "cpinfo-analysis": "hybrid-mesh",
  "policy-insights": "hybrid-mesh",

  // Workspace Security
  "harmony-sase": "workspace",

  // Exposure Management
  "argos-erm": "exposure",
  "reputation-service": "exposure",

  // AI Security
  "threat-emulation": "ai-security",

  // General
  documentation: "general",
};

export function pillarFor(serverId: string): string {
  return SERVER_PILLAR[serverId] ?? "general";
}
