"""Derives the server's advertised capabilities directly from musicpy's own
registries (source of truth, never hand-duplicated) and provides the shared
chord/instrument lookup helpers used by schema.py and theory_check.py.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass

from musicpy import database

EVENT_STYLES: dict[str, list[str]] = {
    "chords": ["block", "arpeggio_up", "arpeggio_updown", "custom_pattern"],
    "bass": ["root_only", "root_fifth", "walking", "block", "custom_pattern"],
    "melody": ["block", "arpeggio_up", "arpeggio_updown", "custom_pattern", "root_only"],
    "drums": [],
    "custom": [
        "block",
        "arpeggio_up",
        "arpeggio_updown",
        "custom_pattern",
        "root_only",
        "root_fifth",
        "walking",
    ],
}


def chord_type_aliases() -> dict[str, list[str]]:
    """canonical family name (first alias) -> all alias strings"""
    return {family[0]: list(family) for family in database.chordTypes.dic}


def all_chord_aliases() -> list[str]:
    return [alias for family in database.chordTypes.dic for alias in family]


def scale_type_families() -> list[str]:
    return [family[0] for family in database.scaleTypes.dic]


def instruments() -> dict[str, int]:
    return dict(database.INSTRUMENTS)


def drum_tokens() -> dict[str, int]:
    return dict(database.drum_mapping)


def drum_kits() -> dict[str, int]:
    """Drum-kit program name -> program number (database.drum_set_dict),
    used to resolve a drums-role track's `instrument` field. This is a
    different registry than `instruments()`/database.INSTRUMENTS -- drum
    kits are General MIDI program 9 (channel), not a melodic instrument.
    """
    return {name: number for number, name in database.drum_set_dict.items()}


def is_valid_note_name(name: str) -> bool:
    """Mirrors musicpy.musicpy.is_valid_note exactly."""
    return len(name) > 0 and name[0] in database.standard and all(
        c in database.accidentals for c in name[1:]
    )


def split_chord_symbol(symbol: str) -> tuple[str, str] | None:
    """Split a chord symbol into (root, type_suffix) using the same
    prefix-scan logic musicpy's own `trans()` parser uses (musicpy.py's
    `trans` walks the string while `is_valid_note` stays true for the
    accumulated prefix). Returns None if no valid root prefix is found.
    An empty suffix means the whole string was just a bare note name
    (e.g. "C"), which `trans()` treats as an implicit major chord.
    """
    if not symbol:
        return None
    root = ""
    for ch in symbol:
        candidate = root + ch
        if is_valid_note_name(candidate):
            root = candidate
        else:
            break
    if not root:
        return None
    return root, symbol[len(root):]


def is_valid_chord_symbol(symbol: str) -> bool:
    """Structural (non-musicpy) check that a chord symbol will resolve.
    Handles bare notes (implicit major), "root+suffix" symbols, and a
    reasonable subset of slash chords (`X/bass-note`, `X/inversion-index`).
    Not a full reimplementation of `trans()` -- the compiler still calls
    into musicpy itself, which is the final authority.
    """
    if "/" in symbol:
        left, _sep, rest = symbol.partition("/")
        if not is_valid_chord_symbol(left):
            return False
        if rest.lstrip("-").isdigit():
            return True
        if rest.endswith("!") and rest[:-1].isdigit():
            return True
        if is_valid_note_name(rest):
            return True
        return is_valid_chord_symbol(rest)
    split = split_chord_symbol(symbol)
    if split is None:
        return False
    _root, suffix = split
    if not suffix:
        return True
    return suffix in database.chordTypes


def chord_family_of(suffix: str) -> tuple[str, ...] | None:
    """The alias-tuple key in database.chordTypes.dic containing `suffix`,
    e.g. both 'm7' and 'min7' resolve to the same family tuple -- used to
    compare a requested chord suffix against a detected one without being
    thrown off by alias-spelling differences."""
    for family in database.chordTypes.dic:
        if suffix in family:
            return family
    return None


def suggest_chord(symbol: str) -> str | None:
    """Best-effort close-match suggestion for an invalid chord symbol,
    used to build error messages like "'Fmadj7' is not a valid chord type.
    Did you mean: Fmaj7?".
    """
    split = split_chord_symbol(symbol)
    aliases = all_chord_aliases()
    if split is None:
        matches = difflib.get_close_matches(symbol, aliases, n=1)
        return matches[0] if matches else None
    root, suffix = split
    if not suffix:
        return None
    matches = difflib.get_close_matches(suffix, aliases, n=1)
    return f"{root}{matches[0]}" if matches else None


@dataclass
class Capabilities:
    chord_types: dict[str, list[str]]
    scale_types: list[str]
    instruments: dict[str, int]
    drum_tokens: dict[str, int]
    drum_kits: dict[str, int]
    event_styles: dict[str, list[str]]
    limits: dict[str, float]


def get_capabilities() -> Capabilities:
    from leadsheet import limits

    return Capabilities(
        chord_types=chord_type_aliases(),
        scale_types=scale_type_families(),
        instruments=instruments(),
        drum_tokens=drum_tokens(),
        drum_kits=drum_kits(),
        event_styles=EVENT_STYLES,
        limits={
            "max_tracks": limits.MAX_TRACKS,
            "max_bars_per_track": limits.MAX_BARS_PER_TRACK,
            "max_duration_seconds": limits.MAX_DURATION_SECONDS,
            "max_payload_bytes": limits.MAX_PAYLOAD_BYTES,
        },
    )
