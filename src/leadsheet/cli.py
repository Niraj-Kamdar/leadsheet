"""`leadsheet` CLI: the one-time setup step pip can't run for us.

pip/wheel installs have no reliable post-install hook, so wiring the MCP
server and skill into Claude Code globally needs an explicit follow-up
command: `pip install leadsheet && leadsheet setup`.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from leadsheet import soundfont

SERVER_NAME = "leadsheet"


def package_skill_dir() -> Path:
    return Path(__file__).parent / "skill"


def skills_dir() -> Path:
    return Path.home() / ".claude" / "skills" / SERVER_NAME


def claude_available() -> bool:
    return shutil.which("claude") is not None


def fluidsynth_available() -> bool:
    return shutil.which("fluidsynth") is not None


def fluidsynth_install_hint() -> str:
    if sys.platform == "darwin":
        return "brew install fluidsynth"
    if sys.platform.startswith("linux"):
        return "apt-get install fluidsynth  (or your distro's package manager)"
    return "install fluidsynth from https://www.fluidsynth.org/"


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


def install_skill() -> Path:
    dest = skills_dir()
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(package_skill_dir(), dest)
    return dest


def cmd_setup(_args: argparse.Namespace) -> int:
    if not claude_available():
        print("error: `claude` (the Claude Code CLI) was not found on PATH.")
        print("Install Claude Code first, then re-run `leadsheet setup`.")
        return 1

    print(f"Registering the leadsheet MCP server (python: {sys.executable}) ...")
    try:
        register_mcp_server()
    except RuntimeError as exc:
        print(f"error: {exc}")
        return 1
    print("  claude mcp add leadsheet -s user  ->  ok")

    print("Installing the leadsheet skill ...")
    dest = install_skill()
    print(f"  wrote {dest}")

    if fluidsynth_available():
        print("Checking the cached soundfont ...")
        try:
            path = soundfont.ensure_soundfont()
            print(f"  soundfont ready at {path}")
        except Exception as exc:  # noqa: BLE001
            print(f"  warning: could not download the soundfont: {exc}")
            print("  audio previews won't be available until this succeeds; MIDI output still works.")
    else:
        print("fluidsynth not found -- audio previews will be skipped (MIDI output still works).")
        print(f"  to enable audio previews, install it: {fluidsynth_install_hint()}")
        print("  then re-run `leadsheet setup`.")

    print()
    print("Setup complete. Restart Claude Code, then ask it to compose something.")
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

    dest = skills_dir()
    print(f"skill installed:    {'yes' if dest.exists() else 'no'} ({dest})")

    fs_found = fluidsynth_available()
    print(f"fluidsynth:         {'found' if fs_found else 'NOT found'}")

    sf_cached = soundfont.is_cached()
    print(f"soundfont cached:   {'yes' if sf_cached else 'no'} ({soundfont.soundfont_path()})")

    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    if claude_available():
        subprocess.run(["claude", "mcp", "remove", SERVER_NAME, "-s", "user"], capture_output=True)
        print("removed the MCP server registration")

    dest = skills_dir()
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
