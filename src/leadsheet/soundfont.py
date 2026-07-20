"""Resolves a cached copy of a General MIDI soundfont for fluidsynth to
render with. musicpy itself does not ship one -- its `daw.py` sf2_loader
is a different, optional, pedalboard-based render path that just loads
whatever path you give it, so leadsheet still has to source one.

Downloaded once into a per-user cache dir on first use (not bundled in
the wheel), per the user's explicit choice.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx

SOUNDFONT_FILENAME = "TimGM6mb.sf2"

# Mirrors of the same well-known ~6MB GM soundfont (CC-BY, Tim Brechbill).
# pretty-midi is a long-lived, widely used project -- lowest link-rot risk.
SOUNDFONT_URLS = [
    "https://raw.githubusercontent.com/craffel/pretty-midi/main/pretty_midi/TimGM6mb.sf2",
    "https://raw.githubusercontent.com/arbruijn/TimGM6mb/master/TimGM6mb.sf2",
]

MIN_EXPECTED_BYTES = 1_000_000  # sanity check the download wasn't an HTML error page


def cache_dir() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    d = base / "leadsheet" / "soundfonts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def soundfont_path() -> Path:
    return cache_dir() / SOUNDFONT_FILENAME


def is_cached() -> bool:
    p = soundfont_path()
    return p.exists() and p.stat().st_size >= MIN_EXPECTED_BYTES


def ensure_soundfont(force: bool = False) -> Path:
    """Downloads and caches the soundfont if it isn't already present.
    Returns the cached path. Raises httpx.HTTPError if every mirror fails."""
    path = soundfont_path()
    if path.exists() and not force and path.stat().st_size >= MIN_EXPECTED_BYTES:
        return path

    tmp_path = path.with_suffix(".part")
    last_error: Exception | None = None
    for url in SOUNDFONT_URLS:
        try:
            with httpx.stream("GET", url, follow_redirects=True, timeout=60) as response:
                response.raise_for_status()
                with open(tmp_path, "wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)
            if tmp_path.stat().st_size < MIN_EXPECTED_BYTES:
                raise ValueError(f"downloaded soundfont from {url} looks too small to be valid")
            tmp_path.rename(path)
            return path
        except Exception as exc:  # noqa: BLE001 -- try the next mirror
            last_error = exc
            tmp_path.unlink(missing_ok=True)
            continue

    raise RuntimeError(
        f"could not download a GM soundfont from any known mirror: {last_error}"
    ) from last_error
