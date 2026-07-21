"""Render MIDI with the best audio backend available.

FluidSynth + FFmpeg remains the highest-fidelity MP3 path. When either
external binary is missing, this module can still produce playable WAV audio:
FluidSynth alone writes WAV directly, while TinySoundFont renders in-process.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
import tempfile
import wave
from io import BytesIO
from pathlib import Path

from leadsheet import soundfont


class AudioUnavailable(Exception):
    """A required system binary (fluidsynth/ffmpeg) isn't installed."""


class AudioRenderError(Exception):
    """An audio backend ran but failed."""


def fluidsynth_available() -> bool:
    return shutil.which("fluidsynth") is not None


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def audio_available() -> bool:
    return fluidsynth_available() or tinysoundfont_available()


def mp3_available() -> bool:
    return fluidsynth_available() and ffmpeg_available()


def tinysoundfont_available() -> bool:
    """Return whether the bundled, in-process fallback can be imported."""
    try:
        import tinysoundfont  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


def _run(cmd: list[str], step: str) -> None:
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        raise AudioRenderError(f"{step} failed: {stderr[-2000:]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioRenderError(f"{step} timed out") from exc


def render_mp3(midi_bytes: bytes) -> bytes:
    """Renders MIDI bytes to MP3 bytes. Raises AudioUnavailable if
    fluidsynth/ffmpeg aren't installed, AudioRenderError if they fail."""
    if not fluidsynth_available():
        raise AudioUnavailable(
            "fluidsynth is not installed -- install it (e.g. `brew install fluidsynth` "
            "or `apt-get install fluidsynth`) to get an audio preview; MIDI is still returned."
        )
    if not ffmpeg_available():
        raise AudioUnavailable(
            "ffmpeg is not installed -- required to encode the rendered audio to mp3."
        )

    sf2_path = soundfont.ensure_soundfont()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        midi_path = tmp_path / "in.mid"
        wav_path = tmp_path / "out.wav"
        mp3_path = tmp_path / "out.mp3"
        midi_path.write_bytes(midi_bytes)

        _run(
            [
                # -F/-r must precede the soundfont/midi positional args --
                # fluidsynth treats flags after them as shell commands, not
                # CLI options, and silently exits 0 without rendering.
                "fluidsynth", "-ni",
                "-F", str(wav_path),
                "-r", "44100",
                str(sf2_path), str(midi_path),
            ],
            step="fluidsynth render",
        )
        _run(
            [
                "ffmpeg", "-y",
                "-i", str(wav_path),
                "-codec:a", "libmp3lame", "-qscale:a", "2",
                str(mp3_path),
            ],
            step="ffmpeg mp3 encode",
        )
        return mp3_path.read_bytes()


def render_wav_with_fluidsynth(midi_bytes: bytes) -> bytes:
    """Render MIDI to WAV using FluidSynth, without requiring FFmpeg."""
    if not fluidsynth_available():
        raise AudioUnavailable("FluidSynth is not installed.")

    sf2_path = soundfont.ensure_soundfont()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        midi_path = tmp_path / "in.mid"
        wav_path = tmp_path / "out.wav"
        midi_path.write_bytes(midi_bytes)
        _run(
            [
                "fluidsynth", "-ni", "-F", str(wav_path), "-r", "44100",
                str(sf2_path), str(midi_path),
            ],
            step="fluidsynth WAV render",
        )
        return wav_path.read_bytes()


def render_wav_with_tinysoundfont(midi_bytes: bytes) -> bytes:
    """Render MIDI to a standard PCM WAV using the in-process fallback."""
    if not tinysoundfont_available():
        raise AudioUnavailable(
            "TinySoundFont is unavailable; reinstall leadsheet to restore the built-in audio fallback."
        )

    import tinysoundfont

    sf2_path = soundfont.ensure_soundfont()
    sample_rate = 44100
    chunk_samples = 4096
    # The sequencer drives MIDI events from generate(). Once its queue is
    # empty, render a short tail so releases are not cut off.
    tail_samples = sample_rate * 2
    synth = tinysoundfont.Synth(samplerate=sample_rate, gain=-3)
    sfid = synth.sfload(str(sf2_path))
    sequencer = tinysoundfont.Sequencer(synth)

    with tempfile.TemporaryDirectory() as tmp:
        midi_path = Path(tmp) / "in.mid"
        midi_path.write_bytes(midi_bytes)
        sequencer.midi_load(str(midi_path))

        pcm = bytearray()
        empty_chunks = 0
        while empty_chunks * chunk_samples < tail_samples:
            frames = synth.generate(chunk_samples)
            samples = frames if frames.format == "f" else frames.cast("f")
            for sample in samples:
                pcm.extend(struct.pack("<h", max(-32768, min(32767, int(sample * 32767)))))
            if sequencer.is_empty():
                empty_chunks += 1
            else:
                empty_chunks = 0

        output = BytesIO()
        with wave.open(output, "wb") as wav_file:
            wav_file.setnchannels(2)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm)
        return output.getvalue()


def remux_and_tag_mp3(mp3_bytes: bytes, target_path: Path, *, title: str, artist: str, comment: str) -> None:
    """Losslessly remuxes (`-c copy`) mp3 bytes straight to `target_path`
    while embedding ID3 tags in the same step -- the step V1's SKILL.md
    used to make the calling model run by hand after every compose."""
    if not ffmpeg_available():
        raise AudioUnavailable("ffmpeg is not installed -- required to save the rendered audio.")
    with tempfile.TemporaryDirectory() as tmp:
        src_path = Path(tmp) / "rendered.mp3"
        src_path.write_bytes(mp3_bytes)
        _run(
            [
                "ffmpeg", "-y",
                "-i", str(src_path),
                "-c", "copy",
                "-metadata", f"title={title}",
                "-metadata", f"artist={artist}",
                "-metadata", f"comment={comment}",
                str(target_path),
            ],
            step="ffmpeg remux/tag",
        )
