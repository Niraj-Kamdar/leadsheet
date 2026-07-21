"""`leadsheet` CLI: the one-time setup step pip can't run for us.

pip/wheel installs have no reliable post-install hook, so wiring the MCP
server and skill into Claude Code globally needs an explicit follow-up
command: `pip install leadsheet && leadsheet setup`.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from leadsheet import audio, soundfont

SERVER_NAME = "leadsheet"


def package_skill_dir() -> Path:
    return Path(__file__).parent / "skill"


def claude_skills_dir() -> Path:
    return Path.home() / ".claude" / "skills" / SERVER_NAME


def codex_skills_dir() -> Path:
    """Return Codex's documented user-scoped skill location."""
    return Path.home() / ".agents" / "skills" / SERVER_NAME


def claude_available() -> bool:
    return shutil.which("claude") is not None


def codex_config_path() -> Path:
    return Path.home() / ".codex" / "config.toml"


def gemini_config_path() -> Path:
    return Path.home() / ".gemini" / "settings.json"


def codex_config_detected() -> bool:
    return codex_config_path().is_file()


def gemini_config_detected() -> bool:
    return gemini_config_path().is_file()


def fluidsynth_available() -> bool:
    return shutil.which("fluidsynth") is not None


def fluidsynth_install_hint() -> str:
    if sys.platform == "darwin":
        return "brew install fluidsynth"
    if sys.platform.startswith("linux"):
        return "apt-get install fluidsynth  (or your distro's package manager)"
    return "install fluidsynth from https://www.fluidsynth.org/"


def ffmpeg_install_hint() -> str:
    if sys.platform == "darwin":
        return "brew install ffmpeg"
    if sys.platform.startswith("linux"):
        return "apt-get install ffmpeg  (or your distro's package manager)"
    return "install ffmpeg from https://ffmpeg.org/"


def audio_backend_hint() -> str:
    if fluidsynth_available() and audio.ffmpeg_available():
        return "FluidSynth + FFmpeg (tagged MP3)"
    if fluidsynth_available():
        return "FluidSynth (playable WAV; install ffmpeg for MP3)"
    if audio.tinysoundfont_available():
        return "TinySoundFont (built-in WAV fallback)"
    return "MIDI only (install FluidSynth or reinstall leadsheet)"


def register_mcp_server() -> None:
    # Absolute interpreter path -- this is what `claude mcp add -s user`
    # stores and re-launches later, regardless of which shell/venv is
    # active at that point, so it must be a path that keeps working.
    python = sys.executable
    subprocess.run(
        ["claude", "mcp", "remove", SERVER_NAME, "-s", "user"],
        capture_output=True, text=True,
    )
    result = subprocess.run(
        ["claude", "mcp", "add", SERVER_NAME, "-s", "user", "--", python, "-m", "leadsheet.server"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"`claude mcp add` failed: {result.stderr.strip() or result.stdout.strip()}")


def is_mcp_registered() -> bool:
    result = subprocess.run(
        ["claude", "mcp", "get", SERVER_NAME], capture_output=True, text=True,
    )
    return result.returncode == 0


def register_codex_mcp_server() -> None:
    """Add or refresh leadsheet's stdio server in an existing Codex config."""
    path = codex_config_path()
    try:
        config = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"could not read Codex config at {path}: {exc}") from exc

    section = (
        f"[mcp_servers.{SERVER_NAME}]\n"
        f'command = {json.dumps(sys.executable)}\n'
        'args = ["-m", "leadsheet.server"]\n'
    )
    pattern = rf"(?ms)^\[mcp_servers\.{re.escape(SERVER_NAME)}\]\n.*?(?=^\[|\Z)"
    updated, count = re.subn(pattern, section, config)
    if not count:
        updated = config.rstrip() + "\n\n" + section

    try:
        path.write_text(updated, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"could not write Codex config at {path}: {exc}") from exc


def register_gemini_mcp_server() -> None:
    """Add or refresh leadsheet's stdio server in an existing Gemini config."""
    path = gemini_config_path()
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"could not read Gemini config at {path}: {exc}") from exc

    if not isinstance(config, dict):
        raise RuntimeError(f"Gemini config at {path} must contain a JSON object")
    servers = config.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise RuntimeError(f"Gemini config at {path} has a non-object mcpServers field")
    servers[SERVER_NAME] = {"command": sys.executable, "args": ["-m", "leadsheet.server"]}

    try:
        path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"could not write Gemini config at {path}: {exc}") from exc


def install_skill(dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(package_skill_dir(), dest)
    return dest


def cmd_setup(_args: argparse.Namespace) -> int:
    claude_found = claude_available()
    codex_found = codex_config_detected()
    gemini_found = gemini_config_detected()
    if not any((claude_found, codex_found, gemini_found)):
        print("error: no supported AI client configuration was detected.")
        print("Install Claude Code, or configure Codex (~/.codex/config.toml) or Gemini (~/.gemini/settings.json), then re-run `leadsheet setup`.")
        return 1

    if claude_found:
        print(f"Registering the leadsheet MCP server with Claude Code (python: {sys.executable}) ...")
        try:
            register_mcp_server()
        except RuntimeError as exc:
            print(f"error: {exc}")
            return 1
        print("  claude mcp add leadsheet -s user  ->  ok")

        print("Installing the leadsheet skill for Claude Code ...")
        dest = install_skill(claude_skills_dir())
        print(f"  wrote {dest}")

    if codex_found:
        print("Installing the leadsheet skill for Codex ...")
        dest = install_skill(codex_skills_dir())
        print(f"  wrote {dest}")

    for client, detected, register in (
        ("Codex", codex_found, register_codex_mcp_server),
        ("Gemini", gemini_found, register_gemini_mcp_server),
    ):
        if not detected:
            continue
        print(f"Registering the leadsheet MCP server with {client} ...")
        try:
            register()
        except RuntimeError as exc:
            print(f"error: {exc}")
            return 1
        print(f"  {client} MCP configuration  ->  ok")

    if fluidsynth_available() or audio.tinysoundfont_available():
        print("Checking the cached soundfont ...")
        try:
            path = soundfont.ensure_soundfont()
            print(f"  soundfont ready at {path}")
        except Exception as exc:  # noqa: BLE001
            print(f"  warning: could not download the soundfont: {exc}")
            print("  audio previews won't be available until this succeeds; MIDI output still works.")
    else:
        print("fluidsynth not found -- using the built-in WAV fallback when available.")
        print(f"  to enable highest-quality tagged MP3 output, install it: {fluidsynth_install_hint()}")
        if not audio.tinysoundfont_available():
            print("  TinySoundFont is also unavailable; reinstall `leadsheet` to restore the fallback.")

    if not audio.ffmpeg_available():
        print(f"  optional MP3 encoder missing; install it with: {ffmpeg_install_hint()}")
    if not audio.tinysoundfont_available():
        print("  optional zero-system-dependency WAV fallback: pip install 'leadsheet[audio]'")

    print(f"Audio backend: {audio_backend_hint()}")

    print()
    clients = [name for name, found in (("Claude Code", claude_found), ("Codex", codex_found), ("Gemini", gemini_found)) if found]
    print(f"Setup complete. Restart {', '.join(clients)}, then ask it to compose something.")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    print(f"python interpreter: {sys.executable}")

    claude_found = claude_available()
    print(f"claude CLI:         {'found' if claude_found else 'NOT found'}")

    if claude_found:
        registered = is_mcp_registered()
        print(f"MCP server:         {'registered (user scope)' if registered else 'NOT registered'}")
    else:
        print("MCP server:         unknown (claude CLI not found)")

    print(f"codex config:       {'found' if codex_config_detected() else 'NOT found'} ({codex_config_path()})")
    print(f"gemini config:      {'found' if gemini_config_detected() else 'NOT found'} ({gemini_config_path()})")

    claude_skill = claude_skills_dir()
    codex_skill = codex_skills_dir()
    print(f"Claude skill:       {'yes' if claude_skill.exists() else 'no'} ({claude_skill})")
    print(f"Codex skill:        {'yes' if codex_skill.exists() else 'no'} ({codex_skill})")

    fs_found = fluidsynth_available()
    print(f"fluidsynth:         {'found' if fs_found else 'NOT found'}")
    print(f"ffmpeg:             {'found' if audio.ffmpeg_available() else 'NOT found'}")
    print(f"audio backend:      {audio_backend_hint()}")

    sf_cached = soundfont.is_cached()
    print(f"soundfont cached:   {'yes' if sf_cached else 'no'} ({soundfont.soundfont_path()})")

    warnings: list[str] = []
    if not fs_found:
        warnings.append(
            f"FluidSynth is missing; install it with: {fluidsynth_install_hint()}"
        )
    if not audio.ffmpeg_available():
        warnings.append(
            f"FFmpeg is missing; install it with: {ffmpeg_install_hint()} "
            "for tagged MP3 output"
        )
    if not audio.tinysoundfont_available():
        warnings.append(
            "TinySoundFont fallback is unavailable; install it with: "
            "pip install 'leadsheet[audio]'"
        )
    if fs_found and not sf_cached:
        warnings.append(
            "The soundfont is not cached; it will be downloaded on first FluidSynth render."
        )

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"  warning: {warning}")
    else:
        print("\nWarnings: none")

    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    if claude_available():
        subprocess.run(["claude", "mcp", "remove", SERVER_NAME, "-s", "user"], capture_output=True)
        print("removed the MCP server registration")

    # Only touch Codex and Gemini when their configurations already exist.
    # Their native CLIs own the rest of the configuration; leave it intact.
    if codex_config_detected():
        path = codex_config_path()
        config = path.read_text(encoding="utf-8")
        pattern = rf"(?ms)^\[mcp_servers\.{re.escape(SERVER_NAME)}\]\n.*?(?=^\[|\Z)"
        path.write_text(re.sub(pattern, "", config).rstrip() + "\n", encoding="utf-8")
        print("removed the Codex MCP server registration")
    if gemini_config_detected():
        path = gemini_config_path()
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(config.get("mcpServers"), dict) and config["mcpServers"].pop(SERVER_NAME, None) is not None:
                path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
                print("removed the Gemini MCP server registration")
        except (OSError, json.JSONDecodeError):
            print(f"warning: could not remove the Gemini MCP registration from {path}")

    for dest in (claude_skills_dir(), codex_skills_dir()):
        if dest.exists():
            shutil.rmtree(dest)
            print(f"removed {dest}")

    if args.purge_cache:
        sf_path = soundfont.soundfont_path()
        if sf_path.exists():
            sf_path.unlink()
            print(f"removed {sf_path}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="leadsheet")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="Register the MCP server and skill with Claude Code (run once after install)")
    sub.add_parser("status", help="Show what's currently configured")

    p_uninstall = sub.add_parser("uninstall", help="Remove the MCP server registration and skill")
    p_uninstall.add_argument("--purge-cache", action="store_true", help="Also delete the cached soundfont")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handlers = {"setup": cmd_setup, "status": cmd_status, "uninstall": cmd_uninstall}
    sys.exit(handlers[args.command](args))


if __name__ == "__main__":
    main()
