#!/usr/bin/env python3
"""Crawl CheckPointSW/mcp-servers and emit server_definitions.json.

Auto-includes any package under `packages/` whose `package.json` declares
`name: "@chkp/*-mcp"` and a non-empty `bin` field. Other dirs (shared libs
like `infra`, `mcp-utils`, `harmony-infra`, `gw-cli-base`) are skipped.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO = "CheckPointSW/mcp-servers"
BRANCH = "main"
API_BASE = f"https://api.github.com/repos/{REPO}"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"

SECRET_PATTERNS = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|PASSPHRASE)", re.I)
URL_SUFFIXES = ("_URL", "_HOST", "_ENDPOINT", "_SERVER")
INT_SUFFIXES = ("_PORT", "_TIMEOUT", "_LIMIT", "_RETRIES", "_INTERVAL")


@dataclass
class EnvVar:
    name: str
    label: str
    type: str = "string"
    required: bool = False
    secret: bool = False
    description: str = ""
    default: str | None = None


@dataclass
class CliArg:
    name: str
    description: str = ""
    default: str | None = None
    required: bool = False


@dataclass
class ServerDef:
    id: str
    display_name: str
    npm_package: str
    description: str = ""
    doc_url: str = ""
    icon: str = "shield"
    env_vars: list[EnvVar] = field(default_factory=list)
    cli_args: list[CliArg] = field(default_factory=list)


def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "cp-mcp-hub-manifest"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def http_get_json(url: str) -> object:
    return json.loads(http_get(url))


def get_source_commit() -> str:
    data = http_get_json(f"{API_BASE}/commits/{BRANCH}")
    assert isinstance(data, dict)
    return str(data["sha"])


def list_packages() -> list[str]:
    data = http_get_json(f"{API_BASE}/contents/packages?ref={BRANCH}")
    assert isinstance(data, list)
    return sorted(item["name"] for item in data if item.get("type") == "dir")


def fetch_text(pkg: str, filename: str) -> str | None:
    url = f"{RAW_BASE}/packages/{pkg}/{filename}"
    try:
        return http_get(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def npm_to_id(npm_name: str) -> str:
    # @chkp/quantum-management-mcp -> quantum-management
    bare = npm_name.split("/", 1)[-1]
    return re.sub(r"-mcp$", "", bare)


def humanize(token: str) -> str:
    return " ".join(w.capitalize() for w in re.split(r"[-_]", token) if w)


def classify_env(name: str, desc: str) -> tuple[str, bool]:
    upper = name.upper()
    if SECRET_PATTERNS.search(upper):
        return "password", True
    if any(upper.endswith(s) for s in URL_SUFFIXES):
        return "url", False
    if any(upper.endswith(s) for s in INT_SUFFIXES):
        return "integer", False
    low = desc.lower()
    if low.startswith(("enable ", "disable ", "whether ", "toggle ")) or "true/false" in low or "boolean" in low:
        return "boolean", False
    return "string", False


REQUIRED_HINT = re.compile(r"\b(required|must be set|mandatory)\b", re.I)
DEFAULT_HINT = re.compile(r"\(default:?\s*([^)]+)\)", re.I)
# Match either "- `VAR`: desc" or "`VAR`: desc" forms
ENV_LINE = re.compile(r"^\s*(?:[-*]\s+)?\**\s*`([A-Z][A-Z0-9_]{2,})`\**\s*[:\-]\s*(.+?)\s*$")
FENCE = re.compile(r"^\s*```")
# Skip these — they are documentation about telemetry/transport, not user-configurable
SKIP_NAMES = {"TELEMETRY_DISABLED", "MCP_TRANSPORT_TYPE", "MCP_TRANSPORT_PORT"}


def parse_env_vars(readme: str) -> list[EnvVar]:
    seen: dict[str, EnvVar] = {}
    in_fence = False
    for line in readme.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        em = ENV_LINE.match(line)
        if not em:
            continue
        name, desc = em.group(1), em.group(2).strip()
        if name in SKIP_NAMES or name in seen:
            continue
        # Trim trailing punctuation/markdown from description
        desc = re.sub(r"\s{2,}$", "", desc).rstrip()
        type_, secret = classify_env(name, desc)
        default_match = DEFAULT_HINT.search(desc)
        default = default_match.group(1).strip() if default_match else None
        required = bool(REQUIRED_HINT.search(desc)) and default is None
        seen[name] = EnvVar(
            name=name,
            label=humanize(name.lower()),
            type=type_,
            required=required,
            secret=secret,
            description=desc,
            default=default,
        )
    return list(seen.values())


def extract_description(readme: str) -> str:
    for block in readme.split("\n\n"):
        block = block.strip()
        if not block or block.startswith("#") or block.startswith("```") or block.startswith("!["):
            continue
        first_line = block.splitlines()[0]
        if first_line.startswith(("[", "|", "<")):
            continue
        return " ".join(block.splitlines()).strip()
    return ""


def build_server_def(pkg_dir: str) -> ServerDef | None:
    pkg_json_raw = fetch_text(pkg_dir, "package.json")
    if not pkg_json_raw:
        print(f"skip {pkg_dir}: no package.json", file=sys.stderr)
        return None
    try:
        pkg_json = json.loads(pkg_json_raw)
    except json.JSONDecodeError as exc:
        print(f"skip {pkg_dir}: bad package.json ({exc})", file=sys.stderr)
        return None
    name = pkg_json.get("name", "")
    if not re.match(r"^@chkp/.*-mcp$", name):
        print(f"skip {pkg_dir}: name={name!r} (not @chkp/*-mcp)", file=sys.stderr)
        return None
    if not pkg_json.get("bin"):
        print(f"skip {pkg_dir}: no bin field (likely shared lib)", file=sys.stderr)
        return None

    server_id = npm_to_id(name)
    readme = fetch_text(pkg_dir, "README.md") or ""
    description = extract_description(readme) or pkg_json.get("description", "")
    env_vars = parse_env_vars(readme)
    if not env_vars:
        print(f"warn {pkg_dir}: no env vars parsed from README", file=sys.stderr)

    return ServerDef(
        id=server_id,
        display_name=humanize(server_id),
        npm_package=name,
        description=description.strip(),
        doc_url=f"https://github.com/{REPO}/tree/{BRANCH}/packages/{pkg_dir}",
        env_vars=env_vars,
    )


def main(out_path: Path) -> int:
    print(f"fetching {API_BASE}/contents/packages", file=sys.stderr)
    commit = get_source_commit()
    packages = list_packages()
    print(f"found {len(packages)} package dirs", file=sys.stderr)
    servers: list[ServerDef] = []
    for pkg in packages:
        defn = build_server_def(pkg)
        if defn:
            servers.append(defn)
    servers.sort(key=lambda s: s.id)
    manifest = {
        "version": "1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_commit": commit,
        "servers": [
            {
                **asdict(s),
                "env_vars": [asdict(e) for e in s.env_vars],
                "cli_args": [asdict(a) for a in s.cli_args],
            }
            for s in servers
        ],
    }
    out_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {out_path} ({len(servers)} servers)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "server_definitions.json"
    sys.exit(main(target))
