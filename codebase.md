<!-- refreshed: 2026-04-28 -->
# Architecture

**Analysis Date:** 2026-04-28

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                                Entry Surfaces                                │
├─────────────────────────┬───────────────────────────┬────────────────────────┤
│   Typer CLI             │   FastMCP server          │   Browser dashboard    │
│  `clawteam.cli`         │  `clawteam.mcp`           │  React + Vite SPA      │
│   (`clawteam` script)   │  (`clawteam-mcp` script)  │  served by board HTTP  │
└────────────┬────────────┴─────────────┬─────────────┴───────────┬────────────┘
             │                          │                         │
             │                          ▼                         ▼
             │         ┌────────────────────────────┐   ┌──────────────────────────┐
             │         │  MCP tool surface          │   │  HTTP + SSE board server │
             │         │  `clawteam/mcp/tools/`     │   │  `clawteam/board/`       │
             │         └─────────────┬──────────────┘   └────────────┬─────────────┘
             │                       │                               │
             ▼                       ▼                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        Coordination Core (in-process)                        │
│                                                                              │
│   Team / Mailbox     Tasks         Lifecycle / Plan       Routing            │
│  `clawteam.team.*`   `store.*`     `team.lifecycle`       `team.router`      │
│                                    `team.plan`            `team.routing_policy`│
│                                                                              │
│   Workspace (git worktrees)        Harness orchestrator                      │
│  `clawteam.workspace.*`            `clawteam.harness.*`                      │
│                                                                              │
│   Identity            Plugin manager        Event bus + hooks                │
│  `clawteam.identity`  `clawteam.plugins.*`  `clawteam.events.*`              │
└─────────┬───────────────────┬───────────────────┬────────────────────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────────────┐
│ Spawn backends     │  │ Transport backends │  │ Persistence (filesystem)   │
│ `clawteam.spawn.*` │  │ `clawteam.transport.*` │ data dir resolved by       │
│  tmux / subprocess │  │  file (default)    │  │ `team.models.get_data_dir` │
│  / wsh             │  │  / p2p (ZMQ)       │  │  ~/.clawteam or            │
│                    │  │                    │  │  walk-up `.clawteam/`      │
└─────────┬──────────┘  └─────────┬──────────┘  └────────────┬───────────────┘
          │                       │                          │
          ▼                       ▼                          ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ External processes                                                           │
│   tmux session `clawteam-{team}` with one window per agent (CLI in pane)     │
│   Native subprocesses (claude / codex / gemini / kimi / qwen / opencode /    │
│     openclaw / pi / nanobot)                                                 │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Typer CLI app | All user-facing commands grouped into sub-apps (config, profile, preset, team, inbox, runtime, task, cost, session, plan, lifecycle, identity, board, workspace, context, template, hook, plugin, harness) plus top-level `spawn`, `launch`, `run`. | `clawteam/cli/commands.py` |
| FastMCP server | Wraps a flat list of Python tool callables (`TOOL_FUNCTIONS`) as MCP tools and runs over stdio. | `clawteam/mcp/server.py` |
| MCP tool surface | Thin façade over team / task / mailbox / plan / board / cost / workspace operations; converts Python errors to `MCPToolError`. | `clawteam/mcp/tools/`, `clawteam/mcp/helpers.py` |
| Board HTTP/SSE server | stdlib `ThreadingHTTPServer` exposing `/api/overview`, `/api/team/{name}`, `/api/events/{name}` (SSE), `POST/PATCH` task & member & message endpoints, `/api/proxy` (allow-listed), and Vite-built static assets. | `clawteam/board/server.py` |
| Board collector | Aggregates `TeamConfig` + tasks + inbox counts + event log + costs + workspace overlaps into a single JSON snapshot for the dashboard. | `clawteam/board/collector.py` |
| Tmux liveness | Detects which member windows currently exist in the tmux session. | `clawteam/board/liveness.py` |
| React dashboard | SPA shell (`App.tsx`) plus topbar (team selector + SSE indicator), summary bar, kanban board, message stream, agent registry, peek panel, and modal dialogs (inject task / set context / add agent / send message). | `clawteam/board/frontend/src/` |
| Identity | Builds `AgentIdentity` from `CLAWTEAM_*` / `CLAUDE_CODE_*` env vars and round-trips them to spawned children. | `clawteam/identity.py` |
| Config | Loads `~/.clawteam/config.json` (always at the home location, ignoring `data_dir`) into the `ClawTeamConfig` Pydantic model. | `clawteam/config.py` |
| Paths | Identifier validation (`[A-Za-z0-9._-]+`) and `ensure_within_root` to prevent path escapes outside the data dir. | `clawteam/paths.py` |
| Team manager | Create / discover / inspect / cleanup teams; persists `config.json` per team and computes inbox names (`user_name` or `name`). | `clawteam/team/manager.py` |
| Mailbox | Sends, broadcasts, peeks, and receives `TeamMessage` JSON via the active `Transport`; mirrors every send into a per-team append-only `events/` log. | `clawteam/team/mailbox.py` |
| Task store (file backend) | Per-task JSON files under `tasks/{team}/`, guarded by an OS advisory lock on `.tasks.lock`; exposes `BaseTaskStore` interface. | `clawteam/store/file.py`, `clawteam/store/base.py` |
| Plan / Lifecycle / Costs | Plan submit/approve/reject flow; shutdown protocol; cost ledger. | `clawteam/team/plan.py`, `clawteam/team/lifecycle.py`, `clawteam/team/costs.py` |
| Routing policy + router | Normalizes inbox messages into `RuntimeEnvelope`s, asks the policy whether to inject, then dispatches via the tmux backend's `inject_runtime_message`. | `clawteam/team/routing_policy.py`, `clawteam/team/router.py` |
| Inbox watcher | Foreground polling loop that consumes the leader inbox and (optionally) hands messages to a `RuntimeRouter` for tmux injection. | `clawteam/team/watcher.py` |
| Spawn backends | Three concrete `SpawnBackend`s (tmux / subprocess / wsh) selected by `get_backend(name)`; record their results in the spawn registry. | `clawteam/spawn/__init__.py`, `clawteam/spawn/tmux_backend.py`, `clawteam/spawn/subprocess_backend.py`, `clawteam/spawn/wsh_backend.py` |
| Spawn registry | JSON file `teams/{team}/spawn_registry.json` mapping agent name → `{backend, tmux_target, pid, command, spawned_at}` for liveness / shutdown. | `clawteam/spawn/registry.py` |
| Native CLI adapter | Per-CLI command shaping (claude, codex, gemini, kimi, qwen, opencode, openclaw, pi, nanobot): permission flags, workspace flags, prompt placement, post-launch injection. | `clawteam/spawn/adapters.py` |
| Transport (file) | Inbox directory per recipient with msg-{ts}-{uuid}.json files; advisory locks for atomic claim. | `clawteam/transport/file.py`, `clawteam/transport/claimed.py` |
| Transport (p2p) | Optional ZeroMQ PUSH/PULL transport with file-transport fallback when peers are offline (requires `pip install clawteam[p2p]`). | `clawteam/transport/p2p.py` |
| Workspace manager | Provisions per-agent git worktrees, tracks them in a registry, supports checkpoint / merge / cleanup. | `clawteam/workspace/manager.py`, `clawteam/workspace/git.py`, `clawteam/workspace/conflicts.py`, `clawteam/workspace/context.py` |
| Harness orchestrator | Persisted phase state machine (`discuss → plan → execute → verify → ship`) with pluggable `PhaseGate`s and a default `HarnessConductor` polling loop. | `clawteam/harness/orchestrator.py`, `clawteam/harness/phases.py`, `clawteam/harness/conductor.py`, `clawteam/harness/spawner.py` |
| Event bus + hooks | In-process pub/sub (sync `emit` + `emit_async` via small thread pool) with shell- or Python-callable hooks loaded from config. | `clawteam/events/bus.py`, `clawteam/events/global_bus.py`, `clawteam/events/hooks.py`, `clawteam/events/types.py` |
| Plugin manager | Discovers / loads `HarnessPlugin` subclasses from entry points, config, or `{data_dir}/plugins/`; passes a `HarnessContext` capability bundle. | `clawteam/plugins/manager.py`, `clawteam/plugins/base.py`, `clawteam/harness/context.py`, `clawteam/plugins/ralph_loop_plugin.py` |
| Templates | Bundled team blueprints (`harness-default.toml`, `software-dev.toml`, etc.) consumed by `clawteam launch`. | `clawteam/templates/` |
| File util | Atomic writes (`atomic_write_text`) and cross-platform advisory file locks (`file_locked`) used by every persistent store. | `clawteam/fileutil.py` |

## Pattern Overview

**Overall:** Local-first, filesystem-backed multi-agent control plane with pluggable spawn / transport / store backends and an in-process event bus. There is no daemon — the CLI is the orchestrator, and every command operates against shared on-disk state.

**Key Characteristics:**
- A single Python package (`clawteam`) exposes both the CLI (`clawteam` script) and the FastMCP server (`clawteam-mcp` script) defined in `pyproject.toml`.
- Every persistent operation routes through `clawteam.team.models.get_data_dir()`, which prefers `CLAWTEAM_DATA_DIR`, then `config.data_dir`, then walks up from the current working directory looking for `.clawteam/`, then falls back to `~/.clawteam/`. This is what makes data project-local.
- Strict layering: CLI / MCP / board never talk to spawn or transport directly without going through the team / store façade (see `MailboxManager.send` → `Transport.deliver`, `BoardCollector` → `TaskStore` + `MailboxManager`).
- Backend selection is by name through factory functions (`spawn.get_backend`, `transport.get_transport`, `store.get_task_store`); plugins can register additional implementations via `register_backend` / `register_transport`.
- Tmux is treated as a first-class runtime: each agent gets a window in `clawteam-{team}`, lifecycle is wired through `tmux set-hook pane-exited|pane-died` to `clawteam lifecycle on-exit|on-crash`, and runtime injection uses a hardened `load-buffer`/`paste-buffer`/`send-keys` flow with a foreground-command allowlist.
- Three-tier liveness:
  1. **SSE liveness** — `useTeamStream` toggles `isConnected` from `EventSource.onopen / onerror`; rendered as the topbar "Stream live/offline" pill (`clawteam/board/frontend/src/components/topbar.tsx`).
  2. **Tmux window liveness** — `board.liveness.agents_online` checks whether a window with the agent's name still exists in `clawteam-{team}`; rendered per-agent in `agent-registry.tsx` and aggregated as `membersOnline` in the team header.
  3. **Pane process liveness** — `spawn.registry.is_agent_alive` consults the registry, then `_tmux_pane_alive` (checks `#{pane_dead}` and rejects bare shells) with a PID fallback for subprocess agents.

## Layers

**Entry surface (CLI / MCP / Board HTTP):**
- Purpose: Translate external input into coordination-core calls.
- Location: `clawteam/cli/commands.py`, `clawteam/mcp/server.py`, `clawteam/board/server.py`, `clawteam/__main__.py`, `clawteam/mcp/__main__.py`.
- Contains: Typer apps, FastMCP wiring, HTTP request handler, SSE loop.
- Depends on: Coordination core (team / store / spawn / harness), config, identity.
- Used by: Humans (CLI / browser) and AI clients (MCP).

**Coordination core (team + store + workspace + harness):**
- Purpose: Express the domain model: teams, members, tasks, plans, mailboxes, harness phases, costs, workspaces.
- Location: `clawteam/team/`, `clawteam/store/`, `clawteam/workspace/`, `clawteam/harness/`, `clawteam/identity.py`.
- Contains: Pydantic models, managers, gates, lifecycle helpers, conductor.
- Depends on: Spawn (to run agents), transport (to deliver messages), events (to notify), file util (to persist).
- Used by: CLI, MCP, board.

**Runtime layer (spawn + transport + events + plugins):**
- Purpose: Concrete process / message / extension mechanisms.
- Location: `clawteam/spawn/`, `clawteam/transport/`, `clawteam/events/`, `clawteam/plugins/`.
- Contains: Backend implementations, registry, `EventBus`, `HookManager`, `PluginManager`.
- Depends on: file util, paths, config; nothing from CLI/MCP/board.
- Used by: Coordination core.

**Persistence (filesystem):**
- Purpose: All durable state.
- Location: data dir resolved by `get_data_dir()`. Directory layout (relative to data dir):
  ```
  teams/{team}/config.json
  teams/{team}/inboxes/{inbox}/msg-*.json
  teams/{team}/events/evt-*.json
  teams/{team}/spawn_registry.json
  teams/{team}/runtime_state.json
  teams/{team}/peers/{agent}.json   (p2p only)
  tasks/{team}/task-{id}.json + .tasks.lock
  costs/{team}/...
  sessions/{team}/...
  workspaces/{team}/{agent}/        (git worktree path)
  workspaces/{team}/workspace-registry.json
  harness/{team}/{harness_id}/state.json
  plugins/{name}/plugin.json
  ```
- Used by: Every store-aware module.

## Data Flow

### `clawteam team start <team>` (the live coordination loop)

1. `team_start` (`clawteam/cli/commands.py:1199`) loads `TeamConfig` via `TeamManager.get_team` and resolves the spawn backend (`clawteam/spawn/__init__.py:get_backend`).
2. For each `TeamMember`, builds the prompt with `clawteam/spawn/prompt.py:build_agent_prompt` and calls `TmuxBackend.spawn` (`clawteam/spawn/tmux_backend.py:45`).
3. `TmuxBackend.spawn` sets `CLAWTEAM_*` env vars, invokes `NativeCliAdapter.prepare_command` (`clawteam/spawn/adapters.py`), exports shell-safe env into the tmux command line, creates / extends the `clawteam-{team}` session with one window per agent, attaches `pane-exited` / `pane-died` hooks, waits for the pane and TUI to be ready, and either (a) injects the prompt via the hardened `load-buffer`/`paste-buffer`/`send-keys` path or (b) uses `tmux send-keys` directly for non-claude TUIs.
4. Pane id (`#{pane_id}`) and pane PID are captured and persisted by `clawteam/spawn/registry.py:register_agent`.
5. `AfterWorkerSpawn` is emitted async on the global `EventBus` (`clawteam/events/global_bus.py`).
6. When `--watcher` is set (default), a detached `python -m clawteam runtime watch <team> --agent <leader>` process is started; it runs `InboxWatcher` (`clawteam/team/watcher.py`) bound to a `RuntimeRouter` (`clawteam/team/router.py`), which normalizes each new mailbox message into a `RuntimeEnvelope`, asks `DefaultRoutingPolicy` (`clawteam/team/routing_policy.py`) whether to dispatch, and if so calls `TmuxBackend.inject_runtime_message`.

### Runtime injection into a live pane (post-spawn)

1. `TmuxBackend.inject_runtime_message` (`clawteam/spawn/tmux_backend.py:293`) resolves the recorded `pane_id` (falling back to `clawteam-{team}:{agent}`).
2. `_pane_safe_to_inject` (`clawteam/spawn/tmux_backend.py:672`) reads `#{pane_current_command}` and refuses unless it matches the allowlist `{claude, codex, gemini, kimi, qwen, opencode, nanobot, openclaw, pi, node, python, python3}` — preventing shell or sub-TUI execution of pasted content.
3. `_inject_prompt_via_buffer` (`clawteam/spawn/tmux_backend.py:701`) writes the rendered notification to a temp file, calls `_run_tmux(["load-buffer", "-b", "prompt-{agent}-{uuid8}", tmp])`, then `paste-buffer`, then two `Enter` send-keys, then `delete-buffer`. Every call goes through `_run_tmux` (`tmux_backend.py:685`), which raises on non-zero exit so failures aren't silently masked.

### Mailbox send

1. `MailboxManager.send` (`clawteam/team/mailbox.py:72`) resolves the recipient inbox via `TeamManager.resolve_inbox` (handles `user_name` namespacing).
2. Builds a `TeamMessage`, calls `Transport.deliver` (file transport writes `{data_dir}/teams/{team}/inboxes/{inbox}/msg-*.json` atomically; p2p attempts ZMQ PUSH and falls back to file).
3. Mirrors the message into the per-team event log (`teams/{team}/events/evt-*.json`).
4. Emits `BeforeInboxSend` async on the bus.

### Board snapshot fetch (SSE)

1. Browser opens `EventSource('/api/events/{team}')` (`clawteam/board/frontend/src/hooks/use-team-stream.ts`).
2. `BoardHandler._serve_sse` (`clawteam/board/server.py:324`) loops every `interval` seconds, asks `TeamSnapshotCache.get` for a fresh snapshot (TTL = `interval`), and writes `data: {json}\n\n`.
3. The cache loader runs `BoardCollector.collect_team` (`clawteam/board/collector.py:68`), which gathers `TeamConfig`, per-member inbox counts, tasks grouped by status, last 200 event-log messages, cost summary, and workspace overlap data, plus a tmux-window-derived `isRunning` flag per member.

### Harness conductor loop

1. `HarnessConductor.run` (`clawteam/harness/conductor.py:83`) spawns the role agents for the current phase via `PhaseRoleSpawner` (`clawteam/harness/spawner.py`).
2. Each iteration: drains the `FileExitJournal`, calls `HarnessOrchestrator.advance` (which checks `PhaseGate`s and emits `PhaseTransition`), and on `execute` runs `ContractExecutor` to materialize tasks from sprint contracts.
3. Periodic `RegistryHealthCheck.check` calls `clawteam/spawn/registry.py:list_dead_agents` and prints health issues.

**State Management:**
- All durable state is JSON on disk. The only in-process state is the `EventBus` singleton (`events/global_bus.py`) and per-process spawn-backend instance dictionaries (e.g. `TmuxBackend._agents`).
- The board uses a tiny per-handler `TeamSnapshotCache` (TTL = SSE poll interval) so concurrent SSE clients share one collector pass.

## Key Abstractions

**`SpawnBackend` (`clawteam/spawn/base.py`):**
- Purpose: Polymorphic interface for "launch an agent process and report a status string."
- Implementations: `TmuxBackend`, `SubprocessBackend`, `WshBackend`. Plugins can register more via `register_backend(name, cls)`.
- Pattern: Abstract base class + `get_backend(name)` factory.

**`Transport` (`clawteam/transport/base.py`):**
- Purpose: Move opaque message bytes between agents; higher layers (`MailboxManager`) own JSON parsing and quarantine decisions.
- Implementations: `FileTransport` (default, supports claimed reads), `P2PTransport` (ZMQ PUSH/PULL with file fallback).
- Pattern: ABC + `get_transport(name, team_name, **kwargs)` factory; transports may optionally expose `claim_messages` for at-least-once semantics.

**`BaseTaskStore` (`clawteam/store/base.py`):**
- Purpose: Pluggable task persistence with concurrency guarantees owned by the implementation.
- Implementations: `FileTaskStore` (one JSON per task, fcntl/msvcrt locks). `clawteam/team/tasks.py` re-exports it as `TaskStore` for back-compat.
- Pattern: ABC + `get_task_store(team_name, backend)` factory keyed by `CLAWTEAM_TASK_STORE` / config.

**`PhaseGate` (`clawteam/harness/phases.py`):**
- Purpose: Open extension point for "is this phase allowed to advance?"
- Implementations: `ArtifactRequiredGate`, `AllTasksCompleteGate`, `HumanApprovalGate`. Plugins contribute extra gates via `HarnessPlugin.contribute_gates`.
- Pattern: ABC; gates are appended per phase on a `PhaseRunner`.

**`HarnessPlugin` + `HarnessContext` (`clawteam/plugins/base.py`, `clawteam/harness/context.py`):**
- Purpose: Capability-bundle for extensions — plugins receive an `EventBus`, `team_name`, lazy `TaskStore` / `SessionStore` / `ArtifactStore`, and `ClawTeamConfig` instead of being limited to event listening.
- Examples: `clawteam/plugins/ralph_loop_plugin.py`.

**`AgentIdentity` (`clawteam/identity.py`):**
- Purpose: Single source of truth for "who am I" inside a spawned agent. Reads `CLAWTEAM_*` then falls back to `CLAUDE_CODE_*` for compatibility, and round-trips itself into child env via `to_env()`.

**`RuntimeEnvelope` / `RouteDecision` (`clawteam/team/routing_policy.py`):**
- Purpose: Decouple "what arrived in an inbox" from "should we paste it into someone's tmux pane and how." Carries source / target / channel / priority / summary / evidence and a dedupe key.

## Entry Points

**`clawteam` console script (`pyproject.toml` → `clawteam.cli.commands:app`):**
- Location: `clawteam/cli/commands.py`.
- Triggers: `clawteam ...` shell invocation, also `python -m clawteam` (`clawteam/__main__.py`).
- Responsibilities: Parses CLI options, normalizes `--data-dir` into `CLAWTEAM_DATA_DIR`, dispatches to ~20 Typer sub-apps and a handful of top-level commands (`spawn`, `launch`, `run`).

**`clawteam-mcp` console script (`pyproject.toml` → `clawteam.mcp.server:main`):**
- Location: `clawteam/mcp/server.py`, also `python -m clawteam.mcp` (`clawteam/mcp/__main__.py`).
- Triggers: An MCP host launches the server over stdio.
- Responsibilities: Wraps each `TOOL_FUNCTIONS` callable with `translate_error` and registers it through `FastMCP("clawteam").tool()`.

**`clawteam board serve` (`clawteam/cli/commands.py:3510` → `clawteam/board/server.py:serve`):**
- Triggers: User runs `clawteam board serve [--host ... --port ... --interval ...]`.
- Responsibilities: Starts a stdlib `ThreadingHTTPServer` on `127.0.0.1:8080` by default, serves the React build from `clawteam/board/static/`, plus REST + SSE APIs.

**Tmux pane hooks (`clawteam/spawn/tmux_backend.py:158`–`167`):**
- Triggers: tmux fires `pane-exited` / `pane-died` for each spawned pane.
- Responsibilities: Invoke `clawteam lifecycle on-exit|on-crash --team --agent`, which in turn updates the spawn registry, releases task locks, and notifies the leader.

**Inbox watcher (`clawteam runtime watch`, `clawteam/cli/commands.py:2084` → `clawteam/team/watcher.py`):**
- Triggers: Detached child started by `team start --watcher` (default), or run manually.
- Responsibilities: Polls leader inbox, prints / forwards messages, optionally injects them into the tmux leader pane via `RuntimeRouter`.

## Architectural Constraints

- **Threading:** Predominantly single-threaded. The board uses `ThreadingHTTPServer` (one thread per HTTP request, including long-lived SSE connections). The event bus owns a 2-worker `ThreadPoolExecutor` for `emit_async` only (`clawteam/events/bus.py:106`). Spawn backends, store, and transport are synchronous.
- **Global state:** Only one durable singleton: the `EventBus` from `clawteam/events/global_bus.py`. Spawn backends keep per-instance dictionaries (`TmuxBackend._agents`) but the CLI creates one per command invocation, so cross-command state always goes through the on-disk spawn registry. `BoardHandler` carries class-level `collector` / `team_cache` set at server startup.
- **Concurrency model:** Coordination across processes happens through the filesystem. `clawteam/store/file.py` and `clawteam/transport/file.py` use OS advisory locks (`fcntl.flock` on POSIX, `msvcrt.locking` on Windows) and `clawteam/fileutil.py:atomic_write_text` for tmp+rename writes.
- **Path safety:** Every directory derived from user input must go through `paths.ensure_within_root(root, *parts)` — refusing to escape the data dir — and through `paths.validate_identifier(value, kind)` with the regex `[A-Za-z0-9._-]+`.
- **Data-dir resolution:** All on-disk reads/writes go through `clawteam/team/models.py:get_data_dir`. Anything that hardcodes `~/.clawteam` or builds a path without it breaks the project-local walk-up.
- **Config location:** `clawteam/config.py:config_path` is hardwired to `~/.clawteam/config.json` and is intentionally NOT affected by `data_dir` overrides — config is global, data is per-project.
- **Backend availability:** `TmuxBackend` returns `"Error: tmux not installed"` instead of raising when `tmux` is missing. `WshBackend` requires `wsh` to be on PATH or in known TideTerm/WaveTerm locations. `P2PTransport` needs the `[p2p]` extra (`pyzmq`).
- **MCP errors:** All MCP tool exceptions must surface as `MCPToolError`; that's enforced by the `_tool` decorator wrapping every callable in `clawteam/mcp/server.py:16` with `translate_error`.

## Anti-Patterns

### Bypassing `get_data_dir()` for filesystem paths

**What happens:** Code constructs `Path.home() / ".clawteam"` directly instead of calling `get_data_dir()`.
**Why it's wrong:** Breaks the project-local data dir feature — the user runs `clawteam team start ...` inside a repo that has `.clawteam/`, but the new code reads/writes `~/.clawteam/` instead. Also breaks every test that overrides `CLAWTEAM_DATA_DIR`.
**Do this instead:** `from clawteam.team.models import get_data_dir; data = get_data_dir() / "teams" / team_name` — and route through `paths.ensure_within_root` if any segment came from user input. Reference: `clawteam/team/manager.py:_team_dir` and `clawteam/store/file.py:_tasks_root`.

### Calling `subprocess.run(["tmux", ...])` without checking the return code

**What happens:** Code pastes prompt content via tmux but ignores `result.returncode` (or never reads `stderr`), so a failed `load-buffer` looks like success and the pane silently never gets the message.
**Why it's wrong:** Silently masks paste-buffer / load-buffer / send-keys failures and leaves orphan paste buffers behind. This is the bug class fixed by commits `efc5f9c` (unique paste buffers + return-code checks) and `1c9a422` (pane_id targeting).
**Do this instead:** Use `_run_tmux` from `clawteam/spawn/tmux_backend.py:685` for any tmux mutation. For injection, go through `_inject_prompt_via_buffer` (`tmux_backend.py:701`) which uses a unique `prompt-{agent}-{uuid8}` buffer name and cleans up.

### Injecting into a tmux pane without checking the foreground command

**What happens:** Code pastes a prompt directly into a pane that is currently running `bash` / `vim` / `less` / `fzf` / a sub-TUI.
**Why it's wrong:** Shells will execute the pasted content (including `$()` and backticks) and TUIs will misinterpret it. This is exactly the bug class fixed by commit `00a094d`.
**Do this instead:** Always gate injection on `_pane_safe_to_inject(target)` (`clawteam/spawn/tmux_backend.py:672`), which reads `#{pane_current_command}` and only allows the agent-CLI allowlist `_INJECT_SAFE_COMMANDS`.

### Targeting a tmux pane by `session:window_name` instead of `pane_id`

**What happens:** Code re-resolves the target as `clawteam-{team}:{agent_name}` every time it wants to inject.
**Why it's wrong:** Window names can be renamed by the user or shifted by `tile_panes` operations; pane ids (`%42`) are stable for the life of the pane. Fixed in commit `1c9a422`.
**Do this instead:** `TmuxBackend.spawn` captures `#{pane_id}` after the pane appears (`tmux_backend.py:230`) and `inject_runtime_message` reads it back from `self._agents` first, only falling back to the window-name target if no pane id is recorded.

### Letting an MCP tool raise a non-`MCPToolError`

**What happens:** A new MCP tool raises `RuntimeError` / a domain exception directly.
**Why it's wrong:** MCP clients see an opaque "Unexpected error" instead of the structured message; the error envelope contract breaks.
**Do this instead:** Either raise `MCPToolError("...")` (or call `mcp.helpers.fail(...)`), or rely on the `_tool` wrapper plus `translate_error` in `clawteam/mcp/server.py:16` and `clawteam/mcp/helpers.py:25` — but only if the underlying exception is `ValueError` / `RuntimeError` / `TaskLockError`.

### Reading inbox JSON and silently dropping malformed messages without acking

**What happens:** A new transport's `fetch` returns parsed dicts (or skips bytes that don't validate) and never tells the mailbox.
**Why it's wrong:** `MailboxManager` owns parsing and quarantine policy; transports should only return raw bytes (or `ClaimedMessage`s). Without that split, malformed messages either get silently lost or stay in the inbox forever.
**Do this instead:** Implement `Transport.fetch` to return `list[bytes]` (and optionally `claim_messages` for at-least-once). `MailboxManager._parse_claimed_messages` (`clawteam/team/mailbox.py:174`) handles `ack()` vs `quarantine(reason)`.

## Error Handling

**Strategy:** Domain-specific exceptions raised low and translated at the boundary.

**Patterns:**
- `paths.validate_identifier` raises `ValueError` for any unsafe identifier; `paths.ensure_within_root` raises `ValueError("Resolved path escapes the configured data directory")`.
- `store.base.TaskLockError` is raised when an update would conflict with another agent's lock; CLI surfaces it as a non-zero exit, MCP surfaces it through `MCPToolError`.
- Spawn backends return `"Error: ..."` strings from `spawn(...)` instead of raising, so the CLI can pipe them straight to the user without a stack trace.
- The board server returns proper HTTP status codes (`400` for malformed requests, `403` for denied proxy targets, `404` for unknown teams, `500` only for unexpected proxy failures).
- `EventBus.emit` swallows handler exceptions (`events/bus.py:99`) so a buggy hook can't crash the orchestrator; failures are silent — instrument the hook itself if you need observability.
- `_load_hooks_from_config` and most plugin discovery sites wrap import / parse failures in bare `except Exception: pass` — the system stays usable when config is missing or malformed.

## Cross-Cutting Concerns

**Logging:** Almost all user-facing output goes through `rich.console.Console` in the CLI; the board server uses stdlib `BaseHTTPRequestHandler.log_message` (suppressed for SSE). The harness conductor prints to `sys.stderr`. Only `clawteam/workspace/manager.py` uses `logging.getLogger`. There is no structured/JSON logging framework.

**Validation:** Pydantic v2 models (`TeamConfig`, `TeamMember`, `TeamMessage`, `TaskItem`, `WorkspaceInfo`, `PhaseState`, `ClawTeamConfig`, `AgentProfile`, `AgentPreset`, `HookDef`) own field validation. Identifier validation uses the `_IDENTIFIER_RE` from `paths.py`.

**Authentication / authorization:** None internally — this is a local developer tool. The board server only binds `127.0.0.1` by default and the `/api/proxy` endpoint enforces an HTTPS-only allowlist (`api.github.com`, `github.com`, `raw.githubusercontent.com`) plus rejection of loopback / private / link-local hostnames (`board/server.py:33`).

**Concurrency / atomicity:** `clawteam/fileutil.py:atomic_write_text` (mkstemp + replace) for every persisted JSON; `file_locked` advisory locks for spawn registry and task store; per-team `.tasks.lock` guards multi-task batch operations.

**Eventing:** The bus is the single observable spine. Events emitted today: `BeforeWorkerSpawn`, `AfterWorkerSpawn`, `WorkerExit`, `WorkerCrash`, `BeforeTaskCreate`, `AfterTaskUpdate`, `TaskCompleted`, `BeforeInboxSend`, `AfterInboxReceive`, `BeforeWorkspaceMerge`, `AfterWorkspaceCleanup`, `TeamLaunch`, `TeamShutdown`, `AgentIdle`, `HeartbeatTimeout`, `PhaseTransition`, `TransportFallback`, `BoardAttach` (`clawteam/events/types.py`).

**Identity propagation:** Spawn backends export `CLAWTEAM_AGENT_ID` / `CLAWTEAM_AGENT_NAME` / `CLAWTEAM_AGENT_TYPE` / `CLAWTEAM_TEAM_NAME` / `CLAWTEAM_AGENT_LEADER` (and `CLAWTEAM_USER` / `CLAWTEAM_WORKSPACE_DIR` when set) into every child process so the spawned agent can rebuild its identity via `AgentIdentity.from_env`.

---

*Architecture analysis: 2026-04-28*
# Codebase Concerns

**Analysis Date:** 2026-04-28

Scope: live source on branch `board-enhancement` only. Findings resolved by
commits `00a094d`, `efc5f9c`, `1c9a422` (tmux-injection RCE hardening),
`a3b5910` (board "Add Agent" 400), and `427475a` (Plane integration removal)
have been dropped from the prior CONCERNS.md.

---

## Security Considerations

### Board message endpoint accepts attacker-controlled `from`

- Risk: Any client that can reach the board can impersonate any agent in the
  team's mailbox / event log.
- Files: `clawteam/board/server.py:226-246`, `clawteam/team/mailbox.py:72-128`
- What happens: `POST /api/team/<name>/message` reads JSON and calls
  `MailboxManager.send(from_agent=payload.get("from", "board-ui"), ...)`. The
  `from` value is forwarded straight into the persisted `TeamMessage` and the
  per-team event log (`{data_dir}/teams/<name>/events/evt-*.json`) with no
  identity check, no allow-list against `TeamConfig.members`, and no signing.
  The frontend at `clawteam/board/frontend/src/lib/api.ts:54-59` only sends
  `{to, content, summary}`, but a curl request can set
  `{"from":"leader","type":"plan_approved","to":"coder-1",...}` and inject a
  forged approval/idle/broadcast into another agent's inbox — and downstream
  agents have no way to tell it apart from a real peer message.
- Current mitigation: None. Default host is `127.0.0.1` (`clawteam/cli/commands.py:3514`),
  which limits exposure to the local machine; CORS `*` (see next item) means
  any browser tab on that machine can also send the request.
- Recommendations: (a) Drop the `from` field from the request body and derive
  it from a server-known sender id (e.g. always `"board-ui"`, or a
  per-board-session identity); (b) reject any client-supplied `from` that
  matches an existing member's `inbox_name_for(...)`; (c) gate write endpoints
  behind a loopback-only auth token written to `~/.clawteam/board.token` on
  first run.

### CORS `*` and zero authentication on the dashboard server

- Risk: Any process or browser tab on the host (or on the LAN, if `--host` is
  changed) can read team state and execute every write endpoint.
- Files: `clawteam/board/server.py:286, 308, 329, 367`,
  `clawteam/cli/commands.py:3510-3524`
- What happens: `BoardHandler` sets `Access-Control-Allow-Origin: *` on every
  JSON, SSE, and OPTIONS response, and does no authentication anywhere.
  Sensitive endpoints — `POST /api/team/<n>/task`, `/api/team/<n>/member`,
  `/api/team/<n>/message`, `PATCH /api/team/<n>/task/<id>` — accept any
  origin. The default bind is `127.0.0.1`, but `--host 0.0.0.0` makes the
  whole API world-readable/writable with no warning.
- Current mitigation: Default `host=127.0.0.1`. Proxy endpoint (`/api/proxy`)
  has SSRF allow-listing in `_normalize_proxy_target` (`server.py:50-70`).
- Recommendations: (a) Issue a random bearer token at server start and refuse
  requests without it; (b) replace `Access-Control-Allow-Origin: *` with a
  per-request echo of an allow-listed origin (or drop CORS entirely now that
  the React SPA is co-served at `/`); (c) refuse to bind a non-loopback host
  unless `--allow-remote` (or auth) is also passed.

### `.clawteam/` data directory not in `.gitignore` and already committed

- Risk: Project-local agent state — task contents, cost ledgers, lock files,
  team configs — are tracked in git and pushed to the remote. Future
  conversations, agent prompts, and budget data leak through commits.
- Files: `.gitignore` (the strings `clawteam` / `.clawteam` are absent),
  `clawteam/team/models.py:15-46` (`get_data_dir()` resolves to `./.clawteam`
  when present), `.clawteam/` (40+ tracked files, e.g.
  `.clawteam/tasks/board-test/task-*.json`,
  `.clawteam/costs/*/summary.json`, `.clawteam/costs/*/summary.json.lock`).
- What happens: `_find_project_data_dir()` walks up from cwd looking for a
  `.clawteam/` directory and uses it as the data root. The repo currently
  contains such a directory with real test team state, and `git ls-files
  .clawteam` returns 40+ entries. There is no rule in `.gitignore` to keep
  new state from being staged.
- Current mitigation: None.
- Recommendations: (a) Add `/.clawteam/` to `.gitignore`; (b) `git rm -r
  --cached .clawteam` to stop tracking the existing snapshot; (c) consider
  storing only the schema fixtures (e.g. `.clawteam/.gitkeep`) that the test
  suite genuinely needs.

### POST/PATCH bodies are read in full without a size cap

- Risk: A misbehaving or malicious client can send an arbitrarily large
  `Content-Length` and force the server to allocate it before any validation
  runs.
- Files: `clawteam/board/server.py:186, 209, 230, 257`
- What happens: Every write handler does
  `body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8")`
  and then `json.loads(body)`. There is no upper bound, no streaming, and no
  attempt to detect chunked transfer.
- Current mitigation: None.
- Recommendations: Cap `Content-Length` at e.g. 64 KB before reading; reject
  with 413 otherwise.

---

## Fragile Areas

### Two divergent agent-liveness mechanisms

- Files: `clawteam/board/liveness.py:11-40` (board-only path),
  `clawteam/spawn/registry.py:55-90` (registry path used by everything else)
- Why fragile: The board UI computes `isRunning` / `membersOnline` by listing
  tmux window names and matching them by string against `member.name`
  (`clawteam/board/collector.py:54, 81, 95`). Every other consumer
  (`clawteam/harness/conductor.py:22-27`, `clawteam/team/waiter.py:171-175`,
  `clawteam/store/file.py:218-236`, `clawteam/cli/commands.py:3161-3163`)
  uses `clawteam/spawn/registry.py::is_agent_alive`, which checks
  `pane_dead`, falls back to PID, and understands the `subprocess` and `wsh`
  backends. Concrete mismatches:
  - Subprocess- and wsh-backend agents always show `isRunning: false` on the
    board because they have no tmux window with their name.
  - Tmux agents whose window survived but whose foreground process dropped
    back to a shell still show `isRunning: true` on the board, while the
    registry correctly reports them dead (registry filters on
    `pane_current_command in {bash,zsh,sh,fish}`, board does not).
  - The board has no equivalent of `list_zombie_agents`, so long-running
    runaways are invisible to the UI.
- Safe modification: Have `clawteam/board/collector.py` call
  `clawteam/spawn/registry.py::is_agent_alive` per member instead of
  `agents_online()`, and reduce `clawteam/board/liveness.py` to a thin
  fallback when the registry is empty.
- Test coverage: `tests/board/test_liveness.py` only covers the
  string-matching path; nothing reconciles the two implementations.

### SSE thread-per-client handler holds an unbounded daemon thread for life

- Files: `clawteam/board/server.py:324-345` (handler),
  `clawteam/board/server.py:367` (`ThreadingHTTPServer`),
  `clawteam/board/frontend/src/hooks/use-team-stream.ts:21-44` (client opens
  one EventSource per mounted view)
- Why fragile: `ThreadingHTTPServer` (via `ThreadingMixIn`) spawns a new
  daemon thread per accepted connection with no upper bound. `_serve_sse`
  enters `while True: ... time.sleep(self.interval)` and only exits when
  `wfile.flush()` raises `BrokenPipeError` / `ConnectionResetError` /
  `OSError`. There is no idle timeout, no max-connections cap, no per-IP
  cap, and no heartbeat that would cause Python to notice a half-open
  client. Practical effects:
  - A leaked browser tab keeps a thread, an open file descriptor, and
    triggers a `collector.collect_team(...)` rebuild every `interval`
    seconds forever.
  - Each `collect_team` reload rebuilds the message history (200 events)
    and walks the workspace for conflicts (`collector.py:128-184`); with N
    stale clients this is N× the I/O the cache can absorb (the
    `TeamSnapshotCache` only deduplicates within `ttl_seconds`).
  - If the host is moved off `127.0.0.1`, there is no defence against a
    client opening hundreds of `/api/events/<team>` streams to exhaust file
    descriptors and CPU.
- Safe modification: (a) Cap concurrent SSE streams (e.g. a
  `BoundedSemaphore`); (b) detect client disconnect by polling
  `self.connection.recv(0, MSG_PEEK)` or by writing a `:keepalive\n\n`
  comment whose flush failure is the disconnect signal; (c) put the loop
  body on a wall-clock deadline (auto-close after N minutes, let the SPA
  reconnect via `EventSource`'s built-in retry).
- Test coverage: None — there is no test for thread lifetime, disconnect
  handling, or concurrent-client behaviour in `tests/test_board.py`.

### `team_name` reaches `BoardCollector.collect_team` without prior validation

- Files: `clawteam/board/server.py:135-146, 312-322`,
  `clawteam/board/collector.py:38-66, 68-201`,
  `clawteam/team/mailbox.py:41-46`
- Why fragile: The HTTP layer parses `team_name` out of the URL and passes
  it straight to `BoardCollector` / `MailboxManager`. The latter calls
  `validate_identifier(team_name, "team name")` and raises `ValueError`,
  but: (a) the exception bubbles up to `_serve_team` only if it happens
  during `collect_team`, which catches `ValueError` and returns a
  reasonable 404; (b) for `_serve_sse` the same `ValueError` is caught
  inside the loop (`server.py:338-339`) and the bad value sits in the URL
  forever, so the loop runs the same failing call every `interval`
  seconds with the same exception traceback being re-built each time.
- Safe modification: Call `validate_identifier(team_name, "team name")` at
  the top of `do_GET` / `do_POST` / `do_PATCH` and 400 immediately.

### Board write paths skip `MailboxManager.send` argument validation

- Files: `clawteam/board/server.py:225-246`, `clawteam/team/mailbox.py:72-128`
- Why fragile: The handler accepts `payload.get("type", "message")` and
  passes it as `msg_type=` to `mailbox.send`. `mailbox.send` declares the
  parameter typed as `MessageType`, but at runtime any string is forwarded
  to `TeamMessage(type=msg_type, ...)` and Pydantic raises `ValueError`
  only inside the constructor. The handler catches everything via `except
  Exception as e: self.send_error(400, str(e))`, which echoes raw
  exception text (often a multi-line Pydantic dump) back to the client and
  into stderr.
- Safe modification: Validate `msg_type` against `MessageType.__members__`
  up front; replace `except Exception` with a tighter
  `except (ValueError, KeyError)` and a stable error envelope.

---

## Tech Debt

### Identical "team_name parts split" routing repeated four times

- Files: `clawteam/board/server.py:182-247, 253-281`
- Issue: Each POST/PATCH handler re-parses `path.strip("/").split("/")`,
  re-checks `len(parts) == 4`, re-reads `Content-Length`, re-decodes the
  body, and uses an identical `try/except Exception → 400` block. The four
  branches differ only in their endpoint suffix and the `MailboxManager` /
  `TaskStore` / `TeamManager` call.
- Files: `clawteam/board/server.py:180-281`
- Impact: Every new endpoint copies the boilerplate (and its bugs — no
  Content-Length cap, broad `except Exception`, raw exception text in 400
  bodies). The handler is already 373 lines and growing.
- Fix approach: Extract a small dispatch table — `(method, regex) →
  callable(team_name, payload)` — and a `_read_json_body(max_bytes=65536)`
  helper that does size capping and JSON parsing.

### `BoardCollector.collect_team` swallows every exception per side-channel

- Files: `clawteam/board/collector.py:128-183`
- Issue: Cost summary, conflict scan, and event-log read are each wrapped
  in `try: ... except Exception: pass`. A real bug in `CostStore`,
  `detect_overlaps`, or `MailboxManager.get_event_log` is silently dropped
  and the field is omitted from the SSE payload, which the frontend then
  interprets as "no data".
- Impact: Hard to debug regressions — the user sees an empty cost panel,
  but there is no log line and the test suite passes because the failure
  path is never asserted.
- Fix approach: Replace with `except (FileNotFoundError, ValueError)` for
  the known-soft-fail cases and let everything else surface; add a
  lightweight logger.

### `BoardHandler` uses class-level `collector`/`team_cache` injection

- Files: `clawteam/board/server.py:120-127, 354-365`
- Issue: `serve()` mutates class attributes on `BoardHandler` before
  starting the server. Any second `serve()` call in the same process (e.g.
  a future test harness or library embedding) overwrites global state. The
  `team_cache` instance is shared across all requests but is invisible
  from the handler signature.
- Fix approach: Pass the collector + cache as constructor args via a
  `partial(BoardHandler, ...)` factory or replace `BaseHTTPRequestHandler`
  with a `Server` subclass that owns the collector.

---

## Test Coverage Gaps

### Board HTTP handlers are tested only for happy paths

- What's not tested: `clawteam/board/server.py` has no test for the
  message endpoint at all (`POST /api/team/<n>/message`), no test for
  attacker-controlled `from`, no test for oversize bodies, no test for
  team-name validation, and no test asserting that PATCH/POST refuse
  malformed JSON gracefully.
- Files: `tests/test_board.py` (covers proxy SSRF, member POST, task
  PATCH, snapshot cache, but not message send)
- Risk: Regressions in the impersonation surface or SSE lifetime won't be
  caught by CI.
- Priority: High (impersonation), Medium (SSE / size cap)

### No test reconciles the two liveness implementations

- What's not tested: Behaviour when an agent is in
  `clawteam/spawn/registry.py` but not in tmux (and vice versa).
- Files: `tests/board/test_liveness.py`,
  `tests/test_registry.py`
- Risk: The board can keep showing dead agents as online indefinitely
  without any test failure.
- Priority: Medium

### SSE handler has no lifetime test

- What's not tested: Client-disconnect handling, max-connections behaviour,
  whether `_serve_sse` actually exits when the socket closes, whether
  `team_name` validation is enforced before the loop starts.
- Files: `tests/test_board.py:263` exercises a single iteration via
  monkeypatching, but never the loop.
- Risk: Thread / FD leaks accumulate silently.
- Priority: Medium

---

## Scaling Limits

### `TeamSnapshotCache` is per-team but `BoardCollector.collect_team` is O(events × messages)

- Files: `clawteam/board/collector.py:128-150` (200-event cap on event-log
  read), `clawteam/team/mailbox.py:61-70`
- Current capacity: 200 most-recent events parsed and re-serialized on
  every cache miss; one cache miss per team per `interval` seconds.
- Limit: For active teams the event log grows without bound (each
  `MailboxManager._log_event` writes a new file under
  `{data_dir}/teams/<n>/events/evt-*.json`); the directory is `glob`'d
  every cache miss with `sorted(... reverse=True)`. At ~10⁵ events the
  directory listing becomes the dominant cost.
- Scaling path: Tail-only read (e.g. keep an offset file), or move the
  event log to an append-only ndjson file so `sorted(...)` over thousands
  of small files is no longer required.

### Per-connection daemon threads with no upper bound

- See "SSE thread-per-client" above.
- Current capacity: Whatever the OS allows.
- Limit: File-descriptor exhaustion / RAM per thread (~8 MB stack default).
- Scaling path: `BoundedSemaphore` + 503 on overflow, or migrate to
  `asyncio` / `aiohttp` for the SSE path.

---

*Concerns audit: 2026-04-28*
# Coding Conventions

**Analysis Date:** 2026-04-28

ClawTeam is a hybrid Python + TypeScript repository. The Python package
(`clawteam/`) is the CLI / coordination engine; the TypeScript package
(`clawteam/board/frontend/`) is the React SPA shipped as `clawteam board serve`'s
static bundle. Conventions differ meaningfully between the two halves and are
documented separately below.

The project skill at `skills/clawteam/SKILL.md` is the authoritative reference
for end-user CLI behavior; this document covers source-level conventions only.

---

## Python — `clawteam/`

### Toolchain

- **Python:** `>=3.10` (`pyproject.toml` line 6). Type syntax assumes 3.10
  (`X | None`, PEP 604).
- **Formatter / linter:** `ruff` only — no `black`, no `isort`. Configured in
  `pyproject.toml`:
  - `line-length = 100`
  - `target-version = "py310"`
  - lint rules: `["E", "F", "I", "N", "W"]` with `E501` (line length) ignored
- **Pydantic:** v2 (`pydantic>=2.0.0,<3.0.0`). All models use `model_config`,
  `model_dump_json`, `model_validate`. Never use deprecated `dict()` / `parse_obj()`.

### File header

Every Python module starts with a one-line module docstring describing scope.
Examples:

- `clawteam/fileutil.py` line 1: `"""Atomic file writes and advisory file locking."""`
- `clawteam/team/manager.py` line 1: `"""Team manager for creating and managing teams."""`
- `clawteam/board/liveness.py` line 1: `"""Detects which team members have a live tmux session/window."""`

After the docstring, immediately enable PEP 563 deferred evaluation:

```python
"""Module summary line."""

from __future__ import annotations
```

`from __future__ import annotations` is present in essentially every non-trivial
module (see `clawteam/team/tasks.py`, `clawteam/store/file.py`,
`clawteam/spawn/tmux_backend.py`, `tests/test_tmux_injection.py`,
`tests/test_data_dir.py`).

### Naming

| Element | Style | Example | File |
|---------|-------|---------|------|
| Modules / packages | `snake_case` | `team_manager` is a class, but the module is `manager.py` | `clawteam/team/manager.py` |
| Classes | `PascalCase` | `TeamManager`, `FileTaskStore`, `TmuxBackend`, `MailboxManager` | `clawteam/team/manager.py:50` |
| Functions / methods | `snake_case` | `atomic_write_text`, `get_data_dir`, `_pane_safe_to_inject` | `clawteam/fileutil.py:28` |
| Module-private helpers | leading `_` | `_now_iso`, `_find_project_data_dir`, `_render_runtime_notification` | `clawteam/team/models.py:39`, `clawteam/spawn/tmux_backend.py:733` |
| Constants | `SCREAMING_SNAKE` | `_INJECT_SAFE_COMMANDS`, `_SHELL_ENV_KEY_RE`, `_ALLOWED_PROXY_HOSTS` | `clawteam/spawn/tmux_backend.py:30`, `clawteam/board/server.py:19` |
| Pydantic enum members | lowercase | `TaskStatus.pending`, `MessageType.broadcast` | `clawteam/team/models.py:53` |

Two naming subtleties to honor:

1. **Aliased Pydantic fields use `camelCase` on the wire.** Python attributes
   are `snake_case` but the JSON form (and therefore the disk format and the
   browser API contract) is camelCase. See `Pydantic models` below.
2. **`from` is a Python keyword**, so `TeamMessage.from_agent` is aliased to
   `"from"` for both validation and serialization
   (`clawteam/team/models.py:124`).

### Pydantic v2 models

All shared records are Pydantic v2 models. Two patterns are mandatory:

```python
class TeamMember(BaseModel):
    """A member of a team."""

    model_config = {"populate_by_name": True}

    name: str = Field(alias="name")
    user: str = Field(default="", alias="user")
    agent_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12], alias="agentId")
    agent_type: str = Field(default="general-purpose", alias="agentType")
    joined_at: str = Field(default_factory=_now_iso, alias="joinedAt")
```

(`clawteam/team/models.py:90`)

- `model_config = {"populate_by_name": True}` — accept both the snake_case
  attribute name and the camelCase alias when validating.
- All on-wire keys go through `Field(alias="…")`. Disk JSON, HTTP responses,
  and CLI `--json` output use the aliases.
- Default IDs come from `uuid.uuid4().hex[:N]` (12 chars for agent IDs, 8 for
  task IDs — `clawteam/team/models.py:154`).
- Default timestamps come from `_now_iso()` returning
  `datetime.now(timezone.utc).isoformat()`. Never use `datetime.utcnow()`
  (naive). See `clawteam/team/models.py:49`.

When `from_agent: str = Field(alias="from", serialization_alias="from")`
is needed (Python keyword collision), supply *both* `alias` and
`serialization_alias` (`clawteam/team/models.py:124`).

**Serialization rules** (used everywhere in `clawteam/cli/commands.py:_dump`):

```python
def _dump(model) -> dict:
    """Dump a pydantic model to dict with by_alias and exclude_none."""
    return json.loads(model.model_dump_json(by_alias=True, exclude_none=True))
```

Every model dump uses `by_alias=True, exclude_none=True`. JSON output is
indented with `indent=2, ensure_ascii=False` for human + machine readers
(`clawteam/cli/commands.py:80`).

### Persistence — `atomic_write_text` and `file_locked`

All disk writes go through `clawteam/fileutil.py`. Never call
`Path.write_text` / `open("w")` directly for shared state.

```python
from clawteam.fileutil import atomic_write_text, file_locked

atomic_write_text(path, content)               # tmp + os.replace, never partial reads

with file_locked(path):                        # advisory lock on <path>.lock
    # read-modify-write a JSON file safely across processes
    ...
```

(`clawteam/fileutil.py:28`, `:55`)

Cross-process safety is taken seriously. `clawteam/store/file.py` ships its own
`_write_lock()` context manager built on the same `fcntl.LOCK_EX` /
`msvcrt.LK_LOCK` primitives (`clawteam/store/file.py:54`). Any code path that
mutates a shared JSON file under `~/.clawteam/` (or its project-local
equivalent) must hold this lock for the entire read-modify-write window.

### Path handling

- Always use `pathlib.Path`, never `os.path.join` for new code.
- The data root is resolved via `get_data_dir()` in `clawteam/team/models.py:15`.
  Resolution order is documented in the function docstring and tested in
  `tests/test_data_dir.py`:
  1. `CLAWTEAM_DATA_DIR` env var
  2. `data_dir` from `~/.config/clawteam/config.json`
  3. nearest `.clawteam/` walking up from `cwd` (project-local, git-style)
  4. `~/.clawteam/` (global fallback)
- Identifiers that build into filesystem paths must go through
  `validate_identifier(...)` and `ensure_within_root(...)` from
  `clawteam/paths.py` to prevent directory traversal. See
  `clawteam/store/file.py:24`, `clawteam/team/manager.py:20`.

### Typer CLI patterns

The CLI is built on Typer and Rich, exposed through `clawteam.cli.commands:app`
(see `pyproject.toml` `[project.scripts]`). Patterns from
`clawteam/cli/commands.py`:

- One root `typer.Typer(no_args_is_help=True)` per `app` and one per command
  group; sub-typers are mounted with `app.add_typer(group_app, name="…")`
  (`clawteam/cli/commands.py:175`, `:259`, `:262`).
- Global options live in `@app.callback()` and write into module-level
  `_json_output` / `_data_dir` flags that downstream commands read
  (`clawteam/cli/commands.py:44`).
- Every command supports `--json` via the global `_output(data, human_fn=…)`
  helper. JSON output is the structured form; the human form is a Rich
  `Table` rendering of the same dict
  (`clawteam/cli/commands.py:77`, `:181`).
- Validation errors print red text and `raise typer.Exit(1)`. Successes print
  green `OK`. See `clawteam/cli/commands.py:215`, `:228`.
- Heavy / optional deps are imported lazily inside the command function
  (`questionary` in `_load_questionary` at `clawteam/cli/commands.py:135`,
  `BoardCollector` import inside `board_*` commands). Top-level imports stay
  cheap so `clawteam --version` is fast.

### Imports

Order (enforced by `ruff` rule `I`):

1. `from __future__ import annotations`
2. stdlib
3. third-party (`typer`, `pydantic`, `rich`, `questionary`)
4. first-party (`from clawteam.…`)

One blank line between groups. Local / lazy imports inside function bodies
are explicitly allowed and frequently used to keep cold-start fast (e.g.
`from clawteam.config import load_config` inside `get_data_dir()`).

### Error handling

- Caller-facing CLI errors: print to `console` with a `[red]…[/red]` Rich tag
  and `raise typer.Exit(1)`. Never `sys.exit` directly from a Typer command.
- Library-layer errors: raise a typed exception (`TaskLockError`,
  `RuntimeError("tmux load-buffer failed …")`). See
  `clawteam/spawn/tmux_backend.py:_run_tmux` (`:685`) — every `subprocess.run`
  whose failure must be observed is wrapped in `_run_tmux` which raises on
  non-zero exit.
- Best-effort side effects (event bus emits, telemetry) are wrapped in
  bare `try/except Exception: pass` (`clawteam/store/file.py:107`).
- Subprocess probes that are allowed to fail silently (e.g. tmux liveness
  detection) explicitly catch `(subprocess.TimeoutExpired, OSError)` and
  return an empty / falsy value (`clawteam/board/liveness.py:28`).

### Subprocess discipline

Two rules learned from the tmux runtime-injection bug fixes (commit on this
branch, covered by `tests/test_tmux_injection.py`):

1. **Check `shutil.which` before invoking external CLIs.** If the binary is
   missing, return a structured failure — never let `FileNotFoundError`
   escape from a library call. See
   `clawteam/board/liveness.py:17`,
   `clawteam/spawn/tmux_backend.py:295`.
2. **Inspect every return code.** Use `_run_tmux(args)` (raises) for
   side-effecting tmux commands, and `subprocess.run(..., capture_output=True,
   text=True)` + manual `returncode` checks for read-only probes. Never use
   `check=True` blindly inside library code — it makes the error message
   less actionable than a hand-rolled `RuntimeError("tmux load-buffer failed
   (exit 1): <stderr>")`.

When generating a unique resource name (paste buffer, temp file, request id),
use `uuid.uuid4().hex[:N]` — see `clawteam/spawn/tmux_backend.py:712`.

### Logging / output

There is no `logging` framework in user-facing code. CLI output goes through
the module-level `console = Console()` from Rich
(`clawteam/cli/commands.py:27`). Library code returns structured values; the
caller decides whether to print.

### Comments and docstrings

- Every public function and class has a triple-quoted docstring on the line
  immediately after the signature.
- Multi-line docstrings start with a one-line summary, blank line, then
  detail. See `clawteam/fileutil.py:28-40` and `clawteam/team/models.py:15-24`
  for canonical examples.
- Inline comments explain *why*, not *what*. The tmux backend has several
  exemplary inline comments about WSL `PROGRAMFILES(X86)` (`:108`),
  `TERM=dumb` from non-interactive shells (`:67`), and Claude nesting
  detection (`:115`).

### Function design

- Prefer keyword arguments for anything beyond two positional parameters.
  Static methods on managers (`TeamManager.create_team(name, leader_name, …)`)
  use keyword-only arguments at call sites in tests
  (`tests/test_board.py:17`).
- Default mutable arguments are forbidden; use `Field(default_factory=list)`
  on Pydantic models and `param: list[str] | None = None` plus an
  `or []` body on plain functions
  (`clawteam/store/file.py:83-95`).

---

## TypeScript — `clawteam/board/frontend/`

The dashboard is React 19 + Vite 6 + Tailwind v4 + shadcn/ui (`base-nova`
style on top of Base UI primitives `@base-ui/react`). The build output is
written to `clawteam/board/static/` and served by the stdlib HTTP server in
`clawteam/board/server.py`.

### Toolchain

- React 19, react-dom 19 (`package.json` lines 16-17)
- TypeScript ~5.8 (`package.json` line 28)
- Vite 6 with `@vitejs/plugin-react` and `@tailwindcss/vite` plugin
  (`vite.config.ts:2-7`)
- Tailwind v4 in CSS-first mode — no `tailwind.config.js`, only
  `@import "tailwindcss"` and `@theme inline {…}` blocks in
  `src/index.css`. The shadcn `components.json` declares
  `"tailwind.config": ""` to make this explicit.
- shadcn style: `"style": "base-nova"` (`components.json:3`),
  `"baseColor": "neutral"`, `"iconLibrary": "lucide"`.
- Drag-and-drop: `@dnd-kit/react` (Kanban board)
- Class composition helpers: `clsx` + `tailwind-merge` exposed as `cn()` in
  `src/lib/utils.ts`.

### File and directory naming

| Element | Style | Example |
|---------|-------|---------|
| Component / hook / lib filenames | `kebab-case.tsx` / `.ts` | `agent-registry.tsx`, `peek-panel.tsx`, `task-card.tsx`, `use-team-stream.ts` |
| Directories | `kebab-case` | `components/kanban/`, `components/modals/`, `components/ui/` |
| Component exports | `PascalCase` named exports | `export function Topbar(...)`, `export function Board(...)` |
| Hooks | `useFoo` named export from `kebab-case` file | `useTeamStream` in `hooks/use-team-stream.ts` |
| Types | `PascalCase` interface in `src/types.ts` | `TeamData`, `Member`, `Task`, `TaskStatus` |
| Type-only constants | `SCREAMING_SNAKE` | `TASK_STATUSES`, `STATUS_LABELS`, `STATUS_COLORS` (`types.ts:49-73`) |

The `App.tsx` and `main.tsx` entry points are the only PascalCase filenames —
this is the standard Vite-React template and should be kept as-is.

### Style: no semicolons

The whole frontend omits trailing semicolons at the end of statements. Verified
across `App.tsx`, `main.tsx`, `lib/api.ts`, all `components/*.tsx`, and all
`components/ui/*.tsx` files (zero matches for `;\s*$`). The single exception
is the `"use client"` directive at the top of files copied verbatim from
shadcn (currently only `components/ui/dialog.tsx:1`).

This is not enforced by a linter (no eslint / prettier config is checked in
under the frontend directory), so contributors must mirror the existing
style by hand. New files: omit semicolons.

Other style points observed throughout:

- Double-quoted strings (`import { foo } from "bar"`).
- 2-space indentation.
- Trailing commas in multiline object / arg lists.
- Arrow components only for inline callbacks; top-level components use
  `export function Name() {}`.

### Imports and path aliases

- The `@/*` alias maps to `./src/*`. Configured in both
  `tsconfig.json:4-6` and `vite.config.ts:9-11`. Always import via the alias:
  `import { Button } from "@/components/ui/button"` — never relative `../..`
  paths across the `src/` tree.
- `components.json` aliases mirror this: `components → @/components`,
  `ui → @/components/ui`, `utils → @/lib/utils`, `hooks → @/hooks`,
  `lib → @/lib`. Honor these when running `shadcn add`.

Import groups (consistent across files, though not linter-enforced):

1. React / react-dom
2. Third-party libs (`@base-ui/react/...`, `@dnd-kit/react`,
   `class-variance-authority`, `lucide-react`)
3. `@/components/...`
4. `@/hooks/...`
5. `@/lib/...`
6. `@/types` (type-only)

Use `import type { ... }` for type-only imports
(`App.tsx:15`, `peek-panel.tsx:19`).

### shadcn / Base UI primitive pattern

UI primitives in `src/components/ui/` are generated by the shadcn CLI on the
`base-nova` style and wrap `@base-ui/react/<primitive>`. The canonical pattern
(from `components/ui/button.tsx`):

```tsx
import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center …",
  {
    variants: { variant: { default: "...", outline: "...", … }, size: {...} },
    defaultVariants: { variant: "default", size: "default" },
  },
)

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
```

Rules:

- Always re-export both the component and its `cva` variants object so that
  callers can compose styles (`buttonVariants({ variant: "outline" })`).
- Always set `data-slot="<primitive>"` on the wrapper. Sibling primitives use
  this for adjacency selectors.
- Always pipe className through `cn(...)` so consumer overrides win the
  tailwind-merge conflict resolution.
- Type the props as `<Primitive>.Props & VariantProps<typeof variants>` —
  do not redeclare prop interfaces by hand.

### Tailwind v4 + theme tokens

All theme colors are CSS variables in `src/index.css` and exposed as Tailwind
utilities through the `@theme inline { … }` block:

```css
:root {
  --background: oklch(0.145 0 0);
  --foreground: oklch(0.985 0 0);
  --primary: oklch(0.985 0 0);
  --primary-foreground: oklch(0.205 0 0);
  --status-pending: #f59e0b;
  --status-progress: #3b82f6;
  /* … */
}

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-primary: var(--primary);
  /* … */
}
```

Conventions:

- **Always reference theme tokens, never raw color values.** Use
  `bg-background`, `text-foreground`, `bg-card/60`, `text-muted-foreground`,
  `border-border` — not `bg-zinc-950` or `text-white`.
  (Counter-example: `agent-registry.tsx` still uses raw `zinc-*` classes; new
  components should not copy that.)
- Status colors are sourced via `STATUS_COLORS[status]` from `src/types.ts:67`,
  which resolves to `var(--color-status-pending)` etc. Components that paint
  status (kanban column header, task card glow) inject the value via inline
  `style={{ background: `linear-gradient(…, ${color}, …)` }}` because the
  color name is dynamic at runtime
  (`components/kanban/column.tsx:23`, `components/kanban/task-card.tsx:46`).
- Use `oklch(...)` for new theme colors; the existing palette is uniformly
  oklch except for the status accents.
- Custom utility classes live in `src/index.css` (e.g. `.atmosphere`,
  `.dot-grid` at `index.css:75-89`). Keep them small and themable.

### React component patterns

- **Functional components only.** No class components anywhere.
- **Named exports for components, default export only for `App`.**
  `App.tsx` uses `export default function App()`; everything else exports by
  name.
- Component props are declared as a top-level `interface FooProps` directly
  above the component:

  ```tsx
  interface BoardProps {
    teamName: string
    tasks: TasksByStatus
    onPeek: (taskId: string) => void
  }

  export function Board({ teamName, tasks, onPeek }: BoardProps) { … }
  ```

  (`components/kanban/board.tsx:8`).
- Local state is `useState`, side effects are `useEffect`, derived values use
  `useMemo` when the dependency cost is real
  (`peek-panel.tsx:63`).
- Refs use `useRef` typed explicitly: `useRef<{ x: number; y: number } | null>(null)`
  (`task-card.tsx:25`).
- Cross-tree state is shared via a single React context exposed by `App.tsx`:
  `TeamContext` + `useTeam()` hook (`App.tsx:23-31`). Don't reach for Redux /
  Zustand — the SSE-driven team snapshot is small and re-rendering top-down is
  fine.

### Data fetching

All HTTP calls live in `src/lib/api.ts` and target the `/api` prefix proxied
to the Python server (`vite.config.ts:17-21` proxies `/api` to
`http://localhost:8080` in dev). Pattern:

```ts
async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
  return res.json()
}
```

(`lib/api.ts:3`)

- Generic helpers (`post<T>`, `patch<T>`) for the verb, then per-endpoint
  named exports (`createTask`, `updateTask`, `addMember`, `sendMessage`).
- Always `encodeURIComponent` path segments.
- Errors throw; UI callers `.catch(console.error)` at the call site (e.g.
  `Board.onDragEnd`).

### Realtime: SSE via custom hook

The team snapshot is streamed over SSE. The hook lives at
`src/hooks/use-team-stream.ts`:

- Returns `{ data, isConnected }`; both are derived state on `useState`.
- Uses a `useRef` to dedupe identical consecutive payloads.
- Distinguishes SSE liveness (`isConnected`) from agent liveness — the latter
  is computed from `data.team.membersOnline` in `App.tsx:95`.
- Always close the `EventSource` in the effect cleanup.

### Tokens vs raw values cheat-sheet

| Use this | Not this |
|----------|----------|
| `bg-background`, `text-foreground` | `bg-zinc-950`, `text-white` |
| `border-border`, `bg-card`, `bg-muted/50` | `border-zinc-800`, `bg-zinc-900` |
| `text-muted-foreground` | `text-zinc-500` |
| `text-destructive` | `text-red-500` |
| `bg-primary text-primary-foreground` | `bg-blue-600 text-white` |
| Inline `style={{ color: STATUS_COLORS[s] }}` for status accents | hard-coded per-status hex |

---

*Convention analysis: 2026-04-28*
# External Integrations

**Analysis Date:** 2026-04-28

This snapshot reflects the post-Plane-removal `board-enhancement` branch.
There is no longer any project-management integration: the
`clawteam/plane/` Python package, its Typer sub-app, its
`extras_require["plane"]`, and all `tests/test_plane_*.py` files were
removed in commit `427475a`. ClawTeam currently has no first-party
integration with Plane, Linear, Jira, GitHub Issues, or any other
external task tracker — task state lives entirely in the file-backed
`TaskStore`.

## APIs & External Services

### Outbound HTTPS

**GitHub README proxy (board dashboard):**
- Single allow-listed proxy endpoint exposed at `GET /api/proxy?url=...`
  in `clawteam/board/server.py:147`.
- Allow-list: `api.github.com`, `github.com`, `raw.githubusercontent.com`
  (`_ALLOWED_PROXY_HOSTS`, `clawteam/board/server.py:19`).
- Hardening:
  - Forces `https` (`_normalize_proxy_target`, line 50).
  - Rejects redirects via a custom `urllib.request.HTTPRedirectHandler`
    (`_NoRedirectHandler`, line 26).
  - Blocks loopback / private / link-local / multicast IPs and the
    literal `localhost` (`_is_blocked_hostname`, line 33).
  - Re-validates the final URL after read to catch redirect-after-allow
    bypasses (line 79).
- Frontend usage: only `clawteam/board/frontend/src/components/modals/set-context.tsx`
  invokes `fetchProxy` (`clawteam/board/frontend/src/lib/api.ts:61`) so the
  user can pull a public README into the "Set Context" dialog.
- Auth: none — endpoint is for public, unauthenticated GitHub content only.

**Outbound model-provider HTTPS (driven by spawned agents, not by
ClawTeam itself):**
- ClawTeam never calls model APIs directly. It launches third-party CLIs
  (`claude`, `codex`, `gemini`, `kimi`, `qwen`, `opencode`, `nanobot`,
  `openclaw`, `pi`) and configures them via env vars.
- Built-in agent presets in `clawteam/spawn/presets.py:43` define
  `base_url` + `auth_env` pairs that get exported into the spawned
  shell. Endpoints referenced from the presets:
  - Anthropic API key only (no base_url override) — `anthropic-official`,
    auth env `ANTHROPIC_API_KEY` (line 46).
  - OpenAI API key only — `openai-official`, auth env `OPENAI_API_KEY`
    (line 56).
  - Google AI Studio (Gemini) — `google-ai-studio`, auth env
    `GEMINI_API_KEY` (line 66).
  - Vertex AI — `gemini-vertex`, env `GOOGLE_GENAI_USE_VERTEXAI=true`,
    `GOOGLE_CLOUD_LOCATION=global` (line 183) — relies on local gcloud ADC.
  - Moonshot Kimi — `https://api.moonshot.cn/anthropic` and
    `https://api.moonshot.cn/v1`, auth env `MOONSHOT_API_KEY` (line 76).
  - DeepSeek — `https://api.deepseek.com/anthropic`, auth env
    `DEEPSEEK_API_KEY` (line 99).
  - Zhipu GLM — `https://open.bigmodel.cn/api/anthropic` (CN) and
    `https://api.z.ai/api/anthropic` (global), auth env `ZHIPU_API_KEY`
    (lines 105, 112).
  - Alibaba Bailian — `https://dashscope.aliyuncs.com/apps/anthropic`
    and `https://coding.dashscope.aliyuncs.com/apps/anthropic`, auth env
    `DASHSCOPE_API_KEY` (lines 117, 128).
  - MiniMax — `https://api.minimaxi.com/anthropic` (CN) and
    `https://api.minimax.io/anthropic` (global), auth env
    `MINIMAX_API_KEY` (lines 138, 148).
  - OpenRouter — `https://openrouter.ai/api` (Claude/Gemini) and
    `https://openrouter.ai/api/v1` (Codex), auth env `OPENROUTER_API_KEY`
    (line 156).
- Profile resolver `clawteam/spawn/profiles.py:162` maps each agent
  basename to the env var its CLI reads:
  - `claude/claude-code` → base URL `ANTHROPIC_BASE_URL`, key
    `ANTHROPIC_AUTH_TOKEN`.
  - `codex/codex-cli` → base URL `OPENAI_BASE_URL`, key `OPENAI_API_KEY`.
  - `gemini` → base URL `GOOGLE_GEMINI_BASE_URL`, key `GEMINI_API_KEY`.
  - `kimi` → base URL `KIMI_BASE_URL`, key `KIMI_API_KEY`.

### Inbound HTTP

**Board dashboard HTTP server** (`clawteam/board/server.py`,
`ThreadingHTTPServer` started by `serve()` at line 354):
- Default bind `127.0.0.1:8080` (`clawteam/cli/commands.py:3513`).
- Routes (handler `BoardHandler`, line 120):
  - `GET /` and `GET /index.html` → static `index.html`.
  - `GET /assets/*` → Vite-built JS/CSS/maps from `clawteam/board/static/assets/`.
  - `GET /api/overview` → all-team summary.
  - `GET /api/team/<name>` → full team snapshot.
  - `GET /api/events/<name>` → SSE stream (`text/event-stream`), pushes
    cached snapshot every `interval` seconds.
  - `GET /api/proxy?url=...` → GitHub README proxy (described above).
  - `POST /api/team/<name>/task` → create task.
  - `POST /api/team/<name>/member` → add agent (omitting `agent_id` is
    allowed since fix in commit `a3b5910`).
  - `POST /api/team/<name>/message` → send mailbox message.
  - `PATCH /api/team/<name>/task/<id>` → update task fields.
  - `OPTIONS *` → CORS preflight (`Access-Control-Allow-Origin: *`).
- Rate limiting / auth: none. CORS is wide open. Server is intended for
  loopback-only operation.

### Inbound stdio

**FastMCP server** (`clawteam/mcp/server.py`):
- Entry point `clawteam-mcp` (`pyproject.toml:41`), wrapper module
  `clawteam/mcp/__main__.py`.
- Transport: stdio via `mcp.run()` from the `mcp` SDK.
- Tools registered (26 total) in `clawteam/mcp/tools/__init__.py`:
  team CRUD (`team_list`, `team_get`, `team_members_list`, `team_create`,
  `team_member_add`), tasks (`task_list`, `task_get`, `task_stats`,
  `task_create`, `task_update`), mailbox (`mailbox_send`, `mailbox_broadcast`,
  `mailbox_receive`, `mailbox_peek`, `mailbox_peek_count`), plans
  (`plan_submit`, `plan_get`, `plan_approve`, `plan_reject`), board
  (`board_overview`, `board_team`), cost (`cost_summary`), workspace
  (`workspace_agent_diff`, `workspace_file_owners`,
  `workspace_cross_branch_log`, `workspace_agent_summary`).
- Each tool function is wrapped in `_tool` (`clawteam/mcp/server.py:16`)
  which translates exceptions through `clawteam/mcp/helpers.py
  translate_error`.

## Data Storage

### Primary store

**File-backed JSON on disk:**
- Resolution order in `clawteam/team/models.py:15` (`get_data_dir`):
  1. `CLAWTEAM_DATA_DIR` env.
  2. `data_dir` field in `~/.clawteam/config.json`.
  3. Nearest `.clawteam/` walking up from `cwd` (project-local discovery
     introduced in commit `2f13883`).
  4. `~/.clawteam/`.
- Layout under the resolved data dir:
  - `teams/<team>/config.json` — `TeamConfig` (`clawteam/team/manager.py:24`).
  - `teams/<team>/inboxes/<inbox_name>/` — per-member mailbox JSONs
    (`clawteam/team/mailbox.py`).
  - `teams/<team>/peers/<agent>.json` — P2P transport peer registry
    (`clawteam/transport/p2p.py:22`).
  - `teams/<team>/spawn_registry.json` — agent process metadata used for
    liveness checking (`clawteam/spawn/registry.py:18`).
  - `tasks/<team>/` — task store backed by `FileTaskStore`
    (`clawteam/store/file.py`, dispatched from `clawteam/store/__init__.py`).
  - `costs/<team>/` — cost ledger (`clawteam/team/costs.py`).
  - `sessions/<team>/` — session persistence for agent resume.
  - `workspaces/<team>/` — git worktrees when the workspace feature is
    enabled.
- All writes go through `clawteam/fileutil.py atomic_write_text`
  (mkstemp + `os.replace`) and inbox/registry mutations use
  `clawteam/fileutil.py file_locked` for cross-process safety.
- All path joins are constrained by `paths.ensure_within_root` and team
  identifiers are validated against `_IDENTIFIER_RE = ^[A-Za-z0-9._-]+$`
  (`clawteam/paths.py:8`).

**Configuration store:**
- `~/.clawteam/config.json` (`clawteam/config.py:76`). Held separate from
  the `data_dir` so user-wide settings (presets, profiles, plugin list,
  hook list) survive switching between project-local data dirs.

### Plugin-extensible stores

**Task store backends** (`clawteam/store/__init__.py:8`):
- Resolution: `backend` arg → `CLAWTEAM_TASK_STORE` env → `task_store`
  field in config → `"file"`.
- Only `FileTaskStore` ships; the docstring notes redis/sql are
  potential future backends, but no other implementations exist.

**Transport backends** (`clawteam/transport/__init__.py:15`):
- `"file"` (default) — `FileTransport` in `clawteam/transport/file.py`,
  uses inbox directories under the data dir.
- `"p2p"` — `P2PTransport` in `clawteam/transport/p2p.py`, ZeroMQ
  PUSH/PULL with `FileTransport` fallback for offline peers; only loaded
  when the optional `p2p` extra is installed.
- Custom transports may register through `register_transport`.

### Caching

**In-memory snapshot cache (board SSE):**
- `TeamSnapshotCache` in `clawteam/board/server.py:96`, TTL = SSE push
  interval. Shared across HTTP handlers under a `threading.Lock`. No
  external cache — Redis/Memcached are not used.

### File storage (binary)

- No object storage. Gource video export writes to the local filesystem
  via `ffmpeg` (`clawteam/board/gource.py:363`).

## Authentication & Identity

**End-user auth:**
- None. ClawTeam is a single-user local CLI; there is no login system,
  no session token, no user database.
- The `user` field on a team member (`clawteam/team/models.py:96`) is a
  cosmetic identifier (defaults to `CLAWTEAM_USER` env var) used to
  scope inbox directory names.
- Agent identity helpers in `clawteam/identity.py`.

**Provider auth:**
- API keys for model providers are read from environment variables only
  (no token persistence inside the repo). Profile env-mapping happens in
  `clawteam/spawn/profiles.py:127` (`apply_profile`) using
  `os.environ.get(profile.api_key_env)`.

**Board dashboard auth:**
- None. Bound to `127.0.0.1` by default; CORS is wide open
  (`Access-Control-Allow-Origin: *` in
  `clawteam/board/server.py:288, 308, 329`). Anyone with network
  access to the bind address can read team state and POST/PATCH tasks.

## Process / Liveness Integrations

These are not third-party services, but they are external systems
ClawTeam shells out to. Three different liveness signals coexist:

**1. tmux liveness** (per-agent process check):
- `clawteam/spawn/registry.py:171` `_tmux_pane_alive` calls
  `tmux list-panes -t <target> -F "#{pane_dead} #{pane_current_command}"`
  and treats `pane_dead == 1` or a foreground shell (`bash/zsh/sh/fish`)
  as dead. Falls back to PID alive check if the tmux target is missing
  (e.g. after tile operations).

**2. Tmux-window-name liveness (board UI)**:
- `clawteam/board/liveness.py:11` `tmux_windows()` runs
  `tmux list-windows -t clawteam-<team> -F "#{window_name}"` and the
  collector marks each member as `isRunning` when its name appears in
  the window set (`clawteam/board/collector.py:81`).
- Distinct from the spawn-registry check — this is what populates
  `members[].isRunning` and `team.membersOnline` in the SSE payload.

**3. SSE liveness (transport-level, post-`908b8ab`)**:
- `clawteam/board/frontend/src/hooks/use-team-stream.ts` exposes
  `isConnected` driven by `EventSource.onopen` (true) and
  `EventSource.onerror` (false). The topbar pill in
  `clawteam/board/frontend/src/components/topbar.tsx:81` shows "Stream
  live" / "Stream offline" purely from this signal, independent of
  whether any agent is alive.
- The header agents-online badge in `clawteam/board/frontend/src/App.tsx:94`
  reflects the tmux-window signal and stays accurate even when the SSE
  stream is healthy but every agent has exited.

**Tmux-injection hardening (commits `00a094d`, `efc5f9c`, `1c9a422`)**:
- `_pane_safe_to_inject` in `clawteam/spawn/tmux_backend.py:672` runs
  `tmux display-message -p -t <target> "#{pane_current_command}"` and
  refuses injection unless the foreground command is in
  `_INJECT_SAFE_COMMANDS` (line 656: claude / codex / gemini / kimi /
  qwen / opencode / nanobot / openclaw / pi / node / python / python3).
  Blocks paste-buffer injection into a stray shell or sub-TUI that
  could execute `$(...)`.
- `_inject_prompt_via_buffer` (line 701) uses a per-call unique buffer
  name (`prompt-<agent>-<uuid8>`) so concurrent injections cannot clobber
  each other; every `tmux load-buffer / paste-buffer / send-keys` call
  is checked through `_run_tmux` (line 685) which raises on non-zero
  exit instead of silently swallowing failures.
- Spawn now records `pane_id` (e.g. `%42`) alongside the
  `session:window` target (`clawteam/spawn/tmux_backend.py:230`), and
  runtime injections target the stable `pane_id` first
  (`inject_runtime_message`, line 293) so window renames or tile moves
  do not break message delivery.

## Spawn-pipeline integrations

**Tmux backend** (`clawteam/spawn/tmux_backend.py`):
- Default backend (`default_backend = "tmux"` in
  `clawteam/config.py:58`).
- Creates session `clawteam-<team>` and one window per agent, named
  after the agent. Sets `pane-exited` and `pane-died` tmux hooks that
  call `clawteam lifecycle on-exit` / `on-crash`
  (`clawteam/spawn/tmux_backend.py:158`).

**Subprocess backend** (`clawteam/spawn/subprocess_backend.py`):
- POSIX + Windows. Launches `subprocess.Popen` with `shell=True`,
  installs an exit hook by chaining `lifecycle on-exit`.

**Wsh backend** (`clawteam/spawn/wsh_backend.py`):
- Targets TideTerm / WaveTerminal. JSON-RPC over Unix socket
  `~/.local/share/tideterm/tideterm.sock` (with fallback to
  `~/.local/state/waveterm/tideterm.sock`) using
  `clawteam/spawn/wsh_rpc.py WshRpcClient`. Methods used:
  `ControllerInputCommand`, `BlockInfoCommand`. Block lifecycle managed
  via the `wsh` CLI (`wsh blocks list --json`,
  `wsh deleteblock -b <block>`).

## Monitoring & Observability

**Error tracking:**
- None. No Sentry, Datadog, or equivalent SDK is imported anywhere
  under `clawteam/`.

**Logs:**
- CLI/Server output goes to stdout/stderr via `rich.Console` or stdlib
  `print`. Board SSE log lines are suppressed in
  `BoardHandler.log_message` (`clawteam/board/server.py:347`) to keep
  the console quiet.
- Per-agent activity is captured by tmux scrollback (visual) and by
  the file-based mailbox/event log
  (`MailboxManager.get_event_log`, called in
  `clawteam/board/collector.py:130`).

**Cost tracking:**
- Internal only — `clawteam/team/costs.py CostStore` aggregates per-team
  token / cost events into the `costs/<team>/` directory; surfaced via
  `clawteam cost ...` and the board `cost` payload
  (`clawteam/board/collector.py:152`).

**Visualization:**
- `clawteam board gource` shells out to the optional `gource` and
  `ffmpeg` binaries to render activity videos
  (`clawteam/board/gource.py`).

## CI/CD & Deployment

**CI:**
- GitHub Actions, single workflow `.github/workflows/ci.yml`.
  - `lint` job: `ruff check clawteam/ tests/` on Python 3.12.
  - `test` job: matrix `{ubuntu-latest, macos-latest} × {3.10, 3.11, 3.12}`,
    runs `pip install -e ".[dev]"` + `python -m pytest tests/ -v --tb=short`.

**Hosting / deployment:**
- Not applicable. Distribution is a Python wheel (Hatchling) installed
  by end users.

**Marketing site:**
- `website/` (separate `package.json` at repo root) builds a Vite SPA;
  no deployment configuration is committed to the repo.

## Environment Configuration

**Required environment variables (functional):**
- None are strictly required at startup. ClawTeam runs entirely off the
  resolved data directory, falling back to `~/.clawteam/`.
- Any model-provider env (e.g. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  …) is required only for the matching spawned agent CLI.

**Common environment variables (operational):**
- See STACK.md → "Environment variables" for the full list registered
  in `clawteam/config.py:103`.

**Secrets location:**
- ClawTeam neither reads nor stores any secret directly. Secrets sit in
  the user's shell environment, in `~/.clawteam/config.json` only when
  the user pastes them into a profile (no built-in encryption), or in
  agent CLIs' own credential stores (e.g. `~/.config/anthropic/`).
- The repo's `.gitignore` ignores `.env` at the root (line 9). The
  scratch script `scripts/openclaw_worker.sh` reads from `.env` files
  if present but never commits them.

## Webhooks & Callbacks

**Incoming:**
- None. The board HTTP server has no webhook routes (the previous Plane
  webhook receiver was removed alongside the Plane subpackage in
  commit `427475a`).

**Outgoing:**
- None. ClawTeam emits internal events through
  `clawteam/events/global_bus.py get_event_bus()` (e.g.
  `AfterWorkerSpawn` from `clawteam/spawn/tmux_backend.py:267`), but
  the bus is in-process only — there is no HTTP push, no message
  broker, no outbound webhook delivery.

---

*Integration audit: 2026-04-28*
# Technology Stack

**Analysis Date:** 2026-04-28

This stack covers the post-Plane-removal `board-enhancement` branch. The
`clawteam/plane/` subpackage has been deleted (commit `427475a`); the
directory exists in the working tree only as an empty `__pycache__` shell and
contributes nothing to the runtime, build, or test pipeline.

## Languages

**Primary:**
- Python 3.10+ (`pyproject.toml` line 6: `requires-python = ">=3.10"`) — entire
  CLI, MCP server, board HTTP server, spawn backends, transports.
- TypeScript 5.8.x (`clawteam/board/frontend/package.json` devDeps:
  `"typescript": "~5.8.0"`) — board dashboard SPA.

**Secondary:**
- TSX/JSX (`clawteam/board/frontend/src/**/*.tsx`) — React component layer.
- POSIX shell (`scripts/openclaw_worker.sh`) — non-interactive OpenClaw worker
  wrapper used by the spawn pipeline.
- TOML — built-in team templates (`clawteam/templates/*.toml`).

## Runtime

**Python interpreter:**
- CPython, supported matrix `3.10`, `3.11`, `3.12` (CI:
  `.github/workflows/ci.yml` lines 22–25; pyproject classifiers lines 16–18).

**Browser runtime (board dashboard):**
- Modern evergreen browsers (`tsconfig.app.json` targets `ES2020`, lib
  includes `DOM`, `DOM.Iterable`).
- Frontend served either by Vite dev server (`port 5173`, proxies `/api` to
  `http://localhost:8080`) or pre-built and served from
  `clawteam/board/static/` by the stdlib HTTP server.

**Package manager:**
- `uv` is the preferred resolver (lockfile `uv.lock` is committed and tracks
  every transitive dependency). The `.gitignore` ignores `uv.lock` at the
  repo root, but the file is force-tracked.
- pip/PyPA tooling supported via `pyproject.toml` (`build-system: hatchling`).
- Node tooling: npm — `package-lock.json` files committed at repo root (for
  `website/`) and at `clawteam/board/frontend/`.

## Frameworks

### Backend (Python)

**CLI framework:**
- `typer>=0.12,<1.0` (`pyproject.toml` line 22; resolved to `0.24.1` in
  `uv.lock`). Single root `Typer` app in `clawteam/cli/commands.py` (line 22)
  with twenty `add_typer` sub-apps: `config`, `preset`, `profile`, `team`,
  `inbox`, `runtime`, `task`, `cost`, `session`, `plan`, `lifecycle`,
  `identity`, `board`, `workspace`, `context`, `template`, `hook`, `plugin`,
  `harness`. There is no `plane` sub-app.

**Data validation:**
- `pydantic>=2.0,<3.0` (resolved 2.12.5). Used for every persisted model:
  `clawteam/team/models.py` (TeamConfig, TeamMember, TaskItem, TeamMessage),
  `clawteam/config.py` (ClawTeamConfig, AgentProfile, AgentPreset, HookDef).
  All models use `model_config = {"populate_by_name": True}` and `Field(...,
  alias="camelCase")` so JSON on disk is camelCase while Python attributes
  stay snake_case.

**Console rendering:**
- `rich>=13.0,<15.0` (resolved 14.3.3). `Console`/`Table` for human-friendly
  CLI output; `clawteam/board/renderer.py` builds the in-terminal kanban view.

**Interactive prompts:**
- `questionary>=2.0.1,<3.0` (resolved 2.1.1). Used by the profile wizard
  (`clawteam/cli/commands.py` `_load_questionary` at line 135 onward).

**MCP SDK:**
- `mcp>=1.0` (resolved 1.27.0). The FastMCP server is mounted via
  `from mcp.server.fastmcp import FastMCP` in `clawteam/mcp/server.py`
  (line 8) and exposes 26 tools registered through `clawteam/mcp/tools/__init__.py`.

**TOML parsing:**
- `tomli>=2.0; python_version<'3.11'` — fallback for Python 3.10 only;
  3.11+ uses stdlib `tomllib`. Used by `clawteam/templates/__init__.py`.

**Optional `p2p` extra:**
- `pyzmq>=25.0,<27.0` (resolved 26.4.0) — only loaded when
  `clawteam/transport/p2p.py` is exercised (it does an inline
  `import zmq` inside `_start_listener`).

### Backend embedded servers (no framework)

- Board HTTP server: stdlib only — `http.server.ThreadingHTTPServer` +
  `BaseHTTPRequestHandler` (`clawteam/board/server.py` line 12). No Flask,
  FastAPI, or Starlette. SSE is implemented manually by writing
  `text/event-stream` chunks (`_serve_sse`, line 324).
- MCP server: `FastMCP` stdio transport, started via `mcp.run()` in
  `clawteam/mcp/server.py:32`.

### Frontend (TypeScript / React)

**Core:**
- `react@^19.1.0` + `react-dom@^19.1.0` (`clawteam/board/frontend/package.json`).
  Strict mode enabled (`clawteam/board/frontend/src/main.tsx:6`).
- `@base-ui/react@^1.4.0` — headless primitive layer (Dialog, Select, Button,
  merge-props, useRender). Drives all shadcn-style UI primitives in
  `clawteam/board/frontend/src/components/ui/*.tsx`.
- shadcn CLI configuration (`clawteam/board/frontend/components.json`),
  style `base-nova`, base color `neutral`, icon library `lucide`. shadcn is a
  generator, not a runtime dep.

**Styling:**
- `tailwindcss@^4.1.0` + `@tailwindcss/vite@^4.1.0` (Tailwind v4, CSS-first
  configuration in `clawteam/board/frontend/src/index.css` via
  `@import "tailwindcss"` and `@theme inline { ... }`). No `tailwind.config.*`
  file — theme tokens are CSS variables.
- `tw-animate-css@^1.4.0` — extra animation utilities.
- `class-variance-authority@^0.7.1` + `clsx@^2.1.1` + `tailwind-merge@^3.5.0`
  — composing variant classes (see `clawteam/board/frontend/src/lib/utils.ts`
  for the `cn(...)` helper).
- `lucide-react@^1.8.0` — icon set.
- Google Fonts loaded inline in `clawteam/board/frontend/index.html` and the
  built `clawteam/board/static/index.html`: Geist, Geist Mono, Instrument
  Serif.

**Drag-and-drop:**
- `@dnd-kit/react@^0.4.0` (the new dnd-kit v0.4 React entry) — drives the
  kanban board in `clawteam/board/frontend/src/components/kanban/board.tsx`
  via `DragDropProvider` + `isSortable`.

**Build / Dev:**
- `vite@^6.3.0` with `@vitejs/plugin-react@^4.4.0` — frontend bundler.
  Output written to `../static` (`clawteam/board/frontend/vite.config.ts`
  line 14: `outDir: "../static", emptyOutDir: true`) so Python ships the
  built assets without separate packaging.
- `typescript@~5.8.0` — `tsc -b` runs as part of `npm run build`.
- Type packages: `@types/node@^22`, `@types/react@^19.1`, `@types/react-dom@^19.1`.

**Marketing site (separate, unrelated to the dashboard):**
- `clawteam-website` at repo root (`package.json`) — `react@^18.3.1`,
  `react-dom@^18.3.1`, `vite@^5.4.11`, `@vitejs/plugin-react@^4.3.4`. Built
  from `website/` with its own `vite.config.mjs`. Note the React 18 / Vite 5
  pinning differs from the React 19 / Vite 6 dashboard.

### Testing

- `pytest>=9.0,<10.0` (resolved 9.0.3). Configured in `pyproject.toml`
  `[tool.pytest.ini_options]` with `testpaths = ["tests"]`. 41 test files in
  `tests/`, none of them target Plane (no `tests/test_plane_*.py` exists).
- Optional dev extra includes `ruff>=0.1.0` (resolved 0.15.9).

### Linting

- `ruff` configured in `pyproject.toml` (`[tool.ruff]` line 62 onward):
  `line-length = 100`, `target-version = "py310"`, lint selects
  `E,F,I,N,W` and ignores `E501`. CI runs `ruff check clawteam/ tests/`
  (`.github/workflows/ci.yml:18`).

## Key Dependencies

**Critical (Python):**
- `typer` (`0.24.1`) — entry point `clawteam = clawteam.cli.commands:app`.
- `pydantic` (`2.12.5`) — every on-disk model.
- `mcp` (`1.27.0`) — FastMCP server entry point
  `clawteam-mcp = clawteam.mcp.server:main`.
- `rich` (`14.3.3`) — TTY rendering.

**Critical (Frontend):**
- `react` / `react-dom` 19 — runtime.
- `@base-ui/react` 1.4 — primitive components.
- `@dnd-kit/react` 0.4 — kanban drag-and-drop.
- `tailwindcss` 4 (+ Vite plugin) — styling.

**Infrastructure:**
- `hatchling` — build backend (`pyproject.toml` lines 48–53). Wheel includes
  the `clawteam` package only.
- `vite` — frontend build, with Python serving the resulting static files.

## Configuration

**User config file:**
- Fixed location `~/.clawteam/config.json`, never moved by `data_dir`
  overrides (`clawteam/config.py:76` `config_path()`).
- Schema = `ClawTeamConfig` Pydantic model
  (`clawteam/config.py:50`), atomically written via `atomic_write_text`.
- Effective-value resolver `get_effective(key)` (`clawteam/config.py:98`)
  consults env var → file → default in that order.

**Environment variables (publicly named, no secrets quoted):**
- `CLAWTEAM_DATA_DIR`, `CLAWTEAM_USER`, `CLAWTEAM_TEAM_NAME`,
  `CLAWTEAM_DEFAULT_PROFILE`, `CLAWTEAM_TRANSPORT`, `CLAWTEAM_TASK_STORE`,
  `CLAWTEAM_WORKSPACE`, `CLAWTEAM_DEFAULT_BACKEND`,
  `CLAWTEAM_SKIP_PERMISSIONS`, `CLAWTEAM_TIMEZONE`, `CLAWTEAM_GOURCE_PATH`,
  `CLAWTEAM_GOURCE_RESOLUTION`, `CLAWTEAM_GOURCE_SECONDS_PER_DAY`,
  `CLAWTEAM_SPAWN_PROMPT_DELAY`, `CLAWTEAM_SPAWN_READY_TIMEOUT`
  (mapping in `clawteam/config.py:103`).
- Spawn-time agent context (set by `TmuxBackend.spawn`,
  `clawteam/spawn/tmux_backend.py:69`): `CLAWTEAM_AGENT_ID`,
  `CLAWTEAM_AGENT_NAME`, `CLAWTEAM_AGENT_TYPE`, `CLAWTEAM_TEAM_NAME`,
  `CLAWTEAM_AGENT_LEADER`, `CLAWTEAM_WORKSPACE_DIR`,
  `CLAWTEAM_CONTEXT_ENABLED`, `CLAWTEAM_BIN`.

**Project-local data directory (post-`2f13883`):**
- `clawteam/team/models.py:15` `get_data_dir()` resolves in this order:
  1. `CLAWTEAM_DATA_DIR` env var.
  2. `data_dir` field in `~/.clawteam/config.json`.
  3. Nearest `.clawteam/` walking up from `cwd` (git-style discovery via
     `_find_project_data_dir()`).
  4. `~/.clawteam/`.
- The current repo already contains a project-local store at
  `.clawteam/{costs,tasks,teams,workspaces}/`.

**Frontend build:**
- `clawteam/board/frontend/vite.config.ts` — alias `@` → `./src`, dev
  proxies `/api` to `localhost:8080`, build output to `../static`.
- `clawteam/board/frontend/tsconfig.json` and `tsconfig.app.json` —
  strict, `noUncheckedIndexedAccess`, `noUnusedLocals`, `noUnusedParameters`,
  `jsx: "react-jsx"`, path alias `@/* → ./src/*`.
- `clawteam/board/frontend/components.json` — shadcn generator config.

**Project metadata:**
- `pyproject.toml` — version `0.3.0`, MIT license, alpha development
  status, two console scripts (`clawteam`, `clawteam-mcp`).

**Build configs:**
- `pyproject.toml` `[build-system]` uses Hatchling, wheel target packages
  `["clawteam"]` (line 53).
- No build script for the frontend ships with the wheel; the assumption is
  that whoever ships a binary distribution runs `npm run build` first to
  populate `clawteam/board/static/`.

## Platform Requirements

**Development:**
- Python 3.10+ with `pip` or `uv`.
- Node 20+ (Vite 6 + React 19 require modern Node) and npm if rebuilding
  the dashboard.
- External binaries (looked up via `shutil.which`, all optional but
  feature-gated):
  - `tmux` — required for the default spawn backend (`clawteam/spawn/tmux_backend.py:58`,
    `clawteam/board/liveness.py:17`).
  - `git` — required for workspace isolation (`clawteam/workspace/git.py`).
  - `gource` — optional, gates `clawteam board gource`
    (`clawteam/board/gource.py:301`).
  - `ffmpeg` — optional, only when `clawteam board gource --export` is used
    (`clawteam/board/gource.py:363`).
  - `wsh` — optional, only when the `wsh` spawn backend is selected
    (`clawteam/spawn/wsh_backend.py:193`).
  - Per-agent CLIs (`claude`, `codex`, `gemini`, `kimi`, `qwen`, `opencode`,
    `nanobot`, `openclaw`, `pi`) — required at runtime for whichever agent
    profile is being launched (detected in
    `clawteam/spawn/adapters.py:106`–`172`).
- Tested OSes per CI matrix: `ubuntu-latest` and `macos-latest`
  (`.github/workflows/ci.yml:24`). Windows has partial support: subprocess
  backend has a Win32 PID-alive branch (`clawteam/spawn/registry.py:200`)
  but tmux/wsh backends are POSIX-only.

**Production:**
- ClawTeam ships as a CLI tool, not a service — there is no production
  deploy target. Users install the wheel locally and run agents on their
  own machine.
- The board dashboard is intended to bind to `127.0.0.1` by default
  (`clawteam/cli/commands.py:3514`); it is not hardened for public exposure.

---

*Stack analysis: 2026-04-28*
# Codebase Structure

**Analysis Date:** 2026-04-28

## Directory Layout

```
ClawTeam/
├── pyproject.toml                # hatchling build, declares `clawteam` + `clawteam-mcp` console scripts
├── uv.lock                       # uv lockfile (Python deps)
├── package.json                  # Trivial root package.json (no JS deps here)
├── package-lock.json
├── README.md / README_CN.md / README_KR.md
├── ROADMAP.md / LICENSE
├── board-*.png / verify-new-ui.png  # board screenshots (kept in repo for docs)
│
├── clawteam/                     # The Python package — primary source root
│   ├── __init__.py               # `__version__ = "0.3.0"`
│   ├── __main__.py               # `python -m clawteam` → CLI app
│   ├── config.py                 # `ClawTeamConfig`, `load_config`, `save_config`, `get_effective`
│   ├── identity.py               # `AgentIdentity` env round-trip
│   ├── paths.py                  # `validate_identifier`, `ensure_within_root`
│   ├── timefmt.py                # Timestamp display helpers
│   ├── fileutil.py               # `atomic_write_text`, `file_locked`
│   │
│   ├── cli/
│   │   ├── __init__.py
│   │   └── commands.py           # ~4700-line Typer app — all `clawteam <subcommand>` commands
│   │
│   ├── mcp/                      # FastMCP server
│   │   ├── __init__.py
│   │   ├── __main__.py           # `python -m clawteam.mcp` → server.main()
│   │   ├── server.py             # FastMCP wiring; registers each callable in TOOL_FUNCTIONS
│   │   ├── helpers.py            # `MCPToolError`, `translate_error`, `to_payload`, `require_team`
│   │   └── tools/
│   │       ├── __init__.py       # TOOL_FUNCTIONS list
│   │       ├── team.py           # team_list / team_get / team_create / team_member_add / ...
│   │       ├── task.py           # task_create / task_update / task_list / task_get / task_stats
│   │       ├── mailbox.py        # mailbox_send / broadcast / receive / peek / peek_count
│   │       ├── plan.py           # plan_submit / plan_get / plan_approve / plan_reject
│   │       ├── board.py          # board_overview / board_team
│   │       ├── cost.py           # cost_summary
│   │       └── workspace.py      # workspace_agent_diff / file_owners / cross_branch_log / agent_summary
│   │
│   ├── board/                    # Dashboard backend + bundled frontend
│   │   ├── __init__.py
│   │   ├── server.py             # ThreadingHTTPServer + REST + SSE + GitHub-allowlisted proxy
│   │   ├── collector.py          # BoardCollector — aggregates JSON snapshot for SSE
│   │   ├── liveness.py           # tmux_windows / agents_online (tier-2 liveness)
│   │   ├── renderer.py           # Terminal/text renderer for `clawteam board show`
│   │   ├── gource.py             # `clawteam board gource` git visualization helper
│   │   ├── static/               # Vite-built artefacts served by server.py
│   │   │   ├── index.html
│   │   │   └── assets/
│   │   │       ├── index-*.js
│   │   │       └── index-*.css
│   │   └── frontend/             # Source for the React + Vite + Tailwind + shadcn dashboard
│   │       ├── package.json      # React 19, @base-ui/react, @dnd-kit/react, Tailwind v4, Vite 6
│   │       ├── package-lock.json
│   │       ├── vite.config.ts    # alias `@` → src; dev proxy `/api` → :8080; build outDir=../static
│   │       ├── tsconfig.json / tsconfig.app.json / tsconfig.node.json
│   │       ├── components.json   # shadcn config
│   │       ├── index.html
│   │       └── src/
│   │           ├── main.tsx
│   │           ├── App.tsx       # Top-level shell + TeamContext
│   │           ├── index.css     # Tailwind v4 + theme tokens
│   │           ├── types.ts      # TeamData / Member / Task / Message + STATUS_* maps
│   │           ├── hooks/
│   │           │   └── use-team-stream.ts   # EventSource-backed SSE hook (tier-1 liveness)
│   │           ├── lib/
│   │           │   ├── api.ts    # fetchOverview / createTask / updateTask / addMember / sendMessage
│   │           │   └── utils.ts  # `cn` className helper
│   │           └── components/
│   │               ├── topbar.tsx
│   │               ├── summary-bar.tsx
│   │               ├── agent-registry.tsx
│   │               ├── message-stream.tsx
│   │               ├── peek-panel.tsx
│   │               ├── kanban/
│   │               │   ├── board.tsx
│   │               │   ├── column.tsx
│   │               │   └── task-card.tsx
│   │               ├── modals/
│   │               │   ├── add-agent.tsx
│   │               │   ├── inject-task.tsx
│   │               │   ├── send-message.tsx
│   │               │   └── set-context.tsx
│   │               └── ui/       # shadcn primitives (badge / button / card / dialog / input /
│   │                             #   label / scroll-area / select / sheet / textarea)
│   │
│   ├── events/
│   │   ├── __init__.py           # Re-exports event types and EventBus
│   │   ├── bus.py                # EventBus (sync emit + 2-worker async pool)
│   │   ├── global_bus.py         # `get_event_bus()` singleton + auto hook loading
│   │   ├── hooks.py              # HookManager — shell + python callable hooks
│   │   └── types.py              # All HarnessEvent dataclasses
│   │
│   ├── harness/                  # Plan-then-execute orchestration
│   │   ├── __init__.py
│   │   ├── orchestrator.py       # HarnessOrchestrator (state, gates, persistence)
│   │   ├── conductor.py          # HarnessConductor polling loop
│   │   ├── phases.py             # PhaseState + PhaseRunner + ArtifactRequiredGate / AllTasksCompleteGate / HumanApprovalGate
│   │   ├── roles.py              # PLANNER / EXECUTOR / EVALUATOR / LEADER + DEFAULT_ROLES
│   │   ├── strategies.py         # SpawnStrategy / RespawnStrategy / HealthStrategy / ExitNotifier / AssignmentStrategy ABCs
│   │   ├── spawner.py            # PhaseRoleSpawner — default SpawnStrategy
│   │   ├── prompts.py            # System-prompt builder for harness agents
│   │   ├── contracts.py          # SprintContract / SuccessCriterion
│   │   ├── contract_executor.py  # Materializes tasks from sprint contracts
│   │   ├── artifacts.py          # ArtifactStore — registers + reads phase artifacts on disk
│   │   ├── exit_journal.py       # FileExitJournal — cross-process worker exit signal
│   │   ├── context.py            # HarnessContext — capability bundle for plugins
│   │   └── context_recovery.py   # Resumes harness state after a crash
│   │
│   ├── plugins/
│   │   ├── __init__.py           # Re-exports HarnessPlugin
│   │   ├── base.py               # HarnessPlugin ABC — `on_register(ctx)`, `contribute_gates`, `contribute_prompts`
│   │   ├── manager.py            # PluginManager — discover from entry_points / config / {data_dir}/plugins/
│   │   └── ralph_loop_plugin.py  # Reference plugin (auto-respawn pattern)
│   │
│   ├── spawn/                    # Process-launching backends + adapters
│   │   ├── __init__.py           # `get_backend(name)` factory + `register_backend`
│   │   ├── base.py               # SpawnBackend ABC
│   │   ├── tmux_backend.py       # TmuxBackend + hardened injection helpers (pane_safe_to_inject,
│   │   │                         #   uuid paste-buffer names, _run_tmux return-code wrapper,
│   │   │                         #   pane_id-based runtime injection)
│   │   ├── subprocess_backend.py # SubprocessBackend — fire-and-forget Popen + on-exit hook
│   │   ├── wsh_backend.py        # WshBackend — TideTerm/WaveTerm blocks
│   │   ├── wsh_rpc.py            # JSON-RPC client used by wsh_backend
│   │   ├── adapters.py           # NativeCliAdapter — claude/codex/gemini/kimi/qwen/opencode/openclaw/pi/nanobot detection + flags
│   │   ├── prompt.py             # build_agent_prompt
│   │   ├── presets.py            # AgentPreset operations (shared endpoints)
│   │   ├── profiles.py           # AgentProfile operations (per-CLI runtime)
│   │   ├── command_validation.py # validate_spawn_command + normalize_spawn_command
│   │   ├── cli_env.py            # build_spawn_path, resolve_clawteam_executable
│   │   ├── registry.py           # spawn_registry.json — register_agent / is_agent_alive / list_dead_agents / list_zombie_agents / stop_agent (tier-3 liveness)
│   │   └── sessions.py           # SessionStore — persist/resume per-agent session state
│   │
│   ├── store/
│   │   ├── __init__.py           # `get_task_store(team_name, backend)` factory
│   │   ├── base.py               # BaseTaskStore ABC + TaskLockError
│   │   └── file.py               # FileTaskStore — fcntl/msvcrt-locked JSON-per-task store
│   │
│   ├── team/                     # Domain layer — teams, mailboxes, tasks, plans, lifecycle
│   │   ├── __init__.py           # Re-exports + lazy `TaskStore`
│   │   ├── manager.py            # TeamManager — create / discover / add_member / cleanup / inbox name resolution
│   │   ├── models.py             # TeamMember / TeamConfig / TeamMessage / TaskItem + enums + get_data_dir()
│   │   ├── tasks.py              # Compatibility shim → store.file.FileTaskStore
│   │   ├── mailbox.py            # MailboxManager — send / broadcast / peek / receive + event-log mirroring
│   │   ├── plan.py               # PlanManager — submit / approve / reject
│   │   ├── lifecycle.py          # LifecycleManager — shutdown protocol + idle notification
│   │   ├── snapshot.py           # Save/restore team configuration snapshots
│   │   ├── waiter.py             # Block until task condition (used by `task wait`)
│   │   ├── watcher.py            # InboxWatcher — `inbox watch` / `runtime watch` polling loop
│   │   ├── router.py             # RuntimeRouter — message → envelope → dispatch
│   │   ├── routing_policy.py     # DefaultRoutingPolicy + RuntimeEnvelope + RouteDecision
│   │   └── costs.py              # CostStore — per-event cost ledger + budget summary
│   │
│   ├── transport/
│   │   ├── __init__.py           # `get_transport(name, team_name, **kwargs)` factory
│   │   ├── base.py               # Transport ABC
│   │   ├── claimed.py            # ClaimedMessage — at-least-once ack/quarantine wrapper
│   │   ├── file.py               # FileTransport — inbox-dir backend (default)
│   │   └── p2p.py                # P2PTransport — pyzmq PUSH/PULL with file fallback
│   │
│   ├── workspace/                # Git worktree isolation per agent
│   │   ├── __init__.py           # `get_workspace_manager(repo_path)` helper
│   │   ├── manager.py            # WorkspaceManager — create / checkpoint / merge / cleanup
│   │   ├── git.py                # Thin wrappers over `git worktree`, `git diff`, etc.
│   │   ├── models.py             # WorkspaceInfo, WorkspaceRegistry
│   │   ├── conflicts.py          # detect_overlaps — file-level conflict summary
│   │   └── context.py            # Diff/log/file-ownership helpers behind `clawteam context`
│   │
│   └── templates/                # Built-in TOML team blueprints used by `clawteam launch`
│       ├── __init__.py
│       ├── code-review.toml
│       ├── harness-default.toml
│       ├── hedge-fund.toml
│       ├── research-paper.toml
│       ├── software-dev.toml
│       └── strategy-room.toml
│
├── scripts/                      # Repo-level shell helpers
│   └── openclaw_worker.sh
│
├── tests/                        # pytest suite — one test module per source module
│   ├── conftest.py
│   ├── __init__.py
│   ├── board/
│   │   └── test_liveness.py
│   ├── test_adapters.py
│   ├── test_board.py
│   ├── test_cli_commands.py
│   ├── test_config.py
│   ├── test_context.py
│   ├── test_costs.py
│   ├── test_data_dir.py
│   ├── test_event_bus.py
│   ├── test_fileutil.py
│   ├── test_gource.py
│   ├── test_harness.py
│   ├── test_identity.py
│   ├── test_inbox_routing.py
│   ├── test_lifecycle.py
│   ├── test_mailbox.py
│   ├── test_manager.py
│   ├── test_mcp_server.py
│   ├── test_mcp_tools.py
│   ├── test_models.py
│   ├── test_plan_storage.py
│   ├── test_presets.py
│   ├── test_profiles.py
│   ├── test_prompt.py
│   ├── test_registry.py
│   ├── test_runtime_routing.py
│   ├── test_snapshots.py
│   ├── test_spawn_backends.py
│   ├── test_spawn_cli.py
│   ├── test_store.py
│   ├── test_tasks.py
│   ├── test_task_store_locking.py
│   ├── test_templates.py
│   ├── test_timefmt.py
│   ├── test_tmux_injection.py
│   ├── test_waiter.py
│   ├── test_workspace_manager.py
│   └── test_wsh_backend.py
│
├── skills/                       # Repo-tracked Claude / Agent skill bundle
│   ├── skills-lock.json
│   └── clawteam/
│       ├── SKILL.md
│       ├── agents/openai.yaml
│       └── references/
│           ├── cli-reference.md
│           └── workflows.md
│
├── .claude/skills/               # Project-local skills consumed by Claude Code
│   ├── clawteam-dev/
│   │   ├── SKILL.md              # Dev bootstrap + smoke-test recipes
│   │   └── scripts/
│   │       ├── bootstrap_clawteam_dev.sh
│   │       └── link_local_clawteam_skills.sh
│   └── frontend-design/
│       ├── SKILL.md
│       └── LICENSE.txt
│
├── .agents/skills/               # Mirror of .claude/skills/ for non-Claude agents
│   ├── clawteam-dev/...
│   └── frontend-design/...
│
├── .clawteam/                    # Project-local data dir (picked up by get_data_dir() walk-up)
│   ├── teams/
│   │   ├── board-test/{config.json, events/, inboxes/{leader,reviewer1,worker1}/}
│   │   └── verify-test/{config.json, events/, inboxes/leader/}
│   ├── tasks/{board-test/, verify-test/}
│   ├── costs/{board-test/, verify-test/}
│   └── workspaces/
│
├── docs/                         # Public docs site (GitHub Pages)
│   ├── index.html / .nojekyll / CNAME
│   ├── board-usage.md
│   ├── transport-architecture.md
│   ├── site-assets/
│   ├── skills/clawteam/{SKILL.md, references/}
│   └── superpowers/{plans/, specs/}
│
├── website/                      # Vite landing-page source (separate from board frontend)
│   ├── index.html
│   ├── vite.config.mjs
│   └── src/{App.jsx, main.jsx, styles.css}
│
├── assets/                       # Static images referenced by README / docs
│
├── .planning/codebase/           # GSD codebase mapping output (this folder)
│
├── .github/workflows/ci.yml      # CI: ruff + pytest
└── .playwright-mcp/              # Captured screenshots from Playwright MCP runs
```

## Directory Purposes

**`clawteam/` (top-level Python package):**
- Purpose: Everything imported by the `clawteam` and `clawteam-mcp` console scripts.
- Contains: One subpackage per major concern (cli, mcp, board, events, harness, plugins, spawn, store, team, transport, workspace, templates).
- Key files: `clawteam/__main__.py`, `clawteam/config.py`, `clawteam/identity.py`, `clawteam/paths.py`.

**`clawteam/cli/`:**
- Purpose: All Typer-based command-line entry points.
- Contains: A single `commands.py` (large by design) that defines `app` and ~20 sub-Typer apps (`config`, `preset`, `profile`, `team`, `inbox`, `runtime`, `task`, `cost`, `session`, `plan`, `lifecycle`, `identity`, `board`, `workspace`, `context`, `template`, `hook`, `plugin`, `harness`).

**`clawteam/mcp/`:**
- Purpose: FastMCP server adapter so any MCP-compatible host can drive ClawTeam.
- Contains: `server.py` (registers each callable from `TOOL_FUNCTIONS`), `helpers.py` (error translation, payload coercion, common require_team), `tools/` (one module per domain).

**`clawteam/board/`:**
- Purpose: Read/write dashboard for the local data dir.
- Contains: `server.py` (HTTP+SSE+proxy), `collector.py` (JSON snapshot), `liveness.py` (tmux window probe), `renderer.py` (terminal renderer), `gource.py` (visualization), pre-built `static/` for serving, and `frontend/` source.

**`clawteam/board/frontend/`:**
- Purpose: React 19 + Vite 6 + Tailwind v4 + shadcn (Radix-based) SPA.
- Contains: `vite.config.ts` (build output goes to `../static`), `src/App.tsx` shell, the `useTeamStream` SSE hook, four modal dialogs, kanban subcomponents, and a `ui/` folder with shadcn primitives.

**`clawteam/events/`:**
- Purpose: Process-local pub/sub spine.
- Contains: `bus.py` (`EventBus`), `global_bus.py` (singleton + auto hook load), `hooks.py` (shell+python hook handlers), `types.py` (all event dataclasses).

**`clawteam/harness/`:**
- Purpose: Plan-then-execute orchestration around the team layer.
- Contains: `phases.py` (state machine), `orchestrator.py` (high-level control), `conductor.py` (foreground polling loop), `spawner.py` / `roles.py` / `strategies.py` / `prompts.py`, contracts + artifacts + exit-journal helpers, plugin `context.py`.

**`clawteam/plugins/`:**
- Purpose: Plugin extension surface.
- Contains: `base.py` (`HarnessPlugin` ABC), `manager.py` (`PluginManager` discovery + load), `ralph_loop_plugin.py` (reference implementation).

**`clawteam/spawn/`:**
- Purpose: Run agent processes and keep track of them.
- Contains: Three backends (`tmux_backend.py`, `subprocess_backend.py`, `wsh_backend.py`), CLI adapter logic (`adapters.py`), prompt builder, presets/profiles, command validation, environment + executable resolution helpers, spawn registry (durable JSON), session store.

**`clawteam/store/`:**
- Purpose: Pluggable task storage.
- Contains: `base.py` (interface + `TaskLockError`) and `file.py` (default JSON-per-task implementation).

**`clawteam/team/`:**
- Purpose: Domain layer (the things humans say "teams" and "tasks" about).
- Contains: Pydantic models, manager (CRUD + cleanup), mailbox (send/broadcast/receive + event log), plan / lifecycle / costs / waiter / snapshot, runtime router + policy, inbox watcher.

**`clawteam/transport/`:**
- Purpose: Pluggable message-bytes movement.
- Contains: ABC + `claimed.py` (ack/quarantine), `file.py` default, `p2p.py` (pyzmq, optional extra).

**`clawteam/workspace/`:**
- Purpose: Per-agent git worktree management for isolated parallel edits.
- Contains: `manager.py` (worktree lifecycle), `git.py` (subprocess wrappers), `models.py`, `conflicts.py` (cross-agent file overlap detection), `context.py` (diff / log / blame helpers exposed under `clawteam context`).

**`clawteam/templates/`:**
- Purpose: TOML team blueprints used by `clawteam launch`.
- Contains: One `*.toml` per archetype (software-dev, code-review, hedge-fund, research-paper, strategy-room, harness-default).

**`tests/`:**
- Purpose: pytest suite. Naming convention: `test_<module>.py` mirrors `clawteam/<module>.py`.
- Contains: Unit tests for every subsystem; `tests/board/` mirrors `clawteam/board/`. Includes `test_tmux_injection.py` covering the hardened injection paths and `test_data_dir.py` covering the project-local walk-up.

**`scripts/`:**
- Purpose: Repo-level shell utilities outside the Python package.
- Contains: `openclaw_worker.sh`.

**`skills/clawteam/` and `.claude/skills/`, `.agents/skills/`:**
- Purpose: Skill bundles consumed by Claude Code / generic agents working inside this repo.
- Contains: `SKILL.md` plus references and bootstrap scripts (`bootstrap_clawteam_dev.sh`, `link_local_clawteam_skills.sh`).

**`docs/` and `website/`:**
- Purpose: Public-facing GitHub Pages site (`docs/`) and a separate Vite landing page source (`website/`). Distinct from the board UI under `clawteam/board/frontend/`.

**`.clawteam/`:**
- Purpose: Project-local data dir captured by `get_data_dir()`'s walk-up. Generated by running `clawteam` commands inside this repo.
- Generated: Yes (by CLI usage).
- Committed: Currently tracked, contains transient test team state. Treat as scratch.

**`.planning/codebase/`:**
- Purpose: GSD-generated codebase analysis documents (this directory).
- Contains: ARCHITECTURE.md, STRUCTURE.md (and any future maps). Do not place runtime code here.

## Key File Locations

**Entry points:**
- `clawteam/cli/commands.py` — `app = typer.Typer(...)` plus every subcommand. `pyproject.toml` registers it as the `clawteam` console script.
- `clawteam/__main__.py` — `python -m clawteam` shim that re-exports `app`.
- `clawteam/mcp/server.py` — `main()` registered as the `clawteam-mcp` console script; also `python -m clawteam.mcp` via `clawteam/mcp/__main__.py`.
- `clawteam/board/server.py` — `serve(host, port, default_team, interval)` invoked by `clawteam board serve`.

**Configuration:**
- `pyproject.toml` — package metadata, dependencies, console scripts, ruff and pytest settings.
- `clawteam/config.py` — `ClawTeamConfig` Pydantic model + `~/.clawteam/config.json` reader/writer.
- `~/.clawteam/config.json` — user-level config (NOT affected by `data_dir` overrides).
- `clawteam/board/frontend/vite.config.ts` — frontend build/dev config (build outDir = `../static`, dev `/api` proxy → `:8080`).
- `clawteam/board/frontend/components.json` — shadcn component config.
- `.github/workflows/ci.yml` — ruff + pytest CI pipeline.

**Core logic:**
- `clawteam/team/models.py` — `TeamConfig`, `TeamMember`, `TeamMessage`, `TaskItem`, all enums, `get_data_dir()` (project-local walk-up).
- `clawteam/team/manager.py` — TeamManager CRUD façade.
- `clawteam/team/mailbox.py` — `MailboxManager.send / broadcast / receive`.
- `clawteam/store/file.py` — locked, atomic per-task JSON store.
- `clawteam/spawn/tmux_backend.py` — primary spawn backend; contains the hardened tmux injection helpers (`_pane_safe_to_inject`, `_inject_prompt_via_buffer`, `_run_tmux`, `inject_runtime_message`).
- `clawteam/spawn/registry.py` — durable per-team `spawn_registry.json` (tier-3 liveness).
- `clawteam/board/collector.py` — produces the JSON consumed by the dashboard SSE stream.
- `clawteam/board/liveness.py` — tier-2 liveness (`agents_online`).
- `clawteam/board/frontend/src/hooks/use-team-stream.ts` — tier-1 liveness via `EventSource`.
- `clawteam/team/router.py` + `clawteam/team/routing_policy.py` — runtime injection routing.
- `clawteam/harness/orchestrator.py` + `clawteam/harness/phases.py` — phase state machine and gates.
- `clawteam/events/bus.py` + `clawteam/events/global_bus.py` — event spine.
- `clawteam/workspace/manager.py` — git worktree manager.

**Testing:**
- `tests/conftest.py` — shared pytest fixtures.
- `tests/test_tmux_injection.py` — covers `_pane_safe_to_inject`, paste-buffer uniqueness, return-code wrapper.
- `tests/test_data_dir.py` — covers project-local walk-up.
- `tests/test_runtime_routing.py` — covers `RuntimeRouter` + `DefaultRoutingPolicy`.
- `tests/test_mcp_server.py`, `tests/test_mcp_tools.py` — FastMCP wiring.

## Naming Conventions

**Files:**
- Python: `snake_case.py` (one module per concern). The only deliberately giant file is `clawteam/cli/commands.py` (Typer subcommand registry).
- TypeScript / React: `kebab-case.tsx` for components and hooks (`use-team-stream.ts`, `agent-registry.tsx`, `task-card.tsx`).
- shadcn UI primitives: lowercase singular (`button.tsx`, `dialog.tsx`).
- Tests mirror source: `clawteam/team/manager.py` → `tests/test_manager.py`, `clawteam/board/liveness.py` → `tests/board/test_liveness.py`.

**Directories:**
- Python subpackages: `snake_case`. Names are concise nouns (`spawn`, `store`, `team`, `transport`, `workspace`, `harness`).
- Frontend: `kebab-case` and topical (`kanban/`, `modals/`, `ui/`, `hooks/`, `lib/`).

**Identifiers used as filesystem path segments (team names, agent names, user names):**
- Must match `^[A-Za-z0-9._-]+$` (`clawteam/paths.py:_IDENTIFIER_RE`). Anything else raises `ValueError` from `validate_identifier`.

**Tmux session naming:**
- `clawteam-{team}` (`TmuxBackend.session_name`). Each agent gets a window named after the member.

**Branch naming for workspaces:**
- `clawteam/{team_name}/{agent_name}` (`clawteam/workspace/manager.py:73`).

**Inbox naming:**
- `{user}_{name}` when `user` is set on the member, else `{name}` (`TeamManager.inbox_name_for`).

## Where to Add New Code

**A new CLI command:**
- Decide which sub-app it belongs to. Existing sub-apps live in `clawteam/cli/commands.py` and are declared with `app.add_typer(<name>_app, name="...")` blocks.
- Add an `@<subapp>.command("...")` function near sibling commands (search for the existing sub-app's first command).
- Update `tests/test_cli_commands.py`. Use the Typer `CliRunner` pattern already established there.
- If the command needs domain logic, put the logic on the relevant manager (`TeamManager`, `MailboxManager`, `WorkspaceManager`, etc.) and keep the CLI handler thin.

**A new MCP tool:**
- Implement the callable in the appropriate `clawteam/mcp/tools/<domain>.py` (or create a new module if the domain is new). Use `helpers.require_team`, `helpers.task_store`, `helpers.team_mailbox`, and `helpers.to_payload` for boilerplate.
- Add the function to `TOOL_FUNCTIONS` in `clawteam/mcp/tools/__init__.py`.
- Add a test in `tests/test_mcp_tools.py` (and `tests/test_mcp_server.py` if you want to verify the FastMCP registration).

**A new spawn backend:**
- Add `clawteam/spawn/<name>_backend.py` implementing `SpawnBackend`.
- Wire it into `clawteam/spawn/__init__.py:get_backend`.
- If it should support runtime injection, add `inject_runtime_message(self, team, agent_name, envelope) -> tuple[bool, str]` (see `TmuxBackend.inject_runtime_message`).
- Always call `clawteam.spawn.registry.register_agent` after a successful spawn; emit `AfterWorkerSpawn` on the global bus.
- Add a test in `tests/test_spawn_backends.py` (or a sibling file mirroring the existing `test_wsh_backend.py`).

**A new transport:**
- Add `clawteam/transport/<name>.py` implementing `Transport`.
- Wire it in `clawteam/transport/__init__.py:get_transport`.
- If you need at-least-once delivery, expose a `claim_messages(agent_name, limit) -> list[ClaimedMessage]` method (see `clawteam/transport/file.py`).

**A new task store backend:**
- Add `clawteam/store/<backend>.py` implementing `BaseTaskStore`. Own your concurrency (locks, transactions).
- Wire it through `clawteam/store/__init__.py:get_task_store`.
- Re-export under `clawteam/team/tasks.py` if you need backwards-compat.

**A new harness phase or gate:**
- Add a `Phase` constant (`clawteam/harness/phases.py`) and (if relevant) a `PhaseGate` subclass.
- Register the gate in `HarnessOrchestrator.__init__` (`clawteam/harness/orchestrator.py`) or via a plugin's `contribute_gates()`.

**A new event type:**
- Add a `@dataclass` in `clawteam/events/types.py` inheriting `HarnessEvent`.
- Re-export from `clawteam/events/__init__.py` if it should be discoverable.
- Plugin-provided event types must call `clawteam.events.bus.register_event_type(cls)` so shell hooks can reference them by name.

**A new plugin:**
- Create a module that defines a `HarnessPlugin` subclass (see `clawteam/plugins/ralph_loop_plugin.py`).
- Distribute via a `clawteam.plugins` entry point, or list its dotted module path in `ClawTeamConfig.plugins`, or drop it under `{data_dir}/plugins/<name>/` with a `plugin.json`.

**A new dashboard panel / dialog:**
- Frontend source: add components under `clawteam/board/frontend/src/components/` (use `kebab-case.tsx`). Reuse primitives from `components/ui/`.
- Hooks live under `src/hooks/`; API calls live in `src/lib/api.ts`.
- Backend support: extend `BoardCollector.collect_team` if you need new fields in the SSE payload, or add a new endpoint in `BoardHandler.do_GET / do_POST / do_PATCH`.
- After changes: rebuild the frontend (`npm run build` from `clawteam/board/frontend/`) so `clawteam/board/static/` reflects the new bundle.

**A new built-in team template:**
- Drop a `<archetype>.toml` under `clawteam/templates/` (mirror `software-dev.toml`'s shape). Add a fixture-based test in `tests/test_templates.py`.

**Tests:**
- One `tests/test_<module>.py` per source module — mirror the package layout. Place board-frontend-specific Python tests under `tests/board/`.

## Special Directories

**`clawteam/board/static/`:**
- Purpose: Pre-built Vite output (HTML + hashed assets) bundled into the wheel and served at runtime.
- Generated: Yes — output of `npm run build` from `clawteam/board/frontend/`.
- Committed: Yes — keeps the package self-contained so end users do not need Node to run `clawteam board serve`.

**`.clawteam/`:**
- Purpose: Project-local data dir (target of the `get_data_dir()` walk-up when running CLI commands inside this repo).
- Generated: Yes — by CLI runs inside the repo.
- Committed: Currently tracked (smoke-test residue); treat its contents as ephemeral.

**`.playwright-mcp/`:**
- Purpose: Screenshots captured by Playwright MCP runs while exercising the dashboard.
- Generated: Yes.
- Committed: Yes (visual regression record).

**`.venv/`:**
- Purpose: Local uv-managed virtualenv.
- Generated: Yes.
- Committed: No (in `.gitignore`).

**`.planning/codebase/`:**
- Purpose: GSD codebase mapping output (the documents you are reading).
- Generated: Yes — by `/gsd-map-codebase` runs.
- Committed: Yes.

---

*Structure analysis: 2026-04-28*
# Testing Patterns

**Analysis Date:** 2026-04-28

ClawTeam ships a single Python test suite under `tests/`. There is **no
JavaScript/TypeScript test runner** in the repository — the React board has no
unit tests, no Vitest config, no Jest config, no Playwright. All quality gates
for the frontend are: `tsc -b` (typecheck) and `vite build` (bundle).
Frontend behavior is exercised indirectly through the Python server-side tests
in `tests/test_board.py`, which assert on the rendered `index.html` shape and
the JSON API contracts the SPA consumes.

The Plane integration was removed in commit `427475a`; the live tree contains
**no** `tests/test_plane_*.py` files. Older `*.stale` planning docs are stale
and should be ignored.

---

## Test Framework

**Runner:**
- pytest `>=9.0.0,<10.0.0` (declared as a dev extra in
  `pyproject.toml` `[project.optional-dependencies].dev`)
- Configured in `pyproject.toml`:
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  ```
  No `addopts`, no `markers`, no `pythonpath` overrides. Defaults apply.

**Assertion Library:**
- Plain `assert` statements. pytest's assertion rewriting handles diffing.

**Mocking:**
- Built-in pytest `monkeypatch` fixture — preferred for env vars,
  attributes on imported modules, `chdir`, and stubbing module-level
  callables.
- `unittest.mock.patch` / `MagicMock` — used when you need a context-manager
  patch, a parametrized side_effect, or a fake object with auto-spec'd
  attributes. Imported at the top of the file:
  `from unittest.mock import MagicMock, patch`
  (see `tests/test_tmux_injection.py:5`, `tests/board/test_liveness.py:6`,
  `tests/test_waiter.py:6`, `tests/test_tasks.py:3`).

**CLI runner:**
- `from typer.testing import CliRunner` for end-to-end CLI tests against
  `clawteam.cli.commands:app`. Used in `tests/test_spawn_cli.py`,
  `tests/test_cli_commands.py`, `tests/test_inbox_routing.py`,
  `tests/test_profiles.py`, `tests/test_presets.py`.

**Run Commands:**

```bash
# Install with dev extras
pip install -e ".[dev]"

# Run the full suite
pytest

# Run a single file
pytest tests/test_tmux_injection.py

# Run a single test
pytest tests/test_data_dir.py::test_walks_up_from_cwd_to_find_project_dotclawteam

# Verbose, with the assertion failure context
pytest -vv

# Lint (separate from tests)
ruff check .
```

There is no coverage configuration — coverage is not currently enforced.

---

## Test File Organization

**Location:** Separate `tests/` directory at the repo root.

**Tree (live, post Plane-removal):**

```
tests/
├── __init__.py                    # makes tests/ a package
├── conftest.py                    # shared fixtures (autouse data-dir isolation)
├── test_adapters.py
├── test_board.py
├── test_cli_commands.py
├── test_config.py
├── test_context.py
├── test_costs.py
├── test_data_dir.py               # NEW on this branch: get_data_dir walk-up
├── test_event_bus.py
├── test_fileutil.py
├── test_gource.py
├── test_harness.py
├── test_identity.py
├── test_inbox_routing.py
├── test_lifecycle.py
├── test_mailbox.py
├── test_manager.py
├── test_mcp_server.py
├── test_mcp_tools.py
├── test_models.py
├── test_plan_storage.py
├── test_presets.py
├── test_profiles.py
├── test_prompt.py
├── test_registry.py
├── test_runtime_routing.py
├── test_snapshots.py
├── test_spawn_backends.py         # 1489 lines — the largest file
├── test_spawn_cli.py
├── test_store.py
├── test_task_store_locking.py
├── test_tasks.py
├── test_templates.py
├── test_timefmt.py
├── test_tmux_injection.py         # NEW on this branch: 28 tmux-injection tests
├── test_waiter.py
├── test_workspace_manager.py
├── test_wsh_backend.py
└── board/
    ├── __init__.py
    └── test_liveness.py           # NEW on this branch: tmux liveness probes
```

A nested `tests/board/` package mirrors `clawteam/board/`. Going forward,
prefer subdirectories (`tests/<subsystem>/`) over flat `test_<subsystem>_*.py`
filenames when a subsystem grows beyond ~3 files. The `board/` subpackage
sets the precedent — add `__init__.py` so pytest can collect it as a
package.

**File naming:** `test_<module>.py` — one file per module under test, plus
larger integration-style files for cross-cutting flows (`test_runtime_routing.py`,
`test_inbox_routing.py`).

**Test naming:** `def test_<behavior_in_snake_case>():`. Names describe the
*behavior under test* and are usually a full sentence:

- `test_pane_safe_to_inject_returns_false_for_shells_and_tuis`
- `test_inject_uses_recorded_pane_id_when_available`
- `test_walks_up_from_cwd_to_find_project_dotclawteam`
- `test_falls_back_to_home_when_no_project_found`
- `test_collect_overview_does_not_call_collect_team`
- `test_team_start_spawns_runtime_watcher_for_leader`

---

## Test Structure

### Module header

Every test module begins with a one-line docstring naming the module under
test, followed by `from __future__ import annotations` when the file uses
PEP 604 union syntax in annotations:

```python
"""Tests for the tmux runtime injection safety guards."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from clawteam.spawn import tmux_backend
```

(`tests/test_tmux_injection.py:1-10`)

### Two organization styles in use

**Style A — Class grouping by feature** (preferred for medium/large files):

```python
class TestTaskCreate:
    def test_create_basic(self, store):
        t = store.create("Write tests", description="pytest suite")
        assert t.subject == "Write tests"
        assert t.status == TaskStatus.pending

    def test_create_with_priority(self, store):
        t = store.create("urgent item", priority=TaskPriority.urgent)
        assert t.priority == TaskPriority.urgent


class TestTaskGet:
    def test_get_existing(self, store): ...
    def test_get_nonexistent(self, store): ...
```

(`tests/test_tasks.py:16`, also `tests/test_models.py:17`,
`tests/test_mailbox.py:40`, `tests/test_fileutil.py:11`,
`tests/test_waiter.py:52`)

Classes are bare (no `unittest.TestCase` inheritance) so pytest fixtures
work transparently. Class names follow `Test<Feature>` and tests inside use
the same `test_<behavior>` style.

**Style B — Top-level functions** (for small, focused files):

```python
def test_env_var_wins(tmp_path, monkeypatch):
    forced = tmp_path / "forced"
    monkeypatch.setenv("CLAWTEAM_DATA_DIR", str(forced))
    monkeypatch.chdir(tmp_path)

    from clawteam.team import models
    assert models.get_data_dir() == forced
```

(`tests/test_data_dir.py:30`, also `tests/test_tmux_injection.py`,
`tests/board/test_liveness.py`, `tests/test_spawn_cli.py`)

Both styles coexist — pick the one that keeps the file readable. Flat test
functions are fine when there's no shared setup; classes are preferred when
tests group naturally around a CRUD verb or scenario.

### Single behavior per test, AAA layout

Each test exercises one behavior. The Arrange-Act-Assert pattern is followed
implicitly:

```python
def test_inject_uses_recorded_pane_id_when_available(monkeypatch):
    # Arrange
    backend = tmux_backend.TmuxBackend()
    backend._agents[("demo", "leader")] = {
        "target": "clawteam-demo:leader",
        "pane_id": "%42",
    }
    envelope = MagicMock(summary="hi", source="w", target="leader", …)

    seen_targets = []
    def fake_run(cmd, *args, **kwargs):
        if "list-panes" in cmd:
            seen_targets.append(cmd[cmd.index("-t") + 1])
            return _completed(stdout="%42\n")
        …
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/tmux")
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("time.sleep", lambda _x: None)

    # Act
    ok, _ = backend.inject_runtime_message("demo", "leader", envelope)

    # Assert
    assert ok is True
    assert all(t == "%42" for t in seen_targets), seen_targets
```

(`tests/test_tmux_injection.py:132`)

---

## Fixtures

### `tests/conftest.py` — autouse data-dir isolation

The single shared conftest is small and aggressive. Every test gets a
clean `~/.clawteam/` rooted in `tmp_path`, automatically:

```python
import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Point CLAWTEAM_DATA_DIR at a temp dir so every test gets a clean slate."""
    data_dir = tmp_path / ".clawteam"
    data_dir.mkdir()
    monkeypatch.setenv("CLAWTEAM_DATA_DIR", str(data_dir))
    # Also override HOME so config_path() doesn't hit real ~/.clawteam/config.json
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return data_dir


@pytest.fixture
def team_name():
    return "test-team"
```

(`tests/conftest.py:1-25`)

**Implications when writing new tests:**

- You **never** need to set `CLAWTEAM_DATA_DIR` yourself for happy-path tests.
- You **never** touch the developer's real `~/.clawteam/`. If a test asserts
  on filesystem state, it's looking at `tmp_path / ".clawteam"`.
- `HOME` and `USERPROFILE` are also redirected — code reading
  `Path.home()` is safe.
- If your test specifically needs to exercise the project-local walk-up
  resolution in `get_data_dir()`, you must override the autouse fixture
  with a local `clean_env` that `monkeypatch.delenv("CLAWTEAM_DATA_DIR",
  raising=False)` — see `tests/test_data_dir.py:11-27` for the canonical
  shape, including the `shutil.rmtree(stray)` step that clears the stray
  `.clawteam/` the autouse fixture pre-creates.

### Common per-file fixtures

```python
@pytest.fixture
def store(team_name):
    return TaskStore(team_name)
```

(`tests/test_tasks.py:11`)

```python
@pytest.fixture
def mailbox():
    m = MagicMock()
    m.receive.return_value = []
    return m

@pytest.fixture
def store():
    s = MagicMock()
    s.list_tasks.return_value = []
    return s

@pytest.fixture
def waiter(mailbox, store):
    return TaskWaiter(
        team_name="test-team",
        agent_name="leader",
        mailbox=mailbox,
        task_store=store,
        poll_interval=0.01,
    )
```

(`tests/test_waiter.py:27-49`)

Fixtures live next to the tests that use them — only the data-dir isolation
is global. Don't promote a fixture to `conftest.py` unless three or more
files actually share it.

---

## Mocking Patterns

### `monkeypatch.setenv` for environment-driven code paths

```python
def test_walks_up_from_cwd_to_find_project_dotclawteam(tmp_path, monkeypatch):
    project = tmp_path / "myrepo"
    (project / ".clawteam").mkdir(parents=True)
    nested = project / "src" / "deep" / "nested"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    from clawteam.team import models
    assert models.get_data_dir() == project / ".clawteam"
```

(`tests/test_data_dir.py:39`)

`monkeypatch.chdir`, `monkeypatch.setenv` / `delenv`, and `monkeypatch.setattr`
on stdlib paths (`subprocess.run`, `os.replace`, `time.sleep`) are the
workhorses.

### `unittest.mock.patch` for context-managed and parametrized stubs

```python
@pytest.mark.parametrize("cmd", ["bash", "zsh", "fish", "sh", "less", "vim", "fzf", "tmux"])
def test_pane_safe_to_inject_returns_false_for_shells_and_tuis(cmd):
    with patch("subprocess.run", return_value=_completed(stdout=f"{cmd}\n")):
        assert tmux_backend._pane_safe_to_inject("session:0") is False
```

(`tests/test_tmux_injection.py:17`)

```python
def test_tmux_windows_returns_window_names_when_session_exists():
    with patch("shutil.which", return_value="/usr/bin/tmux"), \
         patch("subprocess.run", side_effect=_fake_run("leader\ncoder-1\n")):
        assert liveness.tmux_windows("my-swarm") == {"leader", "coder-1"}
```

(`tests/board/test_liveness.py:22`)

Use `patch(...)` context managers when:
- you want a `@pytest.mark.parametrize`'d patch,
- you patch two cooperating callables (`shutil.which` + `subprocess.run`)
  for the duration of one assertion,
- the patched symbol is referenced as a string path
  (`"clawteam.board.server.urllib.request.build_opener"`).

Use `monkeypatch.setattr(...)` when:
- the patch should last the whole test (no `with` indent),
- you're patching attributes on an *imported module object*
  (e.g. `monkeypatch.setattr(subprocess, "run", fake_run)`).

### Fake subprocess with a `_completed` helper

The tmux-heavy tests share a tiny helper to build `subprocess.CompletedProcess`
objects:

```python
def _completed(stdout: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def fake_run(cmd, *args, **kwargs):
    if "list-panes" in cmd:
        return _completed(stdout="%1\n")
    if "display-message" in cmd:
        return _completed(stdout="claude\n")
    if "paste-buffer" in cmd:
        return _completed(returncode=1)
    return _completed()
```

(`tests/test_tmux_injection.py:13`, also `tests/board/test_liveness.py:11`)

Pattern: dispatch on a substring of `cmd` (the argv list passed to
`subprocess.run`). Each test asserts on the side-effecting argv either via
`returncode=1` to drive failure paths or by appending to a `seen_targets`
list closed over by the fake.

For unique-buffer-per-call assertions, capture every invocation:

```python
def test_inject_uses_unique_buffer_name_per_call(monkeypatch):
    calls = []
    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)
        return _completed()
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("time.sleep", lambda _x: None)

    tmux_backend._inject_prompt_via_buffer("session:0", "leader", "first")
    tmux_backend._inject_prompt_via_buffer("session:0", "leader", "second")

    buf_names = [
        cmd[cmd.index("-b") + 1]
        for cmd in calls
        if isinstance(cmd, list) and "-b" in cmd
    ]
    assert len(set(buf_names)) >= 2, f"buffer names collided: {buf_names}"
```

(`tests/test_tmux_injection.py:59`) — note the `monkeypatch.setattr("time.sleep",
lambda _x: None)` to keep the test fast.

### Stubbing static / class methods on managers

```python
monkeypatch.setattr(TeamManager, "discover_teams", staticmethod(fake_discover))
monkeypatch.setattr(BoardCollector, "collect_team_summary", fake_summary)
```

(`tests/test_board.py:208-209`)

When monkeypatching a `@staticmethod`, wrap the replacement in
`staticmethod(...)` so attribute access produces an unbound callable.

### Asserting on raised exceptions

```python
def test_inject_raises_when_load_buffer_fails(monkeypatch):
    def fake_run(cmd, *args, **kwargs):
        if "load-buffer" in cmd:
            return _completed(returncode=1)
        return _completed()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("time.sleep", lambda _x: None)

    with pytest.raises(RuntimeError, match="load-buffer"):
        tmux_backend._inject_prompt_via_buffer("session:0", "leader", "x")
```

(`tests/test_tmux_injection.py:80`)

Always pass `match=` so the test fails on the wrong-but-still-RuntimeError case.

---

## Typer CLI Tests

End-to-end CLI tests construct a `CliRunner`, invoke `app` with argv and
explicit `env=`, and assert on `result.exit_code` and `result.output`.

```python
from typer.testing import CliRunner

from clawteam.cli.commands import app
from clawteam.team.manager import TeamManager


class RecordingBackend:
    def __init__(self):
        self.calls = []

    def spawn(self, **kwargs):
        self.calls.append(kwargs)
        return f"Agent '{kwargs['agent_name']}' spawned"

    def list_running(self):
        return []


def test_team_start_spawns_all_existing_members(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAWTEAM_DATA_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    TeamManager.create_team(name="existing", leader_name="leader", leader_id="l001")
    TeamManager.add_member("existing", "worker-1", "w001", agent_type="coder")
    TeamManager.add_member("existing", "worker-2", "w002", agent_type="reviewer")

    backend = RecordingBackend()
    monkeypatch.setattr("clawteam.spawn.get_backend", lambda _: backend)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["team", "start", "existing", "--no-workspace"],
        env={"CLAWTEAM_DATA_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    spawned_names = {call["agent_name"] for call in backend.calls}
    assert spawned_names == {"leader", "worker-1", "worker-2"}
```

(`tests/test_spawn_cli.py:122`)

Conventions:

1. **Recording backends** — define a tiny class in the test file that records
   spawn args and returns a deterministic message (see `RecordingBackend`,
   `ErrorBackend` at `tests/test_spawn_cli.py:9-29`). Don't mock the entire
   `SpawnBackend` interface.
2. **Patch the factory, not the backend class** —
   `monkeypatch.setattr("clawteam.spawn.get_backend", lambda _: backend)`.
   This honors the `_global_app_state` callback path inside Typer.
3. **Always pass `env=` explicitly** to `runner.invoke` even though
   `monkeypatch.setenv` already set the same value. The `env=` mapping is
   what the spawned subprocess sees.
4. **Assert on `result.exit_code` *first*, then on `result.output`.**
   Include `result.output` as the assertion message so failures explain
   themselves: `assert result.exit_code == 0, result.output`.
5. **Normalize multi-line CLI output** before substring matching:
   `normalized = " ".join(result.output.split())`
   (`tests/test_spawn_cli.py:101`).
6. **For Popen-based watchers**, fake the class:
   ```python
   class FakePopen:
       def __init__(self, args, **kwargs):
           popen_calls.append(list(args))
   monkeypatch.setattr(subprocess, "Popen", FakePopen)
   ```
   (`tests/test_spawn_cli.py:170`)

---

## Concurrency / Locking Tests

The locking tests in `tests/test_task_store_locking.py` use `multiprocessing`
with the `fork` start method, gated behind a skip marker:

```python
@pytest.mark.skipif("fork" not in mp.get_all_start_methods(), reason="requires fork start method")
def test_only_one_agent_can_claim_task_concurrently(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CLAWTEAM_DATA_DIR", str(tmp_path))
    store = TaskStore("demo")
    task = store.create("demo task")

    ctx = mp.get_context("fork")
    result_queue = ctx.Queue()

    proc_a = ctx.Process(target=_claim_task, args=(str(tmp_path), task.id, "agent-a", 0.3, result_queue))
    proc_b = ctx.Process(target=_claim_task, args=(str(tmp_path), task.id, "agent-b", 0.0, result_queue))

    proc_a.start()
    time.sleep(0.05)
    proc_b.start()

    results = sorted(result_queue.get(timeout=10) for _ in range(2))
    proc_a.join(timeout=10)
    proc_b.join(timeout=10)

    assert [result[1] for result in results].count("ok") == 1
    assert [result[1] for result in results].count("err") == 1
    assert any(result[2] == "TaskLockError" for result in results if result[1] == "err")
```

(`tests/test_task_store_locking.py:40`)

For thread-level concurrency tests (atomic write tests), use plain `threading`
with an `errors` list and assert it stays empty
(`tests/test_fileutil.py:53-71`).

---

## What to Mock (and What Not To)

**Always mock:**
- `subprocess.run` and `subprocess.Popen` — never invoke real `tmux`,
  `gource`, or spawn-backend processes from a unit test.
- `shutil.which` — controls whether the binary appears installed.
- `time.sleep` — replace with `lambda _x: None` to keep tests fast
  (`tests/test_tmux_injection.py:67`).
- `time.monotonic` when testing TTL caches
  (`tests/test_board.py:97`).
- Network calls — patch `urllib.request.build_opener` and friends with a
  `FakeResponse`/`FakeOpener` class
  (`tests/test_board.py:304-329`).

**Never mock:**
- `pathlib.Path` operations — write to `tmp_path` instead.
- `json.loads` / `json.dumps` — round-trip real data.
- Pydantic models — instantiate them. They're cheap.
- `atomic_write_text` / `file_locked` — exercise the real lock-and-write
  path; the autouse fixture redirects writes to `tmp_path`.

**Test the real thing when you can:**
- Storage: instantiate `TaskStore("test-team")` and call `create()` /
  `get()` / `update()` against the real on-disk format. The autouse fixture
  isolates the data dir.
- Team config: `TeamManager.create_team(...)` then read back from disk via
  `TeamManager.get_team(...)`.
- Mailbox: `MailboxManager(team_name).send(...)` then `.receive(...)`.

---

## Common Patterns

### Asserting on disk state

```python
def test_create_persists_to_disk(self, store):
    t = store.create("persistent")
    loaded = store.get(t.id)
    assert loaded is not None
    assert loaded.subject == "persistent"
```

(`tests/test_tasks.py:41`)

Reload through the public API rather than reading the JSON file directly —
this catches schema-drift bugs as well as IO bugs.

### Asserting on Pydantic round-trips

```python
def test_serialization_uses_from_alias(self):
    msg = TeamMessage(from_agent="a", to="b", content="c")
    dumped = json.loads(msg.model_dump_json(by_alias=True, exclude_none=True))
    assert "from" in dumped
    assert "from_agent" not in dumped
```

(`tests/test_models.py:93`)

Always serialize with `by_alias=True, exclude_none=True` (the production
contract) and assert on the alias-form keys, not the Python attribute names.

### Asserting on the dashboard JSON contract

The frontend has no tests of its own, so the JSON shape it consumes is
locked down by `tests/test_board.py`:

```python
teams = BoardCollector().collect_overview()

assert teams == [
    {
        "name": "demo",
        "description": "demo team",
        "leader": "leader",
        "members": 1,
        "membersOnline": 0,
        "tasks": 0,
        "pendingMessages": 0,
    }
]
```

(`tests/test_board.py:30`)

When you change the `BoardCollector.collect_team` / `collect_overview` shape,
update the corresponding TypeScript types in
`clawteam/board/frontend/src/types.ts` (`TeamOverview`, `TeamData`,
`Member`, `Task`) **and** add/adjust an exact-match assertion in
`tests/test_board.py`.

### Asserting on the served HTML

Because the SPA replaces an HTML-templating server, there is one canary test
that locks in the SPA shell shape:

```python
def test_board_ui_is_react_spa_shell():
    """The dashboard is now a React SPA; escaping is handled by React at render time."""
    html = Path("clawteam/board/static/index.html").read_text(encoding="utf-8")
    assert '<div id="root"></div>' in html
    assert "/assets/index-" in html
```

(`tests/test_board.py:335`) — keep this test green to guarantee no inline
user-data interpolation is reintroduced into the served HTML.

---

## Anti-patterns (do not copy)

- **Do not call `os.environ` directly to set state.** Use
  `monkeypatch.setenv` so cleanup is automatic.
- **Do not assume the autouse fixture is enough** when your test exercises
  `get_data_dir()` walk-up logic. Override it locally — see
  `tests/test_data_dir.py:11-27`.
- **Do not invoke real `subprocess.run`** in a unit test. Patch
  `subprocess.run` with a fake that dispatches on argv.
- **Do not skip the return-code check on `subprocess.run`** when writing
  *production* code — the corresponding tests
  (`test_inject_raises_when_load_buffer_fails`,
  `test_inject_raises_when_paste_buffer_fails`) will fail loudly.
- **Do not write tests against `/tmp` or the developer's real `~/.clawteam`.**
  Always use `tmp_path`.

---

*Testing analysis: 2026-04-28*
