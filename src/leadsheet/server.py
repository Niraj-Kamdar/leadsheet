"""The local stdio MCP server: compose / validate / revise / list_capabilities.

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

import base64

import mcp.types as types
import musicpy as mp
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.types import Audio

from leadsheet import audio, capabilities, compiler, limits, theory_check
from leadsheet.schema import ComposeResult, PieceSchema

mcp_app = FastMCP("leadsheet")


def _merge_patch(target, patch):
    """RFC 7386 JSON Merge Patch."""
    if not isinstance(patch, dict):
        return patch
    if not isinstance(target, dict):
        target = {}
    result = dict(target)
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = _merge_patch(result.get(key), value)
    return result


def _compose(schema_dict: dict) -> list:
    validation = theory_check.validate(schema_dict)
    if not validation.valid:
        return [validation.model_dump()]

    piece_schema = PieceSchema(**schema_dict)
    warnings = list(validation.warnings)

    piece_obj = compiler.compile_piece(piece_schema)
    midi_bytes = mp.write(piece_obj, bpm=piece_schema.bpm, save_as_file=False).getvalue()

    mp3_bytes = None
    try:
        mp3_bytes = audio.render_mp3(midi_bytes)
    except audio.AudioUnavailable as exc:
        warnings.append(f"audio preview not rendered: {exc}")
    except audio.AudioRenderError as exc:
        warnings.append(f"audio rendering failed: {exc}")

    if mp3_bytes is not None:
        payload_size = len(base64.b64encode(mp3_bytes))
        if payload_size > limits.MAX_PAYLOAD_BYTES:
            warnings.append(
                f"rendered audio ({payload_size} base64 bytes) exceeds MAX_PAYLOAD_BYTES "
                f"({limits.MAX_PAYLOAD_BYTES}) -- shorten the piece to get an inline audio "
                "preview; MIDI is still returned."
            )
            mp3_bytes = None

    result = ComposeResult(
        warnings=warnings,
        detected_chords=validation.detected_chords,
        normalized_schema=piece_schema.model_dump(),
    )

    content: list = [result.model_dump()]
    if mp3_bytes is not None:
        content.append(Audio(data=mp3_bytes, format="mp3"))
    content.append(
        types.EmbeddedResource(
            type="resource",
            resource=types.BlobResourceContents(
                uri="leadsheet://compose/output.mid",
                mimeType="audio/midi",
                blob=base64.b64encode(midi_bytes).decode(),
            ),
        )
    )
    return content


@mcp_app.tool()
def validate(schema: dict) -> dict:
    """Validate a leadsheet PieceSchema JSON object.

    Runs structural validation (field types, chord/instrument names,
    guardrail limits) and, if that passes, a semantic cross-check of every
    chord event against musicpy's own chord-theory detector. Never compiles
    or renders audio -- returns immediately. Call this before `compose` for
    anything non-trivial, and always after a `revise` patch you're unsure
    about.
    """
    return theory_check.validate(schema).model_dump()


@mcp_app.tool()
def compose(schema: dict) -> list:
    """Compile a leadsheet PieceSchema into real music.

    Validates the schema (see `validate`); if invalid, returns the
    validation errors immediately without compiling or rendering anything.
    If valid, deterministically compiles it into a musicpy piece, renders a
    MIDI file and (if fluidsynth is installed) an mp3 audio preview, and
    returns both inline along with any theory-check warnings and the
    normalized schema (carry this into `revise` rather than your original
    possibly-under-specified input).
    """
    return _compose(schema)


@mcp_app.tool()
def revise(base_schema: dict, patch: dict) -> list:
    """Apply a small change to a previously composed piece and recompose it.

    `patch` is an RFC 7386 JSON Merge Patch applied to `base_schema` (which
    should be the `normalized_schema` returned by a prior `compose`/`revise`
    call). Cheaper and less error-prone than resending the whole piece for
    a small top-level change, e.g. `{"bpm": 100, "title": "new title"}`.

    IMPORTANT array caveat: RFC 7386 merge patches replace arrays wholesale,
    they do NOT merge into individual array elements. `tracks` and each
    track's `events` are arrays, so a patch like
    `{"tracks": [{"events": [{"chord": "Dm9"}]}]}` does NOT "just change one
    chord" -- it REPLACES the entire `tracks` array with a single
    under-specified track object (missing `role`/`instrument`/etc.), which
    will fail validation. To change one chord, send the complete `tracks`
    array from `base_schema` with only that one field edited in place, e.g.
    `{"tracks": <the full tracks array, with events[i].chord changed>}`.

    Runs the exact same validate-then-compose pipeline as `compose` against
    the patched schema.
    """
    merged = _merge_patch(base_schema, patch)
    return _compose(merged)


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
