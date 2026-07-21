"""Filesystem-free render core shared by the local stdio server (server.py)
and the leadsheet-remote-mcp hosted HTTP backend: parse -> validate ->
compile -> render, ending in in-memory bytes. Neither caller's notion of
"where the result goes" (disk vs. object storage) lives here.
"""

from __future__ import annotations

import os

# See server.py's identical guard: musicpy unconditionally imports pygame at
# import time, and this module is a second, independent musicpy entrypoint
# (the container never imports server.py), so the guard has to be repeated
# here rather than relied on from that module.
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from dataclasses import dataclass, field

import musicpy as mp

from leadsheet import audio, compiler, dsl, schema, theory_check
from leadsheet.schema import PieceSchema

# The full local fallback ladder, in preference order. The container always
# has fluidsynth+ffmpeg, so it renders with formats=("mp3",) only -- a
# failure there is a broken container, not a reason to silently downgrade.
DEFAULT_FORMATS: tuple[str, ...] = ("mp3", "wav_fluidsynth", "wav_tinysoundfont", "midi")


@dataclass
class RenderResult:
    dsl_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    install_hints: list[str] = field(default_factory=list)
    track_lengths: list[dict] = field(default_factory=list)
    detected_chords: list[dict] = field(default_factory=list)
    title: str | None = None
    bpm: float | None = None
    key: str | None = None
    duration_seconds: float | None = None
    midi_bytes: bytes | None = None
    audio_bytes: bytes | None = None
    audio_format: str | None = None
    audio_backend: str | None = None
    render_ok: bool = False
    render_error: str | None = None


def render_piece(text: str, *, formats: tuple[str, ...] = DEFAULT_FORMATS) -> RenderResult:
    try:
        parsed = dsl.parse_dsl(text)
    except dsl.DslSyntaxError as exc:
        return RenderResult(dsl_valid=False, errors=[str(exc)])

    validation = theory_check.validate(parsed)
    if not validation.valid:
        return RenderResult(dsl_valid=False, errors=validation.errors, track_lengths=validation.track_lengths)

    piece_schema = PieceSchema(**parsed)

    piece_obj = compiler.compile_piece(piece_schema)
    midi_bytes = mp.write(piece_obj, bpm=piece_schema.bpm, save_as_file=False).getvalue()
    comment = f"{piece_schema.bpm} BPM" + (f", {piece_schema.key}" if piece_schema.key else "")
    title = piece_schema.title or "Untitled"

    result = RenderResult(
        dsl_valid=True,
        warnings=list(validation.warnings),
        track_lengths=validation.track_lengths,
        detected_chords=validation.detected_chords,
        title=piece_schema.title,
        bpm=piece_schema.bpm,
        key=piece_schema.key,
        duration_seconds=schema.piece_duration_seconds(piece_schema),
        midi_bytes=midi_bytes,
    )

    try:
        if "mp3" in formats and audio.fluidsynth_available() and audio.ffmpeg_available():
            result.audio_bytes = audio.render_and_tag_mp3(midi_bytes, title=title, artist="leadsheet", comment=comment)
            result.audio_format = "mp3"
            result.audio_backend = "fluidsynth+ffmpeg"
            result.render_ok = True
        elif "wav_fluidsynth" in formats and audio.fluidsynth_available():
            result.audio_bytes = audio.render_wav_with_fluidsynth(midi_bytes)
            result.audio_format = "wav"
            result.audio_backend = "fluidsynth"
            result.render_ok = True
            result.warnings.append(
                "FFmpeg not found; saved playable WAV instead of MP3. "
                "Install ffmpeg for tagged MP3 output."
            )
            result.install_hints.append("Install ffmpeg for tagged MP3 output.")
        elif "wav_tinysoundfont" in formats and audio.tinysoundfont_available():
            result.audio_bytes = audio.render_wav_with_tinysoundfont(midi_bytes)
            result.audio_format = "wav"
            result.audio_backend = "tinysoundfont"
            result.render_ok = True
            result.warnings.append(
                "FluidSynth/FFmpeg not found; used the built-in TinySoundFont WAV fallback. "
                "Install FluidSynth and ffmpeg for the highest-fidelity tagged MP3 output."
            )
            result.install_hints.append(
                "Install FluidSynth and ffmpeg for the highest-fidelity tagged MP3 output."
            )
        elif "midi" in formats:
            result.render_ok = True
            result.warnings.append(
                "No audio renderer is available; saved MIDI only. "
                "Install the optional leadsheet audio extra for a zero-system-dependency WAV fallback, "
                "or install FluidSynth for synthesis and ffmpeg for MP3 encoding."
            )
            result.install_hints.extend([
                "Install the optional audio fallback with: pip install 'leadsheet[audio]'.",
                "Install FluidSynth for synthesis.",
                "Install ffmpeg for MP3 encoding.",
            ])
        else:
            result.render_error = "no configured render format is available in this environment"
    except (audio.AudioUnavailable, audio.AudioRenderError, OSError) as exc:
        result.render_ok = False
        result.render_error = str(exc)

    return result
