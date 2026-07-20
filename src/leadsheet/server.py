"""The local stdio MCP server: compose / validate / list_capabilities.

Run via `python -m leadsheet.server` (what `leadsheet setup` registers with
`claude mcp add`). Transport is stdio only for v1 -- no HTTP, no auth.
"""

from __future__ import annotations

import os

# musicpy unconditionally imports pygame at import time; pygame's SDL audio
# device init is wrapped in try/except but the import itself isn't -- force
# a dummy audio driver so this can never hang/fail on a machine with no
# audio device (e.g. this server spawned headless by Claude Code).
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import re
from pathlib import Path

import musicpy as mp
from mcp.server.fastmcp import FastMCP

from leadsheet import audio, capabilities, compiler, dsl, theory_check
from leadsheet.schema import PieceSchema

mcp_app = FastMCP("leadsheet")


def _slugify(title: str | None) -> str:
    if not title:
        return "untitled"
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "untitled"


def _unique_path(directory: Path, slug: str) -> Path:
    candidate = directory / f"{slug}.mp3"
    n = 2
    while candidate.exists():
        candidate = directory / f"{slug}-{n}.mp3"
        n += 1
    return candidate


def _compose(text: str, source_path: Path, output_dir: str | None) -> dict:
    try:
        parsed = dsl.parse_dsl(text)
    except dsl.DslSyntaxError as exc:
        return {"ok": False, "errors": [str(exc)]}

    validation = theory_check.validate(parsed)
    if not validation.valid:
        return {"ok": False, "errors": validation.errors}

    piece_schema = PieceSchema(**parsed)
    warnings = list(validation.warnings)

    piece_obj = compiler.compile_piece(piece_schema)
    midi_bytes = mp.write(piece_obj, bpm=piece_schema.bpm, save_as_file=False).getvalue()

    try:
        mp3_bytes = audio.render_mp3(midi_bytes)
    except (audio.AudioUnavailable, audio.AudioRenderError) as exc:
        return {"ok": False, "errors": [str(exc)]}

    target_dir = Path(output_dir) if output_dir else source_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = _unique_path(target_dir, _slugify(piece_schema.title))

    comment = f"{piece_schema.bpm} BPM" + (f", {piece_schema.key}" if piece_schema.key else "")
    try:
        audio.remux_and_tag_mp3(
            mp3_bytes,
            target_path,
            title=piece_schema.title or "Untitled",
            artist="leadsheet",
            comment=comment,
        )
    except (audio.AudioUnavailable, audio.AudioRenderError) as exc:
        return {"ok": False, "errors": [str(exc)]}

    return {"ok": True, "path": str(target_path), "warnings": warnings}


@mcp_app.tool()
def validate(path: str) -> dict:
    """Validate a `.leadsheet` B2 DSL file.

    Reads `path`, parses the B2 DSL, and runs structural validation (field
    types, chord/instrument names, guardrail limits) plus, if that passes, a
    semantic cross-check of every chord event against musicpy's own
    chord-theory detector. Never compiles or renders audio -- returns
    immediately. Call this before `compose` for anything non-trivial.
    """
    try:
        text = Path(path).read_text()
    except OSError as exc:
        return {"valid": False, "errors": [str(exc)]}
    try:
        parsed = dsl.parse_dsl(text)
    except dsl.DslSyntaxError as exc:
        return {"valid": False, "errors": [str(exc)]}
    return theory_check.validate(parsed).model_dump()


@mcp_app.tool()
def compose(path: str, output_dir: str | None = None) -> dict:
    """Compile a `.leadsheet` B2 DSL file into real music.

    Reads and parses `path`, validates it (see `validate`); if invalid,
    returns the errors immediately without compiling or rendering anything.
    If valid, deterministically compiles it into a musicpy piece, renders,
    tags, and saves an mp3 next to `path` (or in `output_dir` if given), and
    returns its path along with any theory-check warnings.

    For a follow-up edit ("make it slower", "change the second chord"),
    edit the `.leadsheet` file directly and call `compose` again -- there is
    no separate revise tool.
    """
    try:
        text = Path(path).read_text()
    except OSError as exc:
        return {"ok": False, "errors": [str(exc)]}
    return _compose(text, Path(path), output_dir)


@mcp_app.tool()
def list_capabilities() -> dict:
    """List everything the server can currently validate/compile against.

    Computed live from musicpy's own registries, not hand-maintained --
    chord types, scale types, GM instrument names, drum-pattern tokens,
    drum-kit names, valid `style` values per track role, and the server's
    guardrail limits. Call this once per session if unsure of a valid
    chord/instrument/drum-kit name, instead of guessing.
    """
    caps = capabilities.get_capabilities()
    return {
        "chord_types": caps.chord_types,
        "scale_types": caps.scale_types,
        "instruments": caps.instruments,
        "drum_tokens": caps.drum_tokens,
        "drum_kits": caps.drum_kits,
        "event_styles": caps.event_styles,
        "limits": caps.limits,
    }


def main() -> None:
    mcp_app.run()


if __name__ == "__main__":
    main()
