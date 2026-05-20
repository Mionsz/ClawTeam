"""Agent prompt builder — identity + task + context awareness.

Coordination knowledge (how to use the clawteam CLI) is provided
by the ClawTeam Skill, not duplicated here.
"""

from __future__ import annotations

from .role_defaults import RoleProfile, resolve_role

CLAWTEAM_TRIGGER_BLOCK = """\
## MANDATORY — ClawTeam Mention Trigger

If the user prompt contains any of `clawteam`, `claw team`, `claw-team`,
`ClawTeam`, `claw_team`, `claw teams`, `claw-teams`, or `clawteams` (any
casing, with whitespace, hyphen, or underscore between "claw" and "team(s)"),
you MUST coordinate work via ClawTeam — do not run as a single agent.

Required actions when triggered:
1. Spawn or attach to a ClawTeam team (`clawteam team spawn-team` /
   `mcp_clawteam_team_create`).
2. Decompose the work into ClawTeam tasks (`mcp_clawteam_task_create`) with
   owners, priority, and `blockedBy` dependencies.
3. Spawn workers via `clawteam spawn` and route handoffs through
   `mcp_clawteam_mailbox_send`.
4. Report progress on the ClawTeam board, never via ad-hoc chat summaries.
5. If ClawTeam tooling is unavailable, surface the failure to the user —
   never silently fall back to direct execution.

Full canonical rule: see `AGENTS.md` → "MANDATORY — ClawTeam Mention Trigger".
"""


def _required_reading_block(profile: RoleProfile, repo_root: str | None) -> str:
    """Render the Required Reading section for the spawned agent.

    Always lists the base files (``AGENTS.md`` etc.). Adds folder-level
    pointers from the role profile. When ``repo_root`` is known, paths are
    rendered as absolute so workers running outside the repo (e.g. inside an
    isolated worktree) can still locate them.
    """

    def _abs(path: str) -> str:
        if repo_root:
            return f"{repo_root.rstrip('/')}/{path}"
        return path

    lines: list[str] = ["## Required Reading\n"]
    lines.append(
        "Before starting work, read these files. They define the rules of "
        "this repository — including TDD-first workflow, phase gates, "
        "ClawTeam task governance, and the mandatory ClawTeam-mention "
        "trigger."
    )
    lines.append("")
    lines.append("**Always:**")
    for path in profile.base_files:
        lines.append(f"- {_abs(path)}")

    if profile.include_agents:
        lines.append("")
        lines.append("**Role-specific agent identities (`.github/agents/`):**")
        for path in profile.include_agents:
            lines.append(f"- {_abs(path)}")

    if profile.include_instructions:
        lines.append("")
        lines.append("**Applicable instructions (`.github/instructions/`):**")
        for glob in profile.include_instructions:
            lines.append(f"- {_abs(glob)}")

    if profile.include_prompts:
        lines.append("")
        lines.append("**Reusable prompt templates (`.github/prompts/`):**")
        for glob in profile.include_prompts:
            lines.append(f"- {_abs(glob)}")

    lines.append("")
    lines.append(
        "If a file is missing, continue with the others — do not block. "
        "Skill catalog: `~/.claude/skills/<name>/SKILL.md` (auto-symlinked "
        "from `.github/skills/`)."
    )
    return "\n".join(lines)


def _build_context_block(team_name: str, agent_name: str, repo: str | None = None) -> str:
    """Build a context awareness block from the workspace context layer.

    Includes recent changes from teammates, file overlap warnings,
    and upstream dependency context. Returns empty string if context
    layer is unavailable or no relevant context exists.
    """
    try:
        from clawteam.workspace.context import inject_context
        ctx = inject_context(team_name, agent_name, repo)
        if ctx and "No cross-agent context" not in ctx:
            return ctx
    except Exception:
        pass
    return ""


def build_agent_prompt(
    agent_name: str,
    agent_id: str,
    agent_type: str,
    team_name: str,
    leader_name: str,
    task: str,
    user: str = "",
    workspace_dir: str = "",
    workspace_branch: str = "",
    isolated_workspace: bool = False,
    repo_path: str | None = None,
    role: str | None = None,
    repo_root: str | None = None,
) -> str:
    """Build agent prompt: identity + task + context + coordination.

    ``role`` selects a :class:`RoleProfile` from
    :mod:`clawteam.spawn.role_defaults` to surface required reading and the
    ClawTeam-mention trigger for orchestrator-class workers. ``repo_root``
    (if provided) is used to render absolute paths in the Required Reading
    section so workers in isolated worktrees can still locate them.
    """
    profile = resolve_role(role)
    lines = [
        "## Identity\n",
        f"- Name: {agent_name}",
        f"- ID: {agent_id}",
    ]
    if user:
        lines.append(f"- User: {user}")
    lines.extend([
        f"- Type: {agent_type}",
        f"- Team: {team_name}",
        f"- Leader: {leader_name}",
    ])
    if role:
        lines.append(f"- Role: {role} ({profile.role_class})")
    if workspace_dir:
        lines.extend([
            "",
            "## Workspace",
            f"- Working directory: {workspace_dir}",
        ])
        if isolated_workspace:
            lines.extend([
                f"- Branch: {workspace_branch}",
                "- This is an isolated git worktree. Your changes do not affect the main branch.",
            ])
        else:
            lines.append("- Work directly in this repository path unless told otherwise.")

    if role or repo_root:
        lines.extend(["", _required_reading_block(profile, repo_root)])

    if profile.inline_clawteam_trigger:
        lines.extend(["", CLAWTEAM_TRIGGER_BLOCK])

    lines.extend([
        "",
        "## Task\n",
        task,
    ])

    # Inject cross-agent context awareness
    context_block = _build_context_block(team_name, agent_name, repo_path)
    if context_block:
        lines.extend([
            "",
            "## Context\n",
            context_block,
        ])

    lines.extend([
        "",
        "## Coordination Protocol\n",
        f"- Use `clawteam task list {team_name} --owner {agent_name}` to see your tasks.",
        f"- If that list is empty, check `clawteam task list {team_name}` and your inbox before declaring yourself idle.",
        f"- Starting a task: `clawteam task update {team_name} <task-id> --status in_progress`",
        "- Before marking a task completed, commit your changes in this repository with git.",
        '- Use a clear commit message, e.g. `git add -A && git commit -m "Implement <task summary>"`.',
        f"- Finishing a task: `clawteam task update {team_name} <task-id> --status completed`",
        "- When you finish all tasks, send a summary to the leader:",
        f'  `clawteam inbox send {team_name} {leader_name} "All tasks completed. <brief summary>"`',
        "- If you are blocked or need help, message the leader:",
        f'  `clawteam inbox send {team_name} {leader_name} "Need help: <description>"`',
        f"- After finishing work, report your costs: `clawteam cost report {team_name} --input-tokens <N> --output-tokens <N> --cost-cents <N>`",
        "- Do not exit after the first task unless the leader explicitly tells you to stop.",
        "",
        "## Worker Loop Protocol\n",
        "- For ongoing jobs, do not start a detached daemon/watch loop and then immediately exit.",
        "- Keep the monitoring/reporting loop in the foreground, or keep a foreground watchdog alive that continues checking health and sending updates.",
        f"- After finishing your current task batch, re-check `clawteam task list {team_name} --owner {agent_name}`.",
        f"- If that still shows no tasks, scan `clawteam task list {team_name}` for pending work that matches your assignment before you go idle.",
        f"- Then check for new instructions with `clawteam inbox receive {team_name} --agent {agent_name}`.",
        f"- If you become idle, notify the leader with `clawteam lifecycle idle {team_name}` and continue checking for new work.",
        "- Repeat this loop until the leader confirms shutdown or there is truly no more work to do.",
        "",
    ])
    return "\n".join(lines)
