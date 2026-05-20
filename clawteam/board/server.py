"""Lightweight HTTP server for the Web UI dashboard (stdlib only)."""

from __future__ import annotations

import ipaddress
import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from clawteam.board.collector import BoardCollector
from clawteam.paths import validate_identifier

_MAX_BODY_BYTES = 65_536  # 64 KiB — guards against unbounded memory reads
_MAX_SSE_CONNECTIONS = 64  # per-server FD limit for SSE streams

_STATIC_DIR = Path(__file__).parent / "static"
_ALLOWED_PROXY_HOSTS = {
    "api.github.com",
    "github.com",
    "raw.githubusercontent.com",
}


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects for proxied fetches."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(newurl, code, msg, headers, fp)


def _is_blocked_hostname(hostname: str) -> bool:
    host = hostname.strip().lower()
    if host in {"localhost"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
    )


def _normalize_proxy_target(target_url: str) -> str:
    parsed = urlparse(target_url)
    if parsed.scheme != "https":
        raise ValueError("Proxy only allows https URLs")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("Proxy URL must include a hostname")
    if _is_blocked_hostname(hostname):
        raise ValueError("Proxy target is not allowed")

    if hostname == "github.com":
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) == 2:
            return f"https://api.github.com/repos/{parts[0]}/{parts[1]}/readme"
        return target_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

    if hostname not in _ALLOWED_PROXY_HOSTS:
        raise ValueError("Proxy only allows GitHub-hosted content")

    return target_url


def _fetch_proxy_content(target_url: str) -> bytes:
    normalized = _normalize_proxy_target(target_url)
    opener = urllib.request.build_opener(_NoRedirectHandler)
    req = urllib.request.Request(normalized, headers={"User-Agent": "ClawTeam-Server"})
    with opener.open(req, timeout=10) as resp:
        final_url = resp.geturl()
        _normalize_proxy_target(final_url)
        body = resp.read()

    if normalized.startswith("https://api.github.com/repos/") and final_url == normalized:
        payload = json.loads(body.decode("utf-8"))
        download_url = payload.get("download_url")
        if not download_url:
            raise ValueError("GitHub README proxy target has no downloadable content")
        normalized = _normalize_proxy_target(download_url)
        req = urllib.request.Request(normalized, headers={"User-Agent": "ClawTeam-Server"})
        with opener.open(req, timeout=10) as resp:
            _normalize_proxy_target(resp.geturl())
            return resp.read()

    return body


@dataclass
class TeamSnapshotCache:
    """Tiny TTL cache for full team snapshots shared across HTTP handlers."""

    ttl_seconds: float
    _entries: dict[str, tuple[float, dict]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def get(self, team_name: str, loader) -> dict:
        with self._lock:
            entry = self._entries.get(team_name)
            if entry and time.monotonic() - entry[0] < self.ttl_seconds:
                return entry[1]

        # Load outside the lock so one slow collector run does not block all
        # other readers. Concurrent expiry can trigger duplicate refreshes, but
        # this path only rebuilds an in-memory snapshot and the latest result wins.
        data = loader()
        loaded_at = time.monotonic()
        with self._lock:
            self._entries[team_name] = (loaded_at, data)
        return data


class BoardHandler(BaseHTTPRequestHandler):
    """HTTP handler for the board Web UI."""

    collector: BoardCollector
    default_team: str = ""
    interval: float = 2.0
    team_cache: TeamSnapshotCache
    _sse_semaphore: threading.Semaphore  # set in serve()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _read_body(self) -> bytes | None:
        """Read the request body, capped at _MAX_BODY_BYTES.

        Returns None and sends a 413 response when the declared or actual
        body size would exceed the cap.
        """
        try:
            declared = int(self.headers.get("Content-Length", 0))
        except ValueError:
            declared = 0
        if declared > _MAX_BODY_BYTES:
            self.send_error(413, "Request body too large")
            return None
        return self.rfile.read(min(declared, _MAX_BODY_BYTES))

    def _resolve_team(self, raw: str) -> str | None:
        """Validate and return the team name, or send 400 and return None."""
        name = raw.strip("/")
        if not name:
            self.send_error(400, "Team name required")
            return None
        try:
            validate_identifier(name, "team name")
        except ValueError as exc:
            self.send_error(400, str(exc))
            return None
        return name

    # ------------------------------------------------------------------
    # Request handlers
    # ------------------------------------------------------------------

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/" or path == "/index.html":
            self._serve_static("index.html", "text/html")
        elif path == "/api/overview":
            self._serve_json(self.collector.collect_overview())
        elif path.startswith("/api/team/"):
            team_name = self._resolve_team(path[len("/api/team/"):])
            if team_name is None:
                return
            self._serve_team(team_name)
        elif path.startswith("/api/events/"):
            team_name = self._resolve_team(path[len("/api/events/"):])
            if team_name is None:
                return
            self._serve_sse(team_name)
        elif path.startswith("/api/proxy"):
            from urllib.parse import parse_qs, urlparse
            query = parse_qs(urlparse(self.path).query)
            target_url = query.get("url", [""])[0]
            if not target_url:
                self.send_error(400, "URL required")
                return
            try:
                content = _fetch_proxy_content(target_url)
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_error(500, str(e))
        elif path.startswith("/assets/"):
            # Serve Vite-built JS/CSS assets
            asset_path = path[1:]  # strip leading /
            content_types = {
                ".js": "application/javascript",
                ".css": "text/css",
                ".map": "application/json",
                ".woff2": "font/woff2",
                ".woff": "font/woff",
                ".svg": "image/svg+xml",
            }
            ext = "." + asset_path.rsplit(".", 1)[-1] if "." in asset_path else ""
            ct = content_types.get(ext, "application/octet-stream")
            self._serve_static(asset_path, ct)
        else:
            self.send_error(404)

    def do_POST(self):
        path = self.path.split("?")[0]
        if path.startswith("/api/team/") and path.endswith("/task"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[3] == "task":
                team_name = self._resolve_team(parts[2])
                if team_name is None:
                    return
                raw = self._read_body()
                if raw is None:
                    return
                try:
                    payload = json.loads(raw)
                    from clawteam.team.tasks import TaskStore
                    from clawteam.team.models import TaskPriority
                    store = TaskStore(team_name)
                    priority_val = payload.get("priority")
                    task = store.create(
                        subject=payload.get("subject", ""),
                        description=payload.get("description", ""),
                        owner=payload.get("owner", ""),
                        priority=TaskPriority(priority_val) if priority_val else None,
                    )
                    self._serve_json({"status": "ok", "task_id": task.id})
                except Exception as e:
                    self.send_error(400, str(e))
                return
        # POST /api/team/<name>/member — add agent to team
        if path.startswith("/api/team/") and path.endswith("/member"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[3] == "member":
                team_name = self._resolve_team(parts[2])
                if team_name is None:
                    return
                raw = self._read_body()
                if raw is None:
                    return
                try:
                    payload = json.loads(raw)
                    from clawteam.team.manager import TeamManager
                    name = payload.get("name", "")
                    agent_type = payload.get("agentType", "general-purpose")
                    if not name:
                        self.send_error(400, "name is required")
                        return
                    TeamManager.add_member(team_name, name, agent_type=agent_type)
                    self._serve_json({"status": "ok", "name": name})
                except Exception as e:
                    self.send_error(400, str(e))
                return

        # POST /api/team/<name>/message — send message to agent inbox
        if path.startswith("/api/team/") and path.endswith("/message"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[3] == "message":
                team_name = self._resolve_team(parts[2])
                if team_name is None:
                    return
                raw = self._read_body()
                if raw is None:
                    return
                try:
                    payload = json.loads(raw)
                    from clawteam.team.mailbox import MailboxManager
                    mailbox = MailboxManager(team_name)
                    mailbox.send(
                        from_agent="board-ui",
                        to=payload.get("to", ""),
                        msg_type=payload.get("type", "message"),
                        content=payload.get("content", ""),
                        summary=payload.get("summary", ""),
                    )
                    self._serve_json({"status": "ok"})
                except Exception as e:
                    self.send_error(400, str(e))
                return

        self.send_error(404)

    def do_PATCH(self):
        path = self.path.split("?")[0]
        # PATCH /api/team/<name>/task/<id>
        parts = path.strip("/").split("/")
        if len(parts) == 5 and parts[0] == "api" and parts[1] == "team" and parts[3] == "task":
            team_name = self._resolve_team(parts[2])
            if team_name is None:
                return
            task_id = parts[4]
            raw = self._read_body()
            if raw is None:
                return
            try:
                payload = json.loads(raw)
                from clawteam.team.tasks import TaskStore
                from clawteam.team.models import TaskStatus, TaskPriority
                store = TaskStore(team_name)
                kwargs = {}
                if "status" in payload:
                    kwargs["status"] = TaskStatus(payload["status"])
                if "owner" in payload:
                    kwargs["owner"] = payload["owner"]
                if "subject" in payload:
                    kwargs["subject"] = payload["subject"]
                if "description" in payload:
                    kwargs["description"] = payload["description"]
                if "priority" in payload:
                    kwargs["priority"] = TaskPriority(payload["priority"])
                kwargs["force"] = True
                store.update(task_id, **kwargs)
                self._serve_json({"status": "ok", "task_id": task_id})
            except Exception as e:
                self.send_error(400, str(e))
            return
        self.send_error(404)

    def do_OPTIONS(self):
        """Handle CORS preflight for PATCH requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _serve_static(self, filename: str, content_type: str):
        filepath = _STATIC_DIR / filename
        if not filepath.exists():
            self.send_error(404, f"Static file not found: {filename}")
            return
        content = filepath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _serve_team(self, team_name: str):
        try:
            data = self.collector.collect_team(team_name)
            self._serve_json(data)
        except ValueError as e:
            body = json.dumps({"error": str(e)}).encode("utf-8")
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def _serve_sse(self, team_name: str):
        if not self.server._sse_semaphore.acquire(blocking=False):
            self.send_error(503, "Too many SSE connections")
            return
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                while True:
                    try:
                        data = self.team_cache.get(
                            team_name,
                            lambda: self.collector.collect_team(team_name),
                        )
                    except ValueError as e:
                        data = {"error": str(e)}
                    payload = json.dumps(data, ensure_ascii=False)
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    time.sleep(self.interval)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
        finally:
            self.server._sse_semaphore.release()

    def log_message(self, format, *args):
        # Suppress default stderr logging for SSE connections
        first = str(args[0]) if args else ""
        if "/api/events/" not in first:
            super().log_message(format, *args)


def serve(
    host: str = "127.0.0.1",
    port: int = 8080,
    default_team: str = "",
    interval: float = 2.0,
    max_sse_connections: int = _MAX_SSE_CONNECTIONS,
):
    """Start the Web UI server."""
    collector = BoardCollector()
    BoardHandler.collector = collector
    BoardHandler.default_team = default_team
    BoardHandler.interval = interval
    BoardHandler.team_cache = TeamSnapshotCache(ttl_seconds=interval)

    server = ThreadingHTTPServer((host, port), BoardHandler)
    server._sse_semaphore = threading.Semaphore(max_sse_connections)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
