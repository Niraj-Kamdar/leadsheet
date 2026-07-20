"""MIDI bytes -> WAV -> MP3, via fluidsynth (synthesis) and ffmpeg
(encoding) subprocesses. Degrades gracefully: callers should catch
AudioUnavailable and still return the MIDI content block plus a warning,
rather than failing the whole `compose`/`revise` call, since fluidsynth
is a system dependency pip can't install.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from leadsheet import soundfont


class AudioUnavailable(Exception):
    """A required system binary (fluidsynth/ffmpeg) isn't installed."""


class AudioRenderError(Exception):
    """fluidsynth/ffmpeg ran but failed."""


def fluidsynth_available() -> bool:
    return shutil.which("fluidsynth") is not None


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def audio_available() -> bool:
    return fluidsynth_available() and ffmpeg_available()


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
