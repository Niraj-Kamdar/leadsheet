import json

from leadsheet import cli


def _set_home(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.Path, "home", lambda: tmp_path)


def test_register_codex_mcp_server_replaces_existing_registration(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    config_path = tmp_path / ".codex" / "config.toml"
    config_path.parent.mkdir()
    config_path.write_text(
        '[mcp_servers.leadsheet]\ncommand = "old-python"\nargs = ["old"]\n\n[features]\nfoo = true\n',
        encoding="utf-8",
    )

    cli.register_codex_mcp_server()

    config = config_path.read_text(encoding="utf-8")
    assert config.count("[mcp_servers.leadsheet]") == 1
    assert f"command = {json.dumps(cli.sys.executable)}" in config
    assert 'args = ["-m", "leadsheet.server"]' in config
    assert "[features]\nfoo = true" in config


def test_register_gemini_mcp_server_preserves_existing_settings(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    config_path = tmp_path / ".gemini" / "settings.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps({"theme": "dark", "mcpServers": {"other": {"command": "other"}}}),
        encoding="utf-8",
    )

    cli.register_gemini_mcp_server()

    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["theme"] == "dark"
    assert config["mcpServers"]["other"] == {"command": "other"}
    assert config["mcpServers"]["leadsheet"] == {
        "command": cli.sys.executable,
        "args": ["-m", "leadsheet.server"],
    }


def test_setup_installs_skill_for_codex_without_claude(monkeypatch, tmp_path, capsys):
    _set_home(monkeypatch, tmp_path)
    config_path = tmp_path / ".codex" / "config.toml"
    config_path.parent.mkdir()
    config_path.write_text("[features]\n", encoding="utf-8")
    monkeypatch.setattr(cli, "claude_available", lambda: False)
    monkeypatch.setattr(cli, "fluidsynth_available", lambda: False)

    assert cli.cmd_setup(None) == 0

    skill = tmp_path / ".agents" / "skills" / "leadsheet" / "SKILL.md"
    assert skill.is_file()
    assert "Installing the leadsheet skill for Codex" in capsys.readouterr().out
