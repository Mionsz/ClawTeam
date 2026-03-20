from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from clawteam.cli.commands import app
from clawteam.config import AgentProfile
from clawteam.spawn.profiles import apply_profile


def test_apply_profile_maps_claude_provider_and_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_PROXY_TOKEN", "secret-token")
    profile = AgentProfile(
        agent="claude",
        model="opus",
        base_url="https://proxy.example.com",
        api_key_env="ANTHROPIC_PROXY_TOKEN",
        args=["--debug"],
    )

    command, env, agent = apply_profile(profile)

    assert agent == "claude"
    assert command == ["claude", "--model", "opus", "--debug"]
    assert env["ANTHROPIC_BASE_URL"] == "https://proxy.example.com"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "secret-token"


def test_apply_profile_maps_kimi_env_and_command(monkeypatch):
    monkeypatch.setenv("MOONSHOT_API_KEY", "moonshot-token")
    profile = AgentProfile(
        command=["kimi", "--config-file", "~/.kimi/config.toml"],
        model="kimi-k2-thinking-turbo",
        base_url="https://api.moonshot.cn/v1",
        api_key_env="MOONSHOT_API_KEY",
    )

    command, env, agent = apply_profile(profile)

    assert agent == "kimi"
    assert command[:4] == ["kimi", "--config-file", "~/.kimi/config.toml", "--model"]
    assert command[-1] == "kimi-k2-thinking-turbo"
    assert env["KIMI_BASE_URL"] == "https://api.moonshot.cn/v1"
    assert env["KIMI_API_KEY"] == "moonshot-token"


def test_profile_cli_set_list_show_remove(tmp_path):
    runner = CliRunner()
    env = {
        "HOME": str(tmp_path),
        "CLAWTEAM_DATA_DIR": str(tmp_path / ".clawteam"),
    }

    result = runner.invoke(
        app,
        [
            "profile",
            "set",
            "moonshot-kimi",
            "--command",
            "kimi --config-file ~/.kimi/config.toml",
            "--model",
            "kimi-k2-thinking-turbo",
            "--base-url",
            "https://api.moonshot.cn/v1",
            "--api-key-env",
            "MOONSHOT_API_KEY",
            "--env-map",
            "KIMI_API_KEY=MOONSHOT_API_KEY",
            "--arg",
            "--debug",
        ],
        env=env,
    )
    assert result.exit_code == 0

    result = runner.invoke(app, ["profile", "list"], env=env)
    assert result.exit_code == 0
    assert "moonshot-kimi" in result.output

    result = runner.invoke(app, ["profile", "show", "moonshot-kimi"], env=env)
    assert result.exit_code == 0
    assert "kimi-k2-thinking-turbo" in result.output
    assert "https://api.moonshot.cn/v1" in result.output

    result = runner.invoke(app, ["profile", "remove", "moonshot-kimi"], env=env)
    assert result.exit_code == 0
    assert "Removed profile 'moonshot-kimi'" in result.output


def test_profile_doctor_claude_creates_state_file(tmp_path):
    runner = CliRunner()
    env = {
        "HOME": str(tmp_path),
        "CLAWTEAM_DATA_DIR": str(tmp_path / ".clawteam"),
    }

    result = runner.invoke(app, ["profile", "doctor", "claude"], env=env)

    assert result.exit_code == 0
    state = json.loads((Path(tmp_path) / ".claude.json").read_text(encoding="utf-8"))
    assert state["hasCompletedOnboarding"] is True


def test_profile_doctor_claude_updates_existing_state_file(tmp_path):
    runner = CliRunner()
    env = {
        "HOME": str(tmp_path),
        "CLAWTEAM_DATA_DIR": str(tmp_path / ".clawteam"),
    }
    state_path = Path(tmp_path) / ".claude.json"
    state_path.write_text(
        json.dumps({"theme": "dark", "hasCompletedOnboarding": False}),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["profile", "doctor", "claude"], env=env)

    assert result.exit_code == 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["theme"] == "dark"
    assert state["hasCompletedOnboarding"] is True
