"""Role-based defaults for `clawteam spawn`.

Maps a free-form role hint (e.g. ``orchestrator``, ``nic-port-orchestrator``,
``tdd-writer``, ``coder``, ``checker``, ``manage``, ``risk-auditor``) to:

* ``role_class`` — coarse classification used by the spawn pipeline:
  ``orchestrator``, ``manager``, ``architect``, ``tdd``, ``checker``,
  ``auditor``, ``maker``, ``validator``, ``generic``.
* ``default_skills`` — skill names auto-attached on top of any user-provided
  ``--skill`` flags.
* ``required_reading`` — sets of relative repo paths that should be surfaced
  in the agent prompt's "Required Reading" section so spawned workers behave
  like a Copilot session rooted at the repo.
* ``prefer_root_cwd`` — when ``True``, the orchestrator-class worker should
  run with cwd pinned to the repo root (no isolated worktree) so it inherits
  ``AGENTS.md`` / ``.github/`` discovery.

Roles are matched by exact name first, then by suffix heuristics. Unknown
roles fall back to a minimal ``generic`` profile that still surfaces
``AGENTS.md`` and the ClawTeam skill.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoleProfile:
    """Resolved spawn-time defaults for a role."""

    role_class: str
    default_skills: tuple[str, ...] = ()
    # Folder-level inclusions. Empty tuple means "do not include that folder".
    include_agents: tuple[str, ...] = ()
    include_instructions: tuple[str, ...] = ()
    include_prompts: tuple[str, ...] = ()
    # Always-read root files (relative to repo root).
    base_files: tuple[str, ...] = (
        "AGENTS.md",
        "CLAUDE.md",
        ".github/copilot-instructions.md",
    )
    # Whether to pin cwd to repo root (no worktree).
    prefer_root_cwd: bool = False
    # Whether to inline the mandatory ClawTeam-mention-trigger paragraph.
    inline_clawteam_trigger: bool = False


# --- canonical role profiles ------------------------------------------------

_ORCHESTRATOR_AGENTS: tuple[str, ...] = (
    ".github/agents/orchestrator.agent.md",
    ".github/agents/ai-swarm-orchestrator.agent.md",
    ".github/agents/nic-porting-orchestrator.agent.md",
    ".github/agents/clawteam-manager.agent.md",
)

_ORCHESTRATOR_HELPERS: tuple[str, ...] = (
    ".github/agents/orchestrator-helper-tdd.agent.md",
    ".github/agents/orchestrator-helper-software-architect.agent.md",
    ".github/agents/orchestrator-helper-agent-orchestrator.agent.md",
    ".github/agents/orchestrator-helper-janitor.agent.md",
)

_ALL_INSTRUCTIONS = (".github/instructions/**/*.instructions.md",)
_ALL_PROMPTS = (".github/prompts/**/*.md",)

_NIC_INSTRUCTIONS = (
    ".github/instructions/nic-porting/**/*.instructions.md",
    ".github/instructions/orchestrator-helpers/**/*.instructions.md",
)

ROLE_PROFILES: dict[str, RoleProfile] = {
    # ---- orchestrator class ------------------------------------------------
    "orchestrator": RoleProfile(
        role_class="orchestrator",
        default_skills=(
            "clawteam",
            "clawteam-manage",
            "nic-driver-porting-orchestrator",
            "nic-porting-role-identities",
            "nic-porting-guide-references",
            "umbrella-mcp",
        ),
        include_agents=_ORCHESTRATOR_AGENTS + _ORCHESTRATOR_HELPERS,
        include_instructions=_ALL_INSTRUCTIONS,
        include_prompts=_ALL_PROMPTS,
        prefer_root_cwd=True,
        inline_clawteam_trigger=True,
    ),
    "ai-swarm-orchestrator": RoleProfile(
        role_class="orchestrator",
        default_skills=(
            "clawteam",
            "clawteam-manage",
            "nic-driver-porting-orchestrator",
            "nic-porting-role-identities",
            "nic-porting-guide-references",
        ),
        include_agents=_ORCHESTRATOR_AGENTS + _ORCHESTRATOR_HELPERS,
        include_instructions=_ALL_INSTRUCTIONS,
        include_prompts=_ALL_PROMPTS,
        prefer_root_cwd=True,
        inline_clawteam_trigger=True,
    ),
    "nic-port-orchestrator": RoleProfile(
        role_class="orchestrator",
        default_skills=(
            "clawteam",
            "nic-driver-porting-orchestrator",
            "nic-porting-role-identities",
            "nic-porting-guide-references",
        ),
        include_agents=_ORCHESTRATOR_AGENTS,
        include_instructions=_NIC_INSTRUCTIONS,
        include_prompts=_ALL_PROMPTS,
        prefer_root_cwd=True,
        inline_clawteam_trigger=True,
    ),
    "nic-porting-orchestrator": RoleProfile(
        role_class="orchestrator",
        default_skills=(
            "clawteam",
            "nic-driver-porting-orchestrator",
            "nic-porting-role-identities",
            "nic-porting-guide-references",
        ),
        include_agents=_ORCHESTRATOR_AGENTS,
        include_instructions=_NIC_INSTRUCTIONS,
        prefer_root_cwd=True,
        inline_clawteam_trigger=True,
    ),
    # ---- manager class -----------------------------------------------------
    "manage": RoleProfile(
        role_class="manager",
        default_skills=("clawteam", "clawteam-manage"),
        include_agents=(".github/agents/clawteam-manager.agent.md",),
        include_instructions=_ALL_INSTRUCTIONS,
        prefer_root_cwd=True,
        inline_clawteam_trigger=True,
    ),
    "clawteam-manager": RoleProfile(
        role_class="manager",
        default_skills=("clawteam", "clawteam-manage"),
        include_agents=(".github/agents/clawteam-manager.agent.md",),
        include_instructions=_ALL_INSTRUCTIONS,
        prefer_root_cwd=True,
        inline_clawteam_trigger=True,
    ),
    # ---- architect / tdd helpers (still root-rooted) ----------------------
    "architect": RoleProfile(
        role_class="architect",
        default_skills=(
            "clawteam",
            "nic-porting-role-identities",
            "nic-porting-guide-references",
        ),
        include_agents=(
            ".github/agents/orchestrator-helper-software-architect.agent.md",
            ".github/agents/nic-porting-orchestrator.agent.md",
        ),
        include_instructions=_NIC_INSTRUCTIONS,
        prefer_root_cwd=False,
        inline_clawteam_trigger=False,
    ),
    "tdd-writer": RoleProfile(
        role_class="tdd",
        default_skills=("clawteam", "nic-porting-guide-references"),
        include_agents=(".github/agents/orchestrator-helper-tdd.agent.md",),
        include_instructions=_NIC_INSTRUCTIONS,
        prefer_root_cwd=False,
    ),
    # ---- checker / auditor -------------------------------------------------
    "checker": RoleProfile(
        role_class="checker",
        default_skills=("clawteam", "nic-porting-guide-references"),
        include_agents=(".github/agents/nic-porting-checker.agent.md",),
        include_instructions=_NIC_INSTRUCTIONS,
        prefer_root_cwd=False,
    ),
    "kpi-auditor": RoleProfile(
        role_class="checker",
        default_skills=("clawteam", "nic-porting-guide-references"),
        include_agents=(".github/agents/nic-porting-checker.agent.md",),
        include_instructions=_NIC_INSTRUCTIONS,
        prefer_root_cwd=False,
    ),
    "risk-auditor": RoleProfile(
        role_class="auditor",
        default_skills=("clawteam", "nic-porting-guide-references"),
        include_agents=(".github/agents/nic-porting-risk-auditor.agent.md",),
        include_instructions=_NIC_INSTRUCTIONS,
        prefer_root_cwd=False,
    ),
    # ---- maker / coder class ----------------------------------------------
    "coder": RoleProfile(
        role_class="maker",
        default_skills=("clawteam",),
        include_instructions=_NIC_INSTRUCTIONS,
        prefer_root_cwd=False,
    ),
    "maker": RoleProfile(
        role_class="maker",
        default_skills=("clawteam",),
        include_instructions=_NIC_INSTRUCTIONS,
        prefer_root_cwd=False,
    ),
    "shim-developer": RoleProfile(
        role_class="maker",
        default_skills=("clawteam", "nic-porting-guide-references"),
        include_instructions=_NIC_INSTRUCTIONS,
        prefer_root_cwd=False,
    ),
    "pci-developer": RoleProfile(
        role_class="maker",
        default_skills=("clawteam", "nic-porting-guide-references"),
        include_instructions=_NIC_INSTRUCTIONS,
        prefer_root_cwd=False,
    ),
    # ---- validators (FreeBSD / native) ------------------------------------
    "freebsd-kernel-validator": RoleProfile(
        role_class="validator",
        default_skills=("clawteam", "nic-porting-guide-references"),
        include_agents=(".github/agents/freebsd-kernel-validator.agent.md",),
        include_instructions=_NIC_INSTRUCTIONS,
        prefer_root_cwd=False,
    ),
    # ---- janitor -----------------------------------------------------------
    "janitor": RoleProfile(
        role_class="manager",
        default_skills=("clawteam",),
        include_agents=(".github/agents/orchestrator-helper-janitor.agent.md",),
        include_instructions=(
            ".github/instructions/orchestrator-helpers/**/*.instructions.md",
        ),
        prefer_root_cwd=True,
    ),
}


_GENERIC_PROFILE = RoleProfile(
    role_class="generic",
    default_skills=("clawteam",),
    include_instructions=(),
    prefer_root_cwd=False,
)


# --- suffix-based fallbacks (matched in order) -----------------------------

_SUFFIX_FALLBACKS: tuple[tuple[str, str], ...] = (
    ("-orchestrator", "orchestrator"),
    ("orchestrator", "orchestrator"),
    ("-manager", "clawteam-manager"),
    ("manager", "clawteam-manager"),
    ("-auditor", "risk-auditor"),
    ("-checker", "checker"),
    ("-validator", "freebsd-kernel-validator"),
    ("-architect", "architect"),
    ("-developer", "coder"),
    ("-coder", "coder"),
    ("-writer", "tdd-writer"),
    ("janitor", "janitor"),
)


def resolve_role(role: str | None) -> RoleProfile:
    """Resolve a role hint to a :class:`RoleProfile`.

    Matching is case-insensitive. Exact match wins; otherwise a small set of
    suffix heuristics maps engineering role names (``shim-developer``,
    ``code-reviewer``, ``cicd-engineer``, …) to a coarse class. Unknown
    roles get the minimal :data:`_GENERIC_PROFILE` so they still see
    ``AGENTS.md`` and the ClawTeam skill.
    """
    if not role:
        return _GENERIC_PROFILE
    key = role.strip().lower()
    if not key:
        return _GENERIC_PROFILE
    profile = ROLE_PROFILES.get(key)
    if profile is not None:
        return profile
    for suffix, target in _SUFFIX_FALLBACKS:
        if key.endswith(suffix) or key == suffix:
            mapped = ROLE_PROFILES.get(target)
            if mapped is not None:
                return mapped
    return _GENERIC_PROFILE


def merged_skill_list(
    profile: RoleProfile,
    user_skills: list[str] | None,
) -> list[str]:
    """Combine role-default skills with user-specified skills (de-duped, ordered)."""
    seen: set[str] = set()
    merged: list[str] = []
    for skill in profile.default_skills:
        if skill not in seen:
            seen.add(skill)
            merged.append(skill)
    for skill in user_skills or []:
        if skill and skill not in seen:
            seen.add(skill)
            merged.append(skill)
    return merged


__all__ = [
    "RoleProfile",
    "ROLE_PROFILES",
    "resolve_role",
    "merged_skill_list",
]
